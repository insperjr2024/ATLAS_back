"""Peso do voto por posição. Configurado uma vez e vale pra toda eleição que
abrir depois (o voto copia o peso na hora, então eleição passada não muda)."""

from typing import List

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.repositories.posicao_permissao_repository import PosicaoPermissaoRepository
from src.repositories.sabatina_repository import SabatinaPesoRepository
from src.utils.exceptions import RegraDeNegocioError
from src.utils.sabatina_apuracao import peso_da_posicao


class PesoInput(BaseModel):
    posicao: str
    peso: int = Field(ge=0, le=10)


class UpdatePesosRequest(BaseModel):
    pesos: List[PesoInput]


class GetPesosUseCase:
    """Todas as posições do catálogo, com o peso gravado ou o padrão."""

    def __init__(self, db: Session):
        self.peso_repo = SabatinaPesoRepository(db)
        self.posicao_repo = PosicaoPermissaoRepository(db)

    def execute(self) -> list[dict]:
        gravados = self.peso_repo.como_dict()
        return [
            {
                "posicao": p.posicao,
                "nome": getattr(p, "nome", None) or p.posicao,
                "peso": peso_da_posicao(p.posicao, gravados),
                "padrao": p.posicao not in gravados,
            }
            for p in self.posicao_repo.get_all()
        ]


class UpdatePesosUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.peso_repo = SabatinaPesoRepository(db)
        self.posicao_repo = PosicaoPermissaoRepository(db)

    def execute(self, request: UpdatePesosRequest) -> list[dict]:
        existentes = {p.posicao for p in self.posicao_repo.get_all()}
        for item in request.pesos:
            if item.posicao not in existentes:
                raise RegraDeNegocioError(f'Posição "{item.posicao}" não existe.')
        for item in request.pesos:
            self.peso_repo.definir(item.posicao, item.peso)
        return GetPesosUseCase(self.db).execute()
