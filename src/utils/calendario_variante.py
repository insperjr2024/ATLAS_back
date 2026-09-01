"""Qual calendário acadêmico vale para cada escopo.

Um calendário base é o par **(frente, rótulo)**. A frente sozinha não basta —
dentro da Tech, Ciência da Computação não segue o calendário das engenharias —
e o rótulo sozinho também não: nada impede duas frentes de terem um calendário
de mesmo nome, e o `NULL` (a frente que tem um calendário só) seria o mesmo
para todas elas.

⭐ **A base é do ESCOPO, não do projeto** (`projeto_escopo.calendario`). Um
projeto sinérgico tem escopos em frentes diferentes, e o escopo de Business não
para na semana de avaliação da Tech.

⚠ Isto mudou em 2026-08-31. Antes existia `projeto.calendario`, um override de
projeto inteiro, e o corte era feito por `filtrar_variante`, que olhava só a
VARIANTE e nunca a frente. O efeito era que a escolha não escolhia nada: todo
projeto contava a união dos dias de todas as frentes.

Funções puras, sem banco, como `dias_uteis.py` e `condicoes_alerta.py`: quem
chama já tem os dias em mãos. Isso mantém a escolha testável sem subir Postgres
e evita mais uma query dentro de laço de monitoramento.
"""

from typing import Iterable, List, Optional


def eh_global(dia) -> bool:
    """O dia vale para a faculdade inteira — feriado, sem frente nem curso."""
    return getattr(dia, "frente_id", None) is None


def do_calendario(
    dias: Iterable, frente_id: Optional[int], calendario: Optional[str] = None
) -> List:
    """Os dias de UM calendário base: os dele mais os globais.

    O feriado nacional (`frente_id` nulo) atravessa sempre — é o "a não ser que
    seja feriado" da regra. Fora dele, só passa o dia que é exatamente daquela
    frente E daquele rótulo.

    ⚠ `calendario=None` **não** é curinga: é o rótulo nulo, o da frente que tem
    um calendário só. Numa frente com variantes ele não casa com nada além dos
    dias que valem para a frente inteira, que é o correto — quem não escolheu
    curso não pode receber a semana de avaliação de um curso específico.

    `getattr` em vez de acesso direto porque metade dos testes desta base monta
    o calendário com `SimpleNamespace(data=...)` e listas de `date` puras — o
    mesmo contrato frouxo que `dias_uteis.normalizar` respeita.
    """
    return [
        dia
        for dia in dias
        if eh_global(dia)
        or (
            getattr(dia, "frente_id", None) == frente_id
            and getattr(dia, "variante", None) == calendario
        )
    ]


def do_escopo(dias: Iterable, escopo) -> List:
    """`do_calendario` lendo a frente e o rótulo do próprio escopo.

    É a chamada de quase todo mundo: quem tem o escopo na mão não deveria
    precisar lembrar quais dois campos formam o par.
    """
    return do_calendario(
        dias, getattr(escopo, "frente_id", None), getattr(escopo, "calendario", None)
    )


def datas_por_escopo(dias: Iterable, escopos: Iterable) -> dict:
    """`{escopo.id: [date, ...]}` — o calendário de cada escopo, resolvido de uma vez.

    Existe para o chamador carregar `dia_nao_letivo` UMA vez e ainda assim dar
    a cada escopo o calendário dele, que é o contrato que `dias_uteis.py`
    estabelece no docstring. Sem isto, quem tem vários escopos ou refiltra a
    lista dentro do laço, ou volta a usar a união e perde a escolha.
    """
    dias = list(dias)
    return {e.id: [d.data for d in do_escopo(dias, e)] for e in escopos}


def apenas_globais(dias: Iterable) -> List:
    """Os dias que valem para a faculdade inteira, sem curso nem frente.

    É o recorte do que é do PROJETO e não de um escopo: a ambientação, e o
    prazo de pedido que fecha junto com ela. Um projeto tem uma ambientação só,
    e o calendário de um curso não pode fazê-la terminar em datas diferentes
    conforme o escopo que estiver selecionado na tela.
    """
    return [d for d in dias if eh_global(d)]
