"""⭐ O resultado da banca sai da decisão de diretoria de projetos OU gerente
da frente (§5.5, §8), não mais do voto de quem assistiu.

Antes, a maioria dos avaliadores decidia (`voto_aprovacao`). A pedido
explícito do usuário (2026-09-03): quem assiste continua dando nota e
feedback (outra dimensão — ver `banca_nota.py`), mas quem aprova ou reprova a
banca passou a ser diretoria de projetos ou o gerente de qualquer frente da
banca — QUALQUER UM decide sozinho, sem esperar os demais. Mudança de
direção do próprio usuário: a primeira versão exigia as duas partes
concordarem; não mais.
"""


def apurar_aprovacao(aprovado: bool) -> str:
    """"aprovada" | "nao_aprovada" — a decisão de UM único aprovador já fecha
    a banca. Diretoria de projetos e o gerente de cada frente da banca têm o
    mesmo peso: o primeiro que decidir vale, e `RegistrarAprovacaoBancaUseCase`
    já barra qualquer decisão posterior (`banca.resultado is not None`).

    Função pura de propósito, mesmo espírito de antes: a regra de negócio —
    "qualquer um decide sozinho" — fica num lugar só e testável sem banco.
    """
    return "aprovada" if aprovado else "nao_aprovada"
