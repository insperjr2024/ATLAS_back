from typing import List, Optional

from sqlalchemy.orm import Session

from src.models.posicao_permissao_model import PosicaoPermissaoModel


class PosicaoPermissaoRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_posicao(self, posicao: str) -> Optional[PosicaoPermissaoModel]:
        return self.db.query(PosicaoPermissaoModel).filter(PosicaoPermissaoModel.posicao == posicao).first()

    def get_all(self) -> List[PosicaoPermissaoModel]:
        # Ordem fixa da hierarquia, não a de inserção — a tela sempre lista
        # diretor primeiro, consultor por último.
        ordem = {"diretor": 0, "gerente": 1, "coordenador": 2, "consultor": 3}
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
