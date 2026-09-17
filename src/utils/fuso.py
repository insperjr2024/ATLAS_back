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

⚠️ **Correção (2026-09-16): os carimbos de auditoria também são UTC.** Esta
docstring dizia o contrário — que `criado_em`/`respondido_em`/`submetida_em`
eram hora local do servidor, porque `datetime.now()` "sem fuso" parecia
devolver horário de Brasília quando testado numa máquina local (o
desenvolvedor mora em São Paulo, então o notebook dele também mora). Em
produção o processo roda com o SO em UTC (comum em container/nuvem — o
próprio `hoje_local()` logo abaixo já avisava disso, só que pra `date.today()`,
não pra este caso) — `datetime.now()` no servidor real devolve UTC, não local.
Foi assim que "Enviado em" numa avaliação de banca mostrava 3h adiantado: o
front lia `submetida_em` cru com `new Date(iso)` (sem `Z`, interpretado como
hora local pelo motor JS) em cima de um valor que já era UTC.

A lição: qualquer datetime que sai do backend pro front pelas costas de um
`datetime.now()` puro é UTC, ponto — mesma régua de `banca.data_hora`. Quem lê
esse valor no FRONT usa `paraDataUtc()` (mesma ideia deste módulo, do lado
de lá) antes de formatar. Quem compara no BACKEND contra outro UTC (ex.:
`lote.data_fim`) usa `agora_utc()`, não `datetime.now()` cru — ver o
comentário em `desempenho_lote.py`. Padronizar de vez (gravar tudo já como
UTC-aware, por exemplo) é decisão maior, ainda em aberto; o que este módulo
resolve é a leitura de `banca.data_hora`, onde a convenção sempre foi
conhecida e a comparação com a grade depende dela.
"""

from datetime import date, datetime, timezone
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


def agora_utc() -> datetime:
    """"Agora" na MESMA régua que `banca.data_hora` — UTC sem tzinfo.

    ⚠ Existe pelo motivo oposto do que esta função parecia sugerir antes
    (2026-09-16, corrigido): `datetime.now()` cru do servidor É UTC em
    produção, não local — mas comparações feitas contra ele às vezes foram
    escritas assumindo local, e viviam erradas por 3h em qualquer direção
    dependendo de qual lado do bug se olhava. `agora_utc()` não depende de
    qual SO está por baixo: é sempre UTC explícito, comparável direto com
    `banca.data_hora`/`lote.data_fim`, que também são UTC. Quem compara
    qualquer um dos dois com "agora" usa isto, nunca `datetime.now()` cru.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hoje_local() -> date:
    """"Hoje" de Brasília — NÃO `date.today()` (2026-09-15).

    ⚠ `date.today()`/`datetime.now()` sem fuso dependem do relógio do
    SISTEMA OPERACIONAL do servidor, não do fuso deste módulo — e em
    produção esse relógio ESTÁ em UTC (confirmado 2026-09-16, não é só um
    "se"; ver a correção no topo do arquivo), então `date.today()` já é
    amanhã a partir de 21h daqui. Foi assim que uma tarefa com prazo
    para HOJE aparecia "vencida há 1 dia" três horas antes da meia-noite
    local — `tarefa_status.py` comparava `prazo` (uma data que a pessoa
    pensou em Brasília) contra o "hoje" errado.

    Só usar onde o "hoje" vem do CALENDÁRIO (prazo de tarefa, "quantos dias
    atrás") — comparação com `banca.data_hora` continua sendo com
    `agora_utc()`, que já está certo pelo motivo oposto (ele pede UTC
    explícito, não herda fuso nenhum do SO)."""
    return datetime.now(FUSO_LOCAL).date()


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
