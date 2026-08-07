from datetime import date
from typing import List

from src.models.tarefa_model import ReuniaoSemanalModel, TarefaModel
from src.repositories.base_repository import BaseRepository


class TarefaRepository(BaseRepository[TarefaModel]):
    model = TarefaModel

    def get_by_projeto(self, projeto_id: int) -> List[TarefaModel]:
        return (
            self.db.query(TarefaModel)
            .filter(TarefaModel.projeto_id == projeto_id)
            .order_by(TarefaModel.prazo, TarefaModel.id)
            .all()
        )

    def get_by_projetos(self, projeto_ids: List[int]) -> List[TarefaModel]:
        """Usada direto pelo monitoramento (§7.2), sem passar por HTTP."""
        if not projeto_ids:
            return []
        return (
            self.db.query(TarefaModel).filter(TarefaModel.projeto_id.in_(projeto_ids)).all()
        )


class ReuniaoSemanalRepository(BaseRepository[ReuniaoSemanalModel]):
    model = ReuniaoSemanalModel

    def get_by_projeto(self, projeto_id: int) -> List[ReuniaoSemanalModel]:
        return (
            self.db.query(ReuniaoSemanalModel)
            .filter(ReuniaoSemanalModel.projeto_id == projeto_id)
            .order_by(ReuniaoSemanalModel.data_reuniao.desc())
            .all()
        )

    def get_by_projetos_e_janela(
        self, projeto_ids: List[int], inicio: date, fim: date
    ) -> List[ReuniaoSemanalModel]:
        if not projeto_ids:
            return []
        return (
            self.db.query(ReuniaoSemanalModel)
            .filter(
                ReuniaoSemanalModel.projeto_id.in_(projeto_ids),
                ReuniaoSemanalModel.data_reuniao >= inicio,
                ReuniaoSemanalModel.data_reuniao <= fim,
            )
            .all()
        )

    def get_por_data(self, projeto_id: int, data_reuniao: date, projeto_escopo_id=None):
        """A reunião deste projeto, neste dia, **deste escopo**.

        O escopo entra na busca porque reunião inicial e reunião geral passaram
        a ser marcadas no mesmo calendário do cronograma: no mesmo dia cabem a
        geral do projeto e a inicial de um escopo, e antes uma barrava a outra.

        `projeto_escopo_id=None` procura a reunião GERAL daquele dia — que é o
        que impede duas gerais no mesmo dia, algo que o UNIQUE do MySQL não
        cobre (ele ignora NULL).
        """
        return self.first_by(
            projeto_id=projeto_id,
            data_reuniao=data_reuniao,
            projeto_escopo_id=projeto_escopo_id,
        )

    def get_by_escopo(self, projeto_escopo_id: int) -> List[ReuniaoSemanalModel]:
        """As reuniões deste escopo, da mais antiga para a mais nova.

        A primeira da lista é a "reunião inicial" do §5.4 — é dela que sai a
        `data_inicio` do escopo.
        """
        return (
            self.db.query(ReuniaoSemanalModel)
            .filter(ReuniaoSemanalModel.projeto_escopo_id == projeto_escopo_id)
            .order_by(ReuniaoSemanalModel.data_reuniao)
            .all()
        )
