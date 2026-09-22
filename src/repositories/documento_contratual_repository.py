from typing import List, Optional

from src.models.documento_contratual_model import DocumentoContratualModel
from src.models.projeto_model import ProjetoModel
from src.repositories.base_repository import BaseRepository


class DocumentoContratualRepository(BaseRepository[DocumentoContratualModel]):
    model = DocumentoContratualModel

    def list_by_projeto(self, projeto_id: int) -> List[DocumentoContratualModel]:
        return (
            self.db.query(DocumentoContratualModel)
            .filter(DocumentoContratualModel.projeto_id == projeto_id)
            .order_by(DocumentoContratualModel.criado_em)
            .all()
        )

    def get_by_projeto_e_tipo(self, projeto_id: int, tipo: str) -> Optional[DocumentoContratualModel]:
        return self.first_by(projeto_id=projeto_id, tipo=tipo)

    def list_para_painel(self) -> List[DocumentoContratualModel]:
        """A aba Contratos: TODO documento jurídico, de todo projeto — a
        Kanban tem 7 colunas, a última ("Assinado e Arquivado") é justamente
        quem terminou o ciclo. Diferente do Repositório (`list_arquivados`,
        só o que já terminou); aqui é o inverso, tudo, do primeiro rascunho
        ao arquivado. O recorte de quem vê o quê é do use case (`painel.py`),
        não daqui.

        ⚠ Chamava-se `list_nao_arquivados` e EXCLUÍA `assinado_e_arquivado`
        — certo pra quando a Kanban só tinha 6 colunas (documento "sumia" da
        tela ao ser assinado), errado agora que a 7ª coluna existe pra
        mostrar justamente isso."""
        return (
            self.db.query(DocumentoContratualModel)
            .order_by(DocumentoContratualModel.criado_em.desc())
            .all()
        )

    def list_arquivados(
        self, gestao_id: Optional[int] = None, busca: Optional[str] = None
    ) -> List[DocumentoContratualModel]:
        """O Repositório: todo documento final assinado, mais recente primeiro.

        `busca` casa pelo nome do projeto OU do cliente — quem procura um
        contrato antigo raramente lembra em que tipo de documento ele está.
        """
        query = (
            self.db.query(DocumentoContratualModel)
            .join(ProjetoModel, DocumentoContratualModel.projeto_id == ProjetoModel.id)
            .filter(DocumentoContratualModel.status == "assinado_e_arquivado")
        )
        if gestao_id is not None:
            query = query.filter(DocumentoContratualModel.gestao_id == gestao_id)
        if busca:
            termo = f"%{busca}%"
            query = query.filter(
                (ProjetoModel.nome.ilike(termo)) | (ProjetoModel.cliente.ilike(termo))
            )
        return query.order_by(DocumentoContratualModel.criado_em.desc()).all()
