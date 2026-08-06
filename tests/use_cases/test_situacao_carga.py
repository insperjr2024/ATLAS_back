"""A escala de situações de carga (§7.3).

A diretoria descreve, por papel, o que cada quantidade de projetos significa —
"0 a 1 disponível, 2 ideal, 3 ou mais carga alta". Não é um limite único: um
número só não distingue "está no ponto" de "passou do ponto".

⭐ **Cada situação guarda só o MÍNIMO**, e vale até o mínimo da próxima. Isso
torna buraco e sobreposição impossíveis de configurar, em vez de virar
validação: com `min` e `max` livres, daria para criar "0 a 1" e "3 ou mais" e
deixar quem tem 2 projetos sem situação nenhuma.
"""

from types import SimpleNamespace

import pytest

from src.repositories.situacao_carga_repository import faixa_mais_alta, resolver
from src.use_cases.situacao_carga.gerenciar_situacoes import (
    AtualizarSituacaoRequest,
    SituacaoCargaUseCase,
)
from src.utils.exceptions import RegraDeNegocioError


def situacao(nome, minimo, tom="neutro"):
    return SimpleNamespace(nome=nome, min_projetos=minimo, tom=tom)


#: A escala que a diretoria descreveu para consultor. São sempre três faixas —
#: não há criar nem excluir, só editar nome, mínimo e cor.
ESCALA = [
    situacao("Disponível", 0, "ok"),
    situacao("Quantidade ideal", 2),
    situacao("Demanda alta", 3, "alerta"),
]


class TestResolucao:
    @pytest.mark.parametrize(
        "total,esperado",
        [
            (0, "Disponível"),
            (1, "Disponível"),      # a faixa do zero vai até o mínimo seguinte
            (2, "Quantidade ideal"),
            (3, "Demanda alta"),
            (10, "Demanda alta"),     # a última faixa é aberta para cima
        ],
    )
    def test_cada_quantidade_cai_na_faixa_certa(self, total, esperado):
        assert resolver(ESCALA, total).nome == esperado

    def test_a_ordem_da_lista_nao_importa(self):
        """A resolução ordena por conta própria — quem chama não precisa saber."""
        embaralhada = [ESCALA[2], ESCALA[0], ESCALA[1]]
        assert resolver(embaralhada, 2).nome == "Quantidade ideal"

    def test_escala_vazia_devolve_none(self):
        """Só acontece se o papel não tiver situação cadastrada."""
        assert resolver([], 3) is None

    def test_uma_situacao_so_cobre_tudo(self):
        assert resolver([situacao("Alocado", 0)], 99).nome == "Alocado"


class TestSemBuracos:
    """O ponto da modelagem: qualquer quantidade cai em alguma faixa."""

    @pytest.mark.parametrize("total", range(0, 30))
    def test_nenhuma_quantidade_fica_sem_situacao(self, total):
        assert resolver(ESCALA, total) is not None

    def test_escala_esparsa_tambem_cobre_tudo(self):
        """Mínimos distantes não abrem buraco — a faixa anterior se estica."""
        esparsa = [situacao("Leve", 0), situacao("Pesado", 20)]
        assert resolver(esparsa, 19).nome == "Leve"
        assert resolver(esparsa, 20).nome == "Pesado"


class TestEscalaQueNaoComecaEmZero:
    """O mínimo da primeira faixa é editável: subi-lo deixa os menos carregados
    sem rótulo, que é como a diretoria diz "abaixo disso não rotulo nada"."""

    COMECA_EM_DOIS = [situacao("Quantidade ideal", 2), situacao("Demanda alta", 3)]

    @pytest.mark.parametrize("total", [0, 1])
    def test_abaixo_do_menor_minimo_fica_sem_situacao(self, total):
        assert resolver(self.COMECA_EM_DOIS, total) is None

    def test_de_dois_em_diante_resolve_normalmente(self):
        assert resolver(self.COMECA_EM_DOIS, 2).nome == "Quantidade ideal"
        assert resolver(self.COMECA_EM_DOIS, 3).nome == "Demanda alta"


class TestFaixaMaisAlta:
    """Quem entra no card de demanda alta sai daqui.

    ⭐ A decisão é pela POSIÇÃO na escala, não pelo nome nem pela cor. Nome e cor
    são livres, então decidir por eles deixaria o card à mercê de alguém
    escrever "Carga alta" com essa grafia exata ou lembrar de pintar de
    vermelho — e um card vazio parece "ninguém sobrecarregado", que é a leitura
    errada e silenciosa.
    """

    def test_e_a_de_maior_minimo(self):
        assert faixa_mais_alta(ESCALA).nome == "Demanda alta"

    def test_a_ordem_da_lista_nao_importa(self):
        assert faixa_mais_alta([ESCALA[1], ESCALA[2], ESCALA[0]]).nome == "Demanda alta"

    def test_independe_do_nome(self):
        renomeada = [situacao("Tranquilo", 0), situacao("Sufocado", 3)]
        assert faixa_mais_alta(renomeada).nome == "Sufocado"

    def test_independe_da_cor(self):
        """Escala inteira em verde: o card continua achando a faixa do topo."""
        tudo_verde = [situacao("Leve", 0, "ok"), situacao("Cheio", 3, "ok")]
        assert faixa_mais_alta(tudo_verde).nome == "Cheio"

    def test_bate_com_a_resolucao_de_quem_tem_muito_projeto(self):
        """A pessoa mais carregada tem que cair exatamente na faixa do topo,
        senão o card e a coluna Situação da tabela contariam histórias
        diferentes sobre a mesma pessoa."""
        assert resolver(ESCALA, 99) is faixa_mais_alta(ESCALA)

    def test_escala_vazia_devolve_none(self):
        assert faixa_mais_alta([]) is None


class FakeRepositorio:
    """A escala do coordenador como a diretoria a descreveu: 4 é o ideal."""

    def __init__(self):
        self.faixas = [
            SimpleNamespace(id=1, papel="coordenador", nome="Disponível", min_projetos=0, tom="ok"),
            SimpleNamespace(id=2, papel="coordenador", nome="Quantidade ideal", min_projetos=4, tom="neutro"),
            SimpleNamespace(id=3, papel="coordenador", nome="Carga alta", min_projetos=5, tom="alerta"),
        ]

    def get_by_id(self, id_):
        return next((f for f in self.faixas if f.id == id_), None)

    def listar_por_papel(self, papel):
        return [f for f in self.faixas if f.papel == papel]

    def update(self, id_, **dados):
        faixa = self.get_by_id(id_)
        for campo, valor in dados.items():
            setattr(faixa, campo, valor)
        return faixa


def montar_use_case():
    uc = SituacaoCargaUseCase.__new__(SituacaoCargaUseCase)
    uc.repository = FakeRepositorio()
    return uc


class TestFaixaNaoUltrapassaAVizinha:
    """⭐ O mínimo é editável, mas a ORDEM das três faixas é fixa.

    Sem isso, baixar o mínimo de "Carga alta" para debaixo de "Quantidade
    ideal" troca as duas de lugar: a tela reordena as linhas e quem tem mais
    projetos passa a ser rotulado com o nome do meio, enquanto o card de demanda
    alta — que escolhe pela posição — lista essas mesmas pessoas. As duas telas
    contariam histórias diferentes sobre a mesma pessoa.

    Aconteceu de verdade em 2026-08-06: "Carga alta" de coordenador foi parar em
    3, abaixo de "Quantidade ideal" (4).
    """

    def test_a_faixa_alta_nao_desce_abaixo_da_do_meio(self):
        uc = montar_use_case()
        with pytest.raises(RegraDeNegocioError) as erro:
            uc.atualizar(3, AtualizarSituacaoRequest(min_projetos=3))
        assert "acima de 4" in str(erro.value)

    def test_a_do_meio_nao_sobe_acima_da_alta(self):
        uc = montar_use_case()
        with pytest.raises(RegraDeNegocioError):
            uc.atualizar(2, AtualizarSituacaoRequest(min_projetos=6))

    def test_minimo_repetido_tambem_e_recusado(self):
        """Dois mínimos iguais tornariam a resolução ambígua — a mesma regra
        cobre, porque encostar na vizinha já é ultrapassar."""
        uc = montar_use_case()
        with pytest.raises(RegraDeNegocioError):
            uc.atualizar(1, AtualizarSituacaoRequest(min_projetos=4))

    @pytest.mark.parametrize(
        "id_faixa,novo",
        [
            (1, 3),   # Disponível sobe até encostar em Quantidade ideal
            (2, 2),   # Quantidade ideal desce dentro do espaço livre
            (3, 9),   # Carga alta sobe à vontade: não tem teto
        ],
    )
    def test_mover_dentro_do_espaco_livre_continua_valendo(self, id_faixa, novo):
        """A regra recusa ULTRAPASSAGEM, não ajuste — que é o que a diretoria
        de fato faz quando uma frente muda de tamanho."""
        uc = montar_use_case()
        assert uc.atualizar(id_faixa, AtualizarSituacaoRequest(min_projetos=novo))["min_projetos"] == novo

    def test_renomear_nao_esbarra_na_regra(self):
        uc = montar_use_case()
        assert uc.atualizar(3, AtualizarSituacaoRequest(nome="Sufocado"))["nome"] == "Sufocado"

    def test_a_ordem_sobrevive_a_qualquer_edicao_aceita(self):
        """O que a regra realmente protege: a última faixa continua sendo a
        última, que é de onde sai o card de demanda alta."""
        uc = montar_use_case()
        uc.atualizar(1, AtualizarSituacaoRequest(min_projetos=2))
        uc.atualizar(3, AtualizarSituacaoRequest(min_projetos=7))
        escala = uc.repository.listar_por_papel("coordenador")
        assert faixa_mais_alta(escala).nome == "Carga alta"
