from datetime import datetime, timedelta
from typing import List, Dict
from src.models.candidatura_model import CandidaturaModel
from src.models.avaliacao_model import AvaliacaoModel
from src.models.banca_model import BancaModel
from src.utils.banca_status import banca_ja_ocorreu, calcular_status_banca

#: §8 — quem avalia tem 2 dias corridos a partir da banca realizada. Depois
#: disso o envio é bloqueado (`create_avaliacao.py`), não só destacado.
PRAZO_AVALIACAO_DIAS = 2


def calcular_avaliacoes_pendentes(
    candidaturas: List[CandidaturaModel],
    avaliacoes: List[AvaliacaoModel],
    bancas: List[BancaModel],
    sessao_por_banca: Dict[int, int] = None,
) -> List[Dict]:
    """Quem ainda deve avaliar, e até quando.

    ⭐ **A pendência é por SESSÃO** (§9). `avaliacao.banca_id` é o mesmo na 1ª e
    na 2ª tentativa: sem o número da sessão na chave, quem avaliou a banca que
    reprovou apareceria como "já enviou" na segunda, e nunca seria cobrado a
    avaliá-la. `sessao_por_banca` mapeia banca → sessão corrente; ausente, tudo
    cai em 1, que é o estado de quem nunca remarcou.
    """
    bancas_por_id = {b.id: b for b in bancas}
    sessao_por_banca = sessao_por_banca or {}
    submetidas = {
        (a.banca_id, a.avaliador_id, getattr(a, "sessao", 1) or 1)
        for a in avaliacoes
        if a.status == "submetida"
    }

    resultado = []
    for c in candidaturas:
        banca = bancas_por_id.get(c.banca_id)
        if not banca:
            continue
        # Banca que não aconteceu não tem o que avaliar. Depois da F5 isto
        # depende de `realizado_em`, não mais do relógio.
        if not banca_ja_ocorreu(calcular_status_banca(banca.data_hora, banca.realizado_em, cancelada_em=getattr(banca, "cancelada_em", None))):
            continue
        sessao = sessao_por_banca.get(banca.id, 1)
        if (banca.id, c.usuario_id, sessao) in submetidas:
            continue
        prazo = banca.realizado_em + timedelta(days=PRAZO_AVALIACAO_DIAS)
        resultado.append({
            "usuario_id": c.usuario_id,
            "banca_id": banca.id,
            "nome_projeto": banca.nome_projeto,
            "data_hora": banca.data_hora,
            "prazo_avaliacao": prazo,
            "prazo_expirado": datetime.now() > prazo,
        })
    return resultado