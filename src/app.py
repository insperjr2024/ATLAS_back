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
from src.repositories.desempenho_mentoria_repository import DesempenhoMentoriaRepository
from src.repositories.desempenho_pdi_envio_repository import DesempenhoPdiEnvioRepository
from src.repositories.desempenho_pdi_item_repository import DesempenhoPdiItemRepository
from src.repositories.desempenho_pdi_pasta_repository import DesempenhoPdiPastaRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.avaliacao.get_avaliacoes_pendentes import GetAvaliacoesPendentesUseCase
from src.use_cases.banca.push_alocacao_automatica import PushAlocacaoAutomaticaUseCase
from src.use_cases.notificacao.eventos import notificar_pdi_prazo_proximo, notificar_pdi_prazo_vencido
from src.use_cases.projeto.encerrar_ambientacao import EncerrarAmbientacaoUseCase
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


def rodar_encerramento_de_ambientacao() -> None:
    """🤖 §5.3: Ambientação → Em andamento quando os dias úteis de ambientação
    acabam. Roda de madrugada porque a virada é uma questão de DATA — o projeto
    tem que amanhecer no status certo, antes de qualquer um abrir a tela.

    Roda também na subida do app: um servidor que passou o fim de semana fora
    do ar não pode deixar a virada para o dia seguinte."""
    db = SessionLocal()
    try:
        virados = EncerrarAmbientacaoUseCase(db).execute()
        if virados:
            logger.info("Ambientação encerrada automaticamente nos projetos: %s", virados)
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


def rodar_lembrete_prazo_pdi() -> None:
    """Um aviso por ITEM de PDI vencendo amanhã (pro responsável certo — o
    mentor num "Encontro N", a diretoria num "PDI inicial") e um aviso o dia
    seguinte a quem perdeu o prazo (mentor + diretoria, uma vez só — mesmo
    truque de comparar com "ontem" de `rodar_lembrete_prazo_avaliacao`). O
    prazo é da PASTA, mas cada item dentro dela tem sua própria pendência —
    uma pasta com Foto + Relatório pode notificar duas vezes se faltarem os
    dois.

    O envio nunca é bloqueado depois do prazo — isto é só o aviso."""
    db = SessionLocal()
    try:
        hoje = datetime.now().date()
        amanha = hoje + timedelta(days=1)
        ontem = hoje - timedelta(days=1)

        pasta_repository = DesempenhoPdiPastaRepository(db)
        item_repository = DesempenhoPdiItemRepository(db)
        envio_repository = DesempenhoPdiEnvioRepository(db)
        mentoria_repository = DesempenhoMentoriaRepository(db)
        usuario_repository = UsuarioRepository(db)

        mentorias = mentoria_repository.get_all()
        diretores = usuario_repository.get_por_posicao("diretor")

        lembretes = 0
        avisos_vencido = 0
        for pasta in pasta_repository.get_all():
            if pasta.prazo not in (amanha, ontem):
                continue
            for item in item_repository.get_da_pasta(pasta.id):
                enviados = {e.mentorado_id for e in envio_repository.get_por_item(item.id)}
                for mentoria in mentorias:
                    if mentoria.mentorado_id in enviados:
                        continue
                    mentorado = usuario_repository.get_by_id(mentoria.mentorado_id)
                    nome_mentorado = mentorado.nome if mentorado else f"usuário {mentoria.mentorado_id}"

                    if pasta.prazo == amanha:
                        # "PDI inicial" só a diretoria sobe — não faz sentido
                        # lembrar o mentor de um item que ele não pode enviar.
                        if pasta.tipo == "encontro":
                            notificar_pdi_prazo_proximo(
                                db, mentoria.mentor_id, pasta, item, mentoria.mentorado_id, nome_mentorado
                            )
                            lembretes += 1
                        else:
                            for diretor in diretores:
                                notificar_pdi_prazo_proximo(
                                    db, diretor.id, pasta, item, mentoria.mentorado_id, nome_mentorado
                                )
                            lembretes += 1
                    else:  # ontem — vencido
                        if pasta.tipo == "encontro":
                            notificar_pdi_prazo_vencido(
                                db, mentoria.mentor_id, pasta, item, mentoria.mentorado_id, nome_mentorado
                            )
                        for diretor in diretores:
                            notificar_pdi_prazo_vencido(
                                db, diretor.id, pasta, item, mentoria.mentorado_id, nome_mentorado
                            )
                        avisos_vencido += 1
        if lembretes or avisos_vencido:
            logger.info("Prazo de PDI: %d lembrete(s), %d item(ns) vencido(s) sem envio", lembretes, avisos_vencido)
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
        rodar_encerramento_de_ambientacao,
        # 00:05, e não junto dos outros às 6h: é virada de DATA, e o projeto
        # precisa amanhecer no status certo.
        CronTrigger(hour=0, minute=5),
        id="encerramento_ambientacao",
        replace_existing=True,
    )
    scheduler.add_job(
        rodar_lembrete_prazo_avaliacao,
        CronTrigger(hour=6, minute=15),
        id="lembrete_prazo_avaliacao",
        replace_existing=True,
    )
    scheduler.add_job(
        rodar_lembrete_prazo_pdi,
        CronTrigger(hour=6, minute=30),
        id="lembrete_prazo_pdi",
        replace_existing=True,
    )
    scheduler.start()
    # Põe o banco em dia com o calendário antes de servir a primeira request:
    # sem isto, um app que subiu depois de dias parado serviria projetos em
    # Ambientação vencida até a próxima meia-noite.
    rodar_encerramento_de_ambientacao()
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
