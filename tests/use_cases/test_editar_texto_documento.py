"""Editar o texto do rascunho gerado, parágrafo por parágrafo (§ Contratos, 2026-09-18).

O conteúdo mora no banco (`docx_conteudo`/`pdf_conteudo`), não em disco — o
use case grava num arquivo temporário só pra `editar_docx.py` manipular
(`python-docx` não edita bytes em memória). O monkeypatch fica só na
conversão pra PDF (dependência externa do LibreOffice, não é o que este
teste cobre) — escreve um arquivo .pdf de mentira no mesmo lugar, pra ler os
bytes de volta funcionar igual ao caminho real.
"""

import io
from types import SimpleNamespace

import pytest
from docx import Document

import src.use_cases.documento_contratual.editar_texto as editar_texto_mod
from src.use_cases.documento_contratual.editar_texto import (
    EditarTextoDocumentoContratualUseCase,
    GetParagrafosEditaveisUseCase,
)
from src.utils.exceptions import RegraDeNegocioError


class FakeDocumentoRepo:
    def __init__(self, documento):
        self._documento = documento

    def get_by_id(self, _id):
        return self._documento


class FakeVersaoRepo:
    def __init__(self, versao):
        self._versao = versao
        self.atualizada_com = None

    def ultima_versao_obj(self, _documento_id):
        return self._versao

    def update(self, _versao_id, **kwargs):
        self.atualizada_com = kwargs
        for chave, valor in kwargs.items():
            setattr(self._versao, chave, valor)
        return self._versao


def _fake_converter_docx_para_pdf(docx_path: str) -> str:
    pdf_path = docx_path[:-5] + ".pdf"
    with open(pdf_path, "wb") as f:
        f.write(b"%PDF-1.4 conteudo de mentira")
    return pdf_path


def _docx_bytes(texto="Cláusula 1ª Texto original."):
    doc = Document()
    doc.add_paragraph(texto)
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def documento(status="em_revisao_interna"):
    return SimpleNamespace(id=1, status=status)


def versao_com(docx_conteudo=None):
    return SimpleNamespace(id=9, docx_conteudo=docx_conteudo if docx_conteudo is not None else _docx_bytes())


def montar_editar(doc, versao, monkeypatch):
    monkeypatch.setattr(editar_texto_mod, "converter_docx_para_pdf", _fake_converter_docx_para_pdf)
    uc = EditarTextoDocumentoContratualUseCase.__new__(EditarTextoDocumentoContratualUseCase)
    uc.documentos = FakeDocumentoRepo(doc)
    uc.versoes = FakeVersaoRepo(versao)
    return uc


def montar_get(doc, versao):
    uc = GetParagrafosEditaveisUseCase.__new__(GetParagrafosEditaveisUseCase)
    uc.documentos = FakeDocumentoRepo(doc)
    uc.versoes = FakeVersaoRepo(versao)
    return uc


class TestGetParagrafosEditaveis:
    def test_le_do_conteudo_da_ultima_versao(self):
        uc = montar_get(documento(), versao_com())

        paragrafos = uc.execute(1)

        assert paragrafos == [{"ref": 0, "texto": "Cláusula 1ª Texto original."}]

    def test_recusa_fora_de_status_de_edicao(self):
        uc = montar_get(documento(status="aguardando_aprovacao_cliente"), versao_com())

        with pytest.raises(RegraDeNegocioError, match="editar o texto"):
            uc.execute(1)

    def test_recusa_sem_versao_gerada(self):
        uc = montar_get(documento(), None)

        with pytest.raises(RegraDeNegocioError, match="Nenhum rascunho"):
            uc.execute(1)


class TestEditarTexto:
    def test_aplica_e_converte_pra_pdf(self, monkeypatch):
        versao = versao_com()
        uc = montar_editar(documento(), versao, monkeypatch)

        resultado = uc.execute(1, {0: "Cláusula 1ª Texto revisado."})

        assert resultado == {"alterados": 1}
        docx_editado = Document(io.BytesIO(uc.versoes.atualizada_com["docx_conteudo"]))
        assert docx_editado.paragraphs[0].text == "Cláusula 1ª Texto revisado."
        assert uc.versoes.atualizada_com["pdf_conteudo"] == b"%PDF-1.4 conteudo de mentira"

    def test_recusa_fora_de_status_de_edicao(self, monkeypatch):
        uc = montar_editar(documento(status="assinado_e_arquivado"), versao_com(), monkeypatch)

        with pytest.raises(RegraDeNegocioError, match="editar o texto"):
            uc.execute(1, {0: "x"})

    def test_recusa_sem_edicoes(self, monkeypatch):
        uc = montar_editar(documento(), versao_com(), monkeypatch)

        with pytest.raises(RegraDeNegocioError, match="Nenhuma edição"):
            uc.execute(1, {})
