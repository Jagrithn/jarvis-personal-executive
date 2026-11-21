from pathlib import Path
import re

CAPABILITIES = {
    'browser.research': ('Research a topic on Google', ['research black holes'], None),
    'workflows.research': ('Research and save a sourced report', ['research black holes and save a report'], None),
    'browser.results': ('Read Chrome search results', [], None),
    'browser.search': ('Open a Chrome search', ['search Chrome for local voice models'], None),
    'mac.items': ('Find and open Mac items', ['open Documents'], None),
    'agent.plan': ('Approved OpenJarvis action plan', [], None),
    'apps.calculator': ('Open Calculator', ['open calculator'], 'com.apple.calculator'),
    'apps.finder': ('Open Finder', ['open finder'], 'com.apple.finder'),
    'files.list': ('List demo folder', ['list demo folder', 'list files'], None),
    'files.sample': ('Create sample file', ['create sample file', 'create a sample text file'], None),
    'chat.local': ('Local conversation', ['chat: Explain what you can help me with'], None),
    'memory.index': ('Index selected notes folder', ['index workspace'], None),
    'memory.search': ('Search second brain', ['search memory: JARVIS'], None),
    'memory.review': ('Review indexed sources', ['review memory'], None),
    'memory.export': ('Export memory to workspace', ['export memory'], None),
    'memory.forget': ('Clear indexed memory (keeps originals and history)', ['forget memory'], None),
    'browser.read': ('Read public web page', ['read page: https://example.com'], None),
    'workflows.report': ('Create sourced workspace report', ['create research report'], None),
    'workflows.draft': ('Draft workspace summary (never sends)', ['draft workspace summary'], None),
    'workflows.organize': ('Plan file organization', ['plan file organization'], None),
    'schedules.create': ('Schedule a registered worker', ['schedule worker: research-reporter every 3600'], None),
    'schedules.list': ('List schedules', ['list schedules'], None),
    'schedules.resume': ('Resume paused schedules', ['resume schedules'], None),
    'schedules.cancel': ('Cancel a schedule', ['cancel schedule: UUID'], None),
    'coding.build': ('Build isolated demo app', ['build demo app'], None),
    'workers.list': ('List reusable workers', ['list workers'], None),
    'workers.register': ('Register approved worker template', ['register worker: research-reporter'], None),
    'workers.run': ('Run registered worker', ['run worker: research-reporter'], None),
    'memory.answer': ('Ask second brain', ['ask memory: What is JARVIS?'], None),
}

def route(command, general_conversation=False):
    from workflows import research_report_topic
    if research_report_topic(command):
        return 'workflows.research'
    from knowledge import natural_memory_request
    memory_request = natural_memory_request(command)
    if memory_request:
        return memory_request[0]
    from browser import research_query
    if research_query(command):
        return 'browser.research'
    if re.search(r'\b(?:read|summari[sz]e|explain|tell me)\b.*\b(?:results?|search results|google results|what (?:it|google) says)\b', command, re.I) and not re.search(r"\b(?:don't|do not|never)\b", command, re.I):
        return 'browser.results'
    from browser import chrome_query
    if chrome_query(command) is not None:
        return 'browser.search'
    from knowledge import PREFIXES
    prefixes = dict(PREFIXES, **{'browser.read': 'read page:', 'workers.register': 'register worker:', 'workers.run': 'run worker:', 'schedules.create': 'schedule worker:', 'schedules.cancel': 'cancel schedule:'})
    for capability, prefix in prefixes.items():
        if command.strip().lower().startswith(prefix):
            if not command.split(':', 1)[1].strip():
                raise ValueError('Enter a question after the colon')
            return capability
    normalized = ' '.join(command.lower().strip().rstrip('.').split())
    for key, (_, phrases, _) in CAPABILITIES.items():
        if normalized in phrases:
            return key
    if general_conversation:
        from mac_items import handles
        if handles(command.strip()):
            return 'mac.items'
    # Conversation has no tools; even action-like text here cannot execute an effect.
    if re.match(r"^(hi|hello|hey|thanks|thank you)\b|^(what|why|who|when|where|how|explain|describe|compare|tell me|i am|i'm|i think)\b|^(can|could|would) you (explain|describe|tell|help me understand)\b|^(make it shorter|say that again|continue|give an example)[.!?]*$", normalized):
        return 'chat.local'
    if general_conversation:
        return 'chat.local'
    raise ValueError('Unsupported command')

def authorize(root, capability, requested=None):
    if capability == 'mac.items' and requested is None:
        return {'kind':'standing', 'source':'Owner authorized local search and opening', 'paths':['Mac locations accessible to this account'], 'network':False, 'capability':capability}
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
    return {'kind': 'scoped', 'source': 'explicit command within local capability scope',
            'paths': [str(root)], 'network': capability.startswith('browser.') or capability == 'workflows.research', 'capability': capability}

APPROVALS = {
    'coding.build': 'Run OpenCode in an OS sandbox with local inference to create a static demo; no external network',
    'schedules.create': 'Run the specified registered worker repeatedly while JARVIS is open; Stop All pauses schedules',
    'schedules.resume': 'Resume all paused worker schedules; missed occurrences are not replayed',
    'memory.index': 'Read text, Markdown and selectable-text PDFs from the selected notes folder and update the local index',
    'memory.forget': 'Clear the index only; originals, exports and task history remain',
    'browser.read': 'Fetch the specified public web page over the internet; no logins or actions',
    'workers.register': 'Activate the named fixed worker template within workspace scope',
}
