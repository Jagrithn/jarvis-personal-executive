import os
import subprocess
import time
import uuid
from policy import CAPABILITIES

class Cancelled(Exception):
    pass

def run_process(args, cancel, timeout=10):
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    deadline = time.monotonic() + timeout
    while True:
        try:
            out, err = process.communicate(timeout=.05)
            if process.returncode:
                raise RuntimeError(err.strip() or 'Adapter process failed')
            return out.strip()
        except subprocess.TimeoutExpired:
            if cancel.is_set() or time.monotonic() > deadline:
                process.terminate()
                try:
                    process.communicate(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()
                if cancel.is_set():
                    raise Cancelled('Cancellation requested; any completed OS effect may remain')
                raise TimeoutError('Adapter timed out')

def execute(capability, root, cancel, verifier):
    if cancel.is_set():
        raise Cancelled('Cancelled before execution')
    if capability.startswith('apps.'):
        bundle = CAPABILITIES[capability][2]
        run_process(['/usr/bin/open', '-b', bundle], cancel)
        return {'bundle_id': bundle, 'effect': 'Launch requested; application is not closed on cancellation'}
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(root, flags)
    try:
        if capability == 'files.list':
            return {'entries': sorted(os.listdir(fd))}
        name = 'sample-' + str(uuid.uuid4()) + '.txt'
        content = 'Created by JARVIS — a verified local action.\n'
        file_fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
        with os.fdopen(file_fd, 'w') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        return {'filename': name, 'content': content, 'effect': 'Created new file; retained on cancellation'}
    finally:
        os.close(fd)
