"""Abrir um documento jurídico dentro de um projeto (§ Contratos, 2026-09-16).

Mesmo padrão dos vizinhos de `candidatura`: `__new__` + repositórios fake,
sem sessão de banco — aqui o que se prende é a regra de "que tipos ainda
cabem" e a herança de dados do Contrato de Prestação pros demais.
"""

from types import SimpleNamespace

import pytest

from src.use_cases.documento_contratual.abrir_documento import AbrirDocumentoContratualUseCase
from src.utils.exceptions import RegraDeNegocioError


class FakeProjetoRepo:
    def __init__(self, projeto):
        self._projeto = projeto

    def get_by_id(self, _id):
        return self._projeto


class FakeDocumentoRepo:
    def __init__(self, existentes=()):
        # existentes: [(tipo, dados)]
        self._existentes = {tipo: SimpleNamespace(tipo=tipo, dados=dados) for tipo, dados in existentes}
        self.criados = []

    def list_by_projeto(self, _projeto_id):
        return list(self._existentes.values())

    def get_by_projeto_e_tipo(self, _projeto_id, tipo):
        return self._existentes.get(tipo)

    def create(self, **kwargs):
        self.criados.append(kwargs)
        return SimpleNamespace(id=len(self.criados), **kwargs)


def montar(existentes=()):
    projeto = SimpleNamespace(id=1, nome="ACME LTDA")
    uc = AbrirDocumentoContratualUseCase.__new__(AbrirDocumentoContratualUseCase)
    uc.db = None
    uc.projetos = FakeProjetoRepo(projeto)
    documentos = FakeDocumentoRepo(existentes)
    uc.documentos = documentos
    return uc, documentos


class TestTiposDisponiveis:
    def test_projeto_vazio_oferece_contrato_e_os_quatro_adicionais(self):
        uc, _ = montar()
        assert uc.tipos_disponiveis(1) == ["contrato", "aditivo", "nda", "uso_imagem", "tep"]

    def test_com_contrato_ja_aberto_ele_some_da_lista(self):
        uc, _ = montar(existentes=[("contrato", {})])
        assert "contrato" not in uc.tipos_disponiveis(1)

    def test_tep_nao_depende_do_contrato_existir(self):
        uc, _ = montar()
        assert "tep" in uc.tipos_disponiveis(1)

    def test_tipo_ja_aberto_nao_se_repete(self):
        uc, _ = montar(existentes=[("nda", {})])
        tipos = uc.tipos_disponiveis(1)
        assert "nda" not in tipos
        assert tipos.count("nda") == 0


class TestAbrir:
    def test_contrato_nasce_em_branco(self):
        uc, documentos = montar()
        uc.execute(1, "contrato")
        criado = documentos.criados[0]
        assert criado["status"] == "aguardando_preenchimento"
        assert criado["confirmado"] is False
        assert criado["dados"]["contratante"]["razao_social"] == ""

    def test_nda_herda_contratante_e_testemunhas_do_contrato(self):
        dados_contrato = {
            "contratante": {"razao_social": "ACME LTDA", "cnpj": "00.000.000/0001-00"},
            "testemunhas": [{"nome": "Fulano", "cpf": "111"}],
        }
        uc, documentos = montar(existentes=[("contrato", dados_contrato)])

        uc.execute(1, "nda")

        dados_nda = documentos.criados[0]["dados"]
        assert dados_nda["contratante"]["razao_social"] == "ACME LTDA"
        assert dados_nda["testemunhas"] == [{"nome": "Fulano", "cpf": "111"}]

    def test_sem_contrato_de_ps_o_adicional_nasce_em_branco(self):
        """Projeto institucional, sem venda: NDA/Uso de Imagem/Aditivo ainda
        podem ser abertos, só não têm de onde herdar."""
        uc, documentos = montar()

        uc.execute(1, "uso_imagem")

        dados = documentos.criados[0]["dados"]
        assert dados["contratante"]["razao_social"] == ""
        assert dados["contexto"] == "ACME LTDA"  # chute a partir do nome do projeto

    def test_tipo_ja_existente_e_recusado(self):
        uc, _ = montar(existentes=[("contrato", {})])
        with pytest.raises(RegraDeNegocioError, match="Não é possível iniciar"):
            uc.execute(1, "contrato")

    def test_tipo_desconhecido_e_recusado(self):
        uc, _ = montar()
        with pytest.raises(RegraDeNegocioError, match="desconhecido"):
            uc.execute(1, "orcamento")

    def test_projeto_inexistente_e_recusado(self):
        uc, _ = montar()
        uc.projetos = FakeProjetoRepo(None)
        with pytest.raises(RegraDeNegocioError, match="Projeto não encontrado"):
            uc.execute(999, "contrato")
