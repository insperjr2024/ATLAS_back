from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from src.models.avaliacao_model import AvaliacaoModel
from src.utils.exceptions import ResourceInUseError
from typing import List, Optional
from datetime import datetime


class AvaliacaoRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, banca_id: int, avaliador_id: int, formulario_id: int,
               status: str = "rascunho", comentario_feedback: Optional[str] = None,
               submetida_em: Optional[datetime] = None,
               nome_avaliador: Optional[str] = None,
               tipo_avaliador: Optional[str] = None,
               projeto_avaliado: Optional[str] = None,
               escopo_avaliado_id: Optional[int] = None,
               escopo_avaliado_outro: Optional[str] = None,
               sessao: int = 1) -> AvaliacaoModel:
        avaliacao = AvaliacaoModel(
            banca_id=banca_id,
            avaliador_id=avaliador_id,
            formulario_id=formulario_id,
            sessao=sessao,
            status=status,
            comentario_feedback=comentario_feedback,
            submetida_em=submetida_em,
            nome_avaliador=nome_avaliador,
            tipo_avaliador=tipo_avaliador,
            projeto_avaliado=projeto_avaliado,
            escopo_avaliado_id=escopo_avaliado_id,
            escopo_avaliado_outro=escopo_avaliado_outro,
        )
        self.db.add(avaliacao)
        self.db.commit()
        self.db.refresh(avaliacao)
        return avaliacao

    def get_by_id(self, avaliacao_id: int) -> Optional[AvaliacaoModel]:
        return self.db.query(AvaliacaoModel).filter(AvaliacaoModel.id == avaliacao_id).first()

    def get_all(self) -> List[AvaliacaoModel]:
        return self.db.query(AvaliacaoModel).all()

    def get_by_avaliador(self, avaliador_id: int) -> List[AvaliacaoModel]:
        return self.db.query(AvaliacaoModel).filter(AvaliacaoModel.avaliador_id == avaliador_id).all()

    def get_by_banca(self, banca_id: int, sessao: Optional[int] = None) -> List[AvaliacaoModel]:
        """As avaliações de uma banca — opcionalmente só as de uma sessão (§9).

        ⭐ O filtro por `sessao` é o que separa as tentativas. `banca_id` é o
        mesmo nas duas: sem ele, os votos que reprovaram a 1ª banca contariam
        de novo na 2ª e a segunda chance não existiria na prática.
        """
        query = self.db.query(AvaliacaoModel).filter(AvaliacaoModel.banca_id == banca_id)
        if sessao is not None:
            query = query.filter(AvaliacaoModel.sessao == sessao)
        return query.all()

    def update(self, avaliacao_id: int, **kwargs) -> Optional[AvaliacaoModel]:
        avaliacao = self.get_by_id(avaliacao_id)
        if not avaliacao:
            return None
        for key, value in kwargs.items():
            setattr(avaliacao, key, value)
        self.db.commit()
        self.db.refresh(avaliacao)
        return avaliacao

    def delete(self, avaliacao_id: int) -> bool:
        avaliacao = self.get_by_id(avaliacao_id)
        if not avaliacao:
            return False
        try:
            self.db.delete(avaliacao)
            self.db.commit()
            return True
        except IntegrityError:
            self.db.rollback()
            raise ResourceInUseError()