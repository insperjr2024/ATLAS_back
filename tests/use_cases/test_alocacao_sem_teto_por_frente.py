"""§8 — a alocação NÃO barra por frente (2026-09-03).

⭐ O que estes testes protegem: o "Máx. membros"/"Máx. liderança" por frente
saiu. O piso continua tendo de ser gente DAQUELA frente, mas completar acima
dele é "tanto faz a frente" — o único teto que barra a inscrição é o TOTAL da
banca (`configuracao.vagas_por_banca` ou o da combinação).

Antes disto, uma banca de Business + Direito com "Máx. 3 de Business" recusava
o quarto de Business mesmo com vaga total sobrando. Agora não.

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

BUSINESS, TECH = 1, 2


def montar(monkeypatch, *, frente_ids, frentes, alocados=(), vagas=10):
    """Um `CreateCandidaturaUseCase` sem banco. O teto TOTAL (`vagas`) é o
    único que barra nestes testes: neutralizo a regra da combinação para o
    piso por frente não reservar vaga nenhuma — a reserva é assunto de
    `test_vaga_reservada_pro_piso.py`."""
    monkeypatch.setattr(mod, "calcular_vagas_banca", lambda *a, **k: vagas)
    monkeypatch.setattr(
        "src.use_cases.configuracao.composicao_banca.ResolverComposicaoUseCase.para",
        lambda self, ids: [],
    )
    monkeypatch.setattr(
        "src.utils.composicao_banca.ComposicaoBancaChecker.verificar",
        lambda self, banca, regras, ids: SimpleNamespace(deficits=[]),
    )

    class FakeCandidaturaRepo:
        def __init__(self):
            self.criadas = []

        def get_by_banca(self, _banca_id):
            return [SimpleNamespace(usuario_id=uid) for uid in alocados]

        def create(self, **kwargs):
            self.criadas.append(kwargs["usuario_id"])
            return SimpleNamespace(id=1, **kwargs)

    banca = SimpleNamespace(
        id=1,
        nome_projeto="BLEND I",
        data_hora=datetime.now() + timedelta(days=3),
        realizado_em=None,
        coordenador_id=None,
    )

    uc = CreateCandidaturaUseCase.__new__(CreateCandidaturaUseCase)
    uc.db = None
    candidatura_repo = FakeCandidaturaRepo()
    uc.repository = candidatura_repo
    uc.banca_repository = SimpleNamespace(get_by_id=lambda _id: banca)
    uc.configuracao_repository = SimpleNamespace(
        get=lambda: SimpleNamespace(vagas_por_banca=vagas)
    )
    uc.banca_frente_repository = SimpleNamespace(
        get_by_banca=lambda _id: [SimpleNamespace(frente_id=fid) for fid in frente_ids]
    )
    uc.frente_repository = SimpleNamespace(get_by_id=lambda fid: frentes.get(fid))
    # Banca sem escopo: `membros_da_banca` devolve só o coordenador.
    uc.banca_escopo_repository = SimpleNamespace(get_escopo_ids=lambda _id: [])
    uc.escopo_repository = SimpleNamespace(get_by_id=lambda _id: None)
    uc.membro_repository = SimpleNamespace(get_by_projeto=lambda *a, **k: [])
    uc.equipe_projeto_repository = SimpleNamespace(get_by_banca=lambda _id: [])
    return uc, candidatura_repo


def frente(id, nome, piso_banca=1):
    return SimpleNamespace(id=id, nome=nome, piso_banca=piso_banca, ativa=True)


def alocar(uc, usuario_id):
    return uc.execute(CreateCandidaturaRequest(banca_id=1), usuario_id=usuario_id)


class TestNaoBarraPorFrente:
    def test_muita_gente_de_uma_frente_so_entra_se_couber_no_total(self, monkeypatch):
        """O caso que a regra antiga recusava: cabem 10 na banca, e o sétimo
        de Business entra numa banca que ainda tem vaga."""
        uc, candidaturas = montar(
            monkeypatch,
            frente_ids=[BUSINESS, TECH],
            frentes={
                BUSINESS: frente(BUSINESS, "Business", 3),
                TECH: frente(TECH, "Tech", 2),
            },
            alocados=(10, 11, 12, 13, 14, 15),
            vagas=10,
        )

        alocar(uc, 16)

        assert candidaturas.criadas == [16]

    def test_o_teto_total_da_banca_ainda_barra(self, monkeypatch):
        uc, _ = montar(
            monkeypatch,
            frente_ids=[BUSINESS],
            frentes={BUSINESS: frente(BUSINESS, "Business", 3)},
            alocados=(10, 11, 12, 13, 14),
            vagas=5,
        )

        with pytest.raises(RegraDeNegocioError, match="lotada"):
            alocar(uc, 15)

    def test_banca_legada_sem_frente_vinculada_passa(self, monkeypatch):
        uc, candidaturas = montar(
            monkeypatch, frente_ids=[], frentes={}, alocados=(), vagas=5
        )

        alocar(uc, 10)

        assert candidaturas.criadas == [10]
