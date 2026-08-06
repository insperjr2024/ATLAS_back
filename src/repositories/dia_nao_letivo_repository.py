from datetime import date
from typing import List, Optional

from src.models.dia_nao_letivo_model import DiaNaoLetivoModel
from src.repositories.base_repository import BaseRepository


class DiaNaoLetivoRepository(BaseRepository[DiaNaoLetivoModel]):
    model = DiaNaoLetivoModel

    def get_by_semestre(self, semestre_id: int) -> List[DiaNaoLetivoModel]:
        return (
            self.db.query(DiaNaoLetivoModel)
            .filter(DiaNaoLetivoModel.semestre_id == semestre_id)
            .order_by(DiaNaoLetivoModel.data)
            .all()
        )

    def get_por_intervalo(self, inicio: date, fim: date) -> List[DiaNaoLetivoModel]:
        """Todos os dias não letivos do período, de qualquer semestre.

        O cronograma de um projeto pode atravessar a virada de gestão, então a
        consulta por intervalo não pode ficar presa a um semestre só.
        """
        return (
            self.db.query(DiaNaoLetivoModel)
            .filter(DiaNaoLetivoModel.data >= inicio, DiaNaoLetivoModel.data <= fim)
            .order_by(DiaNaoLetivoModel.data)
            .all()
        )

    def get_por_data(self, semestre_id: int, data: date) -> Optional[DiaNaoLetivoModel]:
        return self.first_by(semestre_id=semestre_id, data=data)

    def get_do_calendario(
        self, semestre_id: int, frente_id: Optional[int]
    ) -> List[DiaNaoLetivoModel]:
        """O calendário base de UMA frente: o que é dela mais o que é global.

        `frente_id` nulo no banco significa "vale para todas" — feriado
        nacional não é de curso nenhum. Por isso a consulta traz os dois, e não
        só os da frente.
        """
        consulta = self.db.query(DiaNaoLetivoModel).filter(
            DiaNaoLetivoModel.semestre_id == semestre_id
        )
        if frente_id is None:
            consulta = consulta.filter(DiaNaoLetivoModel.frente_id.is_(None))
        else:
            consulta = consulta.filter(
                (DiaNaoLetivoModel.frente_id == frente_id)
                | (DiaNaoLetivoModel.frente_id.is_(None))
            )
        return consulta.order_by(DiaNaoLetivoModel.data).all()

    def delete_por_semestre(self, semestre_id: int) -> int:
        """Limpa a carga do semestre — usado para recarregar o calendário."""
        total = (
            self.db.query(DiaNaoLetivoModel)
            .filter(DiaNaoLetivoModel.semestre_id == semestre_id)
            .delete()
        )
        self.db.commit()
        return total

    def delete_da_frente(self, semestre_id: int, frente_id: Optional[int]) -> int:
        """Limpa só o calendário daquela frente, para recarregar o PDF dela.

        Não toca no global nem no das outras — recarregar Business não pode
        apagar o que a diretoria já conferiu em Tech.
        """
        consulta = self.db.query(DiaNaoLetivoModel).filter(
            DiaNaoLetivoModel.semestre_id == semestre_id
        )
        consulta = (
            consulta.filter(DiaNaoLetivoModel.frente_id.is_(None))
            if frente_id is None
            else consulta.filter(DiaNaoLetivoModel.frente_id == frente_id)
        )
        total = consulta.delete()
        self.db.commit()
        return total
