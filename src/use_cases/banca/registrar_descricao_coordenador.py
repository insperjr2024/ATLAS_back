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

from src.repositories.banca_escopo_repository import BancaEscopoRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.utils.equipe_banca import coordenadores_da_banca
from src.utils.exceptions import RegraDeNegocioError


class RegistrarDescricaoCoordenadorRequest(BaseModel):
    descricao: str


class RegistrarDescricaoCoordenadorUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = BancaRepository(db)
        self.banca_escopo_repository = BancaEscopoRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)

    def execute(self, banca_id: int, request: RegistrarDescricaoCoordenadorRequest, usuario_id: int):
        banca = self.repository.get_by_id(banca_id)
        if not banca:
            return None

        if not banca.realizado_em:
            raise RegraDeNegocioError(
                "A banca ainda não foi realizada — a descrição só pode ser registrada depois"
            )
        # ⚠ 2026-09-16, corrigido: projeto pode ter mais de um coordenador —
        # antes só quem era `banca.coordenador_id` (o primeiro) conseguia
        # registrar o relato; um segundo coordenador de verdade tomava
        # "só o coordenador do projeto pode..." do próprio projeto dele.
        coordenadores_ids = coordenadores_da_banca(
            banca, self.banca_escopo_repository, self.escopo_repository, self.membro_repository
        )
        if usuario_id not in coordenadores_ids:
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
