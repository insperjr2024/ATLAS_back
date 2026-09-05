"""Um helper por 📌 evento — o texto e os destinatários num lugar só.

Os use cases que disparam (criar projeto, editar equipe, registrar entrega,
confirmar candidatura) ficam com **uma linha** cada. Sem isto, a redação do
aviso e a regra de quem recebe se espalhariam por quatro arquivos que ninguém
lê junto, e o e-mail da fase 2 acabaria com outra redação.

Todos herdam a garantia de `registrar_notificacao`: falha ao notificar **não**
derruba a ação que gerou o evento.
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session

from src.use_cases.notificacao.destinatarios import (
    inscritos_na_banca,
    lideranca_do_projeto,
    todos_do_projeto,
)
from src.use_cases.notificacao.registrar_notificacao import registrar, registrar_varios


def _formatar(valor) -> str:
    """`date` e `datetime` no formato que o time lê — e "sem data" quando nulo."""
    if valor is None:
        return "sem data"
    if isinstance(valor, datetime):
        return valor.strftime("%d/%m às %H:%M")
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    return str(valor)


def notificar_alocacao(db: Session, projeto, usuario_id: int) -> None:
    """"Você entrou no Projeto Alfa" — só para quem entrou.

    Gerente e diretor não recebem: foram eles que alocaram, e avisar alguém do
    que a própria pessoa acabou de fazer é o tipo de ruído que faz o sino ser
    ignorado.
    """
    registrar(
        db,
        usuario_id=usuario_id,
        tipo="alocado_em_projeto",
        titulo=f"Você entrou no projeto {projeto.nome}",
        corpo=f"Cliente: {projeto.cliente}" if projeto.cliente else None,
        projeto_id=projeto.id,
        rota=f"/projetos/{projeto.id}",
        # Por PROJETO e por pessoa: quem sai e volta na mesma equipe não é
        # avisado duas vezes — o histórico de `projeto_membro` guarda a ida e
        # volta, o sino não precisa repeti-la.
        chave_dedup=f"alocado_em_projeto:projeto={projeto.id}:usuario={usuario_id}",
    )


def notificar_entrega(db: Session, projeto, escopo_id: int, nome_escopo: str) -> None:
    """A entrega sobe para a liderança, não desce para a equipe.

    Quem entregou já sabe que entregou. Quem precisa saber é quem acompanha o
    portfólio — a diretora e o gerente da frente (§7.1: o contraponto positivo
    do monitoramento).
    """
    registrar_varios(
        db,
        lideranca_do_projeto(db, projeto.id),
        tipo="entrega_registrada",
        titulo=f"{projeto.nome} — {nome_escopo} entregue",
        projeto_id=projeto.id,
        rota=f"/projetos/{projeto.id}",
        payload={"projeto_escopo_id": escopo_id},
        chave_dedup=f"entrega_registrada:escopo={escopo_id}",
    )


def notificar_banca_remarcada(
    db: Session, projeto, banca_id: int, nome_escopo: str, de, para
) -> None:
    """§5.6: remarcar banca nunca é silenciosa — e não pode ser silenciosa para
    QUEM DEPENDE DELA, não só no histórico.

    Dois grupos, por motivos diferentes: quem enxerga o projeto (§3) porque o
    plano mudou, e quem **se inscreveu na banca** porque reservou a agenda para
    uma data que não vale mais. O segundo grupo é de fora do projeto por
    exigência do §8 — por isso o alerta aponta para a banca, não para o projeto.
    """
    titulo = f"Banca de {projeto.nome} remarcada — {nome_escopo}"
    corpo = f"De {_formatar(de)} para {_formatar(para)}."

    registrar_varios(
        db,
        todos_do_projeto(db, projeto.id),
        tipo="banca_remarcada",
        titulo=titulo,
        corpo=corpo,
        projeto_id=projeto.id,
        rota=f"/projetos/{projeto.id}/cronograma",
        payload={"banca_id": banca_id},
        # A data nova entra na chave: remarcar de novo é notícia nova.
        chave_dedup=f"banca_remarcada:banca={banca_id}:para={_chave_data(para)}",
    )
    registrar_varios(
        db,
        inscritos_na_banca(db, banca_id),
        tipo="banca_remarcada",
        titulo=f"Banca de {projeto.nome} remarcada",
        corpo=corpo,
        # ⚠ Sem `projeto_id` e apontando para /bancas: quem se inscreveu não é
        # da equipe (§8) e não pode abrir a página do projeto.
        rota=f"/bancas?banca={banca_id}",
        payload={"banca_id": banca_id},
        chave_dedup=f"banca_remarcada:banca={banca_id}:para={_chave_data(para)}",
    )


def notificar_justificativa_pedida(db: Session, projeto, usuario_id: int, sobre: str, pedido_id: int) -> None:
    """§7.4: "a diretoria pergunta ao coordenador" — agora dentro da plataforma.

    ⭐ Vai para o COORDENADOR, e só para ele: é quem sabe por que o escopo
    atrasou. Mandar para a equipe inteira transformaria uma pergunta dirigida
    num aviso de que o projeto está vermelho, que a equipe já vê sozinha.

    A chave leva o `pedido_id`: se a diretoria perguntar de novo sobre OUTRO
    motivo do mesmo projeto, é outra pergunta e merece outro aviso.
    """
    registrar(
        db,
        usuario_id=usuario_id,
        tipo="justificativa_pedida",
        titulo=f"Explique o atraso de {projeto.nome}",
        corpo=sobre,
        projeto_id=projeto.id,
        rota=f"/projetos/{projeto.id}",
        chave_dedup=f"justificativa_pedida:pedido={pedido_id}",
    )


def notificar_entrega_alterada(
    db: Session, projeto, de, para, nome_escopo: Optional[str] = None, escopo_id: Optional[int] = None
) -> None:
    """Mudou a data prometida — do escopo ou da entrega ao cliente.

    Serve aos dois casos porque para quem recebe é a mesma notícia ("a data
    que eu tinha na cabeça mudou"); só o rótulo muda. Vai para todo mundo que
    enxerga o projeto pelo §3: a equipe replaneja, a liderança acompanha o
    portfólio.
    """
    alvo = f"{projeto.nome} — {nome_escopo}" if nome_escopo else f"{projeto.nome} — entrega ao cliente"
    escopo_ou_projeto = f"escopo={escopo_id}" if escopo_id else f"projeto={projeto.id}"

    registrar_varios(
        db,
        todos_do_projeto(db, projeto.id),
        tipo="entrega_alterada",
        titulo=f"Data de entrega alterada — {alvo}",
        corpo=f"De {_formatar(de)} para {_formatar(para)}.",
        projeto_id=projeto.id,
        rota=f"/projetos/{projeto.id}",
        payload={"projeto_escopo_id": escopo_id} if escopo_id else None,
        chave_dedup=f"entrega_alterada:{escopo_ou_projeto}:para={_chave_data(para)}",
    )


def notificar_lote_desempenho(db: Session, lote, pendencias) -> None:
    """Abriu um lote de Avaliação de Desempenho — avisa quem tem o que responder.

    ⚠ Este evento **não é de projeto**, e por isso não passa por
    `destinatarios.py`: o destinatário é quem tem avaliação pendente, venha do
    projeto que vier. Aplicar o recorte do §3 aqui esconderia justamente a
    avaliação que a pessoa precisa preencher.

    Uma notificação por PESSOA, não por par avaliador→avaliado: quem tem 6
    avaliações receberia 6 linhas idênticas, e o sino viraria ruído.

    ⭐ O corpo leva o prazo (2026-09-05, a pedido — "nem quando aparece pra
    eles poderem responder"), espelhando o que a avaliação de banca já fazia
    em `_notificar_prazo_avaliacao`. Data E hora, não só a data: o lote de
    finalização fecha em 48h corridas a partir de um instante, não à meia-
    noite de um dia — "até 07/09" seria impreciso pra ele.
    """
    por_avaliador: dict = {}
    for pendencia in pendencias:
        if pendencia.get("respondida"):
            continue
        por_avaliador[pendencia["avaliador_id"]] = por_avaliador.get(pendencia["avaliador_id"], 0) + 1

    data_fim = getattr(lote, "data_fim", None)
    prazo = f" Responda até {data_fim:%d/%m/%Y às %H:%M}." if data_fim else ""
    corpo = f"{getattr(lote, 'nome', '') or ''}{prazo}".strip() or None

    for avaliador_id, total in por_avaliador.items():
        registrar(
            db,
            usuario_id=avaliador_id,
            tipo="lote_desempenho_aberto",
            titulo=(
                f"Avaliação de Desempenho aberta — {total} "
                f"{'avaliação' if total == 1 else 'avaliações'} para responder"
            ),
            corpo=corpo,
            rota="/avaliacao-desempenho",
            payload={"lote_id": lote.id},
            # Por lote e por pessoa: reabrir o mesmo lote não gera aviso novo,
            # e o total muda sozinho conforme ela responde.
            chave_dedup=f"lote_desempenho_aberto:lote={lote.id}:usuario={avaliador_id}",
        )


def notificar_lote_desempenho_lembrete(db: Session, lote, pendencias) -> None:
    """24h depois de aberto um lote de FINALIZAÇÃO, quem ainda não terminou
    (nem começou, ou respondeu só parte) recebe um empurrão (2026-09-04, a
    pedido — dispara em `rodar_lembrete_lote_finalizacao`, no agendador).

    ⚠ Mesma lógica de agregação de `notificar_lote_desempenho` — mas
    `chave_dedup` própria, senão o dedup do aviso de abertura engoliria este.
    "Só parte" e "nem começou" são o mesmo caso aqui: `pendencias` já é só o
    que falta, sem distinguir 0 de N-1 respondidas — o lembrete é sobre o que
    resta, não sobre o progresso.
    """
    por_avaliador: dict = {}
    for pendencia in pendencias:
        if pendencia.get("respondida"):
            continue
        por_avaliador[pendencia["avaliador_id"]] = por_avaliador.get(pendencia["avaliador_id"], 0) + 1

    for avaliador_id, total in por_avaliador.items():
        registrar(
            db,
            usuario_id=avaliador_id,
            tipo="lote_desempenho_lembrete",
            titulo=(
                f"Falta pouco para o prazo da Avaliação de Desempenho — {total} "
                f"{'avaliação' if total == 1 else 'avaliações'} ainda por responder"
            ),
            corpo=getattr(lote, "nome", None),
            rota="/avaliacao-desempenho",
            payload={"lote_id": lote.id},
            chave_dedup=f"lote_desempenho_lembrete:lote={lote.id}:usuario={avaliador_id}",
        )


def notificar_lote_desempenho_cancelado(db: Session, lote, avaliador_ids) -> None:
    """2026-09-05, a pedido: a banca que abriu este lote sozinha foi
    cancelada DEPOIS de já realizada (imprevisto de última hora) —
    `CancelarBancaUseCase` desfez o lote, e quem tinha o que responder
    precisa saber que não precisa mais.

    ⚠ Uma notificação por PESSOA que aparecia em `GetPendenciasLoteUseCase`
    pra este lote, respondida ou não: mesmo quem já enviou merece saber que
    a rodada inteira foi invalidada, não só quem ainda devia algo."""
    for avaliador_id in set(avaliador_ids):
        registrar(
            db,
            usuario_id=avaliador_id,
            tipo="lote_desempenho_cancelado",
            titulo="Avaliação de Desempenho cancelada",
            corpo=(
                f"{getattr(lote, 'nome', '')} foi cancelada — a banca que abriu esta rodada "
                "não aconteceu de verdade. Não precisa responder."
            ),
            payload={"lote_id": lote.id},
            chave_dedup=f"lote_desempenho_cancelado:lote={lote.id}:usuario={avaliador_id}",
        )


def notificar_pdi_prazo_proximo(
    db: Session, destinatario_id: int, pasta, item, mentorado_id: int, mentorado_nome: str
) -> None:
    """Um dia antes do prazo de um ITEM de PDI (a pasta pode exigir vários —
    ex: Foto + Relatório, cada um com sua própria pendência) — o empurrão
    final antes do aviso de atraso. Disparado por `rodar_lembrete_prazo_pdi`
    (job diário).

    A rota é genérica (não dá pra apontar direto pro item específico): hoje
    o drill-down de PDI é estado local, sem rota por pessoa/pasta/item."""
    registrar(
        db,
        usuario_id=destinatario_id,
        tipo="pdi_prazo_proximo",
        titulo=f"Amanhã é o prazo do item \"{item.nome}\" ({pasta.nome}) de {mentorado_nome}",
        rota="/avaliacao-desempenho/mentorados",
        payload={"pasta_id": pasta.id, "item_id": item.id, "mentorado_id": mentorado_id},
        # Por item+mentorado+destinatário: um lembrete só (o job roda uma vez
        # por dia, e a dedup evita duplicar se rodar de novo no mesmo dia).
        chave_dedup=f"pdi_prazo_proximo:item={item.id}:mentorado={mentorado_id}:destinatario={destinatario_id}",
    )


def notificar_pdi_prazo_vencido(
    db: Session, destinatario_id: int, pasta, item, mentorado_id: int, mentorado_nome: str
) -> None:
    """O dia seguinte ao prazo, pra quem ainda não recebeu o arquivo desse
    item — uma vez só (comparar com "ontem" no job evita repetir todo dia
    pra sempre)."""
    registrar(
        db,
        usuario_id=destinatario_id,
        tipo="pdi_prazo_vencido",
        titulo=(
            f"{mentorado_nome} não teve o item \"{item.nome}\" ({pasta.nome}) "
            f"enviado até o prazo ({_formatar(pasta.prazo)})"
        ),
        rota="/avaliacao-desempenho/mentorados",
        payload={"pasta_id": pasta.id, "item_id": item.id, "mentorado_id": mentorado_id},
        chave_dedup=f"pdi_prazo_vencido:item={item.id}:mentorado={mentorado_id}:destinatario={destinatario_id}",
    )


def notificar_reajuste_solicitado(
    db: Session, destinatario_id: int, projeto_id: int, projeto_escopo_id: int, nome_escopo: str, solicitante_nome: str
) -> None:
    """§8: o coordenador pediu DIAS DE AJUSTE para o escopo.

    Só quem aprova reajuste recebe — nunca o gerente. (O pedido deixou de ser
    "reabrir cronograma oficializado": o cadeado acabou, e o que se pede agora
    são dias a mais na janela do escopo.)"""
    registrar(
        db,
        usuario_id=destinatario_id,
        tipo="reajuste_solicitado",
        titulo=f"{solicitante_nome} pediu reajuste de cronograma — {nome_escopo}",
        projeto_id=projeto_id,
        rota=f"/projetos/{projeto_id}/cronograma",
        payload={"projeto_escopo_id": projeto_escopo_id},
        # Por escopo+destinatário: um pedido pendente por vez (regra do use
        # case), então não precisa de mais nada na chave pra não duplicar.
        chave_dedup=f"reajuste_solicitado:escopo={projeto_escopo_id}:destinatario={destinatario_id}",
    )


def notificar_reajuste_respondido(
    db: Session,
    destinatario_id: int,
    projeto_id: int,
    projeto_escopo_id: int,
    solicitacao_id: int,
    nome_escopo: str,
    aprovado: bool,
    justificativa: str,
) -> None:
    """Avisa quem pediu o reajuste (§5.6) — aprovado ou rejeitado, com a
    justificativa que a diretoria digitou."""
    titulo = f"Reajuste {'aprovado' if aprovado else 'rejeitado'} — {nome_escopo}"
    registrar(
        db,
        usuario_id=destinatario_id,
        tipo="reajuste_respondido",
        titulo=titulo,
        corpo=justificativa,
        projeto_id=projeto_id,
        rota=f"/projetos/{projeto_id}/cronograma",
        payload={"projeto_escopo_id": projeto_escopo_id, "aprovado": aprovado},
        # Pela solicitação, não pelo escopo: uma solicitação só é respondida
        # uma vez (o use case recusa responder de novo), a chave é natural.
        chave_dedup=f"reajuste_respondido:solicitacao={solicitacao_id}",
    )


def _chave_data(valor) -> str:
    """A data em formato estável para a `chave_dedup` — nunca o texto exibido,
    que muda de idioma e de formatação sem que o alerta seja outro."""
    if valor is None:
        return "nula"
    return valor.isoformat()


def notificar_escalacao_banca(
    db: Session, banca_id: int, usuario_id: int, nome_projeto: str, data_hora
) -> None:
    """Hoje cobre a **confirmação de inscrição**; o push automático do §8
    (rodízio respeitando grade horária) ainda não existe no código.

    Quando existir, é este mesmo helper que ele chama — o texto e a chave já
    servem para os dois casos, porque do ponto de vista de quem recebe a
    notícia é a mesma: "você tem banca em tal dia".
    """
    quando = data_hora.strftime("%d/%m às %H:%M") if data_hora else "data a definir"
    registrar(
        db,
        usuario_id=usuario_id,
        tipo="escalacao_banca",
        titulo=f"Você está na banca de {nome_projeto} — {quando}",
        # Sem `projeto_id`: quem participa da banca normalmente NÃO é da equipe
        # do projeto (§8 proíbe), então preencher a FK daria a ele um link para
        # um projeto que o recorte de visão não deixa abrir.
        rota=f"/bancas?banca={banca_id}",
        payload={"banca_id": banca_id},
        chave_dedup=f"escalacao_banca:banca={banca_id}:usuario={usuario_id}",
    )
