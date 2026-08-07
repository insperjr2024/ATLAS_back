"""A descrição do coordenador sobre a banca do projeto dele.

O coordenador não é candidato/avaliador da própria banca — `create_candidatura`
bloqueia isso ("ninguém avalia o próprio grupo"). Em vez do formulário de
avaliação (notas por bloco técnico), ele registra um relato livre depois que a
banca aconteceu. É etapa dele, fora do fluxo de avaliação: não conta pra
composição, prazo ou notas da banca.
"""

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.banca_repository import BancaRepository
from src.utils.exceptions import RegraDeNegocioError


class RegistrarDescricaoCoordenadorRequest(BaseModel):
    descricao: str


class RegistrarDescricaoCoordenadorUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = BancaRepository(db)

    def execute(self, banca_id: int, request: RegistrarDescricaoCoordenadorRequest, usuario_id: int):
        banca = self.repository.get_by_id(banca_id)
        if not banca:
            return None

        if not banca.realizado_em:
            raise RegraDeNegocioError(
                "A banca ainda não foi realizada — a descrição só pode ser registrada depois"
            )
        if usuario_id != banca.coordenador_id:
            raise RegraDeNegocioError(
                "Só o coordenador do projeto pode registrar esta descrição"
            )
        if not (request.descricao or "").strip():
            raise RegraDeNegocioError("A descrição não pode ficar em branco")

        banca = self.repository.update(
            banca_id,
            descricao_coordenador=request.descricao.strip(),
            descricao_coordenador_enviada_em=datetime.now(),
        )
        return {
            "id": banca.id,
            "descricao_coordenador": banca.descricao_coordenador,
            "descricao_coordenador_enviada_em": banca.descricao_coordenador_enviada_em,
        }
