"""Ações do Health Track (§15): problema, responsável, próxima ação, prazo."""

from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.database.database import Base
from src.models.health_track_acao_model import HealthTrackAcaoModel
from src.models.health_track_pilar_model import HealthTrackPilarModel
from src.models.projeto_model import ProjetoModel
from src.models.usuario_model import UsuarioModel
from src.use_cases.health_track.acoes import (
    AcaoRequest,
    ApagarAcaoUseCase,
    ConcluirAcaoUseCase,
    CriarAcaoUseCase,
    EditarAcaoUseCase,
    ListAcoesAbertasUseCase,
    ListAcoesDoProjetoUseCase,
)
from src.utils.exceptions import RegraDeNegocioError

EU = SimpleNamespace(id=1, posicao="diretor_projetos")


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=[UsuarioModel.__table__, ProjetoModel.__table__, HealthTrackPilarModel.__table__, HealthTrackAcaoModel.__table__],
    )
    s = sessionmaker(bind=engine)()
    s.add(UsuarioModel(id=1, nome="Vidda", email_insper="v@insper.edu.br", senha_hash="x", posicao="diretor_projetos"))
    s.add(UsuarioModel(id=2, nome="Coord", email_insper="c@insper.edu.br", senha_hash="x", posicao="coordenador"))
    s.add(HealthTrackPilarModel(id=1, nome="Cronograma", ordem=0, ativo=True))
    s.add(ProjetoModel(id=10, nome="Atlas", status="em_andamento", data_kickoff=date(2026, 9, 1)))
    s.commit()
    yield s
    s.close()


def pedido(**extra):
    base = dict(problema="Cronograma atrasado", proxima_acao="Replanejar entregas", responsavel_id=2, prazo=date(2026, 10, 20), pilar_id=1)
    base.update(extra)
    return AcaoRequest(**base)


def test_cria_e_lista_com_nomes(db):
    acao = CriarAcaoUseCase(db).execute(10, pedido(), EU)
    assert acao["responsavel_nome"] == "Coord" and acao["pilar_nome"] == "Cronograma" and acao["projeto_nome"] == "Atlas"
    assert acao["criado_por_nome"] == "Vidda" and acao["concluida_em"] is None
    assert [a["id"] for a in ListAcoesAbertasUseCase(db).execute()] == [acao["id"]]


def test_atrasada_quando_o_prazo_passou(db):
    acao = CriarAcaoUseCase(db).execute(10, pedido(prazo=date(2020, 1, 1)), EU)
    assert acao["atrasada"] is True
    concluida = ConcluirAcaoUseCase(db).execute(10, acao["id"], True, EU)
    assert concluida["atrasada"] is False and concluida["concluida_por_nome"] == "Vidda"
    assert ListAcoesAbertasUseCase(db).execute() == []
    assert len(ListAcoesDoProjetoUseCase(db).execute(10)) == 1


def test_responsavel_e_pilar_precisam_existir(db):
    with pytest.raises(RegraDeNegocioError):
        CriarAcaoUseCase(db).execute(10, pedido(responsavel_id=99), EU)
    with pytest.raises(RegraDeNegocioError):
        CriarAcaoUseCase(db).execute(10, pedido(pilar_id=99), EU)


def test_editar_e_apagar_so_dentro_do_projeto(db):
    acao = CriarAcaoUseCase(db).execute(10, pedido(), EU)
    editada = EditarAcaoUseCase(db).execute(10, acao["id"], pedido(proxima_acao="Falar com o cliente", prazo=None))
    assert editada["proxima_acao"] == "Falar com o cliente" and editada["prazo"] is None
    with pytest.raises(RegraDeNegocioError):
        ApagarAcaoUseCase(db).execute(11, acao["id"])
    ApagarAcaoUseCase(db).execute(10, acao["id"])
    assert ListAcoesDoProjetoUseCase(db).execute(10) == []
