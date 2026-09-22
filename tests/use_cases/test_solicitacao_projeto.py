"""Vagas em Projetos — o que passou a valer com `vagas_abertas` (⭐
2026-09-22, a pedido).

Antes, "ter vaga" era 100% calculado (`max_consultores - alocados`) e
`listar_vagas` devolvia TODOS os projetos abertos, mesmo sem frente em
comum, com o motivo de impedimento em vez de esconder. Agora um projeto só
aparece com `vagas_abertas=True` (interruptor explícito), e quem PEDE
(consultor) só vê/pede em projeto com frente em comum com a dele.

Sessão de integração com SQLite em memória (mesmo padrão de
`test_trocar_tipo_escopo.py`): as regras testadas aqui atravessam
`self.db.query(...)` direto (`_frente_ids_por_projeto` etc.), difícil de
dublar sem um banco de verdade por trás.
"""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.database import Base
from src.models.frente_model import FrenteModel
from src.models.posicao_permissao_model import PosicaoPermissaoModel
from src.models.projeto_frente_model import ProjetoFrenteModel
from src.models.projeto_membro_model import ProjetoMembroModel
from src.models.projeto_model import ProjetoModel
from src.models.situacao_carga_model import SituacaoCargaModel
from src.models.solicitacao_projeto_model import SolicitacaoProjetoModel
from src.models.usuario_frente_model import UsuarioFrenteModel
from src.models.usuario_model import UsuarioModel
from src.use_cases.solicitacao_projeto.solicitacao_projeto import (
    CriarSolicitacaoRequest,
    SolicitacaoProjetoUseCase,
)
from src.utils.exceptions import RegraDeNegocioError

TABELAS = [
    PosicaoPermissaoModel.__table__,
    UsuarioModel.__table__,
    FrenteModel.__table__,
    ProjetoModel.__table__,
    ProjetoFrenteModel.__table__,
    ProjetoMembroModel.__table__,
    UsuarioFrenteModel.__table__,
    SolicitacaoProjetoModel.__table__,
    SituacaoCargaModel.__table__,
]


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=TABELAS)
    sessao = sessionmaker(bind=engine)()
    try:
        yield sessao
    finally:
        sessao.close()


@pytest.fixture
def base(db):
    """Duas frentes (Business, Tech), dois projetos de Business (um com
    vagas abertas, outro fechado) e um consultor de cada frente."""
    db.add(PosicaoPermissaoModel(posicao="consultor", nome="Consultor(a)"))
    db.flush()

    business = FrenteModel(nome="Business")
    tech = FrenteModel(nome="Tech")
    db.add_all([business, tech])
    db.flush()

    aberto = ProjetoModel(
        nome="Projeto Aberto", criado_por=1, status="em_andamento",
        dias_ambientacao=5, max_consultores=3, vagas_abertas=True,
    )
    fechado = ProjetoModel(
        nome="Projeto Fechado", criado_por=1, status="em_andamento",
        dias_ambientacao=5, max_consultores=3, vagas_abertas=False,
    )
    db.add_all([aberto, fechado])
    db.flush()

    db.add_all([
        ProjetoFrenteModel(projeto_id=aberto.id, frente_id=business.id),
        ProjetoFrenteModel(projeto_id=fechado.id, frente_id=business.id),
    ])

    consultor_business = UsuarioModel(
        nome="Consultora Business", email_insper="business@al.insper.edu.br",
        senha_hash="x", posicao="consultor",
    )
    consultor_tech = UsuarioModel(
        nome="Consultor Tech", email_insper="tech@al.insper.edu.br",
        senha_hash="x", posicao="consultor",
    )
    db.add_all([consultor_business, consultor_tech])
    db.flush()

    db.add_all([
        UsuarioFrenteModel(usuario_id=consultor_business.id, frente_id=business.id),
        UsuarioFrenteModel(usuario_id=consultor_tech.id, frente_id=tech.id),
    ])
    db.commit()

    return {
        "business": business, "tech": tech,
        "aberto": aberto, "fechado": fechado,
        "consultor_business": consultor_business, "consultor_tech": consultor_tech,
    }


def uc(db):
    return SolicitacaoProjetoUseCase(db)


class TestListarVagas:
    def test_consultor_ve_so_projeto_aberto_da_propria_frente(self, db, base):
        resultado = uc(db).listar_vagas(base["consultor_business"])

        ids = {p["id"] for p in resultado["projetos"]}
        assert ids == {base["aberto"].id}

    def test_consultor_de_outra_frente_nao_ve_nenhum(self, db, base):
        resultado = uc(db).listar_vagas(base["consultor_tech"])

        assert resultado["projetos"] == []

    def test_projeto_fechado_nao_aparece_mesmo_pra_quem_e_da_frente(self, db, base):
        resultado = uc(db).listar_vagas(base["consultor_business"])

        ids = {p["id"] for p in resultado["projetos"]}
        assert base["fechado"].id not in ids


class TestCriar:
    def test_recusa_projeto_com_vagas_fechadas(self, db, base):
        with pytest.raises(RegraDeNegocioError, match="não está aceitando gente nova"):
            uc(db).criar(
                base["consultor_business"].id,
                CriarSolicitacaoRequest(projeto_id=base["fechado"].id, justificativa="Quero entrar"),
            )

    def test_recusa_quem_nao_e_de_nenhuma_frente_do_projeto(self, db, base):
        with pytest.raises(RegraDeNegocioError, match="nenhuma frente"):
            uc(db).criar(
                base["consultor_tech"].id,
                CriarSolicitacaoRequest(projeto_id=base["aberto"].id, justificativa="Quero entrar"),
            )

    def test_aceita_consultor_da_frente_em_projeto_aberto(self, db, base):
        resultado = uc(db).criar(
            base["consultor_business"].id,
            CriarSolicitacaoRequest(projeto_id=base["aberto"].id, justificativa="Quero entrar"),
        )

        assert resultado["status"] == "pendente"
        salva = db.query(SolicitacaoProjetoModel).filter_by(id=resultado["id"]).one()
        assert salva.usuario_id == base["consultor_business"].id
        assert salva.projeto_id == base["aberto"].id
