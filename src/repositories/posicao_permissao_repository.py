from typing import List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.posicao_permissao_model import PosicaoPermissaoModel
from src.utils.exceptions import ResourceInUseError


class PosicaoPermissaoRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_posicao(self, posicao: str) -> Optional[PosicaoPermissaoModel]:
        return self.db.query(PosicaoPermissaoModel).filter(PosicaoPermissaoModel.posicao == posicao).first()

    def get_all(self) -> List[PosicaoPermissaoModel]:
        # Ordem fixa da hierarquia, não a de inserção — a tela sempre lista
        # diretor primeiro, consultor por último.
        ordem = {
            "diretor_projetos": 0,
            "diretor_pessoas": 1,
            "diretor": 2,
            "gerente": 3,
            "coordenador": 4,
            "consultor": 5,
        }
        return sorted(
            self.db.query(PosicaoPermissaoModel).all(), key=lambda p: ordem.get(p.posicao, 99)
        )

    def update(self, posicao: str, **kwargs) -> Optional[PosicaoPermissaoModel]:
        registro = self.get_by_posicao(posicao)
        if not registro:
            return None
        for key, value in kwargs.items():
            setattr(registro, key, value)
        self.db.commit()
        self.db.refresh(registro)
        return registro

    def create(self, **kwargs) -> PosicaoPermissaoModel:
        registro = PosicaoPermissaoModel(**kwargs)
        self.db.add(registro)
        self.db.commit()
        self.db.refresh(registro)
        return registro

    def delete(self, posicao: str) -> bool:
        """Chave por `posicao` (o slug), não por `id` — mesma chave que
        `get_by_posicao`/`update` já usam, e que a rota recebe na URL.

        A FK `usuario.posicao -> posicao_permissao.posicao` (migration
        `a9cae5c30c6d`) é quem recusa apagar um cargo com gente nele; aqui só
        traduz o `IntegrityError` pro mesmo contrato que `BaseRepository.delete`
        já usa para frente/escopo.
        """
        registro = self.get_by_posicao(posicao)
        if not registro:
            return False
        try:
            self.db.delete(registro)
            self.db.commit()
            return True
        except IntegrityError:
            self.db.rollback()
            raise ResourceInUseError()
