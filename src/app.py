import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.database.database import SessionLocal
from src.routers import (
    auth,
    avaliacoes,
    bancas,
    catalogo,
    cronograma,
    desempenho,
    monitoramento,
    notificacoes,
    projetos,
    solicitacoes_troca,
    tarefas,
    usuarios,
)
from src.use_cases.banca.push_alocacao_automatica import PushAlocacaoAutomaticaUseCase

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def rodar_push_alocacao_automatica() -> None:
    """§8: uma vez por dia, escala consultores por rodízio para bancas sem
    gente suficiente a uma semana da data. Sessão própria — roda fora de uma
    request, sem `Depends(get_db)` disponível (mesmo padrão de scripts/seed.py)."""
    db = SessionLocal()
    try:
        resumo = PushAlocacaoAutomaticaUseCase(db).execute()
        if resumo:
            logger.info("Push automático de bancas: %s", resumo)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(
        rodar_push_alocacao_automatica,
        CronTrigger(hour=6, minute=0),
        id="push_alocacao_automatica",
        replace_existing=True,
    )
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="API ATLAS", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


app.include_router(auth.router_publico)
app.include_router(auth.router)
app.include_router(catalogo.router)
app.include_router(usuarios.router)
app.include_router(projetos.router)
app.include_router(cronograma.router)
app.include_router(tarefas.router)
app.include_router(monitoramento.router)
app.include_router(bancas.router)
app.include_router(avaliacoes.router)
app.include_router(desempenho.router)
app.include_router(notificacoes.router)
app.include_router(solicitacoes_troca.router)
