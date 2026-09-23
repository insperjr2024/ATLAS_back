"""Notificações sobre o PROJETO em si — criado e vendido (§ Contratos,
2026-09-21). Fica fora de `notificar_documento_contratual.py` de propósito:
esses dois eventos são do `ProjetoModel`, não de um `documento_contratual`
(o projeto pode nascer/virar vendido sem alguém estar olhando pra um
documento específico na hora).

Três eventos, os três pedidos por ela:
  - projeto criado (nasce em "Contrato em elaboração") -> diretoria de projetos + gerentes + vendedor(es)
  - Contrato de Prestação assinado (projeto vira "Vendido") -> diretoria de projetos + gerentes
  - o mesmo momento também abre a declaração de interesse (⭐ 2026-09-22) -> só os CONSULTORES
    ativos das frentes do projeto (não quem já recebe o aviso de "vendido" acima)
"""

from uuid import uuid4

from sqlalchemy.orm import Session

from src.repositories.projeto_frente_repository import ProjetoFrenteRepository
from src.repositories.projeto_vendedor_repository import ProjetoVendedorRepository
from src.repositories.usuario_frente_repository import UsuarioFrenteRepository
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
    """Nasceu em "Contrato em elaboração" — avisa diretoria e quem vendeu (se
    já tiver vendedor definido na criação).

    ⭐ 2026-09-23 — a pedido: gerente saiu daqui — não precisa saber toda vez
    que UM projeto qualquer entra em elaboração, só quando de fato vira
    "Vendido" (`projeto_vendido`, que já é só diretoria e gerentes)."""
    titulo = f'Novo projeto em contrato: "{projeto.nome}".'
    destinatarios = {u.id: u for u in UsuarioRepository(db).get_por_posicao("diretor_projetos")}
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


def vagas_abertas(db: Session, projeto) -> None:
    """⭐ 2026-09-22 — a pedido: o mesmo momento em que o Contrato de PS é
    assinado abre a declaração de interesse do projeto — avisa só os
    CONSULTORES ativos das frentes dele (não diretoria/gerentes, que já
    recebem `projeto_vendido`; não coordenador/gerente/diretor mesmo que
    sejam da frente, só quem de fato pede pra entrar)."""
    titulo = f'Novo projeto vendido "{projeto.nome}" — declaração de interesse aberta no ATLAS.'
    frente_ids = [f.frente_id for f in ProjetoFrenteRepository(db).get_by_projeto(projeto.id)]
    usuarios_repo = UsuarioRepository(db)
    usuario_frente_repo = UsuarioFrenteRepository(db)
    destinatarios = {}
    for frente_id in frente_ids:
        for vinculo in usuario_frente_repo.get_by_frente(frente_id):
            usuario = usuarios_repo.get_by_id(vinculo.usuario_id)
            if usuario and usuario.status == "ativo" and usuario.ativo and usuario.posicao == "consultor":
                destinatarios[usuario.id] = usuario

    for usuario in destinatarios.values():
        registrar(
            db,
            usuario_id=usuario.id,
            tipo="vagas_abertas",
            titulo=titulo,
            projeto_id=projeto.id,
            rota="/vagas",
            chave_dedup=f"projeto:{projeto.id}:vagas_abertas:{uuid4()}",
        )
