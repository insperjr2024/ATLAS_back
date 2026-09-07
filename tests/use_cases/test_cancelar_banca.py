"""§8, 2026-09-04/05 — `CancelarBancaUseCase`: a única saída manual que resta.

Sem o botão "Registrar realização", `data_hora` passar sozinho já marca a
banca como realizada e dispara as duas avaliações (ver
`finalizacao_automatica.py`). Cancelar tira uma banca desse trilho — e desde
2026-09-05 também dá pra cancelar DEPOIS de `realizado_em` (o imprevisto de
última hora), desfazendo o lote de desempenho que a automação abriu sozinha.
"""

from datetime import datetime
from types import SimpleNamespace

import pytest

from src.use_cases.banca.marcar_banca_escopo import CancelarBancaUseCase


class FakeBancaRepository:
    def __init__(self, db):
        pass

    def get_by_id(self, banca_id):
        return BANCAS.get(banca_id)

    def update(self, banca_id, **campos):
        banca = BANCAS[banca_id]
        for k, v in campos.items():
            setattr(banca, k, v)
        return banca


BANCAS = {}


@pytest.fixture(autouse=True)
def _bancas(monkeypatch):
    BANCAS.clear()
    monkeypatch.setattr(
        "src.use_cases.banca.marcar_banca_escopo.BancaRepository", FakeBancaRepository
    )
    yield BANCAS


def _banca(id=1, realizado_em=None, cancelada_em=None):
    b = SimpleNamespace(id=id, data_hora=datetime(2026, 9, 20, 14, 0),
                         realizado_em=realizado_em, cancelada_em=cancelada_em)
    BANCAS[id] = b
    return b


def test_cancela_uma_banca_ainda_nao_realizada(_bancas):
    _banca()

    resultado = CancelarBancaUseCase(db=None).execute(1)

    assert resultado["id"] == 1
    assert BANCAS[1].cancelada_em is not None


def test_banca_inexistente_devolve_none(_bancas):
    assert CancelarBancaUseCase(db=None).execute(999) is None


def test_cancelar_de_novo_e_idempotente(_bancas):
    """Clicar duas vezes (duplo-clique, aba duplicada) não deve estourar nem
    trocar o horário do cancelamento."""
    primeiro_cancelamento = datetime(2026, 9, 18, 9, 0)
    _banca(cancelada_em=primeiro_cancelamento)

    resultado = CancelarBancaUseCase(db=None).execute(1)

    assert resultado["cancelada_em"] == primeiro_cancelamento


class TestCancelamentoTardio:
    """⭐ 2026-09-05, a pedido: "deu merda em cima da hora" — a banca já foi
    marcada realizada pelo relógio, mas na prática não rolou."""

    def _fake_sem_lote(self, monkeypatch):
        class LoteRepoSemLote:
            def __init__(self, db):
                pass

            def get_by_banca_id(self, banca_id):
                return None

        monkeypatch.setattr(
            "src.repositories.desempenho_lote_repository.DesempenhoLoteRepository",
            LoteRepoSemLote,
        )

    def test_reverte_realizado_em(self, _bancas, monkeypatch):
        self._fake_sem_lote(monkeypatch)
        _banca(realizado_em=datetime(2026, 9, 20, 14, 0))

        resultado = CancelarBancaUseCase(db=None).execute(1)

        assert resultado["id"] == 1
        assert BANCAS[1].realizado_em is None
        assert BANCAS[1].cancelada_em is not None

    def test_sem_lote_associado_nao_quebra(self, _bancas, monkeypatch):
        """Banca legada, sem escopo vinculado — a finalização automática
        nunca abriu lote nenhum pra ela. Cancelar tardio continua
        funcionando, só não tem o que desfazer."""
        self._fake_sem_lote(monkeypatch)
        _banca(realizado_em=datetime(2026, 9, 20, 14, 0))

        resultado = CancelarBancaUseCase(db=None).execute(1)

        assert resultado["cancelada_em"] is not None

    def _fake_com_lote(self, monkeypatch, *, ja_respondido, estado):
        lote = SimpleNamespace(id=42, nome="Finalização - Projeto X - Escopo Y")

        class LoteRepo:
            def __init__(self, db):
                pass

            def get_by_banca_id(self, banca_id):
                return lote

            def update(self, lote_id, **campos):
                estado["fechado_com"] = campos
                return lote

            def delete(self, lote_id):
                estado["apagado"] = True
                return True

        class LoteProjetoRepo:
            def __init__(self, db):
                pass

            def delete_by_lote(self, lote_id):
                estado["vinculos_apagados"] = True

        class AvaliacaoRepo:
            def __init__(self, db):
                pass

            def get_by_lote(self, lote_id):
                return [SimpleNamespace(id=1)] if ja_respondido else []

        class PendenciasFake:
            def __init__(self, db):
                pass

            def execute(self, lote_id):
                return [
                    {"avaliador_id": 10, "respondida": ja_respondido},
                    {"avaliador_id": 11, "respondida": False},
                ]

        def notificar_fake(db, lote_arg, avaliador_ids):
            estado["notificados"] = set(avaliador_ids)

        monkeypatch.setattr(
            "src.repositories.desempenho_lote_repository.DesempenhoLoteRepository", LoteRepo
        )
        monkeypatch.setattr(
            "src.repositories.desempenho_lote_projeto_repository.DesempenhoLoteProjetoRepository",
            LoteProjetoRepo,
        )
        monkeypatch.setattr(
            "src.repositories.desempenho_avaliacao_repository.DesempenhoAvaliacaoRepository",
            AvaliacaoRepo,
        )
        monkeypatch.setattr(
            "src.use_cases.desempenho_lote.get_pendencias.GetPendenciasLoteUseCase",
            PendenciasFake,
        )
        monkeypatch.setattr(
            "src.use_cases.notificacao.eventos.notificar_lote_desempenho_cancelado",
            notificar_fake,
        )
        return lote

    def test_lote_sem_ninguem_ter_respondido_e_apagado(self, _bancas, monkeypatch):
        estado = {}
        self._fake_com_lote(monkeypatch, ja_respondido=False, estado=estado)
        _banca(realizado_em=datetime(2026, 9, 20, 14, 0))

        CancelarBancaUseCase(db=None).execute(1)

        assert estado.get("apagado") is True
        assert estado.get("vinculos_apagados") is True
        assert "fechado_com" not in estado

    def test_lote_com_alguem_ja_respondido_e_fechado_nao_apagado(self, _bancas, monkeypatch):
        """Não some trabalho de verdade — fecha pra não cobrar mais quem
        faltava, mas quem já respondeu continua registrado."""
        estado = {}
        self._fake_com_lote(monkeypatch, ja_respondido=True, estado=estado)
        _banca(realizado_em=datetime(2026, 9, 20, 14, 0))

        CancelarBancaUseCase(db=None).execute(1)

        assert estado.get("fechado_com") == {"override_manual": "fechado"}
        assert "apagado" not in estado

    def test_avisa_todo_mundo_que_tinha_pendencia_no_lote(self, _bancas, monkeypatch):
        estado = {}
        self._fake_com_lote(monkeypatch, ja_respondido=False, estado=estado)
        _banca(realizado_em=datetime(2026, 9, 20, 14, 0))

        CancelarBancaUseCase(db=None).execute(1)

        assert estado["notificados"] == {10, 11}

    def test_cancelamento_normal_nao_toca_lote_nenhum(self, _bancas, monkeypatch):
        """Cancelar ANTES de realizada não tem o que desfazer — não deveria
        nem tentar procurar um lote."""
        chamou = {"buscou": False}

        class LoteRepoQueNaoDeveriaSerChamado:
            def __init__(self, db):
                pass

            def get_by_banca_id(self, banca_id):
                chamou["buscou"] = True
                return None

        monkeypatch.setattr(
            "src.repositories.desempenho_lote_repository.DesempenhoLoteRepository",
            LoteRepoQueNaoDeveriaSerChamado,
        )
        _banca()  # sem realizado_em

        CancelarBancaUseCase(db=None).execute(1)

        assert chamou["buscou"] is False
