"""§8, 2026-09-10 — tudo-ou-nada nos critérios ao SUBMETER a avaliação de banca.

Quem respondeu ALGUM critério tem que responder todos os do formulário ativo
pros escopos que a banca cobre. Zero critérios (comentário puro) continua
valendo. Existe porque o formulário é carregado uma vez no front e podia
ir incompleto se a diretoria editasse no meio.
"""

from types import SimpleNamespace

import pytest

import src.use_cases.avaliacao.submeter_avaliacao as mod
from src.use_cases.avaliacao.submeter_avaliacao import SubmeterAvaliacaoUseCase
from src.utils.exceptions import RegraDeNegocioError

BANCA = SimpleNamespace(id=1, escopo_id=5)


def _uc(monkeypatch, *, respondidas, obrigatorias_por_escopo):
    """`SubmeterAvaliacaoUseCase` com só o que `_exigir_criterios_completos`
    toca trocado por dublê. `obrigatorias_por_escopo`: {escopo_id|None: [ids]}.
    A banca cobre os escopos 5 e 17 (via `escopos_avaliados_ids` fake)."""
    uc = SubmeterAvaliacaoUseCase(db=None)

    uc.nota_repository = SimpleNamespace(
        get_by_avaliacao=lambda _id: [SimpleNamespace(pergunta_id=p) for p in respondidas]
    )
    uc.banca_escopo_repository = SimpleNamespace(get_escopo_ids=lambda _id: [11, 78])
    uc.projeto_escopo_repository = SimpleNamespace(get_by_ids=lambda _ids: [])

    perguntas = [
        {"id": pid, "tipo_resposta": "nota", "escopo_id": esc}
        for esc, ids in obrigatorias_por_escopo.items()
        for pid in ids
    ]
    monkeypatch.setattr(
        mod, "GetFormularioAtivoUseCase",
        lambda _db: SimpleNamespace(execute=lambda: {"perguntas": perguntas}),
    )
    monkeypatch.setattr(
        "src.use_cases.banca.get_banca.escopos_avaliados_ids",
        lambda *_a, **_k: [5, 17],
    )
    return uc


def test_comentario_puro_passa(monkeypatch):
    uc = _uc(monkeypatch, respondidas=[], obrigatorias_por_escopo={5: [1, 2], 17: [3, 4]})
    uc._exigir_criterios_completos(99, BANCA)  # não levanta


def test_respondeu_tudo_dos_escopos_da_banca_passa(monkeypatch):
    uc = _uc(
        monkeypatch,
        respondidas=[1, 2, 3, 4, 9],
        obrigatorias_por_escopo={5: [1, 2], 17: [3, 4], None: [9]},
    )
    uc._exigir_criterios_completos(99, BANCA)  # não levanta


def test_pulou_um_bloco_inteiro_e_barrado(monkeypatch):
    # respondeu escopo 5 + geral, pulou o 17 — o caso Enzo
    uc = _uc(
        monkeypatch,
        respondidas=[1, 2, 9],
        obrigatorias_por_escopo={5: [1, 2], 17: [3, 4], None: [9]},
    )
    with pytest.raises(RegraDeNegocioError, match="critérios que você não respondeu"):
        uc._exigir_criterios_completos(99, BANCA)


def test_criterio_de_escopo_que_a_banca_nao_cobre_nao_e_exigido(monkeypatch):
    # escopo 8 não está na banca (cobre 5 e 17) — não entra na conta
    uc = _uc(
        monkeypatch,
        respondidas=[1, 2, 3, 4],
        obrigatorias_por_escopo={5: [1, 2], 17: [3, 4], 8: [7, 8]},
    )
    uc._exigir_criterios_completos(99, BANCA)  # não levanta
