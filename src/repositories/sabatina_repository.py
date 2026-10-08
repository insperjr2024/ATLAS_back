from typing import Dict, List, Optional

from src.models.sabatina_model import (
    SabatinaCandidatoModel,
    SabatinaEleicaoModel,
    SabatinaPesoModel,
    SabatinaVotoModel,
)
from src.repositories.base_repository import BaseRepository


class SabatinaPesoRepository(BaseRepository[SabatinaPesoModel]):
    model = SabatinaPesoModel

    def como_dict(self) -> Dict[str, int]:
        return {p.posicao: p.peso for p in self.get_all()}

    def definir(self, posicao: str, peso: int) -> SabatinaPesoModel:
        atual = self.first_by(posicao=posicao)
        if atual:
            atual.peso = peso
            self.db.commit()
            self.db.refresh(atual)
            return atual
        return self.create(posicao=posicao, peso=peso)


class SabatinaEleicaoRepository(BaseRepository[SabatinaEleicaoModel]):
    model = SabatinaEleicaoModel

    def get_todas(self) -> List[SabatinaEleicaoModel]:
        return (
            self.db.query(SabatinaEleicaoModel)
            .order_by(SabatinaEleicaoModel.criado_em.desc(), SabatinaEleicaoModel.id.desc())
            .all()
        )

    def get_abertas(self) -> List[SabatinaEleicaoModel]:
        return (
            self.db.query(SabatinaEleicaoModel)
            .filter(SabatinaEleicaoModel.status == "aberta")
            .order_by(SabatinaEleicaoModel.aberta_em.desc())
            .all()
        )


class SabatinaCandidatoRepository(BaseRepository[SabatinaCandidatoModel]):
    model = SabatinaCandidatoModel

    def get_by_eleicao(self, eleicao_id: int) -> List[SabatinaCandidatoModel]:
        return (
            self.db.query(SabatinaCandidatoModel)
            .filter(SabatinaCandidatoModel.eleicao_id == eleicao_id)
            .order_by(SabatinaCandidatoModel.ordem, SabatinaCandidatoModel.id)
            .all()
        )

    def substituir(self, eleicao_id: int, usuario_ids: List[int]) -> None:
        """Troca a lista inteira de candidatos (só em rascunho, o use case garante)."""
        self.db.query(SabatinaCandidatoModel).filter(
            SabatinaCandidatoModel.eleicao_id == eleicao_id
        ).delete(synchronize_session=False)
        for ordem, usuario_id in enumerate(dict.fromkeys(usuario_ids)):
            self.db.add(SabatinaCandidatoModel(eleicao_id=eleicao_id, usuario_id=usuario_id, ordem=ordem))
        self.db.commit()


class SabatinaVotoRepository(BaseRepository[SabatinaVotoModel]):
    model = SabatinaVotoModel

    def get_by_eleicao(self, eleicao_id: int) -> List[SabatinaVotoModel]:
        return self.filter_by(eleicao_id=eleicao_id)

    def get_do_eleitor(self, eleicao_id: int, eleitor_id: int) -> Optional[SabatinaVotoModel]:
        return self.first_by(eleicao_id=eleicao_id, eleitor_id=eleitor_id)
