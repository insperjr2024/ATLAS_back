"""A conta da sabatina, sem banco: recebe candidatos, votos e a regra, devolve
o resultado. É o que `FecharEleicaoUseCase`/`GetEleicaoUseCase` chamam e o
que os testes exercitam direto.

Regras (2026-10-05, a pedido):

- cada voto vale o PESO da posição de quem votou (consultor 1, lideranças 2,
  diretoria 3 por padrão; editável em `sabatina_peso`);
- o percentual de aprovação é sobre os votos ponderados DADOS, brancos
  incluídos. Quem faltou não entra na conta, só na lista de pendências;
- é eleito quem passa do percentual (estritamente maior, o "50% mais um").
  Se mais de um passar (só dá com percentual abaixo de 50), fica o mais
  votado. Se ninguém passa, "ninguém eleito"; sem voto nenhum, "sem votos".
"""

from typing import Iterable, Optional

#: Posições com voto de peso 3 quando não há linha em `sabatina_peso`.
_DIRETORIA_PREFIXO = "diretor"
_PRESIDENCIA = ("presidente", "presidencia")
_LIDERANCA = ("gerente", "coordenador")


def peso_padrao(posicao: Optional[str]) -> int:
    """Diretoria e presidência 3, gerente e coordenador 2, o resto 1."""
    p = (posicao or "").lower()
    if p.startswith(_DIRETORIA_PREFIXO) or p in _PRESIDENCIA:
        return 3
    if p in _LIDERANCA:
        return 2
    return 1


def peso_da_posicao(posicao: Optional[str], pesos: dict) -> int:
    """`pesos` é `{posicao: peso}` vindo de `sabatina_peso`."""
    if posicao in pesos:
        return int(pesos[posicao])
    return peso_padrao(posicao)


def peso_do_usuario(posicao: Optional[str], cargo_extra: Optional[str], pesos: dict) -> int:
    """Quem acumula um `cargo_extra` (consultor que também é BDR) vota com o
    MAIOR dos dois pesos. Mesma régua das permissões: o cargo extra soma,
    nunca rebaixa."""
    peso = peso_da_posicao(posicao, pesos)
    if cargo_extra:
        peso = max(peso, peso_da_posicao(cargo_extra, pesos))
    return peso


def apurar(candidatos: Iterable, votos: Iterable, percentual_aprovacao: int) -> dict:
    """`candidatos`: objetos com `id`, `usuario_id`. `votos`: objetos com
    `candidato_id` (None = branco) e `peso`."""
    por_candidato = {c.id: {"candidato_id": c.id, "usuario_id": c.usuario_id, "votos": 0, "ponderado": 0} for c in candidatos}
    brancos = {"votos": 0, "ponderado": 0}
    total_votos = 0
    total_ponderado = 0

    for v in votos:
        total_votos += 1
        total_ponderado += v.peso
        if v.candidato_id is None or v.candidato_id not in por_candidato:
            brancos["votos"] += 1
            brancos["ponderado"] += v.peso
            continue
        por_candidato[v.candidato_id]["votos"] += 1
        por_candidato[v.candidato_id]["ponderado"] += v.peso

    linhas = []
    for dados in por_candidato.values():
        percentual = (dados["ponderado"] / total_ponderado * 100) if total_ponderado else 0.0
        linhas.append(
            {
                **dados,
                "percentual": round(percentual, 1),
                "passou": total_ponderado > 0 and dados["ponderado"] * 100 > percentual_aprovacao * total_ponderado,
            }
        )
    linhas.sort(key=lambda d: (-d["ponderado"], -d["votos"], d["candidato_id"]))

    eleito = next((d for d in linhas if d["passou"]), None)
    for d in linhas:
        d["eleito"] = eleito is not None and d["candidato_id"] == eleito["candidato_id"]

    if total_votos == 0:
        situacao = "sem_votos"
    elif eleito:
        situacao = "eleito"
    else:
        situacao = "ninguem_eleito"

    brancos["percentual"] = round(brancos["ponderado"] / total_ponderado * 100, 1) if total_ponderado else 0.0
    return {
        "situacao": situacao,
        "percentual_aprovacao": percentual_aprovacao,
        "total_votos": total_votos,
        "total_ponderado": total_ponderado,
        "brancos": brancos,
        "candidatos": linhas,
        "eleito_candidato_id": eleito["candidato_id"] if eleito else None,
    }
