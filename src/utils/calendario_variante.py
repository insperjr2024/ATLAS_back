"""Qual calendário acadêmico vale para um projeto.

Uma frente pode ter mais de um calendário (`dia_nao_letivo.variante`), porque
ela cobre mais de um curso e os cursos nem sempre têm as mesmas datas — dentro
da Tech, Ciência da Computação não segue o calendário das engenharias. Este
módulo é o único lugar que sabe escolher entre eles.

Funções puras, sem banco, como `dias_uteis.py` e `condicoes_alerta.py`: quem
chama já tem os dias e as frentes em mãos. Isso mantém a escolha testável sem
subir Postgres e evita mais uma query dentro de laço de monitoramento.
"""

from typing import Dict, Iterable, List, Mapping, Optional


def escolha_por_frente(
    frentes: Iterable, calendario_do_projeto: Optional[str] = None
) -> Dict[int, Optional[str]]:
    """Qual calendário vale em cada frente, do ponto de vista de um projeto.

    Sem `calendario_do_projeto` (o caso da esmagadora maioria), cada frente
    responde com o padrão dela — e o padrão da Tech é justamente o calendário
    que já estava carregado antes de tudo isso existir. É o que faz um projeto
    que não escolheu nada continuar vendo exatamente as mesmas datas de sempre.

    A escolha do projeto vale para TODAS as frentes, e não só para a dele, de
    propósito: num projeto sinérgico ela só encontra dia em quem tem aquele
    calendário. Um projeto de Ciência da Computação com um escopo de Business
    não acha "Ciência da Computação" em Business, cai no padrão de Business
    (nulo) e enxerga o calendário da frente inteira — que é o certo.
    """
    return {
        frente.id: calendario_do_projeto or getattr(frente, "calendario_padrao", None)
        for frente in frentes
    }


def filtrar_variante(dias: Iterable, escolhida_por_frente: Mapping[int, Optional[str]]) -> List:
    """Corta os dias que pertencem a um calendário que não é o escolhido.

    Passam três coisas, e é mais fácil ler pelo que NÃO passa: só fica de fora
    o dia que declara um calendário diferente do escolhido para a frente dele.
    Feriado nacional (sem frente) e dia que vale para a frente inteira (sem
    calendário) atravessam sempre.

    `getattr` em vez de acesso direto porque metade dos testes desta base monta
    o calendário com `SimpleNamespace(data=...)` e listas de `date` puras — o
    mesmo contrato frouxo que `dias_uteis.normalizar` respeita.
    """
    resultado = []
    for dia in dias:
        variante = getattr(dia, "variante", None)
        if variante is None:
            resultado.append(dia)
            continue
        if variante == escolhida_por_frente.get(getattr(dia, "frente_id", None)):
            resultado.append(dia)
    return resultado


def apenas_globais(dias: Iterable) -> List:
    """Os dias que valem para a faculdade inteira, sem curso nem frente.

    Existe para dar nome ao filtro que sete use cases já faziam à mão com
    `if d.frente_id is None`. Não muda nada: variante só existe dentro de uma
    frente, então o recorte global nunca viu, nem verá, dia de curso.
    """
    return [d for d in dias if getattr(d, "frente_id", None) is None]
