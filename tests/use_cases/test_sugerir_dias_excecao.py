"""Sugerir dias de exceção a partir do calendário acadêmico (§ Contratos,
2026-09-21).

Mesmo idioma dos vizinhos: dublês à mão, com as classes de repositório
trocadas no MÓDULO do use case.
"""

from datetime import date
from types import SimpleNamespace

import pytest

import src.use_cases.documento_contratual.sugerir_dias_excecao as mod
from src.use_cases.documento_contratual.sugerir_dias_excecao import SugerirDiasExcecaoUseCase
from src.utils.exceptions import RegraDeNegocioError


def dia(data_str, tipo, frente_id=None):
    return SimpleNamespace(data=date.fromisoformat(data_str), tipo=tipo, frente_id=frente_id)


def montar(monkeypatch, dias, frente_ids=()):
    class DiasFake:
        def __init__(self, db): pass
        def get_por_intervalo(self, inicio, fim):
            return dias

    class FrentesFake:
        def __init__(self, db): pass
        def get_by_projeto(self, projeto_id):
            return [SimpleNamespace(frente_id=fid) for fid in frente_ids]

    monkeypatch.setattr(mod, "DiaNaoLetivoRepository", DiasFake)
    monkeypatch.setattr(mod, "ProjetoFrenteRepository", FrentesFake)
    return SugerirDiasExcecaoUseCase(db=None)


class TestSugerirDiasExcecao:
    def test_so_devolve_dias_tipo_prova(self, monkeypatch):
        dias = [
            dia("2026-09-10", "prova", frente_id=5),
            dia("2026-09-11", "feriado", frente_id=None),
            dia("2026-09-12", "recesso", frente_id=None),
        ]
        uc = montar(monkeypatch, dias, frente_ids=(5,))

        resultado = uc.execute(1, date(2026, 9, 1), date(2026, 9, 30))

        assert resultado == [{"inicio": "2026-09-10", "fim": "2026-09-10"}]

    def test_prova_de_outra_frente_nao_entra(self, monkeypatch):
        dias = [dia("2026-09-10", "prova", frente_id=99)]
        uc = montar(monkeypatch, dias, frente_ids=(5,))

        assert uc.execute(1, date(2026, 9, 1), date(2026, 9, 30)) == []

    def test_prova_global_sem_frente_entra_pra_qualquer_projeto(self, monkeypatch):
        dias = [dia("2026-09-10", "prova", frente_id=None)]
        uc = montar(monkeypatch, dias, frente_ids=(5,))

        assert uc.execute(1, date(2026, 9, 1), date(2026, 9, 30)) == [
            {"inicio": "2026-09-10", "fim": "2026-09-10"}
        ]

    def test_fim_antes_do_inicio_e_erro(self, monkeypatch):
        uc = montar(monkeypatch, [])

        with pytest.raises(RegraDeNegocioError):
            uc.execute(1, date(2026, 9, 30), date(2026, 9, 1))
