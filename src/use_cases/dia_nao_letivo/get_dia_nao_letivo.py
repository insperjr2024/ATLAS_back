from datetime import date
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from src.repositories.dia_nao_letivo_repository import DiaNaoLetivoRepository
from src.repositories.frente_repository import FrenteRepository
from src.repositories.semestre_repository import SemestreRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.utils.calendario_variante import apenas_globais, do_escopo
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


class ListCalendariosParaEscolhaUseCase:
    """Os calendários escolhíveis de CADA frente, numa ida só.

    ⭐ Serve o cadastro do escopo vendido, que precisa perguntar em qual
    calendário os dias daquele escopo são contados (§5.4). O formulário mostra
    várias frentes ao mesmo tempo — um projeto sinérgico vende escopos em duas
    —, então uma chamada por frente transformaria abrir o formulário em N
    requisições.

    Lista SEMPRE uma opção por frente, e é isso que a diferencia de
    `ListCalendariosDaFrenteUseCase`: a frente com um calendário só devolve
    `[{"valor": null, ...}]`, e não lista vazia. Vazio faria a tela esconder o
    campo, que é exatamente o que mantinha os 22 projetos em produção sem
    calendário nenhum — ninguém era perguntado.

    Sem gestão ativa, toda frente responde com a opção única: travar o cadastro
    porque o calendário do semestre ainda não subiu seria pior do que contar só
    feriado, e o escopo pode ser corrigido depois.
    """

    def __init__(self, db: Session):
        self.repository = DiaNaoLetivoRepository(db)
        self.frente_repository = FrenteRepository(db)
        self.semestre_repository = SemestreRepository(db)

    def execute(self):
        semestre = self.semestre_repository.get_ativo()
        saida = []
        for frente in self.frente_repository.get_all():
            nomes = (
                self.repository.listar_variantes(semestre.id, frente.id) if semestre else []
            )
            saida.append(
                {
                    "frente_id": frente.id,
                    "frente_nome": frente.nome,
                    "padrao": frente.calendario_padrao,
                    # `valor` é o que vai em `projeto_escopo.calendario`; nulo é
                    # o rótulo da frente que tem um calendário só, e não "não
                    # escolhido". O `rotulo` existe porque nulo não se mostra.
                    "calendarios": (
                        [{"valor": n, "rotulo": n} for n in nomes]
                        if nomes
                        else [{"valor": None, "rotulo": f"Calendário de {frente.nome}"}]
                    ),
                }
            )
        return saida


class GetDiasNaoUteisUseCase:
    """Os dias que o calendário pinta de cinza (§6.4).

    Devolve fim de semana + calendário do Insper já resolvidos, para o front não
    precisar reimplementar a regra de dia útil em TypeScript.
    """

    def __init__(self, db: Session):
        self.repository = DiaNaoLetivoRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)

    def execute(self, inicio: date, fim: date, projeto_id: Optional[int] = None):
        nao_letivos = self.repository.get_por_intervalo(inicio, fim)
        if projeto_id is not None:
            # ⭐ A UNIÃO dos calendários dos escopos deste projeto. Esta rota
            # responde "quais dias são cinzas na tela dele", e um projeto
            # sinérgico tem escopos em calendários diferentes — a tela precisa
            # enxergar os dois para avisar quando uma etapa pisa no dia não
            # útil da outra frente. Quem CONTA dias usa o calendário de um
            # escopo só; ver `get_escopos_projeto`.
            escopos = self.escopo_repository.get_by_projeto(projeto_id)
            vistos = {id(d) for d in apenas_globais(nao_letivos)}
            do_projeto = apenas_globais(nao_letivos)
            for escopo in escopos:
                for d in do_escopo(nao_letivos, escopo):
                    if id(d) not in vistos:
                        vistos.add(id(d))
                        do_projeto.append(d)
            nao_letivos = sorted(do_projeto, key=lambda d: d.data)
        else:
            # Sem projeto não há calendário base a consultar: valem os dias que
            # são de todas as frentes. Um curinga aqui devolveria a semana de
            # avaliação de um curso para quem não é dele.
            nao_letivos = apenas_globais(nao_letivos)
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
