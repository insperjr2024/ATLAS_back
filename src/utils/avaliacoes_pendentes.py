from datetime import datetime, timedelta
from typing import Dict, List, Optional
from src.models.candidatura_model import CandidaturaModel
from src.models.avaliacao_model import AvaliacaoModel
from src.models.banca_model import BancaModel
from src.utils.banca_status import banca_ja_ocorreu, calcular_status_banca

#: §8 — quem avalia tem 7 dias corridos a partir da banca realizada (2026-09-09,
#: a pedido: era 2, curto demais). Depois disso o envio é bloqueado
#: (`create_avaliacao.py`), não só destacado. O lembrete "amanhã é o último
#: dia" (`rodar_lembrete_prazo_avaliacao`) é relativo a este prazo, então
#: acompanha a mudança sozinho.
PRAZO_AVALIACAO_DIAS = 7


def prazo_avaliacao(banca) -> Optional[datetime]:
    """Até quando a avaliação desta banca aceita envio pelo relógio: a
    realização mais `PRAZO_AVALIACAO_DIAS`. Nulo se a banca não aconteceu."""
    if not getattr(banca, "realizado_em", None):
        return None
    return banca.realizado_em + timedelta(days=PRAZO_AVALIACAO_DIAS)


def avaliacao_aberta(banca, agora: Optional[datetime] = None) -> bool:
    """A avaliação desta banca aceita envio agora?

    Segue o prazo, salvo quando a diretoria forçou pela tela do Dashboard
    (`prazo_avaliacao_override`, 2026-10-06, a pedido): "aberto" reabre por
    exceção pra quem esqueceu; "fechado" encerra antes da hora. É a MESMA
    régua pra submeter, criar avaliação e adicionar avaliador numa banca já
    realizada, pra uma exceção aberta aqui valer em todas as portas.
    """
    override = getattr(banca, "prazo_avaliacao_override", None)
    if override == "aberto":
        return True
    if override == "fechado":
        return False
    prazo = prazo_avaliacao(banca)
    if prazo is None:
        return False
    return (agora or datetime.now()) <= prazo


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
        prazo = prazo_avaliacao(banca)
        resultado.append({
            "usuario_id": c.usuario_id,
            "banca_id": banca.id,
            "nome_projeto": banca.nome_projeto,
            "data_hora": banca.data_hora,
            "prazo_avaliacao": prazo,
            "prazo_expirado": not avaliacao_aberta(banca),
        })
    return resultado