"""Quem pode trocar o TIPO de um escopo vendido ou os dias úteis vendidos.

Mais estreito que `exigir_pode_editar_escopos` (que libera o coordenador do
projeto): esses dois campos ficam só com a diretoria de projetos, mesmo que a
request também mande `ordem` ou `calendario`, que continuam liberados pro
coordenador.
"""

from types import SimpleNamespace

import pytest

from src.use_cases.projeto_escopo.permissao_escopo import exigir_pode_editar_tipo_e_dias
from src.utils.exceptions import RegraDeNegocioError

DIRETOR = SimpleNamespace(id=1, posicao="diretor_projetos")
COORDENADOR = SimpleNamespace(id=2, posicao="coordenador")
GERENTE = SimpleNamespace(id=3, posicao="gerente")


class TestCamposRestritos:
    @pytest.mark.parametrize("campo", ["escopo_id", "nome_customizado", "dias_uteis_vendidos"])
    def test_diretoria_de_projetos_pode(self, campo):
        exigir_pode_editar_tipo_e_dias(DIRETOR, {campo: "qualquer"})

    @pytest.mark.parametrize("campo", ["escopo_id", "nome_customizado", "dias_uteis_vendidos"])
    def test_coordenador_nao_pode(self, campo):
        with pytest.raises(RegraDeNegocioError, match="restrito à diretoria de projetos"):
            exigir_pode_editar_tipo_e_dias(COORDENADOR, {campo: "qualquer"})

    def test_gerente_nao_pode(self):
        with pytest.raises(RegraDeNegocioError, match="restrito à diretoria de projetos"):
            exigir_pode_editar_tipo_e_dias(GERENTE, {"dias_uteis_vendidos": 30})


class TestCamposLivres:
    def test_coordenador_pode_reordenar(self):
        exigir_pode_editar_tipo_e_dias(COORDENADOR, {"ordem": 2})

    def test_coordenador_pode_trocar_calendario(self):
        exigir_pode_editar_tipo_e_dias(COORDENADOR, {"calendario": "Engenharias"})

    def test_coordenador_pode_mudar_entrega_planejada(self):
        exigir_pode_editar_tipo_e_dias(COORDENADOR, {"data_entrega_planejada": "2026-10-10"})

    def test_nao_mandar_campo_nenhum_nao_precisa_de_diretoria(self):
        exigir_pode_editar_tipo_e_dias(COORDENADOR, {})


class TestMisturaDeCampos:
    def test_um_campo_restrito_junto_de_um_livre_ainda_exige_diretoria(self):
        with pytest.raises(RegraDeNegocioError):
            exigir_pode_editar_tipo_e_dias(COORDENADOR, {"ordem": 1, "dias_uteis_vendidos": 20})
