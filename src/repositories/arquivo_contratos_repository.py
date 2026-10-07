from typing import List, Optional

from src.models.arquivo_contratos_model import ArquivoContratosItemModel, ArquivoContratosPastaModel
from src.repositories.base_repository import BaseRepository


class ArquivoContratosPastaRepository(BaseRepository[ArquivoContratosPastaModel]):
    model = ArquivoContratosPastaModel

    def get_filhas(self, pai_id: Optional[int]) -> List[ArquivoContratosPastaModel]:
        q = self.db.query(ArquivoContratosPastaModel)
        q = q.filter(ArquivoContratosPastaModel.pai_id.is_(None)) if pai_id is None else q.filter(
            ArquivoContratosPastaModel.pai_id == pai_id
        )
        return q.order_by(ArquivoContratosPastaModel.nome.desc()).all()

    def get_por_semestre(self, semestre_id: int) -> Optional[ArquivoContratosPastaModel]:
        return self.first_by(semestre_id=semestre_id)

    def get_projeto_em(self, pai_id: int, projeto_id: int) -> Optional[ArquivoContratosPastaModel]:
        return self.first_by(pai_id=pai_id, projeto_id=projeto_id)

    def tem_conteudo(self, pasta_id: int) -> bool:
        if self.db.query(ArquivoContratosPastaModel.id).filter_by(pai_id=pasta_id).first():
            return True
        return self.db.query(ArquivoContratosItemModel.id).filter_by(pasta_id=pasta_id).first() is not None

    def caminho(self, pasta_id: Optional[int]) -> List[ArquivoContratosPastaModel]:
        """Da raiz até a pasta, pra montar o breadcrumb."""
        trilha = []
        atual = self.get_by_id(pasta_id) if pasta_id is not None else None
        while atual is not None:
            trilha.append(atual)
            atual = self.get_by_id(atual.pai_id) if atual.pai_id is not None else None
        return list(reversed(trilha))

    def eh_descendente(self, pasta_id: int, possivel_ancestral_id: int) -> bool:
        return any(p.id == possivel_ancestral_id for p in self.caminho(pasta_id))


class ArquivoContratosItemRepository(BaseRepository[ArquivoContratosItemModel]):
    model = ArquivoContratosItemModel

    def get_por_pasta(self, pasta_id: int) -> List[ArquivoContratosItemModel]:
        return (
            self.db.query(ArquivoContratosItemModel)
            .filter(ArquivoContratosItemModel.pasta_id == pasta_id)
            .order_by(ArquivoContratosItemModel.nome)
            .all()
        )

    def get_por_documento(self, documento_id: int) -> List[ArquivoContratosItemModel]:
        return self.filter_by(documento_id=documento_id)

    def buscar(self, termo: str) -> List[ArquivoContratosItemModel]:
        return (
            self.db.query(ArquivoContratosItemModel)
            .filter(ArquivoContratosItemModel.nome.ilike(f"%{termo}%"))
            .order_by(ArquivoContratosItemModel.nome)
            .limit(100)
            .all()
        )
