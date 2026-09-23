"""As notificações do workflow de documento jurídico (§ Contratos).

⭐ 2026-09-18 — porta de `contratos-backend/src/use_cases/notificacao/
notificacao_service.py`, sobre `registrar()` (o §6.6 do ATLAS) em vez de um
serviço de e-mail próprio — `registrar()` já cuida do e-mail (best-effort,
nunca derruba quem chamou) e do sino.

Eventos do fluxo de documento (o de projeto — criado/vendido — mora em
`notificar_projeto.py`, é sobre o PROJETO, não um documento):
  - confirmado pela venda, pronto pra gerar            -> quem pode gerir o documento (ver
                                                           `_quem_gere_documento`) — só sino
  - aprovado internamente / liberado ao cliente        -> quem vai mandar (vendedor no Contrato de
                                                           Prestação; diretoria + coordenadores no TEP)
                                                           + diretoria de projetos + gerente(s) da(s)
                                                           frente(s) do projeto + quem elaborou
  - assinado                                           -> gerente(s) da(s) frente(s) do projeto
  - cliente respondeu (aprovou ou pediu alteração)     -> os mesmos + quem pode gerir o documento

⭐ 2026-09-23 — a pedido: gerente da frente só entra no E-MAIL a partir da
aprovação interna em diante (aprovado internamente / assinado) — a etapa de
geração (`documento_pronto_para_gerar`/`documento_contrato_confirmado`) virou
só sino pra todo mundo, diretoria e jurídico inclusive.

⭐ 2026-09-21 — os dois primeiros disparos abaixo notificavam
`projeto.criado_por` (quem criou o PROJETO), não necessariamente quem vai de
fato mandar o link pro cliente — o vendedor às vezes não é quem criou o
projeto, e o TEP nem é responsabilidade do criador. Trocado por
`_destinatarios_envio`, a mesma régua de `_pode_enviar_ao_cliente` no
router, só que devolvendo a LISTA de gente em vez de validar uma pessoa só.
"""

from uuid import uuid4

from sqlalchemy.orm import Session

from src.middlewares.authorization import usuario_tem_permissao
from src.repositories.projeto_frente_repository import ProjetoFrenteRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.projeto_vendedor_repository import ProjetoVendedorRepository
from src.repositories.usuario_frente_repository import UsuarioFrenteRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.notificacao.registrar_notificacao import registrar
from src.utils.notificar_projeto import diretoria_e_gerentes
from src.utils.status_documento_contratual import ROTULO_TIPO, nome_do_projeto
from src.utils.usuarios_com_permissao import usuarios_com_permissao


def _rota(documento_id: int) -> str:
    # ⭐ 2026-09-21 — a página do documento virou standalone (`/contratos/
    # :documentoId`), não mais uma aba dentro do projeto — o formato antigo
    # (`/projetos/:id?aba=contratos`) nem existe mais desde a Kanban.
    return f"/contratos/{documento_id}"


def _quem_gere_documento(db: Session, documento) -> list:
    """⭐ 2026-09-22 — a pedido: mesma régua de `_pode_gerir_documento`
    (`routers/documentos_contratuais.py` — diretoria ou `pode_elaborar_
    contratos_proprios`/`pode_elaborar_qualquer_contrato`), devolvendo a
    lista de gente em vez de validar uma pessoa só. Substitui `pode_editar_
    documento_juridico`, removida."""
    usuarios_repo = UsuarioRepository(db)
    destinatarios = {u.id: u for u in usuarios_repo.get_por_posicao("diretor_projetos")}
    for usuario in usuarios_com_permissao(db, "pode_elaborar_qualquer_contrato"):
        # ⭐ 2026-09-23 — a pedido: gerente de frente tem esta caixa (acesso e
        # edição de qualquer contrato é visão geral proposital), mas não é
        # quem toca o dia a dia de gerar/revisar documento — virava
        # notificação em massa pra gente que não ia fazer nada com ela.
        if usuario.posicao == "gerente":
            continue
        destinatarios[usuario.id] = usuario
    if documento.projeto_id:
        vendedor_ids = [v.usuario_id for v in ProjetoVendedorRepository(db).get_by_projeto(documento.projeto_id)]
        for uid in vendedor_ids:
            usuario = usuarios_repo.get_by_id(uid)
            if usuario and usuario_tem_permissao(usuario, db, "pode_elaborar_contratos_proprios"):
                destinatarios[usuario.id] = usuario
    return list(destinatarios.values())


def _gerentes_das_frentes_do_projeto(db: Session, projeto_id) -> list:
    """⭐ 2026-09-23 — a pedido: gerente da frente (ou frentes) DESTE projeto
    — não confundir com `diretoria_e_gerentes` (todos os gerentes, de toda
    frente da Insper Jr). É a régua de quem recebe e-mail quando o contrato
    é aprovado internamente e quando é assinado."""
    if not projeto_id:
        return []
    frente_ids = [f.frente_id for f in ProjetoFrenteRepository(db).get_by_projeto(projeto_id)]
    usuario_frente_repo = UsuarioFrenteRepository(db)
    usuarios_repo = UsuarioRepository(db)
    destinatarios = {}
    for frente_id in frente_ids:
        for vinculo in usuario_frente_repo.get_by_frente(frente_id):
            usuario = usuarios_repo.get_by_id(vinculo.usuario_id)
            if usuario and usuario.posicao == "gerente":
                destinatarios[usuario.id] = usuario
    return list(destinatarios.values())


def documento_pronto_para_gerar(db: Session, documento) -> None:
    """Confirmado pela venda — avisa quem pode gerir o documento e gerar.

    ⭐ 2026-09-22 — a pedido: só sino, sem e-mail. É um aviso de "próximo
    passo" pra quem já está de olho no documento (o mesmo grupo que acabou
    de confirmar ou está gerenciando o contrato), não um evento que precisa
    tirar alguém do que está fazendo.
    """
    tipo = ROTULO_TIPO.get(documento.tipo, "Documento")
    titulo = f'Documento pronto para geração — "{tipo}" do projeto "{nome_do_projeto(documento)}".'
    for usuario in _quem_gere_documento(db, documento):
        registrar(
            db,
            usuario_id=usuario.id,
            tipo="documento_contratual_pronto_para_gerar",
            titulo=titulo,
            projeto_id=documento.projeto_id,
            rota=_rota(documento.id),
            chave_dedup=f"documento_contratual:{documento.id}:pronto_para_gerar:{uuid4()}",
            enviar_email=False,
        )


def documento_contrato_confirmado(db: Session, documento) -> None:
    """⭐ 2026-09-22 — a pedido: Contrato de Prestação elaborado (confirmado,
    entrou em Geração) — avisa diretoria de projetos, gerentes e o(s)
    vendedor(es) do projeto. Só pra tipo "contrato", sem pedido pros
    outros tipos ainda.

    ⭐ 2026-09-23 — a pedido: só sino, sem e-mail. Ninguém precisa de e-mail
    nesta etapa (geração) — diretoria e jurídico não, e o gerente só entra
    no e-mail mais adiante (aprovado internamente / assinado, ver
    `documento_aprovado_internamente`/`documento_assinado`)."""
    titulo = f'Contrato de Prestação elaborado — "{nome_do_projeto(documento)}" está em geração.'
    destinatarios = diretoria_e_gerentes(db)
    vendedor_ids = [v.usuario_id for v in ProjetoVendedorRepository(db).get_by_projeto(documento.projeto_id)]
    usuarios = UsuarioRepository(db)
    for uid in vendedor_ids:
        usuario = usuarios.get_by_id(uid)
        if usuario:
            destinatarios[usuario.id] = usuario

    for usuario in destinatarios.values():
        registrar(
            db,
            usuario_id=usuario.id,
            tipo="documento_contratual_pronto_para_gerar",
            titulo=titulo,
            projeto_id=documento.projeto_id,
            rota=_rota(documento.id),
            chave_dedup=f"documento_contratual:{documento.id}:contrato_confirmado:{uuid4()}",
            enviar_email=False,
        )


def documento_pronto_para_revisao_interna(db: Session, documento) -> None:
    """⭐ 2026-09-22 — a pedido: rascunho gerado, documento entrou em revisão
    interna — avisa quem tem a caixa de aprovar internamente (Jurídico)."""
    tipo = ROTULO_TIPO.get(documento.tipo, "Documento")
    titulo = f'Documento pendente de revisão interna — "{tipo}" do projeto "{nome_do_projeto(documento)}".'
    for usuario in usuarios_com_permissao(db, "pode_aprovar_contrato_internamente"):
        registrar(
            db,
            usuario_id=usuario.id,
            tipo="documento_contratual_pronto_para_revisao_interna",
            titulo=titulo,
            projeto_id=documento.projeto_id,
            rota=_rota(documento.id),
            chave_dedup=f"documento_contratual:{documento.id}:pronto_para_revisao_interna:{uuid4()}",
        )


def documento_aprovado_internamente(db: Session, documento) -> None:
    """Jurídico aprovou por dentro — avisa quem vai mandar ao cliente e quem
    elaborou (confirmou o preenchimento).

    ⭐ 2026-09-23 — a pedido: soma também a diretoria de projetos, o(s)
    gerente(s) da(s) frente(s) do projeto e quem CRIOU o documento (abriu o
    "Novo Contrato") — "todos envolvidos", já que esta é a etapa em que o
    gerente passa a entrar no e-mail (a de geração, não; ver `documento_
    contrato_confirmado`)."""
    tipo = ROTULO_TIPO.get(documento.tipo, "Documento")
    titulo = f'Documento aprovado internamente — já pode mandar ao cliente: "{tipo}" do projeto "{nome_do_projeto(documento)}".'
    destinatarios = {u.id: u for u in _destinatarios_envio(db, documento)}
    for usuario in UsuarioRepository(db).get_por_posicao("diretor_projetos"):
        destinatarios[usuario.id] = usuario
    for usuario in _gerentes_das_frentes_do_projeto(db, documento.projeto_id):
        destinatarios[usuario.id] = usuario
    if documento.confirmado_por:
        elaborador = UsuarioRepository(db).get_by_id(documento.confirmado_por)
        if elaborador:
            destinatarios[elaborador.id] = elaborador
    if documento.criado_por:
        criador = UsuarioRepository(db).get_by_id(documento.criado_por)
        if criador:
            destinatarios[criador.id] = criador
    for usuario in destinatarios.values():
        registrar(
            db,
            usuario_id=usuario.id,
            tipo="documento_contratual_aprovado_internamente",
            titulo=titulo,
            projeto_id=documento.projeto_id,
            rota=_rota(documento.id),
            chave_dedup=f"documento_contratual:{documento.id}:aprovado_internamente:{uuid4()}",
        )


def documento_liberado_para_cliente(db: Session, documento) -> None:
    """Gerado/exportado — avisa quem vai mandar ao cliente que o link já está pronto."""
    tipo = ROTULO_TIPO.get(documento.tipo, "Documento")
    titulo = f'Documento pronto para enviar ao cliente — "{tipo}" do projeto "{nome_do_projeto(documento)}".'
    for usuario in _destinatarios_envio(db, documento):
        registrar(
            db,
            usuario_id=usuario.id,
            tipo="documento_contratual_liberado",
            titulo=titulo,
            projeto_id=documento.projeto_id,
            rota=_rota(documento.id),
            chave_dedup=f"documento_contratual:{documento.id}:liberado:{uuid4()}",
        )


def documento_assinado(db: Session, documento) -> None:
    """⭐ 2026-09-23 — a pedido: documento marcado como assinado — avisa o(s)
    gerente(s) da(s) frente(s) do projeto (mesma régua de `documento_
    aprovado_internamente`, só que aqui o gerente é o único destinatário —
    não é pedido pra somar diretoria/vendedor/quem elaborou nesta etapa)."""
    tipo = ROTULO_TIPO.get(documento.tipo, "Documento")
    titulo = f'Documento assinado — "{tipo}" do projeto "{nome_do_projeto(documento)}".'
    for usuario in _gerentes_das_frentes_do_projeto(db, documento.projeto_id):
        registrar(
            db,
            usuario_id=usuario.id,
            tipo="documento_contratual_assinado",
            titulo=titulo,
            projeto_id=documento.projeto_id,
            rota=_rota(documento.id),
            chave_dedup=f"documento_contratual:{documento.id}:assinado:{uuid4()}",
        )


def cliente_respondeu(db: Session, documento, aprovado: bool, motivo: str = None) -> None:
    """Cliente aprovou ou pediu alteração.

    - Aprovou: avisa quem ia mandar (`_destinatarios_envio` — coordenador do
      TEP incluso, é ele que toca a execução) + quem pode gerir o documento.
    - Pediu alteração: ⭐ 2026-09-23 — a pedido: NÃO avisa o coordenador do
      projeto — só quem pode gerir o documento (jurídico/`pode_elaborar_*` e
      diretoria de projetos, via `_quem_gere_documento`). É um problema do
      texto do contrato pra resolver, não da execução do projeto."""
    tipo = ROTULO_TIPO.get(documento.tipo, "Documento")
    if aprovado:
        titulo = f'O cliente aprovou o documento "{tipo}" do projeto "{nome_do_projeto(documento)}".'
        destinatarios = {u.id: u for u in _destinatarios_envio(db, documento)}
    else:
        titulo = f'O cliente pediu alteração no documento "{tipo}" do projeto "{nome_do_projeto(documento)}".'
        if motivo:
            titulo += f' Pedido: "{motivo}"'
        destinatarios = {}

    for usuario in _quem_gere_documento(db, documento):
        destinatarios[usuario.id] = usuario

    evento = "cliente_aprovou" if aprovado else "cliente_pediu_alteracao"
    for usuario in destinatarios.values():
        registrar(
            db,
            usuario_id=usuario.id,
            tipo=f"documento_contratual_{evento}",
            titulo=titulo,
            projeto_id=documento.projeto_id,
            rota=_rota(documento.id),
            chave_dedup=f"documento_contratual:{documento.id}:{evento}:{uuid4()}",
        )


def _destinatarios_envio(db: Session, documento) -> list:
    """Quem vai de fato mandar o link pro cliente — mesma régua de
    `_pode_enviar_ao_cliente` (`routers/documentos_contratuais.py`), só que
    devolvendo a lista de pessoas em vez de validar uma só:

    - Contrato de Prestação: o(s) vendedor(es) do projeto.
    - TEP: diretoria de projetos + coordenador(es) do projeto.
    - Outros tipos (sem pedido específico ainda): quem criou o projeto,
      mesmo fallback de antes.
    """
    if documento.tipo == "contrato":
        vendedor_ids = [v.usuario_id for v in ProjetoVendedorRepository(db).get_by_projeto(documento.projeto_id)]
        usuarios = UsuarioRepository(db)
        return [u for u in (usuarios.get_by_id(uid) for uid in vendedor_ids) if u]

    if documento.tipo == "tep":
        usuarios_repo = UsuarioRepository(db)
        destinatarios = {u.id: u for u in usuarios_repo.get_por_posicao("diretor_projetos")}
        membros = ProjetoMembroRepository(db).get_by_projeto(documento.projeto_id, apenas_atuais=True)
        for membro in membros:
            if membro.papel != "coordenador":
                continue
            usuario = usuarios_repo.get_by_id(membro.usuario_id)
            if usuario:
                destinatarios[usuario.id] = usuario
        return list(destinatarios.values())

    return _usuario_criador(db, documento)


def _usuario_criador(db: Session, documento) -> list:
    criado_por = getattr(documento.projeto, "criado_por", None)
    if not criado_por:
        return []
    usuario = UsuarioRepository(db).get_by_id(criado_por)
    return [usuario] if usuario else []
