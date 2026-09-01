from typing import Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from src.models.banca_composicao_regra_model import BancaComposicaoRegraModel


class BancaComposicaoRegraRepository:
    """As regras de composição gravadas. Ausência não é erro — ver o modelo."""

    def __init__(self, db: Session):
        self.db = db

    def get_por_combinacao(self, combinacao: str) -> List[BancaComposicaoRegraModel]:
        return (
            self.db.query(BancaComposicaoRegraModel)
            .filter(BancaComposicaoRegraModel.combinacao == combinacao)
            .all()
        )

    def get_todas(self) -> List[BancaComposicaoRegraModel]:
        return self.db.query(BancaComposicaoRegraModel).all()

    def get_por_frente(self, combinacao: str) -> Dict[int, BancaComposicaoRegraModel]:
        return {r.frente_id: r for r in self.get_por_combinacao(combinacao)}

    def definir(
        self, combinacao: str, linhas: Iterable[dict], vagas: Optional[int] = None
    ) -> None:
        """Grava a regra da combinação inteira, substituindo a anterior.

        `vagas` é o teto DA COMBINAÇÃO (2026-09-02) e por isso vai igual em
        todas as linhas: elas são apagadas e recriadas juntas, então as cópias
        não divergem. `None` grava `NULL`, que é "usa o teto global".

        Apaga e recria em vez de fazer upsert linha a linha: a combinação é a
        unidade que a tela edita e salva de uma vez, e um upsert deixaria para
        trás a linha de uma frente que saiu da combinação (o que só acontece se
        alguém apagar uma frente, mas aí a linha órfã exigiria o piso de uma
        frente que não existe mais).
        """
        self.db.query(BancaComposicaoRegraModel).filter(
            BancaComposicaoRegraModel.combinacao == combinacao
        ).delete(synchronize_session=False)
        for linha in linhas:
            self.db.add(
                BancaComposicaoRegraModel(combinacao=combinacao, vagas=vagas, **linha)
            )
        self.db.commit()
