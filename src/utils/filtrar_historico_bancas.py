from typing import List, Optional
from src.models.banca_model import BancaModel
from src.models.equipe_projeto_model import EquipeProjetoModel
from src.models.semestre_model import SemestreModel
from src.utils.banca_status import banca_ja_ocorreu, calcular_status_banca
from src.utils.identificar_semestre import identificar_semestre


def filtrar_historico_bancas(
    bancas: List[BancaModel],
    equipes: List[EquipeProjetoModel],
    semestres: List[SemestreModel],
    consultor_id: Optional[int] = None,
    coordenador_id: Optional[int] = None,
    escopo_id: Optional[int] = None,
    semestre_id: Optional[int] = None
) -> List[BancaModel]:
    bancas_ids_do_consultor = None
    if consultor_id is not None:
        bancas_ids_do_consultor = {e.banca_id for e in equipes if e.usuario_id == consultor_id}

    resultado = []
    for banca in bancas:
        # Histórico é do que aconteceu. Depois da F5, `realizado_em` é quem
        # diz isso — o backfill da migration 5 preservou as bancas antigas.
        if not banca_ja_ocorreu(calcular_status_banca(banca.data_hora, banca.realizado_em)):
            continue
        if consultor_id is not None and banca.id not in bancas_ids_do_consultor:
            continue
        if coordenador_id is not None and banca.coordenador_id != coordenador_id:
            continue
        if escopo_id is not None and banca.escopo_id != escopo_id:
            continue
        if semestre_id is not None:
            semestre = identificar_semestre(banca.data_hora, semestres)
            if not semestre or semestre.id != semestre_id:
                continue
        resultado.append(banca)
    return resultado