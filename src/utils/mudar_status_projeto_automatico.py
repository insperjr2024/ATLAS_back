"""🤖 Trocas de `projeto.status` que o SISTEMA decide, não uma pessoa clicando
(§4 + § Contratos).

Mesma convenção de `encerrar_ambientacao.py` (Ambientação → Em andamento
sozinho quando os dias acabam): grava a troca em `projeto_status_historico`
com `alterado_por` nulo — é o que a tela de Histórico lê para escrever "pelo
sistema" em vez de um nome.

⭐ 2026-09-21 — a pedido: o ciclo do TEP move o projeto sozinho em dois
pontos. Exportar o TEP pro cliente aprovar → "Envio do TEP"; TEP assinado
(ou aceito por prazo) → "Período de ajustes". Ver `exportar_aprovacao.py` e
`marcar_assinado.py`.

⏸ Projeto pausado não é tocado — mesma cautela do encerramento de
ambientação: pausar é parar o relógio, e uma troca automática desfaria a
decisão de quem pausou.
"""

from sqlalchemy.orm import Session

from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.projeto_status_historico_repository import ProjetoStatusHistoricoRepository


def mudar_status_projeto_automaticamente(db: Session, projeto_id: int, status_novo: str) -> None:
    projeto = ProjetoRepository(db).get_by_id(projeto_id)
    if not projeto or projeto.status == status_novo or projeto.status == "pausado":
        return

    status_anterior = projeto.status
    ProjetoRepository(db).update(projeto_id, status=status_novo)
    ProjetoStatusHistoricoRepository(db).create(
        projeto_id=projeto_id,
        status_anterior=status_anterior,
        status_novo=status_novo,
        # 🤖 Sem autor: foi o ciclo do TEP, não uma pessoa escolhendo a etapa.
        alterado_por=None,
    )
