from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.banca_repository import BancaRepository
from src.utils.banca_status import calcular_status_banca
from src.utils.exceptions import RegraDeNegocioError


class UpdateBancaRequest(BaseModel):
    nome_projeto: Optional[str] = None
    escopo_id: Optional[int] = None
    coordenador_id: Optional[int] = None
    data_hora: Optional[datetime] = None
    #: Só a diretoria altera — ver `require_diretor` no use case.
    piso_minimo_override: Optional[int] = None


class UpdateBancaUseCase:
    def __init__(self, db: Session):
        self.repository = BancaRepository(db)

    def execute(self, banca_id: int, request: UpdateBancaRequest, eh_diretor: bool = False):
        data = request.dict(exclude_unset=True)

        if "piso_minimo_override" in data and not eh_diretor:
            raise RegraDeNegocioError("Só a diretoria pode alterar o piso mínimo de uma banca")

        existente = self.repository.get_by_id(banca_id)
        if not existente:
            return None

        # 🔒 §5.6: remarcar a banca de um escopo nunca é silenciosa — exige
        # diretoria e justificativa. Esta rota é a genérica do módulo legado
        # e não tem como cumprir isso, então ela para aqui e manda usar
        # `PUT /escopos-projeto/{id}/banca`, que impõe a regra.
        if existente.projeto_escopo_id is not None and "data_hora" in data:
            if data["data_hora"] != existente.data_hora:
                raise RegraDeNegocioError(
                    "A data da banca de um escopo é remarcada em "
                    "PUT /escopos-projeto/{id}/banca, que exige diretoria e "
                    "justificativa (§5.6)"
                )

        banca = self.repository.update(banca_id, **data)
        if not banca:
            return None
        return {
            "id": banca.id,
            "nome_projeto": banca.nome_projeto,
            "escopo_id": banca.escopo_id,
            "coordenador_id": banca.coordenador_id,
            "data_hora": banca.data_hora,
            "projeto_escopo_id": banca.projeto_escopo_id,
            "realizado_em": banca.realizado_em,
            "resultado": banca.resultado,
            "status": calcular_status_banca(banca.data_hora, banca.realizado_em),
            "piso_minimo_override": banca.piso_minimo_override,
        }


class DeleteBancaUseCase:
    def __init__(self, db: Session):
        self.repository = BancaRepository(db)

    def execute(self, banca_id: int) -> bool:
        return self.repository.delete(banca_id)