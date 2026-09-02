"""O PDF da proposta gravado no banco, não em disco.

O disco do servidor de deploy é efêmero: um arquivo salvo lá some no próximo
redeploy, e os projetos ficavam com um caminho apontando para o nada. O
conteúdo passou a morar em `projeto.anexo_proposta_conteudo`, como o envio de
PDI já fazia.
"""

import io

import pytest

from src.use_cases.projeto.upload_anexo_proposta import (
    TAMANHO_MAXIMO_BYTES,
    UploadAnexoPropostaUseCase,
)
from src.utils.exceptions import RegraDeNegocioError

PDF_VALIDO = b"%PDF-1.7\n" + b"conteudo qualquer de pdf\n" + b"%%EOF"


class ProjetoFake:
    def __init__(self, **campos):
        self.id = 1
        self.link_proposta = campos.get("link_proposta")
        self.anexo_proposta_conteudo = campos.get("anexo_proposta_conteudo")
        self.anexo_proposta_nome = campos.get("anexo_proposta_nome")


class RepoFake:
    def __init__(self, projeto):
        self._projeto = projeto
        self.updates = []

    def get_by_id(self, projeto_id):
        return self._projeto if self._projeto and projeto_id == self._projeto.id else None

    def update(self, projeto_id, **campos):
        self.updates.append(campos)
        for k, v in campos.items():
            setattr(self._projeto, k, v)
        return self._projeto


class ArquivoFake:
    def __init__(self, conteudo: bytes, filename: str = "proposta.pdf"):
        self.filename = filename
        self.file = io.BytesIO(conteudo)


def montar(projeto=None):
    uc = UploadAnexoPropostaUseCase.__new__(UploadAnexoPropostaUseCase)
    uc.db = None
    uc.repository = RepoFake(projeto or ProjetoFake(link_proposta="http://drive/x"))
    return uc


class TestGravaNoBanco:
    def test_conteudo_vai_para_a_coluna_e_o_link_e_zerado(self):
        uc = montar()
        r = uc.execute(1, ArquivoFake(PDF_VALIDO, "Proposta Final.pdf"))

        assert r == {"anexo_proposta_nome": "Proposta Final.pdf"}
        gravado = uc.repository.updates[-1]
        assert gravado["anexo_proposta_conteudo"] == PDF_VALIDO
        assert gravado["anexo_proposta_nome"] == "Proposta Final.pdf"
        assert gravado["link_proposta"] is None

    def test_reenviar_sobrescreve_o_conteudo_anterior(self):
        projeto = ProjetoFake(
            anexo_proposta_conteudo=b"%PDF-antigo", anexo_proposta_nome="velho.pdf"
        )
        uc = montar(projeto)
        novo = b"%PDF-1.4 novo\n%%EOF"
        uc.execute(1, ArquivoFake(novo, "novo.pdf"))

        assert projeto.anexo_proposta_conteudo == novo
        assert projeto.anexo_proposta_nome == "novo.pdf"


class TestValidacao:
    def test_recusa_extensao_que_nao_e_pdf(self):
        uc = montar()
        with pytest.raises(RegraDeNegocioError, match="precisa ser um PDF"):
            uc.execute(1, ArquivoFake(PDF_VALIDO, "proposta.docx"))

    def test_recusa_arquivo_vazio(self):
        uc = montar()
        with pytest.raises(RegraDeNegocioError, match="vazio"):
            uc.execute(1, ArquivoFake(b"", "proposta.pdf"))

    def test_recusa_quem_nao_comeca_com_a_assinatura_pdf(self):
        uc = montar()
        with pytest.raises(RegraDeNegocioError, match="não é um PDF válido"):
            uc.execute(1, ArquivoFake(b"PK\x03\x04 zip disfarcado", "proposta.pdf"))

    def test_recusa_acima_do_limite(self):
        uc = montar()
        gigante = b"%PDF-" + b"0" * (TAMANHO_MAXIMO_BYTES + 1)
        with pytest.raises(RegraDeNegocioError, match="15MB"):
            uc.execute(1, ArquivoFake(gigante, "proposta.pdf"))

    def test_projeto_inexistente(self):
        uc = montar()
        uc.repository = RepoFake(None)
        with pytest.raises(RegraDeNegocioError, match="não encontrado"):
            uc.execute(99, ArquivoFake(PDF_VALIDO))
