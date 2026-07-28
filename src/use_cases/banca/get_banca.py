from sqlalchemy.orm import Session
from src.repositories.banca_repository import BancaRepository


class GetBancaUseCase:
    def __init__(self, db: Session):
        self.repository = BancaRepository(db)

    def execute(self, banca_id: int):
        banca = self.repository.get_by_id(banca_id)
        if not banca:
            return None
        return {
            "id": banca.id,
            "nome_projeto": banca.nome_projeto,
            "escopo_id": banca.escopo_id,
            "coordenador_id": banca.coordenador_id,
            "status": banca.status,
            "data_hora": banca.data_hora,
            "nota_final": banca.nota_final
        }


class ListBancasUseCase:
    def __init__(self, db: Session):
        self.repository = BancaRepository(db)

    def execute(self):
        bancas = self.repository.get_all()
        return [
            {
                "id": b.id,
                "nome_projeto": b.nome_projeto,
                "escopo_id": b.escopo_id,
                "coordenador_id": b.coordenador_id,
                "status": b.status,
                "data_hora": b.data_hora,
                "nota_final": b.nota_final
            }
            for b in bancas
        ]