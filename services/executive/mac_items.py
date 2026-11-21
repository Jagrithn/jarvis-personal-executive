"""Local Finder searches and ordinary opens under the owner's standing grant."""
import os
from pathlib import Path
import re

from adapters import Cancelled, run_process

DOCUMENTS = set('pdf txt md rtf csv doc docx xls xlsx ppt pptx pages numbers key jpg jpeg png gif heic webp mp3 wav m4a mp4 mov epub'.split())
STOP = set('there is a an the in inside that this my mac then and of related to please can could would you me for find search open launch show list all it those called named files file folders folder floder directory documents document app application installed ok on under with from matching chemistryfile'.split())
CHANGE = re.compile(r"\b(delete|remove|move|rename|edit|overwrite|upload|send|run|execute|install|create|copy|download|close|write|don.t|not|never)\b", re.I)
VERB = re.compile(r'\b(open|launch|find|search|list|show)\b', re.I)
APP_BASES = (Path('/Applications'), Path('/System/Applications'), Path('/System/Library/CoreServices'), Path.home()/'Applications')
APP_ALIASES = {'vs code': 'visual studio code', 'vscode': 'visual studio code'}

def name_matches(word, value):
    # Short names such as PES must be whole words, not a suffix of "types".
    return bool(re.search(r'(?<!\w)' + re.escape(word) + r'(?!\w)', value.casefold()))

def installed_apps(name):
    name = APP_ALIASES.get(name, name)
    matches = set()
    for base in APP_BASES:
        if not base.is_dir(): continue
        for current, dirs, files in os.walk(base):
            apps = [d for d in dirs if d.lower().endswith('.app')]
            dirs[:] = [d for d in dirs if d not in apps and not d.startswith('.')]
            for app in apps:
                if Path(app).stem.casefold() == name:
                    matches.add((Path(current)/app).resolve())
    return sorted(matches)

def handles(command):
    command = without_address(command)
    if re.search(r'\b(?:and|then)\s+(?:create|make|delete|send|edit)\b', command, re.I):
        return False
    if CHANGE.search(command) or not VERB.search(command):
        return False
    return bool(re.match(r'^(?:(?:please|can you|could you|would you|ok then)\s+)*(?:open|launch|find|search|show|list)\b', command, re.I)
                or re.search(r'\b(folder|floder|file|directory)\b', command, re.I) and re.search(r'\bopen\b', command, re.I))

def terms(command):
    return list(dict.fromkeys(t for t in re.findall(r'[\w-]+', command.casefold()) if t not in STOP))

def without_address(command):
    return re.sub(r'^\s*(?:(?:okay|ok|hey)[,\s]+)?jarvis\b[,\s:]+', '', command, count=1, flags=re.I).strip()

def eligible(path):
    if path.suffix.lower() == '.app':
        safari = Path('/Applications/Safari.app')
        if path == safari.resolve() and safari.is_symlink() and path.is_dir():
            return True
        return path.is_dir() and any(path.is_relative_to(base) for base in
            (Path('/Applications'), Path('/System/Applications'), Path('/System/Library/CoreServices'), Path.home()/'Applications'))
    return path.is_dir() or (path.is_file() and path.suffix.lower()[1:] in DOCUMENTS and not os.access(path, os.X_OK))

def candidates(command, event):
    common = re.fullmatch(r'(?:please\s+)?(?:open|show|list)\s+(?:my\s+)?(documents|desktop|downloads|applications)(?:\s+folder)?[.!?]*', command.strip(), re.I)
    if common:
        p = Path('/Applications') if common[1].lower() == 'applications' else Path.home()/common[1].capitalize()
        return [p] if p.is_dir() else []
    direct = re.search(r'(?:^|\s)((?:/|~/).+)$', command)
    if direct:
        target = Path(direct[1].strip().strip('"')).expanduser().resolve()
        if not target.exists():
            raise ValueError('No accessible item at that path.')
        return [target] if eligible(target) else []
    words = terms(command)
    if not words:
        raise ValueError('Give a folder, document or application name.')
    want_file = bool(re.search(r'\b(files?|documents?)\b', command, re.I))
    # Direct names work even when Spotlight indexing is disabled.
    name = ' '.join(words)
    want_folder = bool(re.search(r'\b(folder|floder|directory)\b', command, re.I))
    if not want_file and not want_folder:
        apps = installed_apps(name)
        if apps:
            # Prefer the standard system-wide installation when duplicate copies exist.
            return [next((p for p in apps if p.parent == Path('/Applications')), apps[0])]
    found = set()
    for base in (Path('/Applications'), Path('/System/Applications'), Path('/System/Library/CoreServices'), Path.home()/'Applications'):
        p = base / (name + '.app')
        if p.is_dir():
            found.add(next((entry for entry in base.iterdir() if entry.name.casefold()==p.name.casefold()), p).resolve())
    # Search for any distinctive filename; check all terms against its full path.
    query = ' || '.join(f'kMDItemFSName == "*{word}*"cd' for word in words)
    output = run_process(['/usr/bin/mdfind','-0',query], event, timeout=20)
    for value in output.split('\0'):
        if not value: continue
        p = Path(value).resolve()
        if all(name_matches(w, str(p)) for w in words) and eligible(p):
            found.add(p)
    if want_file:
        # Files may be named Chapter 1.pdf inside PES/Chemistry.
        children = set()
        for folder in found:
            if not folder.is_dir() or folder.suffix == '.app': continue
            for base, dirs, files in os.walk(folder):
                if event.is_set(): raise Cancelled('Search cancelled')
                dirs[:] = [d for d in dirs if not d.startswith('.') and not d.endswith('.app')]
                for f in files:
                    p = Path(base)/f
                    if not p.is_symlink() and eligible(p): children.add(p)
                if len(children)>100: break
        found = {p for p in found if p.is_file()} | children
    elif re.search(r'\b(folder|floder|directory)\b', command, re.I):
        found = {p for p in found if p.is_dir() and p.suffix != '.app'}
    exact = [p for p in found if p.stem.strip().casefold()==name]
    return sorted(exact or found)

def perform(command, event, helper, remembered=None):
    command = without_address(command)
    reused = False
    paths = None
    if remembered and len(remembered) == 1 and re.search(r'\b(open|launch)\b', command, re.I) and not re.search(r'\b(and|then|all)\b', command, re.I):
        previous = remembered[0]
        try:
            path = Path(previous['path'])
            current = path.stat()
            if (path.is_absolute() and path.resolve() == path and eligible(path)
                    and current.st_dev == previous['device'] and current.st_ino == previous['inode']):
                paths = [path]
                reused = True
        except (KeyError, OSError, TypeError, ValueError):
            pass
    pair = re.fullmatch(r'(?:please )?(?:open|launch) ([\w .-]+?) and (?:open )?([\w .-]+?)(?: for me)?[.!?]*', command.strip(), re.I)
    if pair:
        groups = [candidates('open ' + name, event) for name in pair.groups()]
        if all(len(group)==1 and group[0].suffix.lower()=='.app' for group in groups):
            paths = [group[0] for group in groups]
        else:
            return {'message':'Specify one installed application at a time when the names are ambiguous.', 'matches':[str(p) for group in groups for p in group[:10]], 'opened':[]}
    elif paths is None:
        paths = candidates(command, event)
    wants_open = bool(re.search(r'\b(open|launch)\b', command, re.I))
    plural = bool(pair or re.search(r'\ball\b', command, re.I))
    opened = []
    if not paths:
        message = 'No matching accessible item found. Try its full path if Spotlight has not indexed it.'
    elif not wants_open:
        message = 'Found these items.'
    elif len(paths)>1 and (not plural or len(paths)>10):
        message = 'Multiple matches. Open the full path of the item you want.'
    else:
        for p in paths:
            if event.is_set(): raise Cancelled('Cancelled; items already opened may remain open.')
            if not eligible(p.resolve()): raise ValueError('Item changed during search.')
            identity = p.stat()
            receipt = run_process([str(helper),'--open-item',str(p)], event, timeout=15)
            opened.append({'path':str(p),'application':receipt,'device':identity.st_dev,'inode':identity.st_ino})
        message = 'Opened ' + ', '.join(p.name for p in paths) + '.'
    return {'message':message,'matches':[str(p) for p in paths[:100]],'opened':opened,
            'outcome': 'opened' if opened else ('needs_clarification' if wants_open and paths else 'not_found' if not paths else 'found'),
            'reused_previous_target': reused}
