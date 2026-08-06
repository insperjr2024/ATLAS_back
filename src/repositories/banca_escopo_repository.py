from typing import Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from src.models.banca_escopo_model import BancaEscopoModel


class BancaEscopoRepository:
    """O vínculo banca ↔ escopos vendidos (N escopos para 1 banca)."""

    def __init__(self, db: Session):
        self.db = db

    def get_escopo_ids(self, banca_id: int) -> List[int]:
        linhas = (
            self.db.query(BancaEscopoModel)
            .filter(BancaEscopoModel.banca_id == banca_id)
            .order_by(BancaEscopoModel.id)
            .all()
        )
        return [linha.projeto_escopo_id for linha in linhas]

    def get_escopo_ids_por_banca(self, banca_ids: Iterable[int]) -> Dict[int, List[int]]:
        """Uma query só para várias bancas — as telas de lista chamam isto."""
        ids = list(banca_ids)
        if not ids:
            return {}
        linhas = (
            self.db.query(BancaEscopoModel)
            .filter(BancaEscopoModel.banca_id.in_(ids))
            .order_by(BancaEscopoModel.id)
            .all()
        )
        mapa: Dict[int, List[int]] = {banca_id: [] for banca_id in ids}
        for linha in linhas:
            mapa.setdefault(linha.banca_id, []).append(linha.projeto_escopo_id)
        return mapa

    def get_banca_id(self, projeto_escopo_id: int) -> Optional[int]:
        linha = (
            self.db.query(BancaEscopoModel)
            .filter(BancaEscopoModel.projeto_escopo_id == projeto_escopo_id)
            .first()
        )
        return linha.banca_id if linha else None

    def definir(self, banca_id: int, projeto_escopo_ids: Iterable[int]) -> None:
        """Deixa a banca cobrindo exatamente estes escopos.

        Só mexe na diferença: escopo que já estava vinculado não é apagado e
        recriado, para o id da linha continuar estável.
        """
        alvo = set(projeto_escopo_ids)
        atuais = (
            self.db.query(BancaEscopoModel)
            .filter(BancaEscopoModel.banca_id == banca_id)
            .all()
        )
        for linha in atuais:
            if linha.projeto_escopo_id not in alvo:
                self.db.delete(linha)
        ja_vinculados = {linha.projeto_escopo_id for linha in atuais}
        for escopo_id in sorted(alvo - ja_vinculados):
            self.db.add(BancaEscopoModel(banca_id=banca_id, projeto_escopo_id=escopo_id))
        self.db.commit()
