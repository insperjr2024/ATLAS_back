from sqlalchemy.orm import Session
from src.repositories.avaliacao_repository import AvaliacaoRepository
from src.repositories.banca_repository import BancaRepository
from src.utils.avaliacoes_pendentes import PRAZO_AVALIACAO_DIAS
from src.utils.exceptions import RegraDeNegocioError
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta


class CreateAvaliacaoRequest(BaseModel):
    banca_id: int
    formulario_id: int
    status: str = "rascunho"
    comentario_feedback: Optional[str] = None
    submetida_em: Optional[datetime] = None
    # Bloco 1 do formulário — ver o docstring de AvaliacaoModel.
    nome_avaliador: Optional[str] = None
    tipo_avaliador: Optional[str] = None
    projeto_avaliado: Optional[str] = None
    escopo_avaliado_id: Optional[int] = None
    escopo_avaliado_outro: Optional[str] = None


class CreateAvaliacaoUseCase:
    def __init__(self, db: Session):
        self.repository = AvaliacaoRepository(db)
        self.banca_repository = BancaRepository(db)

    def execute(self, request: CreateAvaliacaoRequest, avaliador_id: int):
        banca = self.banca_repository.get_by_id(request.banca_id)
        if banca and banca.realizado_em:
            prazo = banca.realizado_em + timedelta(days=PRAZO_AVALIACAO_DIAS)
            if datetime.now() > prazo:
                raise RegraDeNegocioError(
                    "O prazo de 2 dias para avaliar esta banca já passou"
                )

        avaliacao = self.repository.create(
            banca_id=request.banca_id,
            avaliador_id=avaliador_id,
            formulario_id=request.formulario_id,
            status=request.status,
            comentario_feedback=request.comentario_feedback,
            submetida_em=request.submetida_em,
            nome_avaliador=request.nome_avaliador,
            tipo_avaliador=request.tipo_avaliador,
            projeto_avaliado=request.projeto_avaliado,
            escopo_avaliado_id=request.escopo_avaliado_id,
            escopo_avaliado_outro=request.escopo_avaliado_outro,
        )
        return {
            "id": avaliacao.id,
            "banca_id": avaliacao.banca_id,
            "avaliador_id": avaliacao.avaliador_id,
            "formulario_id": avaliacao.formulario_id,
            "status": avaliacao.status,
            "nome_avaliador": avaliacao.nome_avaliador,
            "tipo_avaliador": avaliacao.tipo_avaliador,
            "projeto_avaliado": avaliacao.projeto_avaliado,
            "escopo_avaliado_id": avaliacao.escopo_avaliado_id,
            "escopo_avaliado_outro": avaliacao.escopo_avaliado_outro,
        }