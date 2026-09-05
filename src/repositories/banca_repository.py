from sqlalchemy.orm import Session
from src.models.banca_escopo_model import BancaEscopoModel
from src.models.banca_model import BancaModel
from typing import Dict, List, Optional
from datetime import datetime


class BancaRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, nome_projeto: str, escopo_id: Optional[int], coordenador_id: int,
               data_hora: Optional[datetime], **extras) -> BancaModel:
        # `extras` existe para os call sites antigos, que passam só os 4
        # posicionais. O vínculo com os escopos vendidos NÃO vem por aqui:
        # mora em `banca_escopo`, gravado depois que a banca tem id.
        banca = BancaModel(
            nome_projeto=nome_projeto,
            escopo_id=escopo_id,
            coordenador_id=coordenador_id,
            data_hora=data_hora,
            **extras
        )
        self.db.add(banca)
        self.db.commit()
        self.db.refresh(banca)
        return banca

    def get_by_projeto_escopo(self, projeto_escopo_id: int) -> Optional[BancaModel]:
        """A banca que cobre este escopo — no máximo uma (UNIQUE em
        `banca_escopo.projeto_escopo_id`)."""
        return (
            self.db.query(BancaModel)
            .join(BancaEscopoModel, BancaEscopoModel.banca_id == BancaModel.id)
            .filter(BancaEscopoModel.projeto_escopo_id == projeto_escopo_id)
            .first()
        )

    def mapa_por_escopo(self, projeto_escopo_ids: List[int]) -> Dict[int, BancaModel]:
        """Escopo → banca que o cobre.

        Devolve mapa, não lista: uma banca que cobre três escopos aparece nas
        três chaves, e é isso que as telas precisam — a pergunta delas é sempre
        "qual a banca DESTE escopo".
        """
        if not projeto_escopo_ids:
            return {}
        linhas = (
            self.db.query(BancaEscopoModel.projeto_escopo_id, BancaModel)
            .join(BancaModel, BancaEscopoModel.banca_id == BancaModel.id)
            .filter(BancaEscopoModel.projeto_escopo_id.in_(projeto_escopo_ids))
            .all()
        )
        return {escopo_id: banca for escopo_id, banca in linhas}

    def get_by_projeto_escopos(self, projeto_escopo_ids: List[int]) -> List[BancaModel]:
        """As bancas destes escopos, cada uma UMA vez — quem cobre três escopos
        não vira três itens."""
        por_id = {b.id: b for b in self.mapa_por_escopo(projeto_escopo_ids).values()}
        return list(por_id.values())

    def get_por_data_hora(self, data_hora: datetime) -> List[BancaModel]:
        """Bancas no mesmo horário — a checagem de choque do §8."""
        return self.db.query(BancaModel).filter(BancaModel.data_hora == data_hora).all()

    def get_por_periodo(self, inicio: datetime, fim: datetime) -> List[BancaModel]:
        """Bancas ainda não realizadas com data dentro do intervalo — o
        universo candidato do push automático (§8: uma semana antes).

        ⚠ Exclui `cancelada_em` (2026-09-04): uma banca cancelada não deve
        ganhar avaliador por rodízio — ela não vai acontecer de propósito.
        """
        return (
            self.db.query(BancaModel)
            .filter(
                BancaModel.data_hora.isnot(None),
                BancaModel.data_hora >= inicio,
                BancaModel.data_hora <= fim,
                BancaModel.realizado_em.is_(None),
                BancaModel.cancelada_em.is_(None),
            )
            .all()
        )

    def get_para_finalizacao_automatica(self, referencia: datetime) -> List[BancaModel]:
        """O universo do job que substitui o botão "Registrar realização"
        (2026-09-04): `data_hora` já passou, ninguém marcou como realizada
        nem cancelou. Sem limite inferior de data — um servidor que ficou
        fora do ar pega tudo que passou, igual ao push de alocação."""
        return (
            self.db.query(BancaModel)
            .filter(
                BancaModel.data_hora.isnot(None),
                BancaModel.data_hora <= referencia,
                BancaModel.realizado_em.is_(None),
                BancaModel.cancelada_em.is_(None),
            )
            .all()
        )

    def get_by_id(self, banca_id: int) -> Optional[BancaModel]:
        return self.db.query(BancaModel).filter(BancaModel.id == banca_id).first()

    def get_realizadas_sem_resultado(self) -> List[BancaModel]:
        """Aconteceu e ainda não tem veredito — a fila "Esperando aprovação"."""
        return (
            self.db.query(BancaModel)
            .filter(BancaModel.realizado_em.isnot(None), BancaModel.resultado.is_(None))
            .all()
        )

    def get_all(self) -> List[BancaModel]:
        return self.db.query(BancaModel).all()

    def update(self, banca_id: int, **kwargs) -> Optional[BancaModel]:
        banca = self.get_by_id(banca_id)
        if not banca:
            return None
        for key, value in kwargs.items():
            setattr(banca, key, value)
        self.db.commit()
        self.db.refresh(banca)
        return banca

    def delete(self, banca_id: int) -> bool:
        banca = self.get_by_id(banca_id)
        if not banca:
            return False
        self.db.delete(banca)
        self.db.commit()
        return True