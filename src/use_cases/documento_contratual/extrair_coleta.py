"""Pré-preencher um documento jurídico a partir do .docx de Coleta de Dados
(§ Contratos).

⭐ 2026-09-18 — não persiste nada: devolve `{dados, pendencias}` pro front
aplicar no formulário (a pessoa ainda revisa e confirma, como qualquer
preenchimento manual).
"""

from src.documentos_contratuais.extrair_coleta import extrair_dados_coleta_detalhado
from src.repositories.projeto_repository import ProjetoRepository
from src.utils.adaptar_coleta_para_tipo import adaptar_coleta_para_tipo
from src.utils.exceptions import RegraDeNegocioError
from src.utils.status_documento_contratual import TipoDocumentoContratual


class ExtrairColetaUseCase:
    def __init__(self, db):
        self.projetos = ProjetoRepository(db)

    def execute(self, projeto_id: int, tipo: str, conteudo: bytes) -> dict:
        projeto = self.projetos.get_by_id(projeto_id)
        if not projeto:
            raise RegraDeNegocioError("Projeto não encontrado.")
        try:
            TipoDocumentoContratual(tipo)
        except ValueError:
            raise RegraDeNegocioError(f'Tipo de documento desconhecido: "{tipo}".')
        if not conteudo:
            raise RegraDeNegocioError("Envie um arquivo .docx.")

        try:
            dados_contrato, pendencias = extrair_dados_coleta_detalhado(conteudo)
        except ValueError as e:
            raise RegraDeNegocioError(str(e))

        dados, mensagens = adaptar_coleta_para_tipo(tipo, dados_contrato, pendencias, projeto.nome)
        return {"dados": dados, "pendencias": mensagens}
