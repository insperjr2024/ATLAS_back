from typing import Dict, List, NamedTuple, Tuple

from src.models.projeto_membro_model import ProjetoMembroModel


class ParDesempenho(NamedTuple):
    avaliador_id: int
    avaliado_id: int
    form_type: str  # papel do AVALIADO — decide qual formulário abrir (consultor|coordenador)
    projeto_id: int


def calcular_pares_lote(membros: List[ProjetoMembroModel]) -> List[ParDesempenho]:
    """`membros` = `projeto_membro` ativos (saiu_em IS NULL) dos projetos
    cobertos por um lote. Regra 2.3: dentro do mesmo projeto, todo mundo
    avalia todo mundo, exceto a si mesmo e exceto coordenador avaliando
    coordenador. `form_type` é o papel de quem está sendo avaliado, porque é
    isso que decide qual formulário (consultor/coordenador) abrir."""
    por_projeto: Dict[int, List[ProjetoMembroModel]] = {}
    for membro in membros:
        por_projeto.setdefault(membro.projeto_id, []).append(membro)

    pares: List[ParDesempenho] = []
    for projeto_id, time in por_projeto.items():
        for avaliador in time:
            for avaliado in time:
                if avaliado.usuario_id == avaliador.usuario_id:
                    continue
                if avaliador.papel == "coordenador" and avaliado.papel == "coordenador":
                    continue
                pares.append(
                    ParDesempenho(
                        avaliador_id=avaliador.usuario_id,
                        avaliado_id=avaliado.usuario_id,
                        form_type=avaliado.papel,
                        projeto_id=projeto_id,
                    )
                )
    return pares


def deduplicar_pares(pares: List[ParDesempenho]) -> Dict[Tuple[int, int], dict]:
    """Colapsa (avaliador, avaliado) repetido em 2+ projetos do mesmo lote
    numa entrada só, guardando todos os `projeto_id` — as pendências
    precisam mostrar de qual projeto é cada avaliação faltante (regra 2.7).
    `form_type` é sempre igual dentro do mesmo par (mesmo avaliado = mesmo
    papel), então basta guardar o primeiro."""
    agregados: Dict[Tuple[int, int], dict] = {}
    for par in pares:
        chave = (par.avaliador_id, par.avaliado_id)
        if chave not in agregados:
            agregados[chave] = {"form_type": par.form_type, "projeto_ids": []}
        agregados[chave]["projeto_ids"].append(par.projeto_id)
    return agregados
