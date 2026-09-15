"""2026-09-15 — contexto de uma troca: a saída de quem pediu quebra o piso ou
a liderança da FRENTE dela nesta banca? Se sim, só quem é da mesma frente
(líder dela, se for liderança que falta) pode assumir. Se não (vaga
excedente — o mesmo caso do 2º líder que sobra em `push_alocacao_automatica`),
qualquer elegível serve.

`ComposicaoBancaChecker` já tem os próprios testes de composição (piso,
liderança, excedente etc.) — aqui o que se prende é só a ORQUESTRAÇÃO: "com
todo mundo dá ok? sem quem pediu a troca, ainda dá?". Mesmo estilo de
`test_desalocar_por_pessoa.py` — o dublê do checker abstrai a regra real.
"""

from types import SimpleNamespace

import src.use_cases.configuracao.composicao_banca as composicao_mod
import src.utils.contexto_troca as mod
from src.utils.contexto_troca import calcular_contexto_troca


def usuario(id, posicao="consultor"):
    return SimpleNamespace(id=id, posicao=posicao)


class FakeUsuarioRepo:
    def __init__(self, usuarios):
        self._usuarios = usuarios

    def get_ativos(self):
        return self._usuarios


class FakeBancaFrenteRepo:
    def __init__(self, frente_ids):
        self._frente_ids = frente_ids

    def get_by_banca(self, banca_id):
        return [SimpleNamespace(frente_id=f) for f in self._frente_ids]


class FakeUsuarioFrenteRepo:
    def __init__(self, por_frente: dict):
        self._por_frente = por_frente

    def get_by_usuario(self, usuario_id):
        return [
            SimpleNamespace(frente_id=fid)
            for fid, uids in self._por_frente.items()
            if usuario_id in uids
        ]

    def get_by_frente(self, frente_id):
        return [SimpleNamespace(usuario_id=u) for u in self._por_frente.get(frente_id, [])]


class FakeCandidaturaRepo:
    def __init__(self, candidatos):
        self._candidatos = candidatos

    def get_by_banca(self, banca_id):
        return [SimpleNamespace(usuario_id=u) for u in self._candidatos]


def _fake_checker_cls(deficits_por_conjunto):
    """`deficits_por_conjunto`: função frozenset(ids) -> lista de
    SimpleNamespace(frente_id, piso_faltando, lideranca_faltando) — abstrai a
    regra real de composição, testada à parte em `test_composicao_banca.py`."""

    class FakeChecker:
        def __init__(self, db):
            pass

        def verificar(self, banca, regras, ids):
            return SimpleNamespace(deficits=deficits_por_conjunto(frozenset(ids)))

    return FakeChecker


def montar(
    monkeypatch,
    *,
    ativos,
    frente_ids,
    por_frente,
    candidatos,
    deficits_por_conjunto,
    frente_nome="Business",
    min_lideranca=1,
    min_membros=3,
):
    monkeypatch.setattr(mod, "UsuarioRepository", lambda db: FakeUsuarioRepo(ativos))
    monkeypatch.setattr(mod, "BancaFrenteRepository", lambda db: FakeBancaFrenteRepo(frente_ids))
    monkeypatch.setattr(mod, "UsuarioFrenteRepository", lambda db: FakeUsuarioFrenteRepo(por_frente))
    monkeypatch.setattr(mod, "CandidaturaRepository", lambda db: FakeCandidaturaRepo(candidatos))
    monkeypatch.setattr(mod, "ComposicaoBancaChecker", _fake_checker_cls(deficits_por_conjunto))
    monkeypatch.setattr(
        composicao_mod,
        "ResolverComposicaoUseCase",
        lambda db: SimpleNamespace(
            para=lambda fids: [
                SimpleNamespace(
                    frente_id=1, frente_nome=frente_nome,
                    min_lideranca=min_lideranca, min_membros=min_membros,
                )
            ]
        ),
    )
    banca = SimpleNamespace(id=1, nome_projeto="Projeto X")
    return banca


class TestVagaExcedente:
    def test_saida_de_quem_e_sobra_nao_precisa_de_frente_nenhuma(self, monkeypatch):
        """5 pessoas em Business (piso 3 + liderança 1 = 4 exigidas): a 5ª é
        sobra — sem ela a composição continua igual, então ela sai livre e
        qualquer elegível pode cobrir a vaga."""
        banca = montar(
            monkeypatch,
            ativos=[usuario(1, "gerente"), usuario(2, "coordenador"), usuario(3), usuario(4), usuario(5)],
            frente_ids=[1],
            por_frente={1: [1, 2, 3, 4, 5]},
            candidatos=[1, 2, 3, 4, 5],
            deficits_por_conjunto=lambda ids: [],  # nunca falta nada, com ou sem ninguém
        )

        contexto = calcular_contexto_troca(db=None, banca=banca, usuario_saindo_id=5, excluidos=set())

        assert contexto.vaga_precisada is False
        assert contexto.frente_id is None
        assert set(contexto.elegiveis_ids) == {1, 2, 3, 4}


class TestVagaPrecisada:
    def test_saida_de_quem_fecha_o_piso_restringe_a_frente(self, monkeypatch):
        """Exatamente 4/4: qualquer um que saia descobre o piso de membros —
        só quem é de Business pode assumir."""
        def deficits(ids):
            if 4 in ids:
                return []
            return [SimpleNamespace(frente_id=1, piso_faltando=1, lideranca_faltando=0)]

        banca = montar(
            monkeypatch,
            ativos=[usuario(1, "gerente"), usuario(2), usuario(3), usuario(4), usuario(99)],
            frente_ids=[1],
            por_frente={1: [1, 2, 3, 4]},  # 99 é de fora de Business
            candidatos=[1, 2, 3, 4],
            deficits_por_conjunto=deficits,
        )

        contexto = calcular_contexto_troca(db=None, banca=banca, usuario_saindo_id=4, excluidos=set())

        assert contexto.vaga_precisada is True
        assert contexto.precisa_lideranca is False
        assert contexto.frente_id == 1
        assert contexto.frente_nome == "Business"
        # Só membros de Business (1,2,3) — 99 é de fora e não entra.
        assert set(contexto.elegiveis_ids) == {1, 2, 3}

    def test_saida_do_lider_unico_restringe_a_lideranca_da_frente(self, monkeypatch):
        """A liderança mínima (1) some se o único gerente sair — só quem
        lidera a frente cobre, não qualquer membro."""
        def deficits(ids):
            if 1 in ids:
                return []
            return [SimpleNamespace(frente_id=1, piso_faltando=0, lideranca_faltando=1)]

        banca = montar(
            monkeypatch,
            ativos=[usuario(1, "gerente"), usuario(2), usuario(3)],
            frente_ids=[1],
            por_frente={1: [1, 2, 3]},
            candidatos=[1, 2, 3],
            deficits_por_conjunto=deficits,
        )

        contexto = calcular_contexto_troca(db=None, banca=banca, usuario_saindo_id=1, excluidos=set())

        assert contexto.vaga_precisada is True
        assert contexto.precisa_lideranca is True
        # Ninguém mais em Business lidera a frente — a vaga fica sem quem
        # possa cobrir (a troca não pode fabricar um líder que não existe).
        assert contexto.elegiveis_ids == []

    def test_excluidos_saem_da_lista_mesmo_sendo_da_frente(self, monkeypatch):
        def deficits(ids):
            if 4 in ids:
                return []
            return [SimpleNamespace(frente_id=1, piso_faltando=1, lideranca_faltando=0)]

        banca = montar(
            monkeypatch,
            ativos=[usuario(1, "gerente"), usuario(2), usuario(3), usuario(4)],
            frente_ids=[1],
            por_frente={1: [1, 2, 3, 4]},
            candidatos=[1, 2, 3, 4],
            deficits_por_conjunto=deficits,
        )

        contexto = calcular_contexto_troca(db=None, banca=banca, usuario_saindo_id=4, excluidos={2})

        assert set(contexto.elegiveis_ids) == {1, 3}


class TestSemFrenteRelevante:
    def test_quem_nao_e_de_nenhuma_frente_da_banca_nunca_precisa_de_vaga(self, monkeypatch):
        """Liderança sem frente (diretoria/coord. de vendas) ou alguém que
        entrou pelo preenchimento geral: a saída dela não pode "faltar" pra
        uma frente que ela nunca cobriu — nem chega a consultar o checker."""
        banca = montar(
            monkeypatch,
            ativos=[usuario(1), usuario(2), usuario(9, "diretor_projetos")],
            frente_ids=[1],
            por_frente={1: [1, 2]},  # 9 não é de Business
            candidatos=[1, 2, 9],
            deficits_por_conjunto=lambda ids: (_ for _ in ()).throw(
                AssertionError("checker não devia ser chamado")
            ),
        )

        contexto = calcular_contexto_troca(db=None, banca=banca, usuario_saindo_id=9, excluidos=set())

        assert contexto.vaga_precisada is False
        assert set(contexto.elegiveis_ids) == {1, 2}
