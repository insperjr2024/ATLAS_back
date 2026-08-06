"""Dia útil — a definição da qual depende toda a contagem do §5.4.

📐 Dia útil = segunda a sexta que NÃO está no calendário do Insper.
Fim de semana é calculado; feriado, prova e recesso vêm de `dia_nao_letivo`.

Toda função aqui recebe os dias não letivos como um conjunto de `date` — quem
chama é responsável por carregá-los do banco uma vez e reaproveitar, em vez de
consultar dentro do laço.
"""

from datetime import date, timedelta
from typing import Iterable, List, Set

SABADO = 5
DOMINGO = 6


def normalizar(dias_nao_letivos: Iterable[date]) -> Set[date]:
    """Aceita lista de `date` ou de models com atributo `.data`."""
    return {d.data if hasattr(d, "data") else d for d in dias_nao_letivos}


def eh_dia_util(dia: date, dias_nao_letivos: Iterable[date]) -> bool:
    if dia.weekday() in (SABADO, DOMINGO):
        return False
    return dia not in normalizar(dias_nao_letivos)


def listar_dias_uteis(inicio: date, fim: date, dias_nao_letivos: Iterable[date]) -> List[date]:
    """Dias úteis no intervalo fechado [inicio, fim]. Intervalo invertido = vazio."""
    if inicio is None or fim is None or fim < inicio:
        return []
    nao_letivos = normalizar(dias_nao_letivos)
    dias = []
    atual = inicio
    while atual <= fim:
        if atual.weekday() not in (SABADO, DOMINGO) and atual not in nao_letivos:
            dias.append(atual)
        atual += timedelta(days=1)
    return dias


def contar_dias_uteis(inicio: date, fim: date, dias_nao_letivos: Iterable[date]) -> int:
    """Quantos dias úteis há no intervalo fechado [inicio, fim]."""
    return len(listar_dias_uteis(inicio, fim, dias_nao_letivos))


def somar_dias_uteis(inicio: date, quantidade: int, dias_nao_letivos: Iterable[date]) -> date:
    """A data que fecha `quantidade` dias úteis contando `inicio` como o 1º.

    Usada para achar o fim da ambientação: kickoff + 5 dias úteis.
    `quantidade <= 0` devolve a própria data de início.
    """
    if quantidade <= 0:
        return inicio
    nao_letivos = normalizar(dias_nao_letivos)
    contados = 0
    atual = inicio
    # Teto de segurança: 5 anos. Evita laço infinito se o calendário do semestre
    # for carregado errado (ex.: o ano inteiro marcado como não letivo).
    limite = inicio + timedelta(days=365 * 5)
    while atual <= limite:
        if atual.weekday() not in (SABADO, DOMINGO) and atual not in nao_letivos:
            contados += 1
            if contados == quantidade:
                return atual
        atual += timedelta(days=1)
    raise ValueError(
        f"Não foi possível somar {quantidade} dias úteis a partir de {inicio}: "
        "o calendário não letivo carregado cobre um intervalo grande demais."
    )


def proximo_dia_util(dia: date, dias_nao_letivos: Iterable[date]) -> date:
    """O primeiro dia útil a partir de `dia` (inclusive)."""
    return somar_dias_uteis(dia, 1, dias_nao_letivos)


def dias_uteis_de_atraso(
    prazo: date, referencia: date, dias_nao_letivos: Iterable[date]
) -> int:
    """Quantos dias ÚTEIS se passaram depois que `prazo` venceu.

    ⏱ O intervalo é `(prazo, referencia]` — aberto no prazo, fechado em hoje.
    O dia do prazo é para entregar, então ele não conta como atraso; é a mesma
    convenção de `tarefa_status.eh_vencida`, que só vira `True` no dia
    SEGUINTE ao prazo. Venceu na sexta e hoje é segunda: 1 dia útil de atraso
    (contra 3 corridos).

    É a régua ÚNICA de atraso do sistema: vale tanto para a tarefa vencida da
    aba de Execução quanto para a banca e a entrega do §7.4, desde que a
    diretoria confirmou (2026-08-04) que ali também são dias úteis.

    Devolve 0 quando o prazo ainda não venceu. Devolve 0 também quando venceu
    mas nenhum dia útil passou desde então — atrasado no sábado, com o prazo na
    sexta, é atraso de 0 dias úteis: o time ainda não teve dia de trabalho para
    resolver. Quem decide SE está atrasado é a data, não esta contagem.
    """
    if prazo is None or referencia is None or prazo >= referencia:
        return 0
    return contar_dias_uteis(prazo + timedelta(days=1), referencia, dias_nao_letivos)
