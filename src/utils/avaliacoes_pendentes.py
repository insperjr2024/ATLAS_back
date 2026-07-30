from typing import List, Dict
from src.models.candidatura_model import CandidaturaModel
from src.models.avaliacao_model import AvaliacaoModel
from src.models.banca_model import BancaModel
from src.utils.banca_status import calcular_status_banca


def calcular_avaliacoes_pendentes(
    candidaturas: List[CandidaturaModel],
    avaliacoes: List[AvaliacaoModel],
    bancas: List[BancaModel]
) -> List[Dict]:
    bancas_por_id = {b.id: b for b in bancas}
    submetidas = {(a.banca_id, a.avaliador_id) for a in avaliacoes if a.status == "submetida"}

    resultado = []
    for c in candidaturas:
        banca = bancas_por_id.get(c.banca_id)
        if not banca:
            continue
        if calcular_status_banca(banca.data_hora) != "realizada":
            continue
        if (banca.id, c.usuario_id) in submetidas:
            continue
        resultado.append({
            "usuario_id": c.usuario_id,
            "banca_id": banca.id,
            "nome_projeto": banca.nome_projeto,
            "data_hora": banca.data_hora
        })
    return resultado