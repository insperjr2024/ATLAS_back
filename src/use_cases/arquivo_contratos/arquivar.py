"""O que o ATLAS faz sozinho no arquivo: pasta da gestão, pasta do projeto,
o PDF do contrato assinado, e o "[DELETADO] " de quem saiu do kanban."""

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from src.repositories.arquivo_contratos_repository import (
    ArquivoContratosItemRepository,
    ArquivoContratosPastaRepository,
)
from src.repositories.documento_contratual_versao_repository import DocumentoContratualVersaoRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.semestre_repository import SemestreRepository
from src.use_cases.documento_contratual.modelos import ROTULOS
from src.utils.fuso import agora_utc

PREFIXO_DELETADO = "[DELETADO] "

_MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "março": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}


def data_de_assinatura(dados: Optional[dict]) -> Optional[date]:
    """A data digitada no bloco "Assinatura" do preenchimento (dia, mês por
    número ou nome, ano). Nulo se faltar ou não fechar uma data."""
    assinatura = (dados or {}).get("assinatura") or {}
    try:
        dia = int(assinatura.get("dia"))
        ano = int(assinatura.get("ano"))
        mes_bruto = str(assinatura.get("mes") or "").strip().lower()
        mes = int(mes_bruto) if mes_bruto.isdigit() else _MESES.get(mes_bruto)
        if not mes:
            return None
        return date(ano, mes, dia)
    except (TypeError, ValueError):
        return None


def garantir_pasta_semestre(db: Session, semestre):
    pastas = ArquivoContratosPastaRepository(db)
    pasta = pastas.get_por_semestre(semestre.id)
    if pasta:
        return pasta
    return pastas.create(nome=semestre.nome, pai_id=None, semestre_id=semestre.id)


def garantir_pasta_projeto(db: Session, pasta_semestre, projeto_id: Optional[int], nome_fallback: str):
    pastas = ArquivoContratosPastaRepository(db)
    if projeto_id is not None:
        pasta = pastas.get_projeto_em(pasta_semestre.id, projeto_id)
        if pasta:
            return pasta
        projeto = ProjetoRepository(db).get_by_id(projeto_id)
        nome = projeto.nome if projeto else nome_fallback
        return pastas.create(nome=nome, pai_id=pasta_semestre.id, projeto_id=projeto_id)
    # Documento institucional (sem projeto): pasta pelo nome, sem vínculo.
    for p in pastas.get_filhas(pasta_semestre.id):
        if p.projeto_id is None and p.nome == nome_fallback:
            return p
    return pastas.create(nome=nome_fallback, pai_id=pasta_semestre.id)


def nome_do_arquivo(documento, nome_projeto: str) -> str:
    return f"{nome_projeto} - {ROTULOS.get(documento.tipo, documento.tipo)}.pdf"


def arquivar_documento_assinado(db: Session, documento) -> Optional[object]:
    """Põe (ou atualiza) o PDF da última versão em Gestão/Projeto. A gestão é
    a da DATA DE ASSINATURA digitada; sem ela, a de hoje. Sem gestão
    cadastrada pra data, não arquiva (nada quebra: o kanban segue)."""
    versao = DocumentoContratualVersaoRepository(db).ultima_versao_obj(documento.id)
    if not versao or not versao.pdf_conteudo:
        return None
    semestres = SemestreRepository(db)
    quando = data_de_assinatura(documento.dados) or date.today()
    semestre = semestres.get_por_data(quando) or semestres.get_por_data(date.today())
    if not semestre:
        return None

    pasta_semestre = garantir_pasta_semestre(db, semestre)
    nome_projeto = (
        documento.projeto.nome
        if getattr(documento, "projeto_id", None) and getattr(documento, "projeto", None)
        else (documento.nome_projeto_externo or documento.cliente_externo or "Sem projeto")
    )
    pasta_projeto = garantir_pasta_projeto(db, pasta_semestre, documento.projeto_id, nome_projeto)

    itens = ArquivoContratosItemRepository(db)
    nome = nome_do_arquivo(documento, nome_projeto)
    conteudo = bytes(versao.pdf_conteudo)
    existente = next((i for i in itens.get_por_documento(documento.id)), None)
    if existente:
        return itens.update(
            existente.id,
            nome=nome,
            conteudo=conteudo,
            tamanho=len(conteudo),
            pasta_id=pasta_projeto.id,
            atualizado_em=agora_utc(),
        )
    return itens.create(
        pasta_id=pasta_projeto.id,
        nome=nome,
        mime="application/pdf",
        tamanho=len(conteudo),
        conteudo=conteudo,
        origem="atlas",
        documento_id=documento.id,
    )


def marcar_documento_deletado(db: Session, documento_id: int) -> None:
    """Apagar no kanban não apaga do arquivo: o item ganha o prefixo e
    perde o vínculo."""
    itens = ArquivoContratosItemRepository(db)
    for item in itens.get_por_documento(documento_id):
        nome = item.nome if item.nome.startswith(PREFIXO_DELETADO) else PREFIXO_DELETADO + item.nome
        itens.update(item.id, nome=nome, documento_id=None, atualizado_em=agora_utc())
