"""Approved fixed work order via OpenCode, confined by a mandatory macOS sandbox.

Caller must obtain explicit task approval before execute_coding. Generated code is
never executed. The worker has no tools; it returns a static HTML artifact.
"""
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time
import uuid
from adapters import Cancelled

OPENCODE = Path('/opt/homebrew/bin/opencode')
SANDBOX = Path('/usr/bin/sandbox-exec')
MAX_LOG = 2 * 1024 * 1024
TIMEOUT = 180
MODEL = 'local/qwen2.5:7b'
PROMPT = '''Create a polished static Assignment Tracker demo as one complete HTML document.
Return only HTML, optionally fenced as html. No tool calls. Include <!doctype html>,
html, head, title Assignment Tracker, style, body, h1 Assignment Tracker, and a table
with Assignment, Due, Status columns and three example assignments. Use dark navy
and cyan styling, responsive CSS and readable labels. This is a static preview:
include visible text that editing and persistence are not implemented. NO scripts,
forms, links, images, external resources, CSS imports, url(), or event handlers.
Keep under 5000 characters. /no_think'''


def safe_directory(path):
    path = Path(path).absolute()
    if path.resolve() != path or path.is_symlink() or not path.is_dir():
        raise ValueError('Expected existing directory without symlink components')
    return path


def _read(path, limit=MAX_LOG):
    safe_directory(path.parent)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit or info.st_nlink != 1:
            raise ValueError('Artifact must be a bounded regular file with one link')
        value = stream.read(limit + 1)
        if len(value) > limit: raise ValueError('Artifact limit exceeded')
        return value


def _write(path, content):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(content)


def sandbox_policy(job, executable):
    # No home-directory, credential, arbitrary network or global-write grants.
    def quoted(path): return json.dumps(str(path))
    runtime = Path(sys.base_prefix).resolve()
    reads = ['/System', '/usr/lib', '/usr/share/icu', '/usr/bin', '/bin', '/private/var/db/dyld',
             str(runtime), str(executable.parent), str(job)]
    rules = ['(version 1)', '(deny default)', '(allow process-exec process-fork)',
             '(allow signal (target same-sandbox))', '(allow sysctl-read)',
             '(allow network-outbound (remote ip "localhost:11435"))']
    ancestors = {p for base in (runtime, executable.parent, job) for p in base.parents}
    rules += ['(allow file-read-metadata (literal ' + quoted(p) + '))' for p in sorted(ancestors)]
    rules += ['(allow file-read* (subpath ' + quoted(p) + '))' for p in reads]
    rules += ['(allow file-read* (literal "/") (literal "/dev/null") (literal "/dev/urandom") (literal "/dev/random") (literal "/private/etc/localtime"))',
              '(allow file-write* (subpath ' + quoted(job / 'work') + '))',
              '(allow file-write* (literal "/dev/null"))']
    return '\n'.join(rules)


def worker_environment(job):
    work = job / 'work'
    config = {'model': MODEL, 'small_model': MODEL,
              'enabled_providers': ['local'], 'autoupdate': False, 'share': 'disabled',
              'snapshot': False, 'permission': {'*': 'deny'}, 'mcp': {}, 'plugin': [],
              'provider': {'local': {'npm': '@ai-sdk/openai-compatible', 'name': 'Local only',
                  'options': {'baseURL': 'http://127.0.0.1:11435/v1'},
                  'models': {'qwen2.5:7b': {'name': 'Qwen 2.5 7B local', 'limit': {'context': 8192, 'output': 1200}}}}}}
    return {'PATH': '/usr/bin:/bin', 'HOME': str(work / 'home'),
            'XDG_CONFIG_HOME': str(work / 'config'), 'XDG_DATA_HOME': str(work / 'data'),
            'XDG_CACHE_HOME': str(work / 'cache'), 'XDG_STATE_HOME': str(work / 'state'),
            'TMPDIR': str(work / 'tmp'), 'LANG': 'en_US.UTF-8', 'NO_COLOR': '1',
            'OPENCODE_CONFIG_CONTENT': json.dumps(config), 'OPENCODE_DISABLE_AUTOUPDATE': 'true',
            'OPENCODE_DISABLE_MODELS_FETCH': 'true', 'OPENCODE_DISABLE_DEFAULT_PLUGINS': 'true',
            'OPENCODE_DISABLE_PROJECT_CONFIG': 'true', 'OPENCODE_DISABLE_CLAUDE_CODE': 'true'}


def _kill_group(process):
    try: os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError: pass
    try: process.wait(timeout=0.5)
    except subprocess.TimeoutExpired: pass
    # Also terminate descendants surviving after the leader exits.
    try: os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError: pass
    process.wait(timeout=2)


def run_bounded(args, job, env, cancel, log, timeout=TIMEOUT):
    if cancel.is_set(): raise Cancelled('Coding cancelled before process start')
    # Log is outside worker-writable work/; only inherited stdout can append it.
    with open(log, 'xb') as output:
        process = subprocess.Popen(args, cwd=job / 'work', env=env, stdin=subprocess.DEVNULL,
                                   stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        deadline = time.monotonic() + timeout
        try:
            while process.poll() is None:
                if cancel.is_set(): raise Cancelled('Coding cancelled; partial local job retained')
                if time.monotonic() > deadline: raise TimeoutError('Coding worker timed out; partial job retained')
                if os.fstat(output.fileno()).st_size > MAX_LOG: raise RuntimeError('Coding worker log limit exceeded')
                time.sleep(0.05)
            if cancel.is_set(): raise Cancelled('Coding cancelled; partial local job retained')
            if process.returncode:
                detail = _read(log).decode('utf-8', errors='replace')[-1200:]
                raise RuntimeError('Sandboxed worker failed (exit %s): %s' % (process.returncode, detail))
        finally:
            _kill_group(process)
    return _read(log)


def _preflight(job, env, cancel, policy):
    # A positive write, forbidden protected read/write, personal-home read,
    # external and wrong-loopback network probes all execute in the actual policy.
    probe = '''import errno, pathlib, socket, sys
job=pathlib.Path(sys.argv[1]); home=pathlib.Path(sys.argv[2])
(job/'work'/'probe-ok').write_text('ok')
for path,mode in [(job/'control'/'sentinel','r'),(job/'outside-write','w'),(home/'.zshrc','r')]:
    try:
        f=open(path,mode); f.close()
    except PermissionError: pass
    except FileNotFoundError:
        if path.name!='.zshrc': raise
    else: raise RuntimeError('Sandbox file boundary failed')
for target in [('1.1.1.1',443),('127.0.0.1',11434)]:
    s=socket.socket(); s.settimeout(1)
    try: s.connect(target)
    except OSError as e:
        if e.errno not in (errno.EPERM,errno.EACCES): raise RuntimeError('Network denial unproven: '+str(e))
    else: raise RuntimeError('Sandbox network boundary failed')
    finally: s.close()
s=socket.create_connection(('127.0.0.1',11435),timeout=2); s.close()
print('SANDBOX_PROBE_OK')
'''
    # Sentinel is explicitly denied even though the rest of job is readable.
    try:
        out = run_bounded([str(SANDBOX), '-f', str(policy), sys.executable, '-I', '-c', probe,
                           str(job), str(Path.home())], job, env, cancel, job / 'control' / 'probe.log', 10)
        if b'SANDBOX_PROBE_OK' not in out: raise RuntimeError('Sandbox proof missing')
    except (RuntimeError, TimeoutError) as exc:
        raise RuntimeError('Coding unavailable: mandatory sandbox/local-inference preflight failed: ' + str(exc)) from exc


class _StaticHTML(HTMLParser):
    allowed = set('html head meta title style body main header footer section article div span h1 h2 h3 p strong em small table thead tbody tr th td caption ul ol li br hr'.split())
    def __init__(self):
        super().__init__(convert_charrefs=True); self.tags = set(); self.text = []; self.style = False
    def handle_starttag(self, tag, attrs):
        if tag not in self.allowed: raise ValueError('Only passive static HTML elements allowed: ' + tag)
        self.tags.add(tag)
        for name, value in attrs:
            if name.startswith('on') or name in {'src', 'href', 'action', 'srcdoc', 'http-equiv'}:
                raise ValueError('Active/external HTML attribute rejected')
        self.style = tag == 'style' or self.style
    def handle_endtag(self, tag):
        if tag == 'style': self.style = False
    def handle_data(self, data): self.text.append(data)


def inspect_html(raw):
    if len(raw) > 100_000: raise ValueError('HTML too large')
    text = raw.decode('utf-8')
    # Conservative: no CSS escapes, urls/imports or executable markup.
    if re.search(r'url\s*\(|@import|expression\s*\(|javascript:|\\', text, re.I):
        raise ValueError('External/escaped CSS or executable content rejected')
    parsed = _StaticHTML(); parsed.feed(text); parsed.close()
    if not {'html', 'head', 'title', 'body', 'h1', 'table', 'th', 'td'} <= parsed.tags:
        raise ValueError('Required assignment tracker HTML structure missing')
    content = ' '.join(parsed.text).lower()
    if not all(term in content for term in ['assignment', 'due', 'status']):
        raise ValueError('Required tracker labels missing')
    return {'check': 'Independent passive HTML structure and labels', 'structural_only': True,
            'executed': False, 'functional_correctness_verified': False}


def _extract(log):
    chunks = []
    for line in log.decode('utf-8').splitlines():
        try: event = json.loads(line)
        except json.JSONDecodeError: continue
        if event.get('type') == 'error': raise RuntimeError('OpenCode returned an error: ' + str(event)[:700])
        if event.get('type') == 'text': chunks.append(event.get('part', {}).get('text', ''))
    text = '\n'.join(chunks).strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:html)?\s*', '', text, count=1, flags=re.I)
        text = re.sub(r'\s*```$', '', text, count=1)
    raw = text.encode()
    inspect_html(raw)
    return raw


def execute_coding(capability, command, root, cancel):
    """Execute only after caller approval. No user-supplied prompt or shell accepted."""
    if cancel.is_set(): raise Cancelled('Coding cancelled before execution')
    if capability != 'coding.build' or ' '.join(command.lower().strip().rstrip('.').split()) != 'build demo app':
        raise ValueError('Only approved fixed build demo app work order is supported')
    root = safe_directory(root)
    if not OPENCODE.is_file(): raise RuntimeError('Coding unavailable: OpenCode runtime missing')
    if not SANDBOX.is_file(): raise RuntimeError('Coding unavailable: macOS sandbox-exec missing')
    executable = OPENCODE.resolve()
    job = root / ('jarvis-code-' + uuid.uuid4().hex)
    job.mkdir(mode=0o700)
    (job / 'control').mkdir(mode=0o700); (job / 'work').mkdir(mode=0o700)
    for name in ['home', 'config', 'data', 'cache', 'state', 'tmp']:
        (job / 'work' / name).mkdir(mode=0o700)
    _write(job / 'control' / 'sentinel', b'boundary test')
    policy = job / 'control' / 'sandbox.sb'
    profile = sandbox_policy(job, executable) + '\n(deny file-read* (literal ' + json.dumps(str(job / 'control' / 'sentinel')) + '))\n'
    _write(policy, profile.encode())
    env = worker_environment(job)
    try:
        _preflight(job, env, cancel, policy)
        log = run_bounded([str(SANDBOX), '-f', str(policy), str(executable), 'run', '--pure',
                           '--format', 'json', '--model', MODEL, PROMPT], job, env, cancel,
                          job / 'control' / 'worker.log')
        raw = _extract(log)
        if cancel.is_set(): raise Cancelled('Coding cancelled before publishing artifact')
        _write(job / 'control' / 'index.html', raw)
        result = {'job': job.name, 'filename': job.name + '/control/index.html',
                  'sha256': hashlib.sha256(raw).hexdigest(), 'worker_log_sha256': hashlib.sha256(log).hexdigest(),
                  'runtime': 'OpenCode', 'model': MODEL, 'sandbox_preflight': True,
                  'notice': 'Static generated demo; structural checks only. No interaction or production reliability claim.'}
        _write(job / 'control' / 'result.json', json.dumps(result, indent=2).encode())
        return result
    except Exception as exc:
        _write(job / 'control' / 'failure.json', json.dumps({'error': str(exc), 'job': job.name}).encode())
        raise


def verify_coding(capability, result, root):
    if capability != 'coding.build': raise ValueError('Unknown coding capability')
    name = result.get('job')
    if not isinstance(name, str) or not re.fullmatch(r'jarvis-code-[a-f0-9]{32}', name):
        raise ValueError('Coding job outside scope')
    root = safe_directory(root); job = safe_directory(root / name)
    saved = json.loads(_read(job / 'control' / 'result.json'))
    if result != saved or result.get('sandbox_preflight') is not True:
        raise ValueError('Controller metadata mismatch')
    if result.get('filename') != name + '/control/index.html': raise ValueError('Artifact outside scope')
    raw = _read(job / 'control' / 'index.html', 100_000)
    log = _read(job / 'control' / 'worker.log')
    if hashlib.sha256(raw).hexdigest() != result.get('sha256') or hashlib.sha256(log).hexdigest() != result.get('worker_log_sha256'):
        raise ValueError('Independent artifact/log digest mismatch')
    if _extract(log) != raw: raise ValueError('Artifact differs from actual worker text')
    if b'SANDBOX_PROBE_OK' not in _read(job / 'control' / 'probe.log'):
        raise ValueError('Missing sandbox preflight evidence')
    return [inspect_html(raw), {'check': 'Independent artifact and worker-log read-back',
                               'sha256': result['sha256'], 'sandbox_preflight': True}]
