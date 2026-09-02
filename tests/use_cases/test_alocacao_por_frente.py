"""Quem aparece nas tabelas da aba Alocação (§7.3).

⭐ **Para o gerente, a população é a FRENTE dele — não os projetos dele.**

Antes a lista saía de quem estava alocado nos projetos visíveis, e isso errava
a pergunta nos dois sentidos:

- o consultor da frente que ainda não entrou em projeto nenhum SUMIA — e ele é
  exatamente quem a aba existe para achar, a vaga livre;
- o consultor de OUTRA frente que passou por um projeto sinérgico do gerente
  APARECIA — alguém que ele não aloca e cuja carga não é problema dele.

A régua passou a ser o vínculo de `usuario_frente`, a mesma que o §7.5 usa para
decidir quais projetos o gerente enxerga.

A DIRETORIA não entra em tabela nenhuma: os três cargos não pegam projeto, e
listá-los só inflava a capacidade com vagas que ninguém vai ocupar.
"""

from types import SimpleNamespace

import pytest

from src.use_cases.monitoramento import monitoramento as mod
from src.use_cases.monitoramento.monitoramento import AlocacaoUseCase

BUSINESS, TECH = 1, 2

#: A escala mínima que `linha()` precisa para resolver a situação de cada um.
#: O assunto deste arquivo é a POPULAÇÃO, não a escala — `test_situacao_carga`
#: cobre a resolução das faixas.
ESCALA = [
    SimpleNamespace(nome="Disponível", min_projetos=0, tom="ok"),
    SimpleNamespace(nome="Quantidade ideal", min_projetos=2, tom="neutro"),
    SimpleNamespace(nome="Demanda alta", min_projetos=3, tom="alerta"),
]

#: O núcleo do cenário. Murilo gerencia Tech.
USUARIOS = [
    SimpleNamespace(id=1, nome="Murilo", posicao="gerente", status="ativo"),
    SimpleNamespace(id=2, nome="Coord Tech", posicao="coordenador", status="ativo"),
    SimpleNamespace(id=3, nome="Coord Business", posicao="coordenador", status="ativo"),
    SimpleNamespace(id=4, nome="Cons Tech Alocado", posicao="consultor", status="ativo"),
    SimpleNamespace(id=5, nome="Cons Tech Livre", posicao="consultor", status="ativo"),
    SimpleNamespace(id=6, nome="Cons Business", posicao="consultor", status="ativo"),
    SimpleNamespace(id=7, nome="Diretora", posicao="diretor_projetos", status="ativo"),
]

VINCULOS = [(1, TECH), (2, TECH), (3, BUSINESS), (4, TECH), (5, TECH), (6, BUSINESS)]

#: Um projeto sinérgico só: o gerente de Tech o enxerga, e nele trabalham gente
#: de Tech E de Business. É o caso que separa "quem está no meu projeto" de
#: "quem é da minha frente".
PROJETOS = [SimpleNamespace(id=10, nome="Sinérgico", status="em_andamento")]
MEMBROS = [
    (10, 2, "coordenador"),   # Coord Tech
    (10, 3, "coordenador"),   # Coord Business — entrou pelo sinérgico
    (10, 4, "consultor"),     # Cons Tech Alocado
    (10, 6, "consultor"),     # Cons Business — entrou pelo sinérgico
]


class FakeRepo:
    def __init__(self, itens):
        self._itens = list(itens)

    def get_all(self):
        return self._itens


class FakeMembros:
    def __init__(self, membros):
        self._membros = membros

    def get_by_projetos(self, ids, apenas_atuais=False):
        return [
            SimpleNamespace(projeto_id=p, usuario_id=u, papel=papel)
            for p, u, papel in self._membros
            if p in ids
        ]


class FakeSituacoes:
    def garantir_padrao(self, papel):
        return ESCALA


@pytest.fixture
def uc(monkeypatch):
    """`AlocacaoUseCase` sem banco: o assunto é `entra()`, não SQL.

    `_projetos_visiveis` devolve sempre a carteira inteira — o recorte de
    PROJETOS já é testado em `test_filtro_status_monitoramento`; o que muda
    aqui é o recorte de PESSOAS.
    """
    instancia = AlocacaoUseCase.__new__(AlocacaoUseCase)
    instancia.db = object()
    instancia.membro_repository = FakeMembros(MEMBROS)
    instancia.usuario_repository = FakeRepo(USUARIOS)
    instancia.situacao_repository = FakeSituacoes()
    instancia.frente_repository = FakeRepo(
        [SimpleNamespace(id=BUSINESS, nome="Business"), SimpleNamespace(id=TECH, nome="Tech")]
    )
    instancia.usuario_frente_repository = FakeRepo(
        [SimpleNamespace(usuario_id=u, frente_id=f) for u, f in VINCULOS]
    )
    monkeypatch.setattr(
        AlocacaoUseCase, "_projetos_visiveis", lambda self, *a, **k: list(PROJETOS)
    )
    monkeypatch.setattr(mod, "frentes_do_usuario", lambda user, db: [TECH])
    return instancia


def nomes(linhas):
    return {l["nome"] for l in linhas}


GERENTE = SimpleNamespace(id=1, nome="Murilo", posicao="gerente")
DIRETORA = SimpleNamespace(id=7, nome="Diretora", posicao="diretor_projetos")


class TestPopulacaoDoGerente:
    def test_ve_o_consultor_da_frente_que_nao_esta_em_projeto_nenhum(self, uc):
        """⭐ O ponto da mudança. Ele é a vaga livre que a aba existe para
        achar, e a régua antiga — "quem está nos meus projetos" — o escondia
        justamente por estar disponível."""
        r = uc.execute(GERENTE)
        assert "Cons Tech Livre" in nomes(r["consultores"])

    def test_nao_ve_o_consultor_de_outra_frente_mesmo_num_projeto_dele(self, uc):
        """Cons Business trabalha no sinérgico que o gerente de Tech enxerga.
        O projeto é dele; a pessoa não — quem aloca Business é o gerente de
        Business, e a carga dela não é problema deste painel."""
        r = uc.execute(GERENTE)
        assert "Cons Business" not in nomes(r["consultores"])

    def test_a_mesma_regra_vale_para_os_coordenadores(self, uc):
        r = uc.execute(GERENTE)
        assert nomes(r["coordenadores"]) == {"Murilo", "Coord Tech"}


class TestCoordenadorDeVendas:
    """O coordenador comercial não entra na tabela de capacidade: tem a
    posição, mas não conduz execução, e listá-lo daria ao núcleo uma vaga de
    coordenação que ninguém vai ocupar."""

    def _uc_com_vendas(self, uc):
        vendas = SimpleNamespace(
            id=8, nome="Coord Vendas", posicao="coordenador", status="ativo",
            coordenador_vendas=True,
        )
        uc.usuario_repository = FakeRepo([*USUARIOS, vendas])
        uc.usuario_frente_repository = FakeRepo(
            [SimpleNamespace(usuario_id=u, frente_id=f) for u, f in [*VINCULOS, (8, TECH)]]
        )
        return uc

    def test_nao_aparece_para_a_diretoria(self, uc):
        r = self._uc_com_vendas(uc).execute(DIRETORA)
        assert "Coord Vendas" not in nomes(r["coordenadores"])

    def test_nao_aparece_para_o_gerente_da_frente_dele(self, uc):
        r = self._uc_com_vendas(uc).execute(GERENTE)
        assert "Coord Vendas" not in nomes(r["coordenadores"])

    def test_coordenador_comum_continua_aparecendo(self, uc):
        r = self._uc_com_vendas(uc).execute(DIRETORA)
        assert "Coord Tech" in nomes(r["coordenadores"])

    def test_a_carga_continua_saindo_dos_projetos(self, uc):
        """A população mudou, a medição não: quem está no sinérgico conta 1,
        quem não está conta 0."""
        por_nome = {l["nome"]: l for l in uc.execute(GERENTE)["consultores"]}
        assert por_nome["Cons Tech Alocado"]["total"] == 1
        assert por_nome["Cons Tech Livre"]["total"] == 0

    def test_frente_id_de_outro_gerente_nao_amplia(self, uc):
        """§7.5: o `?frente_id=` do gerente no máximo RESTRINGE dentro das
        frentes dele. Pedir Business cai de volta em Tech, nunca abre."""
        r = uc.execute(GERENTE, frente_id=BUSINESS)
        assert "Cons Business" not in nomes(r["consultores"])
        assert "Cons Tech Livre" in nomes(r["consultores"])

    def test_capacidade_so_conta_a_frente_dele(self, uc):
        """O card de capacidade é alimentado pelas MESMAS linhas das tabelas —
        se Business escapasse para elas, escaparia para o card também."""
        r = uc.execute(GERENTE)
        assert [l["frente_nome"] for l in r["capacidade"]["por_frente"]] == ["Tech"]


class TestPopulacaoDaDiretoria:
    def test_ve_o_nucleo_inteiro(self, uc):
        """Sem filtro, a diretoria de projetos enxerga tudo — inclusive quem
        não está em projeto nenhum, em qualquer frente."""
        r = uc.execute(DIRETORA)
        assert nomes(r["consultores"]) == {
            "Cons Tech Alocado",
            "Cons Tech Livre",
            "Cons Business",
        }


class TestDiretoriaForaDasTabelas:
    @pytest.mark.parametrize("quem", [GERENTE, DIRETORA])
    def test_nenhum_cargo_de_diretoria_aparece(self, uc, quem):
        """Os três cargos não pegam projeto: listá-los inflava a capacidade
        com vagas que ninguém vai ocupar."""
        r = uc.execute(quem)
        assert "Diretora" not in nomes(r["coordenadores"]) | nomes(r["consultores"])
