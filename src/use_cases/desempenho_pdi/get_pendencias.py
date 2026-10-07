from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session

from src.repositories.desempenho_mentoria_repository import DesempenhoMentoriaRepository
from src.repositories.desempenho_pdi_envio_repository import DesempenhoPdiEnvioRepository
from src.repositories.desempenho_pdi_item_repository import DesempenhoPdiItemRepository
from src.repositories.desempenho_pdi_pasta_repository import DesempenhoPdiPastaRepository
from src.repositories.usuario_repository import UsuarioRepository


def entregue_com_atraso(enviado_em: Optional[datetime], prazo: Optional[date]) -> bool:
    """Envio depois do dia do prazo. O prazo é uma data (sem hora): entregar
    no próprio dia, a qualquer hora, está no prazo."""
    if enviado_em is None or prazo is None:
        return False
    return enviado_em.date() > prazo


class ListPendenciasPdiUseCase:
    """Quem ainda não enviou o arquivo deste ITEM (não mais a pasta inteira,
    cada item da checklist tem sua própria pendência). O universo é todo
    mundo com mentoria vinculada.

    2026-10-06, a pedido: quem entregou DEPOIS do prazo da pasta continua
    na lista, marcado `status = "atrasado"`, pra diretoria ver que faltou
    no dia sem perder o registro de que acabou entregando. Quem não
    entregou é `status = "pendente"`.
    """

    def __init__(self, db: Session):
        self.mentoria_repository = DesempenhoMentoriaRepository(db)
        self.envio_repository = DesempenhoPdiEnvioRepository(db)
        self.item_repository = DesempenhoPdiItemRepository(db)
        self.pasta_repository = DesempenhoPdiPastaRepository(db)
        self.usuario_repo = UsuarioRepository(db)

    def execute(self, item_id: int) -> list[dict]:
        item = self.item_repository.get_by_id(item_id)
        pasta = self.pasta_repository.get_by_id(item.pasta_id) if item else None
        prazo = pasta.prazo if pasta else None
        envios = {e.mentorado_id: e for e in self.envio_repository.get_por_item(item_id)}
        nomes = {u.id: u.nome for u in self.usuario_repo.get_all()}
        saida = []
        for m in self.mentoria_repository.get_all():
            envio = envios.get(m.mentorado_id)
            if envio and not entregue_com_atraso(envio.enviado_em, prazo):
                continue
            saida.append(
                {
                    "mentorado_id": m.mentorado_id,
                    "mentorado_nome": nomes.get(m.mentorado_id),
                    "mentor_id": m.mentor_id,
                    "mentor_nome": nomes.get(m.mentor_id),
                    "status": "atrasado" if envio else "pendente",
                    "enviado_em": envio.enviado_em if envio else None,
                }
            )
        # Pendentes primeiro, depois quem entregou atrasado; alfabético dentro.
        saida.sort(key=lambda p: (p["status"] != "pendente", (p["mentorado_nome"] or "").casefold()))
        return saida
