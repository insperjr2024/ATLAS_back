"""Os 5 estados de uma banca (§7.4, §8).

Antes da F5 isto tinha 9 linhas e dizia que toda banca com data passada era
`realizada` — o estado *"venceu e não aconteceu"* simplesmente não existia no
sistema. Era o que travava o placar da gestão em 100% e impedia a aba Atrasos
de existir.

    sem `data_hora` ............................... nao_marcada
    `cancelada_em` preenchido ...................... cancelada
    `realizado_em` preenchido ..................... realizada
    `data_hora` no futuro ......................... aberta
    `data_hora` no passado, sem `realizado_em` .... atrasada   ← o que faltava

A ordem importa: `cancelada_em` vem antes de `realizado_em`, que vem antes da
data — uma banca cancelada não pode "reaparecer" atrasada, e uma que
aconteceu depois do previsto continua realizada.

⭐ **2026-09-04, a pedido: `atrasada` deixou de ser um estado de espera.**
Não existe mais o botão "Registrar realização" — o job de finalização
automática (`use_cases/banca/finalizacao_automatica.py`) grava
`realizado_em` sozinho assim que `data_hora` passa, salvo se a banca foi
`cancelada_em` antes disso. `atrasada` agora só existe na janela entre
`data_hora` passar e a próxima passada do job (minutos, não dias) — é o
estado transitório, não mais um limbo que dependia de alguém clicar.
"""

from datetime import date, datetime
from typing import Optional

NAO_MARCADA = "nao_marcada"
ABERTA = "aberta"
REALIZADA = "realizada"
ATRASADA = "atrasada"
CANCELADA = "cancelada"


def calcular_status_banca(
    data_hora: Optional[datetime],
    realizado_em: Optional[datetime] = None,
    referencia: Optional[datetime] = None,
    cancelada_em: Optional[datetime] = None,
) -> str:
    if cancelada_em is not None:
        return CANCELADA
    if realizado_em is not None:
        return REALIZADA
    if data_hora is None:
        return NAO_MARCADA
    referencia = referencia or datetime.now()
    return ATRASADA if referencia >= data_hora else ABERTA


def banca_ja_ocorreu(status: str) -> bool:
    """Só `realizada` conta como ocorrida.

    É o que separa "a data passou" de "a banca aconteceu" — a distinção que
    o placar da gestão e as avaliações pendentes dependem. `cancelada`
    também não ocorreu: não há apuração nem avaliação para ela.
    """
    return status == REALIZADA


def aceita_inscricao(status: str) -> bool:
    """Uma banca `atrasada` AINDA aceita inscrição — ela ainda vai acontecer
    (a rigor, por poucos minutos, até o job de finalização automática passar).

    `cancelada` não aceita — ela não vai mais acontecer de propósito.
    """
    return status in (ABERTA, ATRASADA)


def dias_de_atraso(
    data_hora: Optional[datetime],
    realizado_em: Optional[datetime] = None,
    referencia: Optional[date] = None,
) -> int:
    """Dias **corridos** desde a data vencida.

    Zero quando a banca não está atrasada.

    ⚠ NÃO é mais o insumo do placar da gestão nem da aba Atrasos: desde
    2026-08-04 o atraso do §7.4 é contado em dias ÚTEIS, e quem faz isso é
    `dias_uteis.dias_uteis_de_atraso`. Esta função ficou sem chamador em
    produção — só os testes a exercitam. Mantida porque a contagem corrida
    ainda pode servir de referência, mas não a use para medir atraso sem
    checar antes qual régua vale.
    """
    referencia = referencia or date.today()
    # A referência precisa atravessar para o cálculo do status, senão ele cai
    # no relógio real e o "está atrasada?" discorda da data que se pediu.
    fim_do_dia = datetime.combine(referencia, datetime.max.time())
    if calcular_status_banca(data_hora, realizado_em, fim_do_dia) != ATRASADA:
        return 0
    return max(0, (referencia - data_hora.date()).days)
