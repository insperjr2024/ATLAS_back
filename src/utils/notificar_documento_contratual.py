"""As notificações do workflow de documento jurídico (§ Contratos).

⭐ 2026-09-18 — porta de `contratos-backend/src/use_cases/notificacao/
notificacao_service.py`, sobre `registrar()` (o §6.6 do ATLAS) em vez de um
serviço de e-mail próprio — `registrar()` já cuida do e-mail (best-effort,
nunca derruba quem chamou) e do sino.

Eventos do fluxo de documento (o de projeto — criado/vendido — mora em
`notificar_projeto.py`, é sobre o PROJETO, não um documento):
  - confirmado pela venda, pronto pro Jurídico gerar  -> quem tem `pode_editar_documento_juridico`
  - aprovado internamente / liberado ao cliente        -> quem vai mandar (vendedor no Contrato de
                                                           Prestação; diretoria + coordenadores no TEP)
  - cliente respondeu (aprovou ou pediu alteração)     -> os mesmos + Jurídico

⭐ 2026-09-21 — os dois primeiros disparos abaixo notificavam
`projeto.criado_por` (quem criou o PROJETO), não necessariamente quem vai de
fato mandar o link pro cliente — o vendedor às vezes não é quem criou o
projeto, e o TEP nem é responsabilidade do criador. Trocado por
`_destinatarios_envio`, a mesma régua de `_pode_enviar_ao_cliente` no
router, só que devolvendo a LISTA de gente em vez de validar uma pessoa só.
"""

from uuid import uuid4

from sqlalchemy.orm import Session

from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.projeto_vendedor_repository import ProjetoVendedorRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.notificacao.registrar_notificacao import registrar
from src.utils.status_documento_contratual import ROTULO_TIPO, nome_do_projeto
from src.utils.usuarios_com_permissao import usuarios_com_permissao


def _rota(documento_id: int) -> str:
    # ⭐ 2026-09-21 — a página do documento virou standalone (`/contratos/
    # :documentoId`), não mais uma aba dentro do projeto — o formato antigo
    # (`/projetos/:id?aba=contratos`) nem existe mais desde a Kanban.
    return f"/contratos/{documento_id}"


def documento_pronto_para_gerar(db: Session, documento) -> None:
    """Confirmado pela venda — avisa o Jurídico que já pode gerar."""
    tipo = ROTULO_TIPO.get(documento.tipo, "Documento")
    titulo = f'Documento pronto para geração — "{tipo}" do projeto "{nome_do_projeto(documento)}".'
    for usuario in usuarios_com_permissao(db, "pode_editar_documento_juridico"):
        registrar(
            db,
            usuario_id=usuario.id,
            tipo="documento_contratual_pronto_para_gerar",
            titulo=titulo,
            projeto_id=documento.projeto_id,
            rota=_rota(documento.id),
            chave_dedup=f"documento_contratual:{documento.id}:pronto_para_gerar:{uuid4()}",
        )


def documento_aprovado_internamente(db: Session, documento) -> None:
    """Jurídico aprovou por dentro — avisa quem vai mandar ao cliente."""
    tipo = ROTULO_TIPO.get(documento.tipo, "Documento")
    titulo = f'Documento aprovado internamente — já pode mandar ao cliente: "{tipo}" do projeto "{nome_do_projeto(documento)}".'
    for usuario in _destinatarios_envio(db, documento):
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


def cliente_respondeu(db: Session, documento, aprovado: bool, motivo: str = None) -> None:
    """Cliente aprovou ou pediu alteração — avisa quem ia mandar + Jurídico."""
    tipo = ROTULO_TIPO.get(documento.tipo, "Documento")
    if aprovado:
        titulo = f'O cliente aprovou o documento "{tipo}" do projeto "{nome_do_projeto(documento)}".'
    else:
        titulo = f'O cliente pediu alteração no documento "{tipo}" do projeto "{nome_do_projeto(documento)}".'
        if motivo:
            titulo += f' Pedido: "{motivo}"'

    destinatarios = {u.id: u for u in _destinatarios_envio(db, documento)}
    for usuario in usuarios_com_permissao(db, "pode_editar_documento_juridico"):
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
