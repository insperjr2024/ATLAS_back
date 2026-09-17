from sqlalchemy.orm import Session
from src.repositories.banca_frente_repository import BancaFrenteRepository
from pydantic import BaseModel


class CreateBancaFrenteRequest(BaseModel):
    banca_id: int
    frente_id: int


class CreateBancaFrenteUseCase:
    def __init__(self, db: Session):
        self.repository = BancaFrenteRepository(db)

    def execute(self, request: CreateBancaFrenteRequest):
        # ⚠ Sem isto, chamar duas vezes (duplo clique, dois fluxos tentando
        # garantir a mesma frente) cria uma segunda linha pro mesmo
        # (banca_id, frente_id) — não há unique constraint no banco. A
        # duplicata não é só cosmética: dobra o piso mínimo e as vagas
        # calculadas pra aquela frente (2026-09-17, banca real com "Business"
        # duas vezes na ficha).
        existente = next(
            (bf for bf in self.repository.get_by_banca(request.banca_id) if bf.frente_id == request.frente_id),
            None,
        )
        banca_frente = existente or self.repository.create(
            banca_id=request.banca_id,
            frente_id=request.frente_id
        )
        return {
            "id": banca_frente.id,
            "banca_id": banca_frente.banca_id,
            "frente_id": banca_frente.frente_id
        }