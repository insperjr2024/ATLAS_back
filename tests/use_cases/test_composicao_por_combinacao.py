"""⭐ A composição de banca por COMBINAÇÃO de frentes (2026-09-01).

Antes: `frente.piso_banca` (um mínimo por frente, igual em qualquer banca) e
`configuracao.lideranca_minima_por_frente` (um global). Business era 3 sozinho
e 3 numa banca de quatro frentes, e não havia teto por frente nenhum.

Agora a regra é por (combinação, frente), e o que estes testes protegem é a
transição:

- **Combinação sem linha vale o PADRÃO**, derivado do que já existia. É isso
  que faz a virada não mexer em banca marcada e que dá regra a uma frente
  cadastrada amanhã, sem migration.
- **Liderança é vaga A MAIS** do que o mínimo de membros. Business sozinho
  passa a pedir 3 + 1 = 4 pessoas, não 3.
- **A chave da combinação é ordenada**: Direito + Business acha a regra que
  alguém gravou como Business + Direito.
"""

from types import SimpleNamespace

import pytest

from src.use_cases.configuracao import composicao_banca as mod
from src.use_cases.configuracao.composicao_banca import ResolverComposicaoUseCase
from src.utils.combinacao_frentes import chave, ler, todas

BUSINESS, DIREITO, TECH, PROCESSOS = 1, 2, 3, 4


def frente(id_, nome, piso, ativa=True):
    return SimpleNamespace(id=id_, nome=nome, piso_banca=piso, ativa=ativa)


@pytest.fixture
def resolver(monkeypatch):
    """`ResolverComposicaoUseCase` com os repositórios dublados.

    O mundo é o de produção: Business 3 · Direito 1 · Tech 2 · Processos 2, e
    `lideranca_minima_por_frente` = 1.
    """

    def _montar(gravadas=None, lideranca_padrao=1, frentes=None, vagas_padrao=5):
        gravadas = gravadas or {}
        frentes = frentes or [
            frente(BUSINESS, "Business", 3),
            frente(DIREITO, "Direito", 1),
            frente(TECH, "Tech", 2),
            frente(PROCESSOS, "Processos", 2),
        ]

        class RegraFake:
            def __init__(self, db): pass
            def get_por_frente(self, combinacao):
                return gravadas.get(combinacao, {})

        class FrenteFake:
            def __init__(self, db): pass
            def get_all(self): return frentes

        class ConfigFake:
            def __init__(self, db): pass
            def get(self):
                return SimpleNamespace(
                    lideranca_minima_por_frente=lideranca_padrao,
                    vagas_por_banca=vagas_padrao,
                )

        monkeypatch.setattr(mod, "BancaComposicaoRegraRepository", RegraFake)
        monkeypatch.setattr(mod, "FrenteRepository", FrenteFake)
        monkeypatch.setattr(mod, "ConfiguracaoRepository", ConfigFake)
        return ResolverComposicaoUseCase(db=None)

    return _montar


def gravada(frente_id, min_m, min_l, vagas=None):
    """Uma linha de `banca_composicao_regra` gravada. Só piso — o teto por
    frente saiu (2026-09-03)."""
    return SimpleNamespace(
        frente_id=frente_id, min_membros=min_m, min_lideranca=min_l, vagas=vagas,
    )


class TestOPadrao:
    def test_combinacao_nao_configurada_usa_o_piso_da_frente(self, resolver):
        uc = resolver()

        regras = uc.para([BUSINESS])

        assert [r.min_membros for r in regras] == [3]
        assert [r.configurada for r in regras] == [False]

    def test_lideranca_padrao_vem_da_configuracao_global(self, resolver):
        uc = resolver(lideranca_padrao=2)

        assert uc.para([TECH])[0].min_lideranca == 2

    def test_sem_configuracao_a_lideranca_cai_em_um(self, resolver, monkeypatch):
        uc = resolver()
        monkeypatch.setattr(type(uc.configuracao_repository), "get", lambda self: None)

        assert uc.para([TECH])[0].min_lideranca == 1


class TestLiderancaEhVagaAMais:
    def test_business_sozinho_pede_quatro_pessoas(self, resolver):
        """⭐ A mudança de 2026-09-01: 3 membros + 1 liderança. Antes o gerente
        cabia dentro dos 3, e a banca fechava com três pessoas."""
        uc = resolver()

        assert uc.para([BUSINESS])[0].minimo_de_pessoas == 4

    def test_o_blend_pede_seis(self, resolver):
        """Business (3+1) + Direito (1+1) = 6 — o exemplo do usuário."""
        uc = resolver()

        regras = uc.para([BUSINESS, DIREITO])

        assert sum(r.minimo_de_pessoas for r in regras) == 6


class TestAChaveDaCombinacao:
    def test_a_ordem_dos_ids_nao_importa(self, resolver):
        """Direito + Business acha a regra gravada como Business + Direito."""
        uc = resolver(gravadas={"1-2": {BUSINESS: gravada(BUSINESS, 9, 9)}})

        regras = uc.para([DIREITO, BUSINESS])

        assert regras[0].min_membros == 9

    def test_frente_repetida_colapsa(self):
        """Dois escopos de Business são a mesma combinação que um."""
        assert chave([BUSINESS, BUSINESS]) == chave([BUSINESS])

    def test_ida_e_volta_da_chave(self):
        assert ler(chave([3, 1, 2])) == [1, 2, 3]

    def test_combinacao_vazia_nao_estoura(self):
        """A banca legada, sem frente vinculada, passa por aqui."""
        assert ler("") == []

    def test_quatro_frentes_geram_quinze_combinacoes(self):
        assert len(todas([1, 2, 3, 4])) == 15


class TestOQueFoiConfigurado:
    def test_a_regra_gravada_vence_o_padrao(self, resolver):
        uc = resolver(gravadas={"1": {BUSINESS: gravada(BUSINESS, 2, 1)}})

        regra = uc.para([BUSINESS])[0]

        assert regra.min_membros == 2
        assert regra.configurada is True

    def test_a_mesma_frente_pode_ter_numero_diferente_por_combinacao(self, resolver):
        """⭐ O motivo de a matriz existir: Business afrouxa quando a banca já
        tem outras três frentes."""
        uc = resolver(
            gravadas={"1-2-3-4": {BUSINESS: gravada(BUSINESS, 2, 1)}}
        )

        sozinho = uc.para([BUSINESS])[0]
        acompanhado = next(
            r for r in uc.para([BUSINESS, DIREITO, TECH, PROCESSOS])
            if r.frente_id == BUSINESS
        )

        assert sozinho.min_membros == 3
        assert acompanhado.min_membros == 2

    def test_frente_sem_linha_na_combinacao_configurada_cai_no_padrao(self, resolver):
        """Gravar só Business em BUS+DIR não pode deixar Direito sem regra."""
        uc = resolver(gravadas={"1-2": {BUSINESS: gravada(BUSINESS, 2, 1)}})

        direito = next(r for r in uc.para([BUSINESS, DIREITO]) if r.frente_id == DIREITO)

        assert direito.min_membros == 1
        assert direito.configurada is False


class TestOSeletorDaTela:
    def test_lista_as_quinze_combinacoes(self, resolver):
        uc = resolver()

        assert len(uc.listar_combinacoes()) == 15

    def test_frente_inativa_fica_de_fora(self, resolver):
        """Desativar uma frente derruba o seletor de 15 para 7 — ela não entra
        em banca nova, e listá-la dobraria a tela com combinações mortas."""
        uc = resolver(frentes=[
            frente(BUSINESS, "Business", 3),
            frente(DIREITO, "Direito", 1),
            frente(TECH, "Tech", 2),
            frente(PROCESSOS, "Processos", 2, ativa=False),
        ])

        assert len(uc.listar_combinacoes()) == 7

    def test_o_resumo_traz_o_minimo_e_o_rotulo(self, resolver):
        uc = resolver()

        blend = next(c for c in uc.listar_combinacoes() if c["combinacao"] == "1-2")

        assert blend["rotulo"] == "Business + Direito"
        assert blend["minimo_total"] == 6
        assert blend["sinergica"] is True
        assert blend["configurada"] is False


class TestOTetoDaCombinacao:
    """⭐ O teto de vagas passou a poder ser da COMBINAÇÃO (2026-09-02).

    Era um número só para a plataforma inteira: a banca de Direito sozinha
    (que exige 2 pessoas) e a de Business + Tech + Processos (que exige 9)
    cabiam o mesmo tanto de gente.
    """

    def test_sem_teto_proprio_vale_o_global(self, resolver):
        uc = resolver(vagas_padrao=6)

        assert uc.vagas_da_combinacao([BUSINESS]) == 6
        assert uc.vagas_proprias_da_combinacao([BUSINESS]) is None

    def test_o_teto_gravado_na_combinacao_ganha_do_global(self, resolver):
        uc = resolver(
            gravadas={"1-3": {BUSINESS: gravada(BUSINESS, 3, 1, vagas=9),
                              TECH: gravada(TECH, 2, 0, vagas=9)}},
            vagas_padrao=6,
        )

        assert uc.vagas_da_combinacao([TECH, BUSINESS]) == 9
        assert uc.vagas_proprias_da_combinacao([BUSINESS, TECH]) == 9

    def test_uma_combinacao_nao_herda_o_teto_da_outra(self, resolver):
        """Business + Tech com teto 9 não muda o teto de Business sozinho."""
        uc = resolver(
            gravadas={"1-3": {BUSINESS: gravada(BUSINESS, 3, 1, vagas=9),
                              TECH: gravada(TECH, 2, 0, vagas=9)}},
            vagas_padrao=6,
        )

        assert uc.vagas_da_combinacao([BUSINESS]) == 6

    def test_banca_legada_sem_frente_fica_no_global(self, resolver):
        """Sem frente não há combinação — e o global é o que sempre valeu
        para ela."""
        uc = resolver(vagas_padrao=6)

        assert uc.vagas_da_combinacao([]) == 6
        assert uc.vagas_proprias_da_combinacao([]) is None

    def test_o_seletor_mostra_o_teto_de_cada_combinacao(self, resolver):
        uc = resolver(
            gravadas={"1": {BUSINESS: gravada(BUSINESS, 3, 1, vagas=4)}},
            vagas_padrao=6,
        )

        por_chave = {c["combinacao"]: c for c in uc.listar_combinacoes()}

        assert por_chave["1"]["vagas"] == 4
        assert por_chave["2"]["vagas"] == 6
