"""Notificações sobre o PROJETO em si — criado e vendido (§ Contratos,
2026-09-21). Fica fora de `notificar_documento_contratual.py` de propósito:
esses dois eventos são do `ProjetoModel`, não de um `documento_contratual`
(o projeto pode nascer/virar vendido sem alguém estar olhando pra um
documento específico na hora).

Dois eventos, os dois pedidos por ela:
  - projeto criado (nasce em "Contrato em elaboração") -> diretoria de projetos + gerentes + vendedor(es)
  - Contrato de Prestação assinado (projeto vira "Vendido") -> diretoria de projetos + gerentes
"""

from uuid import uuid4

from sqlalchemy.orm import Session

from src.repositories.projeto_vendedor_repository import ProjetoVendedorRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.notificacao.registrar_notificacao import registrar


def _rota(projeto_id: int) -> str:
    return f"/projetos/{projeto_id}"


def diretoria_e_gerentes(db: Session) -> dict:
    usuarios = UsuarioRepository(db)
    destinatarios = {u.id: u for u in usuarios.get_por_posicao("diretor_projetos")}
    destinatarios.update({u.id: u for u in usuarios.get_por_posicao("gerente")})
    return destinatarios


def projeto_criado(db: Session, projeto) -> None:
    """Nasceu em "Contrato em elaboração" — avisa diretoria, gerentes e
    quem vendeu (se já tiver vendedor definido na criação)."""
    titulo = f'Novo projeto em contrato: "{projeto.nome}".'
    destinatarios = diretoria_e_gerentes(db)
    vendedores = ProjetoVendedorRepository(db).get_by_projeto(projeto.id)
    usuarios = UsuarioRepository(db)
    for vendedor in vendedores:
        usuario = usuarios.get_by_id(vendedor.usuario_id)
        if usuario:
            destinatarios[usuario.id] = usuario

    for usuario in destinatarios.values():
        registrar(
            db,
            usuario_id=usuario.id,
            tipo="projeto_criado_em_contrato",
            titulo=titulo,
            projeto_id=projeto.id,
            rota=_rota(projeto.id),
            chave_dedup=f"projeto:{projeto.id}:criado:{uuid4()}",
        )


def projeto_vendido(db: Session, projeto) -> None:
    """Contrato de Prestação assinado, projeto virou "Vendido" — avisa
    diretoria e gerentes."""
    titulo = f'Contrato assinado — "{projeto.nome}" agora é Vendido.'
    for usuario in diretoria_e_gerentes(db).values():
        registrar(
            db,
            usuario_id=usuario.id,
            tipo="projeto_vendido",
            titulo=titulo,
            projeto_id=projeto.id,
            rota=_rota(projeto.id),
            chave_dedup=f"projeto:{projeto.id}:vendido:{uuid4()}",
        )
