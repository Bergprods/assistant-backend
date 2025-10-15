from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
# legacy agents removed; we now use services under my_ai_assistant.services
from my_ai_assistant.services.agent_service import AgentService
from my_ai_assistant.services.orchestrator_service import OrchestratorService
import asyncio
import os
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="My AI Assistant API")

# allow CORS for dev and compose proxying
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    services: list[str] | None = None
    wait_for: float | None = 3.0


# instantiate orchestrator
# We'll instantiate an OrchestratorService later and register services on it.
orchestrator_service = None

# Try to wire an assistant if OpenAI credentials are available
try:
    from my_ai_assistant.providers.openai_adapter import OpenAIAdapter
    openai_key = os.getenv('OPENAI_API_KEY')
    if openai_key:
        try:
            # wrap the provider adapter in the BaseAssistant so it exposes .generate
            from my_ai_assistant.assistant import BaseAssistant
            adapter = OpenAIAdapter(api_key=openai_key)
            base_assistant = BaseAssistant(adapter)
            # create AgentService and OrchestratorService and attach to orchestrator
            agent_service = AgentService(base_assistant)
            orchestrator_service = OrchestratorService(agent_service)
            # register stub services on the orchestrator_service registry
            from my_ai_assistant.services import github_service as gh_svc
            from my_ai_assistant.services import homeassistant_service as ha_svc
            from my_ai_assistant.services import smalltalk_service as st_svc
            orchestrator_service.register('github', gh_svc.GitHubService(), description='Create issues/projects in GitHub')
            orchestrator_service.register('homeassistant', ha_svc.HomeAssistantService(), description='Control Home Assistant devices')
            orchestrator_service.register('smalltalk', st_svc.SmallTalkService(), description='Small talk and confirmations')
            logger.info('OrchestratorService wired via AgentService and BaseAssistant')
        except Exception:
            # log full exception to help debugging adapter init issues
            logger.exception('Failed to initialize OpenAIAdapter and services')
    else:
        logger.info('OPENAI_API_KEY not provided; orchestrator will use heuristic fallback')
except Exception:
    logger.exception('OpenAIAdapter module not available; skipping assistant wiring')


@app.post('/api/chat')
async def chat(req: ChatRequest):
    if not req.message:
        raise HTTPException(400, 'message required')
    # First, try to interpret the message via the orchestrator's assistant
    interpreted = None
    try:
        if orchestrator_service is not None:
            interpreted = await orchestrator_service.interpret(req.message, orchestrator_service.list_services())
    except Exception as e:
        logger.exception('Assistant interpretation failed: %s', e)
        interpreted = None

    # Fallback heuristic when no assistant is configured or interpretation failed
    if not interpreted:
        text = req.message.lower()
        intents = []
        intent_desc = {}
        if any(k in text for k in ('issue', 'bug', 'create issue', 'ticket')):
            intents.append('github')
            intent_desc['github'] = 'Create a GitHub issue summarizing the request.'
        if any(k in text for k in ('turn on', 'turn off', 'lights', 'switch', 'home assistant', 'hvac')):
            intents.append('homeassistant')
            intent_desc['homeassistant'] = 'Send a command to Home Assistant to control devices.'
        if not intents:
            intents = []
            direct = 'Jag kan inte automatiskt utföra det här. Kan du ge mer information eller omformulera?' 
        else:
            direct = 'Jag förbereder det du bad om och återkommer när det är klart.'

        interpreted = {
            'intents': intents,
            'directResponse': direct,
            'intentDescriptions': intent_desc,
        }

    # Schedule dispatch in background (do not block returning the direct response)
    try:
        # schedule dispatch via the orchestrator_service
        if orchestrator_service is not None:
            asyncio.create_task(orchestrator_service.dispatch(req.message, services=interpreted.get('intents'), wait_for=None))
    except Exception:
        # ignore background scheduling failures for now
        pass

    return {
        'ok': True,
        'directResponse': interpreted.get('directResponse', ''),
        'intents': interpreted.get('intents', []),
        'intentDescriptions': interpreted.get('intentDescriptions', {}),
    }


@app.get('/health')
def health():
    return {'ok': True}


@app.get('/api/assistant_status')
def assistant_status():
    """Return debug info about whether an assistant adapter is wired to the orchestrator."""
    inst = orchestrator_service
    openai_key_present = bool(os.getenv('OPENAI_API_KEY'))
    if inst is None:
        return {'wired': False, 'adapter': None, 'openai_key_present': openai_key_present}
    # try to report class name
    cls = type(inst).__name__
    return {'wired': True, 'adapter': cls, 'openai_key_present': openai_key_present}
