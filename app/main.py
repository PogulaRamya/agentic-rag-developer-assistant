from contextlib import asynccontextmanager
from pathlib import Path
import logging
import secrets
from threading import BoundedSemaphore
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from .settings import Settings
from .models import Question
from .retrieval import DemoRetriever, HybridRetriever
from .agent import DeveloperAgent
from .bigquery import TrendTool

log=logging.getLogger(__name__)

def create_app(settings=None, agent=None):
    settings=settings or Settings.from_env()
    @asynccontextmanager
    async def lifespan(app):
        app.state.agent=agent or DeveloperAgent(settings,
            DemoRetriever() if settings.mode=='demo' else HybridRetriever(settings),
            None if settings.mode=='demo' else TrendTool(settings))
        yield
    app=FastAPI(title='Agentic RAG Developer Assistant',version='0.1.0',lifespan=lifespan)
    slots=BoundedSemaphore(4)
    @app.get('/',response_class=HTMLResponse)
    def home():
        return (Path(__file__).parent/'static/index.html').read_text()
    @app.get('/health')
    def health():
        return {'status':'ok','mode':settings.mode}
    @app.post('/ask')
    def ask(body:Question,x_api_key:str=Header(default='')):
        if settings.api_key and not secrets.compare_digest(x_api_key,settings.api_key):
            raise HTTPException(401,'Invalid API key')
        if not slots.acquire(blocking=False):
            raise HTTPException(429,'Too many concurrent requests')
        try:
            state=app.state.agent.run(body.question)
            return dict(answer=state['answer'],citations=state['citations'],route=state['plan'].route,
                        trace=state['trace'],mode=settings.mode,insufficient_evidence=state['insufficient_evidence'],
                        trend=state.get('trend'), retrieved_contexts=state.get('evidence',[]))
        except Exception:
            log.exception('Assistant request failed')
            raise HTTPException(503,'A backend is unavailable. Check service logs and configuration.') from None
        finally:
            slots.release()
    return app

app=create_app()
