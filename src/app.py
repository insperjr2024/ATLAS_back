import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

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
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.avaliacao.get_avaliacoes_pendentes import GetAvaliacoesPendentesUseCase
from src.use_cases.banca.push_alocacao_automatica import PushAlocacaoAutomaticaUseCase
from src.utils.notificar import notificar

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


def rodar_lembrete_prazo_avaliacao() -> None:
    """§8: dois avisos por dia sobre o prazo de 2 dias pra avaliar uma banca
    realizada — pro avaliador, a 1 dia do fim (a notificação de "banca
    realizada" já sai na hora, em `RegistrarRealizacaoBancaUseCase`; esta é
    o empurrão final antes do bloqueio); pra diretoria, no dia seguinte a
    quem perdeu o prazo (uma vez só — comparar com "ontem" evita repetir o
    aviso todo dia pra sempre pra quem nunca vai mais poder enviar)."""
    db = SessionLocal()
    try:
        hoje = datetime.now().date()
        amanha = hoje + timedelta(days=1)
        ontem = hoje - timedelta(days=1)
        pendentes = GetAvaliacoesPendentesUseCase(db).execute()
        usuario_repository = UsuarioRepository(db)
        diretores = usuario_repository.get_por_posicao("diretor")

        lembretes = 0
        avisos_diretoria = 0
        for item in pendentes:
            prazo_data = item["prazo_avaliacao"].date()
            if not item["prazo_expirado"] and prazo_data == amanha:
                notificar(
                    db,
                    item["usuario_id"],
                    f"Amanhã é o último dia para avaliar a banca de {item['nome_projeto']}.",
                    banca_id=item["banca_id"],
                    # Mesmo tipo que `marcar_banca_escopo` usa ao abrir o prazo:
                    # é a mesma pendência, um empurrão depois. Sem isto caía no
                    # `banca_aviso` genérico e escapava do filtro da central.
                    tipo="avaliacao_pendente",
                )
                lembretes += 1
            elif item["prazo_expirado"] and prazo_data == ontem:
                avaliador = usuario_repository.get_by_id(item["usuario_id"])
                nome_avaliador = avaliador.nome if avaliador else f"usuário {item['usuario_id']}"
                mensagem = (
                    f"{nome_avaliador} não enviou a avaliação da banca de {item['nome_projeto']} "
                    f"dentro do prazo (venceu em {item['prazo_avaliacao']:%d/%m/%Y})."
                )
                for diretor in diretores:
                    notificar(db, diretor.id, mensagem, banca_id=item["banca_id"])
                avisos_diretoria += 1
        if lembretes or avisos_diretoria:
            logger.info(
                "Prazo de avaliação: %d lembrete(s), %d aviso(s) à diretoria",
                lembretes,
                avisos_diretoria,
            )
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
    scheduler.add_job(
        rodar_lembrete_prazo_avaliacao,
        CronTrigger(hour=6, minute=15),
        id="lembrete_prazo_avaliacao",
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
