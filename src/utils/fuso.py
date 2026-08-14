"""⭐ A conversão entre o que o banco guarda e o que a pessoa vê.

**A convenção do `banca.data_hora` é UTC.** Quem escreve é o front, com
`new Date(...).toISOString()`, e quem lê de volta é o front, convertendo para o
horário local. O par fecha, e por isso a tela sempre mostrou a hora certa.

⚠ **O que NÃO fecha é comparar esse valor com hora local do lado do servidor.**
A grade horária é preenchida em horário de aula — 14:15 é 14:15 de São Paulo,
não de Greenwich. Enquanto o backend comparava `banca.data_hora.time()` cru com
a faixa da grade, a checagem errava por 3 horas e fazia o oposto do que
prometia: escalava quem tinha aula na hora da banca e poupava quem estava livre.

Este módulo existe para que essa conversão tenha **um lugar só**, com nome, em
vez de virar um `timedelta(hours=3)` solto em cada chamador — o offset do Brasil
já mudou (horário de verão) e pode mudar de novo; `ZoneInfo` acompanha, um
número fixo não.

📐 Não confundir com os carimbos de auditoria (`criado_em`, `respondido_em`,
`submetida_em`), que hoje são gravados com `datetime.now()` — hora local. Esses
não passam por aqui: converter um valor que já é local o deslocaria de novo.
Padronizar o backend inteiro num fuso só é uma decisão maior, ainda em aberto;
o que este módulo resolve é a leitura de `banca.data_hora`, onde a convenção
é conhecida e a comparação com a grade depende dela.
"""

from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

#: O fuso em que o núcleo opera — é o das aulas, das bancas e das reuniões.
FUSO_LOCAL = ZoneInfo("America/Sao_Paulo")


def normalizar_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """O mesmo instante como UTC **sem tzinfo** — a forma que o banco guarda.

    ⚠ Existe por causa de uma armadilha do Python: comparar um `datetime` com
    fuso a um sem fuso com `==`/`!=` **nunca levanta erro e nunca dá igual**.
    O front manda `toISOString()`, que o Pydantic converte num datetime AWARE;
    a coluna devolve um NAIVE. Toda guarda escrita como
    `request.data_hora != existente.data_hora` disparava sempre, mesmo quando
    a data não havia sido tocada — foi o que travou o botão Editar da tela de
    Bancas para qualquer campo, não só a data.

    Normalizar na entrada é o que torna essas comparações honestas.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def para_hora_local(dt: datetime) -> datetime:
    """Um `datetime` gravado em UTC, lido como hora de parede local.

    Devolve **sem tzinfo**, de propósito: quem chama compara com `time()` e
    `weekday()` de dados que também são ingênuos (a grade horária guarda
    `hora_inicio`/`hora_fim` puros). Devolver um valor com fuso obrigaria cada
    chamador a lembrar de tirá-lo de novo.

    `datetime` que já venha com fuso é respeitado — converte a partir do fuso
    dele, não assume UTC.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(FUSO_LOCAL).replace(tzinfo=None)
