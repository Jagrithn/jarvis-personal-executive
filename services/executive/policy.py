from pathlib import Path

CAPABILITIES = {
    'apps.calculator': ('Open Calculator', ['open calculator'], 'com.apple.calculator'),
    'apps.finder': ('Open Finder', ['open finder'], 'com.apple.finder'),
    'files.list': ('List demo folder', ['list demo folder', 'list files'], None),
    'files.sample': ('Create sample file', ['create sample file', 'create a sample text file'], None),
}

def route(command):
    normalized = ' '.join(command.lower().strip().rstrip('.').split())
    for key, (_, phrases, _) in CAPABILITIES.items():
        if normalized in phrases:
            return key
    raise ValueError('Unsupported command. Try: ' + ', '.join(v[1][0] for v in CAPABILITIES.values()))

def authorize(root, capability, requested=None):
    if capability not in CAPABILITIES:
        raise ValueError('Capability is not allowed')
    if root.is_symlink() or root.resolve() != root.absolute():
        raise ValueError('Workspace must not contain symlink components')
    if requested is not None:
        path = Path(requested)
        if '..' in path.parts:
            raise ValueError('Path traversal rejected')
        path = path if path.is_absolute() else root / path
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError('Path outside workspace rejected')
        if path.is_symlink():
            raise ValueError('Symlink rejected')
        # This release deliberately has no arbitrary file operations.
        if path != root:
            raise ValueError('Only the designated demo folder is supported')
    return {'kind': 'scoped', 'source': 'owner-approved Phase 1 capabilities',
            'paths': [str(root)], 'network': False, 'capability': capability}
