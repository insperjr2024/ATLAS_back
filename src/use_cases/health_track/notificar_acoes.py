"""Avisos das ações do Health Track (§15).

Quem recebe uma ação não vê o Health Track (coordenador e consultor não
têm a caixa), então o aviso é a única forma de a pessoa saber que ficou
responsável por algo. O texto leva problema, próxima ação e prazo; a rota é
a página do projeto, que ela enxerga. As cores do Health Track não vão.
"""

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from src.use_cases.notificacao.registrar_notificacao import registrar


def _prazo(prazo: Optional[date]) -> str:
    return f" até {prazo:%d/%m}" if prazo else ""


def notificar_acao_atribuida(db: Session, acao, projeto_nome: str, por_nome: Optional[str]) -> None:
    if not acao.responsavel_id:
        return
    registrar(
        db,
        usuario_id=acao.responsavel_id,
        tipo="acao_atribuida",
        titulo=f"Você ficou responsável por uma ação em {projeto_nome}{_prazo(acao.prazo)}",
        corpo=f"Problema: {acao.problema}\nPróxima ação: {acao.proxima_acao}"
        + (f"\nAberta por {por_nome}." if por_nome else ""),
        projeto_id=acao.projeto_id,
        rota=f"/projetos/{acao.projeto_id}",
        payload={"acao_id": acao.id},
        # Chave com o responsável: trocar o responsável avisa a pessoa nova;
        # salvar sem trocar não repete o aviso.
        chave_dedup=f"acao_atribuida:acao={acao.id}:responsavel={acao.responsavel_id}",
    )


def notificar_acao_concluida(db: Session, acao, projeto_nome: str, concluida_por_id: Optional[int], por_nome: Optional[str]) -> None:
    """Pra quem abriu a ação, se não foi quem concluiu."""
    if not acao.criado_por or acao.criado_por == concluida_por_id:
        return
    registrar(
        db,
        usuario_id=acao.criado_por,
        tipo="acao_concluida",
        titulo=f"Ação concluída em {projeto_nome}: {acao.proxima_acao}" + (f" (por {por_nome})" if por_nome else ""),
        corpo=f"Problema: {acao.problema}",
        projeto_id=acao.projeto_id,
        rota=f"/health-track/projetos/{acao.projeto_id}",
        payload={"acao_id": acao.id},
        chave_dedup=f"acao_concluida:acao={acao.id}:em={acao.concluida_em:%Y%m%d%H%M%S}",
    )


def notificar_acao_prazo_vencido(db: Session, destinatario_id: int, acao, projeto_nome: str, responsavel_nome: Optional[str]) -> None:
    """O dia seguinte ao prazo, uma vez só (o job compara com "ontem")."""
    registrar(
        db,
        usuario_id=destinatario_id,
        tipo="acao_prazo_vencido",
        titulo=f"Ação em {projeto_nome} passou do prazo ({acao.prazo:%d/%m}): {acao.proxima_acao}",
        corpo=f"Problema: {acao.problema}" + (f"\nResponsável: {responsavel_nome}." if responsavel_nome else ""),
        projeto_id=acao.projeto_id,
        rota=f"/projetos/{acao.projeto_id}",
        payload={"acao_id": acao.id},
        chave_dedup=f"acao_prazo_vencido:acao={acao.id}:prazo={acao.prazo:%Y%m%d}:destinatario={destinatario_id}",
    )
