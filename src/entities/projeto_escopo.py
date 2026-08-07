from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class ProjetoEscopo:
    """O escopo vendido dentro de um projeto (§4, §5.1).

    "Outro" = `escopo_id` vazio + `nome_customizado` preenchido — o use case
    valida que exatamente um dos dois existe, nunca os dois nem nenhum.
    """

    id: Optional[int] = None
    projeto_id: Optional[int] = None
    escopo_id: Optional[int] = None
    nome_customizado: Optional[str] = None
    frente_id: Optional[int] = None
    # ⭐ Imutável — o registro comercial. Precisar de mais tempo soma em
    # `dias_uteis_ajustados`; o que passar dos dois é atraso, e é derivado.
    dias_uteis_vendidos: int = 0
    dias_uteis_ajustados: int = 0
    status: str = "nao_iniciado"
    # ⭐ A reunião inicial. Abre a janela do escopo e faz a contagem correr.
    data_inicio: Optional[date] = None
    data_entrega_planejada: Optional[date] = None
    # Preenchê-la congela a contagem (§5.4) — trava do §5.5 no use case.
    data_entrega_real: Optional[date] = None
    tipo_atraso_entrega: Optional[str] = None
