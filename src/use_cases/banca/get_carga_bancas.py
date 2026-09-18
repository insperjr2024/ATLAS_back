"""Quantas bancas cada consultor/coordenador já carrega (2026-09-15, a pedido).

⭐ Mesmo dado que o push automático usa pra rodízio (`CandidaturaRepository.
contagem_bancas_por_usuario`), só que agora exposto pra diretoria/gerência
CONFERIREM — antes só existia dentro do cálculo do push, sem nenhuma tela
mostrando pra fora. Cancelada não conta (mesmo filtro do rodízio), e por
padrão soma JÁ REALIZADAS + futuras — mas aqui, diferente do push, o recorte
é escolha de quem está olhando (`filtro`, 2026-09-17, a pedido): só quem já
avaliou, só quem ainda vai, ou as duas somadas.
"""

from typing import Literal

from sqlalchemy.orm import Session

from src.repositories.candidatura_repository import CandidaturaRepository
from src.repositories.usuario_repository import UsuarioRepository

FiltroCargaBancas = Literal["todas", "realizadas", "futuras"]

#: `None` pra `contagem_bancas_por_usuario` quer dizer "sem filtro de
#: realizado_em" — mesmo default do push.
_REALIZADO_POR_FILTRO: dict[str, bool | None] = {
    "todas": None,
    "realizadas": True,
    "futuras": False,
}


class GetCargaBancasUseCase:
    def __init__(self, db: Session):
        self.candidatura_repository = CandidaturaRepository(db)
        self.usuario_repository = UsuarioRepository(db)

    def execute(self, filtro: FiltroCargaBancas = "todas") -> list[dict]:
        realizado = _REALIZADO_POR_FILTRO[filtro]
        contagem = self.candidatura_repository.contagem_bancas_por_usuario(realizado)
        linhas = [
            {
                "usuario_id": u.id,
                "nome": u.nome,
                "posicao": u.posicao,
                "quantidade_bancas": contagem.get(u.id, 0),
            }
            for u in self.usuario_repository.get_ativos()
            # ⚠ 2026-09-16, corrigido: "vendas" (o antigo `coordenador_vendas`,
            # virou cargo de verdade na migration `bb255f970798`) some daqui
            # sem isto — continua sendo escalado pelo push (cobre o TOTAL da
            # banca, só não fecha piso de frente) e a diretoria perde o
            # rastro da carga dele, como se tivesse se desalocado sozinho.
            if u.posicao in ("consultor", "coordenador", "gerente", "vendas")
        ]
        linhas.sort(key=lambda linha: (-linha["quantidade_bancas"], linha["nome"]))
        return linhas
