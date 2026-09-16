"""Quantas bancas cada consultor/coordenador já carrega (2026-09-15, a pedido).

⭐ Mesmo dado que o push automático usa pra rodízio (`CandidaturaRepository.
contagem_bancas_por_usuario`), só que agora exposto pra diretoria/gerência
CONFERIREM — antes só existia dentro do cálculo do push, sem nenhuma tela
mostrando pra fora. Conta bancas JÁ REALIZADAS + futuras, cancelada não
conta (mesmo filtro do rodízio).
"""

from sqlalchemy.orm import Session

from src.repositories.candidatura_repository import CandidaturaRepository
from src.repositories.usuario_repository import UsuarioRepository


class GetCargaBancasUseCase:
    def __init__(self, db: Session):
        self.candidatura_repository = CandidaturaRepository(db)
        self.usuario_repository = UsuarioRepository(db)

    def execute(self) -> list[dict]:
        contagem = self.candidatura_repository.contagem_bancas_por_usuario()
        linhas = [
            {
                "usuario_id": u.id,
                "nome": u.nome,
                "posicao": u.posicao,
                "quantidade_bancas": contagem.get(u.id, 0),
            }
            for u in self.usuario_repository.get_ativos()
            if u.posicao in ("consultor", "coordenador", "gerente")
        ]
        linhas.sort(key=lambda linha: (-linha["quantidade_bancas"], linha["nome"]))
        return linhas
