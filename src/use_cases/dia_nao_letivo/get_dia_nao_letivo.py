from datetime import date
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from src.repositories.dia_nao_letivo_repository import DiaNaoLetivoRepository
from src.repositories.frente_repository import FrenteRepository
from src.utils.calendario_variante import escolha_por_frente, filtrar_variante
from src.utils.dias_uteis import contar_dias_uteis, listar_dias_uteis
from src.utils.exceptions import RegraDeNegocioError


def _serializar(dia):
    return {
        "id": dia.id,
        "data": dia.data,
        "tipo": dia.tipo,
        "descricao": dia.descricao,
        # Nulo = vale para todas as frentes. A tela usa isso para marcar o dia
        # como global e não deixar editá-lo de dentro de uma frente.
        "frente_id": dia.frente_id,
        # Nulo = vale para a frente inteira. Preenchido, é o rótulo do
        # calendário do curso — é o que a coluna Origem da tela mostra, e o que
        # permite ver dois calendários juntos sem confundir de quem é cada dia.
        "variante": dia.variante,
    }


class ListDiasNaoLetivosUseCase:
    def __init__(self, db: Session):
        self.repository = DiaNaoLetivoRepository(db)

    def execute(
        self,
        semestre_id: int,
        frente_id=None,
        apenas_da_frente: bool = False,
        variantes: Optional[Sequence[str]] = None,
    ):
        """Sem `frente_id`, devolve o semestre inteiro (compatível com antes).

        Com ele, devolve o calendário base daquela frente: o que é dela mais o
        global. `apenas_da_frente` corta o global — é o que a tela de edição
        usa, para a diretoria não apagar um feriado nacional achando que está
        mexendo só no calendário de Business.

        `variantes` escolhe QUAIS calendários da frente entram, quando ela tem
        mais de um. Vários ao mesmo tempo é o caso normal da tela: cada dia já
        carrega o dono na resposta, então mostrar engenharias e Ciência da
        Computação juntas é comparar, e não misturar. Sem nenhuma, vem só o que
        vale para a frente inteira.
        """
        escolhidas = list(variantes or [])
        if frente_id is None and not apenas_da_frente:
            dias = self.repository.get_by_semestre(semestre_id)
        elif apenas_da_frente:
            dias = [
                d
                for d in self.repository.get_by_semestre(semestre_id)
                if d.frente_id == frente_id
                and (d.variante is None or d.variante in escolhidas)
            ]
        else:
            dias = self.repository.get_do_calendario(semestre_id, frente_id, escolhidas)
        return [_serializar(d) for d in dias]


class ListCalendariosDaFrenteUseCase:
    """Os calendários que existem numa frente, para a tela montar o seletor.

    Devolve também o padrão da frente, para a tela marcar qual deles um projeto
    segue quando não escolheu nenhum.
    """

    def __init__(self, db: Session):
        self.repository = DiaNaoLetivoRepository(db)
        self.frente_repository = FrenteRepository(db)

    def execute(self, semestre_id: int, frente_id: int):
        frente = self.frente_repository.get_by_id(frente_id)
        if not frente:
            raise RegraDeNegocioError("Frente não encontrada")
        return {
            "frente_id": frente_id,
            "padrao": frente.calendario_padrao,
            "calendarios": self.repository.listar_variantes(semestre_id, frente_id),
        }


class GetDiasNaoUteisUseCase:
    """Os dias que o calendário pinta de cinza (§6.4).

    Devolve fim de semana + calendário do Insper já resolvidos, para o front não
    precisar reimplementar a regra de dia útil em TypeScript.
    """

    def __init__(self, db: Session):
        self.repository = DiaNaoLetivoRepository(db)
        self.frente_repository = FrenteRepository(db)

    def execute(self, inicio: date, fim: date, projeto_id: Optional[int] = None):
        if projeto_id is not None:
            # O recorte por data sai aqui em Python porque `get_do_projeto`
            # carrega tudo de propósito — o cronograma atravessa a virada de
            # gestão. São dezenas de linhas, não milhares.
            nao_letivos = [
                d
                for d in self.repository.get_do_projeto(projeto_id)
                if inicio <= d.data <= fim
            ]
        else:
            nao_letivos = self.repository.get_por_intervalo(inicio, fim)
            # Sem projeto não há curso a consultar, e cada frente responde com
            # o calendário padrão dela. É o que faz esta rota, que a tela de
            # cronograma usa sem contexto de projeto, continuar devolvendo as
            # mesmas datas de sempre.
            nao_letivos = filtrar_variante(
                nao_letivos, escolha_por_frente(self.frente_repository.get_all())
            )
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
