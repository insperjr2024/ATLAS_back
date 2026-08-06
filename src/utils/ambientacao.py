"""A janela de ambientação (§5.3) — e quando ela acaba.

*"A ambientação vem logo após o kickoff; a quantidade de dias úteis dela é
informada no cadastro do projeto (por padrão 5)."*

📐 A janela é **kickoff + N dias úteis, contando o kickoff como o 1º** — a
mesma régua de `somar_dias_uteis`, a mesma que pinta a faixa cinza do
cronograma. Aqui ela ganha um nome só, porque agora duas coisas dependem dela:
a faixa e a virada automática de status.

Função pura, como o resto de `utils/`: quem chama carrega os dias não letivos
uma vez e passa. `referencia` é injetável para os testes não congelarem o
relógio.
"""

from datetime import date
from typing import Iterable, Optional

from src.utils.dias_uteis import somar_dias_uteis


def fim_da_ambientacao(
    data_kickoff: Optional[date],
    dias_ambientacao: int,
    dias_nao_letivos: Iterable[date],
) -> Optional[date]:
    """O último dia da ambientação, ou `None` quando ela não tem janela.

    Sem kickoff não há de onde contar. Com zero dias de ambientação também não
    há janela: o projeto passou direto para a execução, e devolver o próprio
    kickoff faria a virada esperar um dia inteiro à toa.

    `None` também quando o calendário carregado é grande demais para fechar a
    conta (`somar_dias_uteis` levanta): melhor não ter fim do que ter um fim
    inventado que viraria o status do projeto errado.
    """
    if not data_kickoff or dias_ambientacao <= 0:
        return None
    try:
        return somar_dias_uteis(data_kickoff, dias_ambientacao, dias_nao_letivos)
    except ValueError:
        return None


def ambientacao_encerrada(
    data_kickoff: Optional[date],
    dias_ambientacao: int,
    dias_nao_letivos: Iterable[date],
    referencia: Optional[date] = None,
) -> bool:
    """A ambientação já acabou em `referencia`?

    ⏱ O dia do fim ainda É ambientação — a virada acontece no dia SEGUINTE,
    mesma convenção de `tarefa_status.eh_vencida` e de `dias_uteis_de_atraso`.
    Encerrar no próprio último dia cortaria um dia útil dos que foram vendidos
    como ambientação.

    Sem janela (sem kickoff, ou zero dias) devolve `False`: quem não tem
    ambientação para acabar não é virado por ela. Projeto com `dias_ambientacao`
    zerado sai de Ambientação pela mão de alguém, como sempre saiu.
    """
    fim = fim_da_ambientacao(data_kickoff, dias_ambientacao, dias_nao_letivos)
    if fim is None:
        return False
    return (referencia or date.today()) > fim
