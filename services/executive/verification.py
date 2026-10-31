import hashlib
import os
from adapters import run_process

def verify(capability, result, root, cancel, helper):
    if capability.startswith('apps.'):
        output = run_process([str(helper), result['bundle_id']], cancel)
        if output != result['bundle_id']:
            raise RuntimeError('Application running-state verification failed')
        return [{'check': 'NSWorkspace.runningApplications', 'observed': output}]
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if capability == 'files.list':
            observed = sorted(os.listdir(fd))
            if observed != result['entries']:
                raise RuntimeError('Directory changed during verification')
            return [{'check': 'independent directory listing', 'observed': observed}]
        file_fd = os.open(result['filename'], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
        with os.fdopen(file_fd, 'rb') as stream:
            content = stream.read()
        if content.decode() != result['content']:
            raise RuntimeError('File read-back mismatch')
        return [{'check': 'file read-back', 'path': str(root / result['filename']),
                 'sha256': hashlib.sha256(content).hexdigest(), 'bytes': len(content)}]
    finally:
        os.close(fd)
