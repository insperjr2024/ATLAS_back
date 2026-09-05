from typing import List, Dict
from src.models.avaliacao_model import AvaliacaoModel
from src.models.banca_model import BancaModel
from src.models.semestre_model import SemestreModel
from src.utils.banca_status import banca_ja_ocorreu, calcular_status_banca


def calcular_desempenho_consultor(
    usuario_id: int,
    semestre: SemestreModel,
    avaliacoes: List[AvaliacaoModel],
    bancas: List[BancaModel]
) -> Dict:
    bancas_por_id = {b.id: b for b in bancas}

    def banca_no_semestre(banca_id: int) -> bool:
        banca = bancas_por_id.get(banca_id)
        if not banca or not banca.data_hora:
            return False
        return semestre.inicio <= banca.data_hora.date() <= semestre.fim

    bancas_realizadas_semestre = [
        b for b in bancas
        if banca_no_semestre(b.id)
        and banca_ja_ocorreu(calcular_status_banca(b.data_hora, b.realizado_em, cancelada_em=getattr(b, "cancelada_em", None)))
    ]

    avaliacoes_submetidas_usuario = [
        a for a in avaliacoes
        if a.avaliador_id == usuario_id
        and a.status == "submetida"
        and banca_no_semestre(a.banca_id)
    ]

    total_bancas = len(bancas_realizadas_semestre)
    bancas_atendidas = len(avaliacoes_submetidas_usuario)
    percentual = round((bancas_atendidas / total_bancas) * 100, 2) if total_bancas > 0 else 0.0

    return {
        "semestre_id": semestre.id,
        "semestre_nome": semestre.nome,
        "bancas_atendidas": bancas_atendidas,
        "total_bancas_realizadas": total_bancas,
        "percentual": percentual
    }