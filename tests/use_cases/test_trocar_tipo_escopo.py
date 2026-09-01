"""Trocar o TIPO de um escopo já vendido: qual item do catálogo ele é, ou
"Outro" com nome digitado.

A invariante é a mesma do cadastro (`validar_escopo_vendido`): exatamente um
dos dois, `escopo_id` ou `nome_customizado`, preenchido. A diferença é que
aqui os dois campos já têm um valor ANTERIOR, e mandar só um dos dois não pode
deixar o outro divergindo dele.
"""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.database import Base
from src.models.escopo_model import EscopoModel
from src.models.frente_model import FrenteModel
from src.models.projeto_escopo_model import ProjetoEscopoModel
from src.models.projeto_model import ProjetoModel
from src.use_cases.projeto_escopo.update_escopo_projeto import (
    UpdateEscopoProjetoRequest,
    UpdateEscopoProjetoUseCase,
)
from src.utils.exceptions import RegraDeNegocioError

TABELAS = [
    FrenteModel.__table__,
    ProjetoModel.__table__,
    ProjetoEscopoModel.__table__,
    EscopoModel.__table__,
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
    tech = FrenteModel(nome="Tech", piso_banca=2)
    db.add(tech)
    db.flush()

    pesquisa = EscopoModel(nome="Pesquisa de mercado", frente_id=tech.id)
    marketing = EscopoModel(nome="Plano de marketing", frente_id=tech.id)
    db.add_all([pesquisa, marketing])
    db.flush()

    projeto = ProjetoModel(
        nome="Projeto Alfa", cliente="Cliente", criado_por=1, status="em_andamento", dias_ambientacao=5
    )
    db.add(projeto)
    db.flush()

    escopo_outro = ProjetoEscopoModel(
        projeto_id=projeto.id, frente_id=tech.id, nome_customizado="Consultoria pontual", dias_uteis_vendidos=20,
    )
    escopo_catalogo = ProjetoEscopoModel(
        projeto_id=projeto.id, frente_id=tech.id, escopo_id=pesquisa.id, dias_uteis_vendidos=25,
    )
    db.add_all([escopo_outro, escopo_catalogo])
    db.commit()

    return {
        "pesquisa": pesquisa.id,
        "marketing": marketing.id,
        "escopo_outro": escopo_outro.id,
        "escopo_catalogo": escopo_catalogo.id,
    }


def escopo(db, escopo_id):
    return db.query(ProjetoEscopoModel).filter(ProjetoEscopoModel.id == escopo_id).first()


class TestTrocarDeOutroParaCatalogo:
    def test_troca_e_limpa_o_nome_customizado(self, db, base):
        UpdateEscopoProjetoUseCase(db).execute(
            base["escopo_outro"], UpdateEscopoProjetoRequest(escopo_id=base["marketing"])
        )
        atual = escopo(db, base["escopo_outro"])
        assert atual.escopo_id == base["marketing"]
        assert atual.nome_customizado is None

    def test_escopo_id_que_nao_existe_no_catalogo_e_recusado(self, db, base):
        with pytest.raises(RegraDeNegocioError, match="não encontrado no catálogo"):
            UpdateEscopoProjetoUseCase(db).execute(
                base["escopo_outro"], UpdateEscopoProjetoRequest(escopo_id=999)
            )


class TestTrocarDeCatalogoParaOutro:
    def test_troca_e_limpa_o_escopo_id(self, db, base):
        UpdateEscopoProjetoUseCase(db).execute(
            base["escopo_catalogo"],
            UpdateEscopoProjetoRequest(escopo_id=None, nome_customizado="Mentoria avulsa"),
        )
        atual = escopo(db, base["escopo_catalogo"])
        assert atual.escopo_id is None
        assert atual.nome_customizado == "Mentoria avulsa"

    def test_so_mandar_escopo_id_nulo_sem_nome_e_recusado(self, db, base):
        """Tirar do catálogo sem dizer o nome deixaria os dois vazios."""
        with pytest.raises(RegraDeNegocioError, match="Escolha um escopo do catálogo"):
            UpdateEscopoProjetoUseCase(db).execute(
                base["escopo_catalogo"], UpdateEscopoProjetoRequest(escopo_id=None)
            )


class TestTrocarDentroDoCatalogo:
    def test_de_um_item_do_catalogo_para_outro(self, db, base):
        UpdateEscopoProjetoUseCase(db).execute(
            base["escopo_catalogo"], UpdateEscopoProjetoRequest(escopo_id=base["marketing"])
        )
        atual = escopo(db, base["escopo_catalogo"])
        assert atual.escopo_id == base["marketing"]
        assert atual.nome_customizado is None


class TestMandarOsDois:
    def test_escopo_id_e_nome_customizado_juntos_e_recusado(self, db, base):
        with pytest.raises(RegraDeNegocioError, match="não os dois"):
            UpdateEscopoProjetoUseCase(db).execute(
                base["escopo_outro"],
                UpdateEscopoProjetoRequest(escopo_id=base["marketing"], nome_customizado="Nome novo"),
            )


class TestNaoMexerNoTipo:
    def test_editar_so_os_dias_nao_mexe_no_tipo(self, db, base):
        """`exclude_unset`: corrigir só os dias vendidos não pode apagar o
        tipo do escopo, nem o do catálogo nem o "Outro"."""
        UpdateEscopoProjetoUseCase(db).execute(
            base["escopo_outro"], UpdateEscopoProjetoRequest(dias_uteis_vendidos=30)
        )
        atual = escopo(db, base["escopo_outro"])
        assert atual.nome_customizado == "Consultoria pontual"
        assert atual.dias_uteis_vendidos == 30
