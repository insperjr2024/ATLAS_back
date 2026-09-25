"""Apagar um documento jurídico de vez — mesmo já assinado e arquivado
(§ Contratos, 2026-09-24, a pedido).

⚠ Diferente de `deletar_documento.py`: aquele é "abri por engano", só serve
enquanto o documento nunca saiu de "aguardando preenchimento". Este é o
oposto — a diretoria erra um contrato, ou precisa tirar algo que nunca devia
ter sido gerado, DEPOIS de confirmado, revisado, aprovado ou até assinado. A
permissão pra isso mora no router (só `eh_diretoria_de_projetos`); esta
classe só cuida de apagar por inteiro sem violar FK.

⚠ **Nunca apaga o `projeto`.** `documento_contratual.projeto_id` aponta PRO
projeto — a seta é nessa direção, não ao contrário. Apagar o documento não
tem como levar o projeto junto, mesmo sendo o TEP/Contrato que o originou;
quem quiser excluir o projeto em si usa a rota própria dele.
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.repositories.documento_contratual_repository import DocumentoContratualRepository
from src.repositories.documento_contratual_versao_repository import (
    DocumentoContratualVersaoRepository,
)
from src.repositories.solicitacao_alteracao_contratual_repository import (
    SolicitacaoAlteracaoContratualRepository,
)
from src.repositories.token_aprovacao_contratual_repository import (
    TokenAprovacaoContratualRepository,
)
from src.utils.exceptions import RegraDeNegocioError, ResourceInUseError


class HardDeletarDocumentoContratualUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.documentos = DocumentoContratualRepository(db)
        self.versoes = DocumentoContratualVersaoRepository(db)
        self.solicitacoes = SolicitacaoAlteracaoContratualRepository(db)
        self.tokens = TokenAprovacaoContratualRepository(db)

    def execute(self, documento_id: int) -> None:
        documento = self.documentos.get_by_id(documento_id)
        if not documento:
            raise RegraDeNegocioError("Documento não encontrado.")

        # Ordem importa: `solicitacao_alteracao_contratual` e
        # `token_aprovacao_contratual` referenciam tanto o documento quanto
        # a versão (`versao_id`) — têm que sair ANTES de
        # `documento_contratual_versao`, senão a FK da versão barra.
        for solicitacao in self.solicitacoes.list_by_documento(documento_id):
            self.db.delete(solicitacao)
        for token in self.tokens.list_by_documento(documento_id):
            self.db.delete(token)
        for versao in self.versoes.list_by_documento(documento_id):
            self.db.delete(versao)
        self.db.delete(documento)

        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ResourceInUseError()
