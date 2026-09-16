"""`RegistrarDescricaoCoordenadorUseCase` — o relato livre do coordenador
sobre a banca, depois de realizada.

⭐ 2026-09-16, corrigido: projeto pode ter mais de um coordenador
(2026-08-20), mas a checagem só olhava `banca.coordenador_id` (o primeiro) —
um segundo coordenador de verdade, tão dono do relato quanto o primeiro,
tomava "só o coordenador do projeto pode registrar esta descrição" do
próprio projeto dele.
"""

from datetime import datetime
from types import SimpleNamespace

import pytest

from src.use_cases.banca.registrar_descricao_coordenador import (
    RegistrarDescricaoCoordenadorRequest,
    RegistrarDescricaoCoordenadorUseCase,
)
from src.utils.exceptions import RegraDeNegocioError


def montar(*, realizado_em, coordenador_id=90, escopo_ids=(7,), membros_coordenadores=(90,)):
    banca = SimpleNamespace(id=1, coordenador_id=coordenador_id, realizado_em=realizado_em)

    class BancaRepo:
        def get_by_id(self, _):
            return banca

        def update(self, _id, **kwargs):
            for k, v in kwargs.items():
                setattr(banca, k, v)
            return banca

    uc = RegistrarDescricaoCoordenadorUseCase.__new__(RegistrarDescricaoCoordenadorUseCase)
    uc.db = None
    uc.repository = BancaRepo()
    uc.banca_escopo_repository = SimpleNamespace(get_escopo_ids=lambda _: list(escopo_ids))
    uc.escopo_repository = SimpleNamespace(
        get_by_id=lambda _: SimpleNamespace(projeto_id=52) if escopo_ids else None
    )
    uc.membro_repository = SimpleNamespace(
        get_by_projeto=lambda *a, **k: [
            SimpleNamespace(usuario_id=uid, papel="coordenador") for uid in membros_coordenadores
        ]
    )
    return uc


def test_o_primeiro_coordenador_registra(monkeypatch):
    uc = montar(realizado_em=datetime.now(), coordenador_id=90, membros_coordenadores=(90, 93))

    resultado = uc.execute(1, RegistrarDescricaoCoordenadorRequest(descricao="Foi bem."), usuario_id=90)

    assert resultado["descricao_coordenador"] == "Foi bem."


def test_segundo_coordenador_do_mesmo_projeto_tambem_registra():
    """A pessoa que a banca não conhece por `coordenador_id`, mas que é
    coordenadora do mesmo projeto (`projeto_membro`), pode registrar."""
    uc = montar(realizado_em=datetime.now(), coordenador_id=90, membros_coordenadores=(90, 93))

    resultado = uc.execute(1, RegistrarDescricaoCoordenadorRequest(descricao="Também foi bem."), usuario_id=93)

    assert resultado["descricao_coordenador"] == "Também foi bem."


def test_quem_nao_e_coordenador_do_projeto_e_recusado():
    uc = montar(realizado_em=datetime.now(), coordenador_id=90, membros_coordenadores=(90, 93))

    with pytest.raises(RegraDeNegocioError, match="Só o coordenador"):
        uc.execute(1, RegistrarDescricaoCoordenadorRequest(descricao="Não sou eu."), usuario_id=91)


def test_banca_ainda_nao_realizada_e_recusada():
    uc = montar(realizado_em=None, coordenador_id=90, membros_coordenadores=(90,))

    with pytest.raises(RegraDeNegocioError, match="realizada"):
        uc.execute(1, RegistrarDescricaoCoordenadorRequest(descricao="Cedo demais."), usuario_id=90)


def test_banca_legada_sem_escopo_cai_so_no_coordenador_id():
    """Sem escopo vinculado não há projeto pra consultar — só `banca.
    coordenador_id` mesmo, como sempre foi."""
    uc = montar(realizado_em=datetime.now(), coordenador_id=90, escopo_ids=())

    resultado = uc.execute(1, RegistrarDescricaoCoordenadorRequest(descricao="Ok."), usuario_id=90)

    assert resultado["descricao_coordenador"] == "Ok."
