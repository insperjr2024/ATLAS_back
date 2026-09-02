from datetime import date
from typing import Dict, Iterable, List

from src.models.tarefa_model import (
    ReuniaoSemanalModel,
    TarefaModel,
    TarefaResponsavelModel,
)
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

    def responsaveis_por_tarefa(self, tarefa_ids: Iterable[int]) -> Dict[int, List[int]]:
        """`{tarefa_id: [usuario_id, ...]}` para uma lista de tarefas de uma vez.

        Uma consulta agregada, não uma por tarefa: o board e o monitoramento
        pedem isso para o projeto inteiro.
        """
        ids = list(tarefa_ids)
        if not ids:
            return {}
        linhas = (
            self.db.query(TarefaResponsavelModel.tarefa_id, TarefaResponsavelModel.usuario_id)
            .filter(TarefaResponsavelModel.tarefa_id.in_(ids))
            .order_by(TarefaResponsavelModel.id)
            .all()
        )
        mapa: Dict[int, List[int]] = {}
        for tarefa_id, usuario_id in linhas:
            mapa.setdefault(tarefa_id, []).append(usuario_id)
        return mapa

    def definir_responsaveis(self, tarefa_id: int, usuario_ids: Iterable[int]) -> List[int]:
        """Deixa os responsáveis da tarefa exatamente iguais a `usuario_ids`.

        Só mexe na DIFERENÇA (apaga quem saiu, insere quem entrou), como
        `projeto_vendedor.definir` — assim o `id` de quem já estava não muda.
        """
        desejados = list(dict.fromkeys(usuario_ids))
        atuais = {
            r.usuario_id: r
            for r in self.db.query(TarefaResponsavelModel).filter(
                TarefaResponsavelModel.tarefa_id == tarefa_id
            )
        }
        for usuario_id, linha in atuais.items():
            if usuario_id not in desejados:
                self.db.delete(linha)
        for usuario_id in desejados:
            if usuario_id not in atuais:
                self.db.add(
                    TarefaResponsavelModel(tarefa_id=tarefa_id, usuario_id=usuario_id)
                )
        self.db.commit()
        return desejados


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
