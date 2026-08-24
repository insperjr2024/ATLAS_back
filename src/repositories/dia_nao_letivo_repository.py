from datetime import date
from typing import List, Optional, Sequence

from src.models.dia_nao_letivo_model import DiaNaoLetivoModel
from src.models.frente_model import FrenteModel
from src.models.projeto_model import ProjetoModel
from src.repositories.base_repository import BaseRepository
from src.utils.calendario_variante import escolha_por_frente, filtrar_variante


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

    def get_do_projeto(self, projeto_id: int) -> List[DiaNaoLetivoModel]:
        """O calendário que vale para ESTE projeto, de todos os semestres.

        Mesmo alcance do `get_all()` que os use cases de janela e contagem já
        usavam — o cronograma atravessa a virada de gestão —, com uma diferença
        só: os dias de um calendário de curso que não é o dele ficam de fora.

        Três queries onde antes havia uma. Vale para quem resolve UM projeto;
        quem varre a carteira inteira (monitoramento, fila de aprovações) deve
        carregar dias e frentes uma vez e chamar `filtrar_variante` no laço.
        """
        projeto = self.db.query(ProjetoModel).filter(ProjetoModel.id == projeto_id).first()
        escolhidos = escolha_por_frente(
            self.db.query(FrenteModel).all(),
            getattr(projeto, "calendario", None) if projeto else None,
        )
        return filtrar_variante(self.get_all(), escolhidos)

    def get_do_calendario(
        self,
        semestre_id: int,
        frente_id: Optional[int],
        variantes: Optional[Sequence[str]] = None,
    ) -> List[DiaNaoLetivoModel]:
        """O calendário base de UMA frente: o que é dela mais o que é global.

        `frente_id` nulo no banco significa "vale para todas" — feriado
        nacional não é de curso nenhum. Por isso a consulta traz os dois, e não
        só os da frente.

        `variantes` desce mais um degrau: dentro da frente, traz o que vale
        para ela inteira (`variante` nula) mais os calendários pedidos. Aceita
        VÁRIOS de propósito — a tela de conferência mostra engenharias e
        Ciência da Computação lado a lado, cada dia marcado com o dono, e
        forçar uma consulta por calendário só transformaria comparar os dois
        em alternar entre eles.

        Sem `variantes`, vem apenas o que não é de curso nenhum: quem não
        escolheu não pode receber a semana de provas de um curso específico.
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
        if variantes:
            consulta = consulta.filter(
                DiaNaoLetivoModel.variante.in_(list(variantes))
                | DiaNaoLetivoModel.variante.is_(None)
            )
        else:
            consulta = consulta.filter(DiaNaoLetivoModel.variante.is_(None))
        return consulta.order_by(DiaNaoLetivoModel.data).all()

    def listar_variantes(self, semestre_id: int, frente_id: int) -> List[str]:
        """Os calendários que existem naquela frente, para a tela montar as abas.

        Sai da própria carga em vez de uma tabela de domínio: um calendário
        existe enquanto tiver dia dentro, e some quando o último sai. Não há
        estado a limpar depois de a diretoria apagar uma carga inteira.
        """
        linhas = (
            self.db.query(DiaNaoLetivoModel.variante)
            .filter(
                DiaNaoLetivoModel.semestre_id == semestre_id,
                DiaNaoLetivoModel.frente_id == frente_id,
                DiaNaoLetivoModel.variante.isnot(None),
            )
            .distinct()
            .all()
        )
        return sorted(linha[0] for linha in linhas)


    def delete_por_semestre(self, semestre_id: int) -> int:
        """Limpa a carga do semestre — usado para recarregar o calendário."""
        total = (
            self.db.query(DiaNaoLetivoModel)
            .filter(DiaNaoLetivoModel.semestre_id == semestre_id)
            .delete()
        )
        self.db.commit()
        return total

    def delete_da_frente(
        self, semestre_id: int, frente_id: Optional[int], variante: Optional[str] = None
    ) -> int:
        """Limpa só o calendário daquela frente, para recarregar o PDF dela.

        Não toca no global nem no das outras — recarregar Business não pode
        apagar o que a diretoria já conferiu em Tech.

        A `variante` estreita o mesmo recorte mais um degrau, e por isso é
        obrigatória no caminho de cima: sem ela, subir o PDF de Ciência da
        Computação apagaria o de Engenharias, que está na mesma frente.
        """
        consulta = self.db.query(DiaNaoLetivoModel).filter(
            DiaNaoLetivoModel.semestre_id == semestre_id
        )
        consulta = (
            consulta.filter(DiaNaoLetivoModel.frente_id.is_(None))
            if frente_id is None
            else consulta.filter(DiaNaoLetivoModel.frente_id == frente_id)
        )
        consulta = (
            consulta.filter(DiaNaoLetivoModel.variante.is_(None))
            if variante is None
            else consulta.filter(DiaNaoLetivoModel.variante == variante)
        )
        total = consulta.delete()
        self.db.commit()
        return total

    def renomear_variante(self, semestre_id: int, frente_id: int, de: str, para: str) -> int:
        """Renomeia um calendário. O nome É a chave, então isto é um UPDATE.

        Quem chama precisa atualizar `frente.calendario_padrao` e
        `projeto.calendario` na mesma transação — os três guardam o rótulo, e
        deixar um para trás desliga silenciosamente o calendário dos projetos
        que apontavam para o nome antigo.
        """
        total = (
            self.db.query(DiaNaoLetivoModel)
            .filter(
                DiaNaoLetivoModel.semestre_id == semestre_id,
                DiaNaoLetivoModel.frente_id == frente_id,
                DiaNaoLetivoModel.variante == de,
            )
            .update({DiaNaoLetivoModel.variante: para})
        )
        return total
