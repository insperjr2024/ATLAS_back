"""§8, 2026-09-11 — a trava dos 7 dias é POR PESSOA, não da banca inteira.

Antes: a menos de 7 dias, se o TOTAL batesse o piso, NINGUÉM saía — nem quem
tinha acabado de entrar sobrando, nem a 4ª pessoa de uma frente que só
precisa de 3. Agora só trava quem a saída de fato descobre um piso (membros
ou liderança) que hoje está coberto — `DeleteCandidaturaUseCase.
_saida_quebraria_composicao`, o espelho (ao contrário) da reserva de vaga de
`create_candidatura`.

`ComposicaoBancaChecker` já tem os próprios testes (composição por frente,
liderança sem frente etc.) — aqui o que se prende é só a ORQUESTRAÇÃO: "com
todo mundo dá `ok`? sem esta pessoa, ainda dá?". Por isso o dublê de
`ComposicaoBancaChecker.verificar` é um `essenciais.issubset(ids)` — abstrai
a regra de composição real e deixa o teste focado em quem pode sair.
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import src.use_cases.candidatura.update_candidatura as mod
import src.use_cases.configuracao.composicao_banca as composicao_config_mod
from src.use_cases.candidatura.update_candidatura import DeleteCandidaturaUseCase
from src.utils.exceptions import RegraDeNegocioError

AGORA = datetime.now(timezone.utc).replace(tzinfo=None)


class FakeCandidaturaRepo:
    """`existentes`: lista de (candidatura_id, usuario_id). `delete` MUTA de
    verdade — é o que deixa testar a re-checagem em cima do estado que a
    saída anterior deixou, sem precisar de banco nenhum."""

    def __init__(self, existentes):
        self._existentes = list(existentes)

    def get_by_id(self, cid):
        for id_, uid in self._existentes:
            if id_ == cid:
                return SimpleNamespace(id=id_, usuario_id=uid, banca_id=1)
        return None

    def get_by_banca(self, banca_id):
        return [SimpleNamespace(id=i, usuario_id=u) for i, u in self._existentes]

    def delete(self, cid):
        antes = len(self._existentes)
        self._existentes = [(i, u) for i, u in self._existentes if i != cid]
        return len(self._existentes) < antes


class FakeBancaFrenteRepo:
    def __init__(self, com_vinculo=True):
        self._com_vinculo = com_vinculo

    def get_by_banca(self, banca_id):
        return [SimpleNamespace(frente_id=1)] if self._com_vinculo else []


def _fake_checker_cls(essenciais: set):
    """`essenciais` é o conjunto de usuario_id sem os quais a composição NÃO
    fecha — abstração de "o piso de membros e liderança de cada frente"."""

    class FakeChecker:
        def __init__(self, db):
            pass

        def verificar(self, banca, regras, ids):
            return SimpleNamespace(ok=set(essenciais).issubset(ids))

    return FakeChecker


class FakeResolver:
    def __init__(self, db):
        pass

    def para(self, frente_ids):
        return []  # o conteúdo não importa: quem decide é o FakeChecker


@pytest.fixture
def cenario(monkeypatch):
    def _montar(*, existentes, daqui_dias=3, essenciais=None, com_vinculo=True, piso_override=None):
        banca = SimpleNamespace(
            id=1,
            data_hora=AGORA + timedelta(days=daqui_dias),
            realizado_em=None,
            cancelada_em=None,
            piso_minimo_override=piso_override,
        )
        cand_repo = FakeCandidaturaRepo(existentes)

        uc = DeleteCandidaturaUseCase.__new__(DeleteCandidaturaUseCase)
        uc.db = None
        uc.repository = cand_repo
        uc.banca_repository = SimpleNamespace(get_by_id=lambda bid: banca)
        uc.banca_frente_repository = FakeBancaFrenteRepo(com_vinculo)

        monkeypatch.setattr(mod, "ComposicaoBancaChecker", _fake_checker_cls(essenciais or set()))
        monkeypatch.setattr(composicao_config_mod, "ResolverComposicaoUseCase", FakeResolver)

        return uc, cand_repo

    return _montar


class TestPorFrente:
    def test_pessoa_extra_sai_livre_mesmo_com_o_piso_no_ponto(self, cenario):
        """Business 4/3: o piso pede 3 (uids 1,2,3); o 4º (uid 4) é sobra —
        sem ele a composição continua `ok`, então ele sai sem trava."""
        uc, cand_repo = cenario(
            existentes=[(101, 1), (102, 2), (103, 3), (104, 4)],
            essenciais={1, 2, 3},
        )
        assert uc.execute(104) is True
        assert [i for i, _ in cand_repo._existentes] == [101, 102, 103]

    def test_pessoa_que_fecha_o_piso_fica_presa(self, cenario):
        """Business exatamente 3/3: qualquer um dos três é essencial — sem
        ele a composição quebra, e a saída é travada."""
        uc, _ = cenario(
            existentes=[(101, 1), (102, 2), (103, 3)],
            essenciais={1, 2, 3},
        )
        with pytest.raises(RegraDeNegocioError, match="composição mínima descoberta"):
            uc.execute(101)

    def test_saida_sequencial_a_segunda_pessoa_e_bloqueada_na_hora(self, cenario):
        """⭐ O caso do enunciado: alguém sai, e minutos depois outra pessoa
        tenta sair também. Nenhum job de 5 em 5 min no meio — é o MESMO
        objeto, reagindo ao estado que a primeira saída deixou, na mesma
        chamada seguinte."""
        uc, cand_repo = cenario(
            existentes=[(101, 1), (102, 2), (103, 3), (104, 4)],
            essenciais={1, 2, 3},
        )
        # A 4ª pessoa (sobra) sai livre.
        assert uc.execute(104) is True
        # Agora está exatamente no piso (1,2,3) — a próxima fica presa,
        # e a checagem já reflete o estado pós-saída, sem esperar nada.
        with pytest.raises(RegraDeNegocioError, match="composição mínima descoberta"):
            uc.execute(101)
        assert [i for i, _ in cand_repo._existentes] == [101, 102, 103]

    def test_banca_ja_abaixo_do_piso_nao_trava_ninguem(self, cenario):
        """Só 2 de 3 essenciais alocados: a composição já não fecha AGORA —
        travar a saída de mais alguém não protegeria nada."""
        uc, _ = cenario(
            existentes=[(101, 1), (102, 2)],
            essenciais={1, 2, 3},
        )
        assert uc.execute(101) is True

    def test_diretoria_passa_por_cima_mesmo_no_ponto_exato(self, cenario):
        uc, _ = cenario(
            existentes=[(101, 1), (102, 2), (103, 3)],
            essenciais={1, 2, 3},
        )
        assert uc.execute(101, eh_gestao=True) is True

    def test_longe_da_banca_ninguem_trava(self, cenario):
        uc, _ = cenario(
            existentes=[(101, 1), (102, 2), (103, 3)],
            essenciais={1, 2, 3},
            daqui_dias=20,
        )
        assert uc.execute(101) is True


class TestBancaLegadaSemFrente:
    """Sem `banca_frente`, não há composição por frente a proteger — só o
    TOTAL, mesma régua de antes disto virar por pessoa (ver também
    `test_desalocar_banca_trava_7_dias.py`, com banco de verdade)."""

    def test_no_total_so_trava_quem_fecha_o_numero_exato(self, cenario):
        uc, _ = cenario(
            existentes=[(101, 1), (102, 2)],
            com_vinculo=False,
            piso_override=2,
        )
        with pytest.raises(RegraDeNegocioError, match="composição mínima descoberta"):
            uc.execute(101)

    def test_no_total_sobrando_gente_ninguem_trava(self, cenario):
        uc, _ = cenario(
            existentes=[(101, 1), (102, 2), (103, 3)],
            com_vinculo=False,
            piso_override=2,
        )
        assert uc.execute(101) is True
