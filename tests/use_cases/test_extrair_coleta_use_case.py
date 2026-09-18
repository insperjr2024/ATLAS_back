"""O use case que liga upload -> extração -> adaptação por tipo, sem persistir."""

from types import SimpleNamespace

import pytest
from docx import Document

from src.use_cases.documento_contratual.extrair_coleta import ExtrairColetaUseCase
from src.utils.exceptions import RegraDeNegocioError


class FakeProjetoRepo:
    def __init__(self, projeto):
        self._projeto = projeto

    def get_by_id(self, _id):
        return self._projeto


def _docx_minimo():
    import io

    doc = Document()
    tabela = doc.add_table(rows=0, cols=2)
    header = tabela.add_row()
    header.cells[0].text = "INFORMAÇÕES DA CLIENTE"
    header.cells[1].text = "INFORMAÇÕES DA CLIENTE"
    row = tabela.add_row()
    row.cells[0].text = "Razão Social"
    row.cells[1].text = "empresa exemplo"
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def montar(projeto):
    uc = ExtrairColetaUseCase.__new__(ExtrairColetaUseCase)
    uc.projetos = FakeProjetoRepo(projeto)
    return uc


def test_extrai_e_adapta_pro_tipo_pedido():
    uc = montar(SimpleNamespace(id=1, nome="Projeto Alfa"))

    resultado = uc.execute(1, "nda", _docx_minimo())

    assert resultado["dados"]["contratante"]["razao_social"] == "EMPRESA EXEMPLO"
    assert "financeiro" not in resultado["dados"]  # NDA não herda financeiro
    assert isinstance(resultado["pendencias"], list)


def test_recusa_projeto_inexistente():
    uc = montar(None)

    with pytest.raises(RegraDeNegocioError, match="Projeto não encontrado"):
        uc.execute(1, "contrato", _docx_minimo())


def test_recusa_tipo_desconhecido():
    uc = montar(SimpleNamespace(id=1, nome="Projeto Alfa"))

    with pytest.raises(RegraDeNegocioError, match="desconhecido"):
        uc.execute(1, "tipo_invalido", _docx_minimo())


def test_recusa_sem_arquivo():
    uc = montar(SimpleNamespace(id=1, nome="Projeto Alfa"))

    with pytest.raises(RegraDeNegocioError, match="Envie um arquivo"):
        uc.execute(1, "contrato", b"")


def test_recusa_docx_invalido():
    uc = montar(SimpleNamespace(id=1, nome="Projeto Alfa"))

    with pytest.raises(RegraDeNegocioError, match="não é um .docx válido"):
        uc.execute(1, "contrato", b"nao e um docx")
