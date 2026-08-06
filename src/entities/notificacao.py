from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Notificacao:
    """Uma linha da central de notificações (§6.6).

    Só os 📌 eventos nascem daqui. As 🔄 condições viram `Condicao`
    (`utils/condicoes_alerta.py`) e só ganham linha quando alguém as marca
    como lidas — ver a docstring de `NotificacaoModel`.
    """

    id: Optional[int] = None
    usuario_id: Optional[int] = None
    tipo: str = ""
    origem: str = "evento"
    titulo: str = ""
    corpo: Optional[str] = None
    projeto_id: Optional[int] = None
    payload: dict = field(default_factory=dict)
    chave_dedup: str = ""
    lida_em: Optional[datetime] = None
    #: 🔮 Fase 2 (canal de e-mail). Sempre nulo enquanto só existir o in-app.
    email_enviado_em: Optional[datetime] = None
    criado_em: Optional[datetime] = None
