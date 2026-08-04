from datetime import date

from sqlalchemy.orm import Session

from src.repositories.dia_nao_letivo_repository import DiaNaoLetivoRepository
from src.utils.dias_uteis import contar_dias_uteis, listar_dias_uteis


def _serializar(dia):
    return {"id": dia.id, "data": dia.data, "tipo": dia.tipo, "descricao": dia.descricao}


class ListDiasNaoLetivosUseCase:
    def __init__(self, db: Session):
        self.repository = DiaNaoLetivoRepository(db)

    def execute(self, semestre_id: int):
        return [_serializar(d) for d in self.repository.get_by_semestre(semestre_id)]


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
