from datetime import date

from sqlalchemy.orm import Session

from src.repositories.dia_nao_letivo_repository import DiaNaoLetivoRepository
from src.utils.dias_uteis import contar_dias_uteis, listar_dias_uteis


def _serializar(dia):
    return {
        "id": dia.id,
        "data": dia.data,
        "tipo": dia.tipo,
        "descricao": dia.descricao,
        # Nulo = vale para todas as frentes. A tela usa isso para marcar o dia
        # como global e não deixar editá-lo de dentro de uma frente.
        "frente_id": dia.frente_id,
    }


class ListDiasNaoLetivosUseCase:
    def __init__(self, db: Session):
        self.repository = DiaNaoLetivoRepository(db)

    def execute(self, semestre_id: int, frente_id=None, apenas_da_frente: bool = False):
        """Sem `frente_id`, devolve o semestre inteiro (compatível com antes).

        Com ele, devolve o calendário base daquela frente: o que é dela mais o
        global. `apenas_da_frente` corta o global — é o que a tela de edição
        usa, para a diretoria não apagar um feriado nacional achando que está
        mexendo só no calendário de Business.
        """
        if frente_id is None and not apenas_da_frente:
            dias = self.repository.get_by_semestre(semestre_id)
        elif apenas_da_frente:
            dias = [
                d
                for d in self.repository.get_by_semestre(semestre_id)
                if d.frente_id == frente_id
            ]
        else:
            dias = self.repository.get_do_calendario(semestre_id, frente_id)
        return [_serializar(d) for d in dias]


class GetDiasNaoUteisUseCase:
    """Os dias que o calendário pinta de cinza (§6.4).

    Devolve fim de semana + calendário do Insper já resolvidos, para o front não
    precisar reimplementar a regra de dia útil em TypeScript.
    """

    def __init__(self, db: Session):
        self.repository = DiaNaoLetivoRepository(db)

    def execute(self, inicio: date, fim: date):
        nao_letivos = self.repository.get_por_intervalo(inicio, fim)
        uteis = set(listar_dias_uteis(inicio, fim, nao_letivos))

        dias = []
        atual = inicio
        while atual <= fim:
            if atual not in uteis:
                registro = next((d for d in nao_letivos if d.data == atual), None)
                dias.append(
                    {
                        "data": atual,
                        "tipo": registro.tipo if registro else "fim_de_semana",
                        "descricao": registro.descricao if registro else None,
                    }
                )
            atual = date.fromordinal(atual.toordinal() + 1)

        return {
            "inicio": inicio,
            "fim": fim,
            "dias_uteis": contar_dias_uteis(inicio, fim, nao_letivos),
            "nao_uteis": dias,
        }
