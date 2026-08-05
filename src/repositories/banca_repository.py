from sqlalchemy.orm import Session
from src.models.banca_model import BancaModel
from typing import List, Optional
from datetime import datetime


class BancaRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, nome_projeto: str, escopo_id: Optional[int], coordenador_id: int,
               data_hora: Optional[datetime], **extras) -> BancaModel:
        # `extras` deixa a F5 passar `projeto_escopo_id` sem quebrar os call
        # sites antigos, que continuam chamando com os 4 posicionais.
        banca = BancaModel(
            nome_projeto=nome_projeto,
            escopo_id=escopo_id,
            coordenador_id=coordenador_id,
            data_hora=data_hora,
            **extras
        )
        self.db.add(banca)
        self.db.commit()
        self.db.refresh(banca)
        return banca

    def get_by_projeto_escopo(self, projeto_escopo_id: int) -> Optional[BancaModel]:
        return (
            self.db.query(BancaModel)
            .filter(BancaModel.projeto_escopo_id == projeto_escopo_id)
            .first()
        )

    def get_by_projeto_escopos(self, projeto_escopo_ids: List[int]) -> List[BancaModel]:
        if not projeto_escopo_ids:
            return []
        return (
            self.db.query(BancaModel)
            .filter(BancaModel.projeto_escopo_id.in_(projeto_escopo_ids))
            .all()
        )

    def get_por_data_hora(self, data_hora: datetime) -> List[BancaModel]:
        """Bancas no mesmo horário — a checagem de choque do §8."""
        return self.db.query(BancaModel).filter(BancaModel.data_hora == data_hora).all()

    def get_por_periodo(self, inicio: datetime, fim: datetime) -> List[BancaModel]:
        """Bancas ainda não realizadas com data dentro do intervalo — o
        universo candidato do push automático (§8: uma semana antes)."""
        return (
            self.db.query(BancaModel)
            .filter(
                BancaModel.data_hora.isnot(None),
                BancaModel.data_hora >= inicio,
                BancaModel.data_hora <= fim,
                BancaModel.realizado_em.is_(None),
            )
            .all()
        )

    def get_by_id(self, banca_id: int) -> Optional[BancaModel]:
        return self.db.query(BancaModel).filter(BancaModel.id == banca_id).first()

    def get_all(self) -> List[BancaModel]:
        return self.db.query(BancaModel).all()

    def update(self, banca_id: int, **kwargs) -> Optional[BancaModel]:
        banca = self.get_by_id(banca_id)
        if not banca:
            return None
        for key, value in kwargs.items():
            setattr(banca, key, value)
        self.db.commit()
        self.db.refresh(banca)
        return banca

    def delete(self, banca_id: int) -> bool:
        banca = self.get_by_id(banca_id)
        if not banca:
            return False
        self.db.delete(banca)
        self.db.commit()
        return True