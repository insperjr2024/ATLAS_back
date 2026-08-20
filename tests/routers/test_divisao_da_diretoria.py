"""A divisão da diretoria em três cargos (2026-08-20) — quem passa em cada porta.

Antes existia `diretor`, um cargo só, e 43 rotas presas nele. A divisão criou
`diretor_projetos` (herdeiro dos poderes), `diretor_pessoas` (gente +
Avaliação de Desempenho) e `diretor` (só visualização).

⭐ **O caso que este arquivo existe para travar é o `diretor` de hoje.** Ele
mantém o nome do cargo que mandava em tudo, e a única coisa que o impede de
continuar mandando é cada guarda ter sido reapontada uma a uma. Uma que
escape não gera erro nenhum: gera um diretor "só-visualização" arquivando
projeto.

As guardas são dependências do FastAPI e devolvem o usuário ou levantam 403 —
dá para exercitá-las direto, sem subir rota nem banco.
"""

import pytest
from fastapi import HTTPException
from types import SimpleNamespace

from src.middlewares.authorization import (
    DIRETORIA,
    DIRETORIA_DE_PESSOAS,
    DIRETORIA_DE_PROJETOS,
    eh_diretoria,
    eh_diretoria_de_projetos,
    eh_lideranca,
    require_diretor_projetos,
    require_diretoria_de_pessoas,
    require_gestao,
    require_lideranca,
)

TODAS = ("diretor_projetos", "diretor_pessoas", "diretor", "gerente", "coordenador", "consultor")


def quem(posicao: str):
    return SimpleNamespace(id=1, nome=f"Fulano {posicao}", posicao=posicao)


def passa(guarda, posicao: str) -> bool:
    """A guarda deixa esta posição entrar?"""
    try:
        guarda(current_user=quem(posicao))
        return True
    except HTTPException as e:
        assert e.status_code == 403, f"esperava 403, veio {e.status_code}"
        return False


class TestOsTresCargosExistemESaoDistintos:
    def test_os_tres_estao_em_diretoria(self):
        assert set(DIRETORIA) == {"diretor_projetos", "diretor_pessoas", "diretor"}

    def test_so_um_herda_os_poderes_de_projeto(self):
        assert DIRETORIA_DE_PROJETOS == ("diretor_projetos",)

    def test_as_acoes_de_pessoas_sao_de_dois(self):
        assert set(DIRETORIA_DE_PESSOAS) == {"diretor_projetos", "diretor_pessoas"}


class TestDiretorSoVisualizacao:
    """O cargo `diretor` não conduz NADA. É o coração da divisão."""

    @pytest.mark.parametrize(
        "guarda",
        [require_diretor_projetos, require_diretoria_de_pessoas, require_gestao, require_lideranca],
    )
    def test_e_barrado_em_toda_guarda_de_acao(self, guarda):
        assert passa(guarda, "diretor") is False

    def test_mas_enxerga_o_portfolio_inteiro(self):
        """Ser barrado nas ações não pode tirar dele a visão — é o cargo de
        acompanhar, e sem o recorte amplo ele não veria projeto nenhum."""
        assert eh_diretoria(quem("diretor")) is True

    def test_nao_e_lideranca(self):
        """`eh_lideranca` era `posicao != "consultor"`, que o daria como
        liderança sem ninguém notar."""
        assert eh_lideranca(quem("diretor")) is False


class TestDiretorDeGestaoDePessoas:
    def test_faz_as_acoes_de_gente(self):
        assert passa(require_diretoria_de_pessoas, "diretor_pessoas") is True

    @pytest.mark.parametrize("guarda", [require_diretor_projetos, require_gestao, require_lideranca])
    def test_nao_conduz_projeto(self, guarda):
        assert passa(guarda, "diretor_pessoas") is False

    def test_enxerga_o_portfolio_inteiro(self):
        assert eh_diretoria(quem("diretor_pessoas")) is True


class TestDiretorDeProjetos:
    """Herdou o `diretor` de antes: passa em tudo que ele passava."""

    @pytest.mark.parametrize(
        "guarda",
        [require_diretor_projetos, require_diretoria_de_pessoas, require_gestao, require_lideranca],
    )
    def test_passa_em_todas(self, guarda):
        assert passa(guarda, "diretor_projetos") is True

    def test_e_o_unico_com_o_override_de_projeto(self):
        for posicao in TODAS:
            esperado = posicao == "diretor_projetos"
            assert eh_diretoria_de_projetos(quem(posicao)) is esperado


class TestOsOutrosCargosNaoMudaram:
    """A divisão não podia mexer em quem não é diretoria — regressão silenciosa
    fácil de cometer ao reescrever as guardas em bloco."""

    def test_gerente_segue_na_gestao_e_na_lideranca(self):
        assert passa(require_gestao, "gerente") is True
        assert passa(require_lideranca, "gerente") is True
        assert passa(require_diretor_projetos, "gerente") is False

    def test_coordenador_segue_so_na_lideranca(self):
        assert passa(require_lideranca, "coordenador") is True
        assert passa(require_gestao, "coordenador") is False

    def test_consultor_nao_passa_em_nenhuma(self):
        for guarda in (
            require_diretor_projetos,
            require_diretoria_de_pessoas,
            require_gestao,
            require_lideranca,
        ):
            assert passa(guarda, "consultor") is False

    def test_ninguem_de_fora_da_diretoria_entra_em_eh_diretoria(self):
        for posicao in ("gerente", "coordenador", "consultor"):
            assert eh_diretoria(quem(posicao)) is False
