"""§8 — as últimas vagas ficam RESERVADAS pro piso por frente (2026-09-04).

Se falta 1 liderança de Business e sobra 1 vaga, só quem cobre essa cota entra;
quem não cobre é recusado, porque ocuparia a vaga que a composição precisa.

O déficit em si — quem é liderança, de que frente, o coordenador de vendas que
não conta — tem cobertura própria em `tests/utils/test_composicao_banca.py`.
Aqui o que se testa é a ARITMÉTICA da reserva: quanto falta de piso vs. quantas
vagas sobram depois da pessoa entrar.

Mesmo padrão dos vizinhos: `__new__` + repositórios fake, sem sessão de banco.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from src.use_cases.candidatura import create_candidatura as mod
from src.use_cases.candidatura.create_candidatura import (
    CreateCandidaturaRequest,
    CreateCandidaturaUseCase,
)
from src.utils.exceptions import RegraDeNegocioError

BUSINESS = 1
#: Quem, ao entrar, zera o déficit de liderança (ver `deficit_por_ids`).
LIDER_DE_BUSINESS = 99


def montar(monkeypatch, *, alocados, vagas, deficit_por_ids):
    """`deficit_por_ids(ids) -> [DeficitFrente-like]` é o gancho que deixa
    cada teste dizer 'a pessoa X cobre a cota, a Y não' sem montar posição e
    vínculo de frente de mentira."""
    monkeypatch.setattr(mod, "calcular_vagas_banca", lambda *a, **k: vagas)
    monkeypatch.setattr(
        "src.use_cases.configuracao.composicao_banca.ResolverComposicaoUseCase.para",
        lambda self, ids: [SimpleNamespace(frente_id=BUSINESS, frente_nome="Business")],
    )
    monkeypatch.setattr(
        "src.utils.composicao_banca.ComposicaoBancaChecker.verificar",
        lambda self, banca, regras, ids: SimpleNamespace(deficits=deficit_por_ids(ids)),
    )

    class FakeCandidaturaRepo:
        def __init__(self):
            self.criadas = []

        def get_by_banca(self, _):
            return [SimpleNamespace(usuario_id=uid) for uid in alocados]

        def create(self, **kw):
            self.criadas.append(kw["usuario_id"])
            return SimpleNamespace(id=1, **kw)

    banca = SimpleNamespace(
        id=1,
        nome_projeto="FRUTAS I",
        data_hora=datetime.now() + timedelta(days=3),
        realizado_em=None,
        coordenador_id=None,
    )
    uc = CreateCandidaturaUseCase.__new__(CreateCandidaturaUseCase)
    uc.db = None
    repo = FakeCandidaturaRepo()
    uc.repository = repo
    uc.banca_repository = SimpleNamespace(get_by_id=lambda _: banca)
    uc.banca_frente_repository = SimpleNamespace(
        get_by_banca=lambda _: [SimpleNamespace(frente_id=BUSINESS)]
    )
    uc.frente_repository = SimpleNamespace(
        get_by_id=lambda fid: SimpleNamespace(id=fid, nome="Business", ativa=True)
    )
    uc.banca_escopo_repository = SimpleNamespace(get_escopo_ids=lambda _: [])
    uc.escopo_repository = SimpleNamespace(get_by_id=lambda _: None)
    uc.membro_repository = SimpleNamespace(get_by_projeto=lambda *a, **k: [])
    uc.equipe_projeto_repository = SimpleNamespace(get_by_banca=lambda _: [])
    return uc, repo


def deficit(lideranca=0, membros=0):
    return SimpleNamespace(
        frente_id=BUSINESS,
        frente_nome="Business",
        lideranca_faltando=lideranca,
        piso_faltando=membros,
    )


def alocar(uc, uid):
    return uc.execute(CreateCandidaturaRequest(banca_id=1), usuario_id=uid)


class TestVagaReservada:
    def test_ultima_vaga_recusa_quem_nao_cobre_a_cota(self, monkeypatch):
        """7/8: 1 vaga, e falta 1 liderança de Business que a pessoa 50 não
        cobre — a inscrição dela tornaria a composição impossível."""
        uc, _ = montar(
            monkeypatch,
            alocados=range(10, 17),
            vagas=8,
            deficit_por_ids=lambda ids: [deficit(lideranca=1)],
        )
        with pytest.raises(RegraDeNegocioError, match="reservada"):
            alocar(uc, 50)

    def test_quem_cobre_a_cota_entra_na_ultima_vaga(self, monkeypatch):
        uc, repo = montar(
            monkeypatch,
            alocados=range(10, 17),
            vagas=8,
            deficit_por_ids=lambda ids: (
                [] if LIDER_DE_BUSINESS in ids else [deficit(lideranca=1)]
            ),
        )
        alocar(uc, LIDER_DE_BUSINESS)
        assert repo.criadas == [LIDER_DE_BUSINESS]

    def test_com_folga_de_vaga_qualquer_um_entra(self, monkeypatch):
        """3/8: sobram 5 vagas pra 1 de déficit — há folga, ninguém é barrado."""
        uc, repo = montar(
            monkeypatch,
            alocados=range(10, 13),
            vagas=8,
            deficit_por_ids=lambda ids: [deficit(lideranca=1)],
        )
        alocar(uc, 50)
        assert repo.criadas == [50]

    def test_dois_deficits_e_duas_vagas_deixa_entrar_quem_cobre_um(self, monkeypatch):
        """6/8: 2 vagas, falta 1 liderança + 1 membro. Quem cobre a liderança
        entra — sobra 1 vaga pro 1 membro que ainda falta."""
        uc, repo = montar(
            monkeypatch,
            alocados=range(10, 16),
            vagas=8,
            deficit_por_ids=lambda ids: (
                [deficit(membros=1)] if LIDER_DE_BUSINESS in ids
                else [deficit(lideranca=1, membros=1)]
            ),
        )
        alocar(uc, LIDER_DE_BUSINESS)
        assert repo.criadas == [LIDER_DE_BUSINESS]

    def test_banca_legada_sem_frente_vinculada_nao_reserva(self, monkeypatch):
        uc, repo = montar(
            monkeypatch,
            alocados=range(10, 17),
            vagas=8,
            deficit_por_ids=lambda ids: [deficit(lideranca=1)],
        )
        uc.banca_frente_repository = SimpleNamespace(get_by_banca=lambda _: [])
        alocar(uc, 50)
        assert repo.criadas == [50]
