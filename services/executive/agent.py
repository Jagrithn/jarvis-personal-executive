"""Native OpenJarvis conversation and bounded proposals; no effects in inference."""
import json
import re

ALLOWED = ('apps.calculator', 'apps.finder', 'files.list', 'files.sample')
PERSONALITY = (
    'Speak like a thoughtful, capable personal assistant in a natural conversation. '
    'Be warm and direct, use everyday language, and match the tone of the user. '
    'Give the answer first; avoid canned greetings, repetitive offers of help, '
    'robotic wording, and long lists unless useful. Keep answers to one to three '
    'short sentences unless more detail is requested. Remember the recent '
    'conversation and ask a brief clarifying question when it is needed. '
    'Be honest about uncertainty and never claim an action happened unless a tool confirms it. '
)
PLAN_LIMIT = ("I couldn't match that request to my available actions. I can open Finder or Calculator, "
              "Try a direct request such as ‘find Chemistry files in PES’ or ‘open Documents’. No action was taken.")

def plain_chat(question):
    """Only clearly conversational requests bypass the action-planning turn."""
    text = question.strip().lower()
    return bool(re.match(r'^(?:hi|hello|hey|thanks|thank you)[.!?\s]*$', text)
                or re.match(r'^(?:what|why|who|when|how|explain|describe|compare)\b', text))

def converse(question, history):
    from openjarvis.agents.orchestrator import OrchestratorAgent
    from openjarvis.agents._stubs import AgentContext
    from openjarvis.core.types import Message, Role, ToolResult
    from openjarvis.engine.ollama import OllamaEngine
    from openjarvis.tools._stubs import BaseTool, ToolSpec
    actions = []

    class Propose(BaseTool):
        tool_id = 'propose_actions'
        @property
        def spec(self):
            return ToolSpec(name=self.tool_id, description='Propose supported actions for owner approval. Does not execute anything.', parameters={'type':'object','properties':{'actions':{'type':'array','items':{'type':'string','enum':list(ALLOWED)},'minItems':1,'maxItems':4}},'required':['actions'],'additionalProperties':False}, category='planning')
        def execute(self, **params):
            proposed = params.get('actions')
            if set(params) != {'actions'} or not isinstance(proposed, list) or not 1 <= len(proposed) <= 4 or any(a not in ALLOWED for a in proposed) or actions:
                return ToolResult(tool_name=self.tool_id, content='Invalid or duplicate proposal', success=False)
            actions.extend(proposed)
            return ToolResult(tool_name=self.tool_id, content='Proposal recorded. Nothing executed. Owner approval is required.', success=True)

    engine = OllamaEngine(host='http://127.0.0.1:11435', timeout=60)
    context = AgentContext()
    context.conversation.add(Message(role=Role.SYSTEM, content='The desktop also handles direct Mac searches and opens, such as “find Chemistry files in PES” and “open Documents”. These are separate from your proposal tool.'))
    for item in (history or [])[-6:]:
        context.conversation.add(Message(role=Role.USER if item['role']=='user' else Role.ASSISTANT, content=item['content'][:1500]))
    if plain_chat(question):
        try:
            instruction = (PERSONALITY + 'You are JARVIS, a local assistant using qwen2.5:7b through OpenJarvis. '
                           'Answer this conversation directly in one or two short sentences. You have no action tools in this turn. '
                           'Do not claim to have opened apps, read files, browsed the web, or performed an action. '
                           'You can describe your actual abilities: local chat, bounded Mac opening, Chrome search and public reading, '
                           'selected Obsidian note search, and local voice. For an action request, say to ask directly. '
                           'Do not invent current facts or connected accounts.')
            messages = [Message(role=Role.SYSTEM, content=instruction), *context.conversation.messages,
                        Message(role=Role.USER, content=question)]
            response = engine.generate(messages, model='qwen2.5:7b', temperature=0.2,
                                       max_tokens=120, num_ctx=4096)
            from knowledge import visible_answer
            answer = visible_answer(response.get('content'))
            return {'answer': answer, 'actions': [], 'conversation_version': 2,
                    'model': response['model'], 'engine': 'OpenJarvis OllamaEngine',
                    'sources': [], 'usage': response.get('usage', {}),
                    'notice': 'Model answers are not independently fact-checked.'}
        finally:
            engine._client.close()
    agent = OrchestratorAgent(engine, 'qwen2.5:7b', tools=[Propose()], temperature=0, max_tokens=350, max_turns=3, parallel_tools=False, system_prompt=PERSONALITY + 'You are JARVIS, running qwen2.5:7b locally through OpenJarvis. Answer ordinary questions directly. For requested actions use propose_actions. Supported actions: open Calculator (apps.calculator), open Finder (apps.finder), list the designated demo workspace (files.list), create a uniquely named sample text file there (files.sample). Never substitute these for unsupported actions such as searching personal files, typing into apps or writing arbitrary content. No action is executed during conversation. Do not claim execution. You have no internet access. Explain unsupported capabilities honestly.')
    try:
        result = agent.run(question, context)
        answer = result.content.strip()
        if not answer and not actions:
            # Some Ollama tool-call responses contain neither text nor parsed calls.
            # Retry once without tool execution, using the same constrained proposal format.
            instruction = (PERSONALITY + 'You are JARVIS running qwen2.5:7b. Return JSON with keys answer (one or two short sentences) '
                           'and actions (ordered array). For ordinary questions answer directly and leave actions empty. '
                           'Propose only actions explicitly requested: apps.finder opens Finder, apps.calculator opens Calculator, '
                           'files.list lists the demo workspace, files.sample creates a new sample text file. '
                           'For unsupported or ambiguous requests explain the limit and return no actions. '
                           'All proposed actions require approval and none have executed.')
            messages = [Message(role=Role.SYSTEM, content=instruction), *context.conversation.messages,
                        Message(role=Role.USER, content=question)]
            raw = engine.generate(messages, model='qwen2.5:7b', temperature=0, max_tokens=350,
                                  num_ctx=8192, response_format={'type':'json_object'})
            try:
                proposal = json.loads(raw['content'])
            except (TypeError, ValueError):
                proposal = None
            steps = proposal.get('actions') if isinstance(proposal, dict) else None
            if isinstance(steps, list) and len(steps) <= 4 and all(a in ALLOWED for a in steps):
                actions.extend(steps)
                answer = proposal.get('answer')
            else:
                answer = PLAN_LIMIT
        if actions:
            answer = 'Approval required for ' + ', '.join(actions) + '.'
        elif isinstance(answer, str) and re.search(r'\b(proposed actions|if you approve|need your approval|awaiting your approval)\b', answer, re.I):
            # Only a validated proposal can produce an approval control in the app.
            answer = PLAN_LIMIT
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError('Local model returned no visible answer')
        return {'answer': answer.strip(), 'actions': actions, 'conversation_version':2, 'model':'qwen2.5:7b', 'engine':'OpenJarvis OrchestratorAgent', 'sources':[], 'notice':'Model answers are not independently fact-checked.'}
    finally:
        engine._client.close()
