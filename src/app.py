import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.database.database import SessionLocal, engine
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
    grade_horaria,
    solicitacoes_projeto,
    usuarios,
)
from src.repositories.desempenho_lote_repository import DesempenhoLoteRepository
from src.repositories.desempenho_mentoria_repository import DesempenhoMentoriaRepository
from src.repositories.desempenho_pdi_envio_repository import DesempenhoPdiEnvioRepository
from src.repositories.desempenho_pdi_item_repository import DesempenhoPdiItemRepository
from src.repositories.desempenho_pdi_pasta_repository import DesempenhoPdiPastaRepository
from src.repositories.notificacao_repository import NotificacaoRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.avaliacao.get_avaliacoes_pendentes import GetAvaliacoesPendentesUseCase
from src.use_cases.banca.finalizacao_automatica import FinalizacaoAutomaticaBancaUseCase
from src.use_cases.banca.push_alocacao_automatica import PushAlocacaoAutomaticaUseCase
from src.use_cases.desempenho_lote.get_pendencias import GetPendenciasLoteUseCase
from src.use_cases.notificacao.enviar_email_notificacao import enfileirar
from src.use_cases.notificacao.eventos import (
    notificar_lote_desempenho_lembrete,
    notificar_pdi_prazo_proximo,
    notificar_pdi_prazo_vencido,
)
from src.use_cases.projeto.avancar_status import AvancarStatusAutomaticoUseCase
from src.use_cases.projeto.encerrar_ambientacao import EncerrarAmbientacaoUseCase
from src.use_cases.monitoramento.monitoramento import _BaseMonitoramento, _agrupar
from src.models.projeto_model import ProjetoModel
from src.utils.condicoes_alerta import BANCA_HOJE, TAREFA_VENCIDA, detectar_condicoes, para_papel
from src.utils.notificar import notificar
from src.utils.tarefa_status import janela_semana

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


def rodar_avanco_de_status() -> None:
    """🤖 §4: o status do projeto acompanha os fatos, sem ninguém clicar.

    Duas transições têm gatilho inequívoco — a primeira banca realizada leva a
    Validação em bancas, e todos os escopos entregues levam a Período de
    ajustes. As demais continuam manuais porque não há o que observar: Envio de
    TEP é um documento fora da plataforma, e finalizar é decisão da diretoria.

    Roda de madrugada, junto do encerramento de ambientação, pelo mesmo motivo:
    o projeto tem de amanhecer no status certo. O gatilho imediato existe nos
    atos que o disparam (registrar banca, marcar entrega) — este job é a rede
    para o que foi gravado por outro caminho.
    """
    db = SessionLocal()
    try:
        avancados = AvancarStatusAutomaticoUseCase(db).execute()
        if avancados:
            logger.info("Status avançado automaticamente nos projetos: %s", avancados)
    finally:
        db.close()


def rodar_finalizacao_automatica_de_bancas() -> None:
    """§8/§6.5: substitui o botão "Registrar realização" (2026-09-04, a
    pedido). De 5 em 5 minutos — mesma frequência do push de alocação, e pelo
    mesmo motivo: uma banca marcada logo depois da passada do job não pode
    esperar até o dia seguinte pra abrir a avaliação de desempenho.

    Idempotente pela própria condição da varredura
    (`get_para_finalizacao_automatica`): uma vez `realizado_em` gravado, a
    banca sai do universo candidato e não é processada de novo."""
    db = SessionLocal()
    try:
        resumo = FinalizacaoAutomaticaBancaUseCase(db).execute()
        if resumo:
            logger.info("Finalização automática de bancas: %s", resumo)
    finally:
        db.close()


def rodar_lembrete_lote_finalizacao() -> None:
    """24h depois de aberto, quem ainda tem pendência num lote de
    FINALIZAÇÃO recebe um lembrete (2026-09-04, a pedido).

    ⚠ Só "finalizacao", nunca "periodico": o periódico já não tem lembrete de
    24h nenhum hoje (o dele é `rodar_lembrete_prazo_pdi`-like, inexistente até
    aqui) — inventar um pra ele agora seria mudar comportamento que ninguém
    pediu. A janela de disparo é a mesma do lote estar aberto
    (`get_abertos_agora`): passado o `data_fim` (48h), o lote fecha sozinho e
    o lembrete para de fazer sentido.

    Dedup por `chave_dedup` (lote+pessoa) faz a varredura de 5 em 5 minutos
    custar uma query e nada mais depois do primeiro disparo — mesmo padrão
    dos outros lembretes deste arquivo."""
    db = SessionLocal()
    try:
        agora = datetime.now()
        lote_repo = DesempenhoLoteRepository(db)
        avisos = 0
        for lote in lote_repo.get_abertos_agora():
            if lote.tipo != "finalizacao":
                continue
            if agora - lote.data_inicio < timedelta(hours=24):
                continue
            pendencias = GetPendenciasLoteUseCase(db).execute(lote.id) or []
            if any(not p.get("respondida") for p in pendencias):
                notificar_lote_desempenho_lembrete(db, lote, pendencias)
                avisos += 1
        if avisos:
            logger.info("Lembrete de lote de finalização: %d lote(s) com pendência", avisos)
    finally:
        db.close()


def rodar_lembrete_prazo_avaliacao() -> None:
    """§8: dois avisos por dia sobre o prazo de 2 dias pra avaliar uma banca
    realizada — pro avaliador, a 1 dia do fim (a notificação de "banca
    realizada" já sai na hora, em `RegistrarRealizacaoBancaUseCase`; esta é
    o empurrão final antes do bloqueio); pra diretoria DE PROJETOS, no dia
    seguinte a quem perdeu o prazo (uma vez só — comparar com "ontem" evita
    repetir o aviso todo dia pra sempre pra quem nunca vai mais poder
    enviar).

    ⚠ `diretor_projetos`, nunca `diretor` (2026-09-05, corrigido a pedido:
    "SEMPRE pra avisar diretoria de projetos e NUNCA avisar a diretoria
    normal"). Quem conduz banca — cancela, aprova, cobra prazo — é sempre a
    diretoria de projetos em toda esta plataforma; a diretoria genérica
    (`posicao == "diretor"`) não tem nada a ver com o ciclo de vida de uma
    banca."""
    db = SessionLocal()
    try:
        hoje = datetime.now().date()
        amanha = hoje + timedelta(days=1)
        ontem = hoje - timedelta(days=1)
        pendentes = GetAvaliacoesPendentesUseCase(db).execute()
        usuario_repository = UsuarioRepository(db)
        diretores = usuario_repository.get_por_posicao("diretor_projetos")

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


def rodar_lembrete_condicoes() -> None:
    """A fase 2 prometida em `condicoes_alerta.py`: `tarefa_vencida` e
    `banca_hoje` passam a sair por e-mail também, não só no sino.

    ⚠ **Mesma detecção, não uma segunda régua.** Roda `detectar_condicoes` e
    `para_papel` — as mesmas funções que montam o sino — sobre TODOS os
    projetos ativos de uma vez (sem `current_user`: aqui não há recorte de
    visão, é o job quem decide quem recebe, pelo papel na equipe).

    ⚠ **A linha nasce com `origem="condicao"`, nunca `registrar()`.**
    `registrar()` sempre grava `origem="evento"` — usar ele aqui faria a
    MESMA tarefa vencida aparecer duas vezes no sino: uma vez como evento
    persistido por este job, outra como condição recalculada a cada leitura
    (`detectar_condicoes` continua rodando, e não tem como saber que este job
    já avisou). `origem="condicao"` é o mesmo formato que `marcar_lida.py`
    já grava quando a PESSOA dispensa — só entra no mapa de leituras
    (`get_leituras_de_condicao`), nunca na lista de eventos do sino.

    ⚠ **O dedup por `chave_dedup` é o que evita spam.** `tarefa_vencida` não
    leva data na chave: um lembrete só, na primeira vez que a tarefa aparece
    vencida, não um por dia enquanto continuar vencida. `banca_hoje` leva a
    data — mas só é verdade no próprio dia da banca, então também dispara
    uma vez só, natural.

    As demais condições (`kickoff_pendente`, `banca_nao_marcada`,
    `ambientacao_sem_banca`, `projeto_sem_reuniao`) e os agregados da liderança
    ficam de fora de propósito — só os dois tipos acima têm o "fixo" decidido
    em 2026-08-17.
    """
    db = SessionLocal()
    try:
        base = _BaseMonitoramento(db)
        notificacao_repository = NotificacaoRepository(db)
        projetos = db.query(ProjetoModel).filter(ProjetoModel.arquivado_em.is_(None)).all()
        if not projetos:
            return

        hoje = datetime.now().date()
        ctx = base._contexto(projetos)
        inicio, fim = janela_semana(hoje)
        reunioes = base.reuniao_repository.get_by_projetos_e_janela(ctx["ids"], inicio, fim)
        _tarefas = base.tarefa_repository.get_by_projetos(ctx["ids"])
        condicoes = detectar_condicoes(
            projetos,
            escopos_por_projeto=ctx["escopos_por_projeto"],
            bancas_por_escopo=ctx["bancas_por_escopo"],
            nomes_escopo=ctx["nomes_escopo"],
            tarefas_por_projeto=_agrupar(_tarefas, "projeto_id"),
            encerra_por_coluna=base._encerra_por_coluna(),
            projetos_com_reuniao={r.projeto_id for r in reunioes},
            responsaveis_por_tarefa=base.tarefa_repository.responsaveis_por_tarefa(
                t.id for t in _tarefas
            ),
            # Mesma régua do monitoramento (ver `listar_notificacoes`). Este job
            # só manda `tarefa_vencida` e `banca_hoje`, então `ambientacao_sem_banca`
            # é descartada logo abaixo — mas calculada certo enquanto existir.
            dias_nao_letivos=base._calendario_global(),
            hoje=hoje,
        )
        relevantes = [c for c in condicoes if c.tipo in (TAREFA_VENCIDA, BANCA_HOJE)]
        if not relevantes:
            return

        membros_por_projeto = _agrupar(
            base.membro_repository.get_by_projetos(ctx["ids"], apenas_atuais=True), "projeto_id"
        )

        enviados = 0
        for projeto_id, condicoes_do_projeto in _agrupar(relevantes, "projeto_id").items():
            for membro in membros_por_projeto.get(projeto_id, []):
                for condicao in para_papel(condicoes_do_projeto, membro.papel, membro.usuario_id):
                    linha = notificacao_repository.criar_se_nao_existe(
                        usuario_id=membro.usuario_id,
                        tipo=condicao.tipo,
                        origem="condicao",
                        titulo=condicao.titulo,
                        projeto_id=condicao.projeto_id,
                        payload={"rota": condicao.rota},
                        chave_dedup=condicao.chave_dedup,
                    )
                    # `None` = já existia (dedup) ou a pessoa já tinha
                    # dispensado antes deste job rodar — não manda de novo.
                    if linha is None:
                        continue
                    enfileirar(
                        notificacao_id=linha.id,
                        usuario_id=membro.usuario_id,
                        tipo=condicao.tipo,
                        titulo=condicao.titulo,
                        corpo=None,
                        rota=condicao.rota,
                    )
                    enviados += 1
        if enviados:
            logger.info("Lembrete de condições: %d e-mail(s) enfileirado(s)", enviados)
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

    O envio nunca é bloqueado depois do prazo — isto é só o aviso.

    ⚠ `diretor_projetos`, nunca `diretor` (2026-09-05, mesma correção de
    `rodar_lembrete_prazo_avaliacao`, estendida pra cá a pedido: "a regra
    vale pra plataforma inteira")."""
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
        diretores = usuario_repository.get_por_posicao("diretor_projetos")

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
        # De 5 em 5 minutos, e não uma vez por dia: a regra do §8 é "uma semana
        # antes da banca", e com varredura diária uma banca marcada logo depois
        # do horário do job só era atendida quase 24h atrasada.
        #
        # A frequência é barata porque a varredura é idempotente e sai cedo: só
        # preenche até o piso, quem já está inscrito entra em `_excluidos`, a
        # notificação tem chave, e sem banca na janela o `execute` retorna na
        # primeira query. Roda em thread (o job é `def`, não `async def`), então
        # não disputa o event loop com as requisições.
        CronTrigger(minute="*/5"),
        id="push_alocacao_automatica",
        replace_existing=True,
    )
    scheduler.add_job(
        rodar_finalizacao_automatica_de_bancas,
        # Mesma frequência e mesmo motivo do push de alocação: uma banca cuja
        # `data_hora` acabou de passar não pode esperar até a meia-noite pra
        # abrir a avaliação de desempenho de quem participou.
        CronTrigger(minute="*/5"),
        id="finalizacao_automatica_de_bancas",
        replace_existing=True,
    )
    scheduler.add_job(
        rodar_lembrete_lote_finalizacao,
        CronTrigger(minute="*/5"),
        id="lembrete_lote_finalizacao",
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
        rodar_avanco_de_status,
        # 00:10, logo depois do encerramento de ambientação (00:05): um projeto
        # que acabou de virar para Em andamento já é avaliado na mesma noite.
        CronTrigger(hour=0, minute=10),
        id="avanco_de_status",
        replace_existing=True,
    )
    scheduler.add_job(
        rodar_lembrete_prazo_avaliacao,
        CronTrigger(hour=6, minute=15),
        id="lembrete_prazo_avaliacao",
        replace_existing=True,
    )
    # Pausado (19/08/2026, pedido direto): PDI ainda não está em uso pela
    # diretoria, e o lembrete diário estava incomodando. A função continua
    # aqui pronta — é só reativar o `add_job` abaixo quando o PDI voltar a
    # ser usado de verdade.
    # scheduler.add_job(
    #     rodar_lembrete_prazo_pdi,
    #     CronTrigger(hour=6, minute=30),
    #     id="lembrete_prazo_pdi",
    #     replace_existing=True,
    # )
    scheduler.add_job(
        rodar_lembrete_condicoes,
        CronTrigger(hour=6, minute=20),
        id="lembrete_condicoes",
        replace_existing=True,
    )
    scheduler.start()
    # Põe o banco em dia com o calendário antes de servir a primeira request:
    # sem isto, um app que subiu depois de dias parado serviria projetos em
    # Ambientação vencida até a próxima meia-noite.
    rodar_encerramento_de_ambientacao()
    # Na mesma ordem do agendamento: ambientação primeiro, e o avanço logo
    # depois já enxerga quem acabou de virar para Em andamento.
    rodar_avanco_de_status()
    # Mesma razão dos dois acima — e o motivo de a alocação automática nunca
    # ter acontecido de fato. O agendador vive DENTRO do processo, então "toda
    # hora" só dispara enquanto há processo de pé; servidor fora do ar não
    # acumula disparo, ele os perde. Sem esta chamada, uma banca podia
    # atravessar a janela inteira de 7 dias sem ninguém escalado, e a primeira
    # subida seguinte não corrigia nada.
    rodar_push_alocacao_automatica()
    # Mesmo motivo: sem confirmação manual nenhuma sobrando (o botão saiu),
    # uma banca cuja `data_hora` passou enquanto o servidor estava fora do ar
    # ficaria SEM avaliação de desempenho até a próxima subida se ninguém
    # rodasse isto na hora.
    rodar_finalizacao_automatica_de_bancas()
    yield
    scheduler.shutdown()


app = FastAPI(title="API ATLAS", lifespan=lifespan)


@app.middleware("http")
async def registrar_erro_inesperado(request: Request, call_next):
    """Todo 500 sai daqui — com log utilizável e com os headers de CORS.

    Duas coisas que o tratamento padrão do Starlette não dá, e que custaram
    uma investigação inteira:

    1. **O log não dizia qual rota morreu.** O traceback do uvicorn sai sem
       método nem caminho, então "deu erro ao criar banca" não tinha como
       virar uma linha de log específica. Aqui sai `POST /bancas` junto.

    2. **A resposta de erro nascia FORA do CORSMiddleware.** Exceção não
       tratada sobe até o `ServerErrorMiddleware`, que responde por cima de
       todo mundo — sem `Access-Control-Allow-Origin`. No navegador isso não
       vira "erro 500": vira `Failed to fetch`, ou seja, a mesma falha
       aparecia como problema de conexão em dev e como erro de servidor em
       produção (onde o rewrite do Vercel torna a chamada same-origin).
       Respondendo aqui dentro, o CORS ainda embrulha a resposta.

    O estado do pool vai no log de propósito: `QueuePool limit ... timed out`
    é a falha que grava a ação e derruba a request logo depois, e ela só é
    reconhecível olhando quantas conexões estavam em uso na hora.

    ⚠ O corpo não leva `detail`. A tela tem o texto dela para 5xx
    (`api.ts`), e mandar o erro técnico para cá só o exibiria para quem não
    pode fazer nada com ele.
    """
    try:
        return await call_next(request)
    except Exception:  # noqa: BLE001 — é o último anteparo antes do uvicorn
        logger.exception(
            "Erro não tratado em %s %s (pool: %s)",
            request.method,
            request.url.path,
            engine.pool.status(),
        )
        return JSONResponse(status_code=500, content={"erro": "interno"})


# ⚠ Adicionado DEPOIS do middleware acima de propósito: `add_middleware`
# empilha do mais recente para o mais externo, então o CORS fica por fora e
# consegue embrulhar o 500 que o outro devolve.
app.add_middleware(
    CORSMiddleware,
    # Local (qualquer porta) + o front em produção. Domínio exato, sem
    # wildcard: um curinga tipo `atlasijr.*\.vercel\.app` também deixaria
    # passar o projeto de outra conta chamado "atlasijr-qualquercoisa" —
    # o Vercel só garante unicidade do nome completo, não do prefixo.
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+|https://atlasijr\.vercel\.app",
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
app.include_router(grade_horaria.router)
app.include_router(solicitacoes_projeto.router)
app.include_router(projetos.router)
app.include_router(cronograma.router)
app.include_router(tarefas.router)
app.include_router(monitoramento.router)
app.include_router(bancas.router)
app.include_router(avaliacoes.router)
app.include_router(desempenho.router)
app.include_router(notificacoes.router)
app.include_router(solicitacoes_troca.router)
