"""Rodadas do Health Track (`use_cases/health_track/rodadas.py`): a diretoria
abre, cada projeto em acompanhamento precisa ser avaliado ou justificado, e
só então a rodada conclui."""

from datetime import date, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.models  # noqa: F401
from src.database.database import Base
from src.models.health_track_acao_model import HealthTrackAcaoModel
from src.models.health_track_avaliacao_model import HealthTrackAvaliacaoModel
from src.models.health_track_pilar_model import HealthTrackPilarModel
from src.models.health_track_regra_model import HealthTrackRegraModel
from src.models.health_track_rodada_model import HealthTrackRodadaModel, HealthTrackRodadaProjetoModel
from src.models.notificacao_model import NotificacaoModel
from src.models.posicao_permissao_model import PosicaoPermissaoModel
from src.models.projeto_model import ProjetoModel
from src.models.usuario_model import UsuarioModel
from src.use_cases.health_track.registrar_avaliacao import (
    CorPilarRequest,
    RegistrarAvaliacaoRequest,
    RegistrarAvaliacaoUseCase,
)
from src.use_cases.health_track.rodadas import (
    AbrirRodadaUseCase,
    ConcluirRodadaUseCase,
    DesfazerJustificativaUseCase,
    GetRodadaAtualUseCase,
    JustificarProjetoUseCase,
    JustificarRequest,
)
from src.utils.exceptions import RegraDeNegocioError

DIRETORA = SimpleNamespace(id=1, posicao="diretor_projetos")


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=[
            UsuarioModel.__table__,
            ProjetoModel.__table__,
            HealthTrackPilarModel.__table__,
            HealthTrackAvaliacaoModel.__table__,
            HealthTrackRegraModel.__table__,
            HealthTrackRodadaModel.__table__,
            HealthTrackRodadaProjetoModel.__table__,
            HealthTrackAcaoModel.__table__,
            # Abrir a rodada avisa quem tem a caixa: precisa do catálogo de
            # permissões e da tabela do sino (vazios, ninguém é avisado).
            PosicaoPermissaoModel.__table__,
            NotificacaoModel.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    s.add(UsuarioModel(id=1, nome="Vidda", email_insper="v@insper.edu.br", senha_hash="x", posicao="diretor_projetos"))
    s.add(HealthTrackPilarModel(id=1, nome="Cliente", ordem=0, ativo=True))
    s.add(HealthTrackRegraModel(
        verde_max_amarelos=1, verde_max_vermelhos=0, vermelho_min_amarelos=3, vermelho_min_vermelhos=1,
        vigente_desde=datetime(2000, 1, 1),
    ))
    for pid, nome, status in [
        (10, "Em andamento", "em_andamento"),
        (11, "Pausado", "pausado"),
        (12, "Já na TEP", "envio_tep"),
        (13, "Só vendido", "vendido"),
    ]:
        s.add(ProjetoModel(id=pid, nome=nome, status=status, data_kickoff=date(2026, 9, 1)))
    s.commit()
    yield s
    s.close()


def avaliar(db, projeto_id):
    RegistrarAvaliacaoUseCase(db).execute(
        projeto_id, RegistrarAvaliacaoRequest(avaliacoes=[CorPilarRequest(pilar_id=1, cor="verde")]), DIRETORA
    )


def test_abrir_congela_so_quem_esta_em_acompanhamento(db):
    r = AbrirRodadaUseCase(db).execute(DIRETORA)
    assert {p["projeto_id"] for p in r["projetos"]} == {10, 11}
    assert r["pendente"] == 2 and r["total"] == 2
    assert GetRodadaAtualUseCase(db).execute()["id"] == r["id"]


def test_nao_abre_duas(db):
    AbrirRodadaUseCase(db).execute(DIRETORA)
    with pytest.raises(RegraDeNegocioError):
        AbrirRodadaUseCase(db).execute(DIRETORA)


def test_avaliar_marca_o_item_sozinho(db):
    r = AbrirRodadaUseCase(db).execute(DIRETORA)
    avaliar(db, 10)
    atual = GetRodadaAtualUseCase(db).execute()
    assert {p["projeto_id"]: p["situacao"] for p in atual["projetos"]} == {10: "avaliada", 11: "pendente"}
    assert atual["id"] == r["id"]


def test_avaliar_sem_rodada_aberta_e_livre(db):
    avaliar(db, 10)
    assert GetRodadaAtualUseCase(db).execute() is None


def test_concluir_exige_zero_pendentes(db):
    r = AbrirRodadaUseCase(db).execute(DIRETORA)
    avaliar(db, 10)
    with pytest.raises(RegraDeNegocioError, match="pendente"):
        ConcluirRodadaUseCase(db).execute(r["id"], DIRETORA)
    JustificarProjetoUseCase(db).execute(r["id"], 11, JustificarRequest(justificativa="Projeto pausado."), DIRETORA)
    fechada = ConcluirRodadaUseCase(db).execute(r["id"], DIRETORA)
    assert fechada["concluida_em"] is not None
    assert fechada["justificada"] == 1 and fechada["avaliada"] == 1
    assert GetRodadaAtualUseCase(db).execute() is None


def test_justificativa_pode_ser_desfeita_e_nao_cobre_projeto_avaliado(db):
    r = AbrirRodadaUseCase(db).execute(DIRETORA)
    JustificarProjetoUseCase(db).execute(r["id"], 11, JustificarRequest(justificativa="Parado."), DIRETORA)
    volta = DesfazerJustificativaUseCase(db).execute(r["id"], 11)
    assert {p["projeto_id"]: p["situacao"] for p in volta["projetos"]}[11] == "pendente"
    avaliar(db, 10)
    with pytest.raises(RegraDeNegocioError):
        JustificarProjetoUseCase(db).execute(r["id"], 10, JustificarRequest(justificativa="x" * 5), DIRETORA)


def test_avaliar_depois_de_justificar_vira_avaliada(db):
    r = AbrirRodadaUseCase(db).execute(DIRETORA)
    JustificarProjetoUseCase(db).execute(r["id"], 11, JustificarRequest(justificativa="Parado."), DIRETORA)
    avaliar(db, 11)
    item = {p["projeto_id"]: p for p in GetRodadaAtualUseCase(db).execute()["projetos"]}[11]
    assert item["situacao"] == "avaliada" and item["justificativa"] is None


def test_apagar_o_ciclo_devolve_o_projeto_a_pendente_na_rodada(db):
    from src.use_cases.health_track.apagar import ApagarCicloUseCase

    AbrirRodadaUseCase(db).execute(DIRETORA)
    avaliar(db, 10)
    atual = GetRodadaAtualUseCase(db).execute()
    assert {p["projeto_id"]: p["situacao"] for p in atual["projetos"]}[10] == "avaliada"
    ciclo = db.query(HealthTrackAvaliacaoModel).filter_by(projeto_id=10).first().avaliado_em
    assert ApagarCicloUseCase(db).execute(10, ciclo) == {"apagadas": 1}
    atual = GetRodadaAtualUseCase(db).execute()
    assert {p["projeto_id"]: p["situacao"] for p in atual["projetos"]}[10] == "pendente"


def test_zerar_apaga_avaliacoes_rodadas_e_acoes(db):
    from src.use_cases.health_track.apagar import ZerarHealthTrackUseCase

    AbrirRodadaUseCase(db).execute(DIRETORA)
    avaliar(db, 10)
    r = ZerarHealthTrackUseCase(db).execute()
    assert r["avaliacoes"] == 1 and r["rodadas"] == 1 and r["acoes"] == 0
    assert GetRodadaAtualUseCase(db).execute() is None
    assert db.query(HealthTrackAvaliacaoModel).count() == 0
