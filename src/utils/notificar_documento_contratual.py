"""As três notificações do workflow de documento jurídico (§ Contratos).

⭐ 2026-09-18 — porta de `contratos-backend/src/use_cases/notificacao/
notificacao_service.py`, sobre `registrar()` (o §6.6 do ATLAS) em vez de um
serviço de e-mail próprio — `registrar()` já cuida do e-mail (best-effort,
nunca derruba quem chamou) e do sino.

Três eventos, mesmos do sistema antigo:
  - confirmado pela venda, pronto pro Jurídico gerar -> quem tem `pode_editar_documento_juridico`
  - gerado/exportado, link liberado ao cliente        -> quem abriu o documento
  - cliente respondeu (aprovou ou pediu alteração)    -> quem abriu + Jurídico
"""

from uuid import uuid4

from sqlalchemy.orm import Session

from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.notificacao.registrar_notificacao import registrar
from src.utils.status_documento_contratual import ROTULO_TIPO
from src.utils.usuarios_com_permissao import usuarios_com_permissao


def _rota(projeto_id: int) -> str:
    return f"/projetos/{projeto_id}?aba=contratos"


def documento_pronto_para_gerar(db: Session, documento) -> None:
    """Confirmado pela venda — avisa o Jurídico que já pode gerar."""
    tipo = ROTULO_TIPO.get(documento.tipo, "Documento")
    titulo = f'Documento pronto para geração — "{tipo}" do projeto "{documento.projeto.nome}".'
    for usuario in usuarios_com_permissao(db, "pode_editar_documento_juridico"):
        registrar(
            db,
            usuario_id=usuario.id,
            tipo="documento_contratual_pronto_para_gerar",
            titulo=titulo,
            projeto_id=documento.projeto_id,
            rota=_rota(documento.projeto_id),
            chave_dedup=f"documento_contratual:{documento.id}:pronto_para_gerar:{uuid4()}",
        )


def documento_aprovado_internamente(db: Session, documento) -> None:
    """Jurídico aprovou por dentro — avisa quem abriu o documento que já
    pode preparar o envio ao cliente."""
    tipo = ROTULO_TIPO.get(documento.tipo, "Documento")
    titulo = f'Documento aprovado internamente — já pode mandar ao cliente: "{tipo}" do projeto "{documento.projeto.nome}".'
    for usuario in _usuario_criador(db, documento):
        registrar(
            db,
            usuario_id=usuario.id,
            tipo="documento_contratual_aprovado_internamente",
            titulo=titulo,
            projeto_id=documento.projeto_id,
            rota=_rota(documento.projeto_id),
            chave_dedup=f"documento_contratual:{documento.id}:aprovado_internamente:{uuid4()}",
        )


def documento_liberado_para_cliente(db: Session, documento) -> None:
    """Gerado/exportado — avisa quem abriu o documento que o link já está pronto."""
    tipo = ROTULO_TIPO.get(documento.tipo, "Documento")
    titulo = f'Documento pronto para enviar ao cliente — "{tipo}" do projeto "{documento.projeto.nome}".'
    for usuario in _usuario_criador(db, documento):
        registrar(
            db,
            usuario_id=usuario.id,
            tipo="documento_contratual_liberado",
            titulo=titulo,
            projeto_id=documento.projeto_id,
            rota=_rota(documento.projeto_id),
            chave_dedup=f"documento_contratual:{documento.id}:liberado:{uuid4()}",
        )


def cliente_respondeu(db: Session, documento, aprovado: bool, motivo: str = None) -> None:
    """Cliente aprovou ou pediu alteração — avisa quem abriu + Jurídico."""
    tipo = ROTULO_TIPO.get(documento.tipo, "Documento")
    if aprovado:
        titulo = f'O cliente aprovou o documento "{tipo}" do projeto "{documento.projeto.nome}".'
    else:
        titulo = f'O cliente pediu alteração no documento "{tipo}" do projeto "{documento.projeto.nome}".'
        if motivo:
            titulo += f' Pedido: "{motivo}"'

    destinatarios = {u.id: u for u in _usuario_criador(db, documento)}
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
            rota=_rota(documento.projeto_id),
            chave_dedup=f"documento_contratual:{documento.id}:{evento}:{uuid4()}",
        )


def _usuario_criador(db: Session, documento) -> list:
    criado_por = getattr(documento.projeto, "criado_por", None)
    if not criado_por:
        return []
    usuario = UsuarioRepository(db).get_by_id(criado_por)
    return [usuario] if usuario else []
