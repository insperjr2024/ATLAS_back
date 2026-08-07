from sqlalchemy.orm import Session
from src.models.solicitacao_troca_model import SolicitacaoTrocaModel
from typing import List, Optional
from datetime import datetime


class SolicitacaoTrocaRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, banca_id: int, usuario_original_id: int, candidatura_id: int,
               criado_em: datetime, usuario_convidado_id: Optional[int] = None) -> SolicitacaoTrocaModel:
        solicitacao = SolicitacaoTrocaModel(
            banca_id=banca_id,
            usuario_original_id=usuario_original_id,
            candidatura_id=candidatura_id,
            criado_em=criado_em,
            usuario_convidado_id=usuario_convidado_id,
        )
        self.db.add(solicitacao)
        self.db.commit()
        self.db.refresh(solicitacao)
        return solicitacao

    def get_by_id(self, solicitacao_id: int) -> Optional[SolicitacaoTrocaModel]:
        return self.db.query(SolicitacaoTrocaModel).filter(SolicitacaoTrocaModel.id == solicitacao_id).first()

    def get_by_candidatura(self, candidatura_id: int) -> List[SolicitacaoTrocaModel]:
        return (
            self.db.query(SolicitacaoTrocaModel)
            .filter(SolicitacaoTrocaModel.candidatura_id == candidatura_id)
            .all()
        )

    def get_all(self) -> List[SolicitacaoTrocaModel]:
        return self.db.query(SolicitacaoTrocaModel).all()

    def update(self, solicitacao_id: int, **kwargs) -> Optional[SolicitacaoTrocaModel]:
        solicitacao = self.get_by_id(solicitacao_id)
        if not solicitacao:
            return None
        for key, value in kwargs.items():
            setattr(solicitacao, key, value)
        self.db.commit()
        self.db.refresh(solicitacao)
        return solicitacao
