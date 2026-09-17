"""§ Contratos — abrir, preencher, confirmar e gerar documentos jurídicos.

⭐ 2026-09-16 — Fase 1 da integração com a antiga plataforma Contratos. Cobre
o ciclo "abrir → preencher → confirmar → gerar rascunho"; o que vem depois
(exportar aprovação pro cliente, marcar assinado, arquivar) é fase futura —
ver o plano publicado nesta sessão.

⚠ Permissão de ABRIR um documento é por TIPO, não uma caixa só: o Contrato
de Prestação usa a mesma permissão de criar projeto (é a venda que traz os
dados dele); TEP tem caixa própria (`pode_solicitar_tep`); NDA/Uso de
Imagem/Aditivo usam `pode_responsavel_por_vendas` (BDR, Coordenador/Diretor
de Vendas, Diretora de Projetos — quem já pode "vender"/tocar comercial do
projeto). Diretoria de projetos e quem tem `pode_editar_documento_juridico`
(o Jurídico) sempre podem, qualquer tipo.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Any, Dict

from src.database.database import get_db
from src.middlewares.authorization import (
    eh_diretoria_de_projetos,
    pode_ver_projeto,
    usuario_tem_permissao,
)
from src.middlewares.validate_user_auth_token import get_current_user
from src.use_cases.documento_contratual.abrir_documento import AbrirDocumentoContratualUseCase
from src.use_cases.documento_contratual.atualizar_dados import (
    AtualizarDadosDocumentoContratualUseCase,
)
from src.use_cases.documento_contratual.confirmar_preenchimento import (
    ConfirmarPreenchimentoDocumentoContratualUseCase,
)
from src.use_cases.documento_contratual.gerar_documento import GerarDocumentoContratualUseCase
from src.use_cases.documento_contratual.get_documento import (
    GetDocumentoContratualUseCase,
    ListDocumentosContratuaisPorProjetoUseCase,
    serializar_documento_contratual,
)
from src.utils.exceptions import RegraDeNegocioError

router = APIRouter(tags=["documentos contratuais"], dependencies=[Depends(get_current_user)])


class AbrirDocumentoContratualRequest(BaseModel):
    tipo: str


class AtualizarDadosRequest(BaseModel):
    dados: Dict[str, Any]


def _pode_abrir_documento(usuario, db: Session, tipo: str) -> bool:
    if eh_diretoria_de_projetos(usuario):
        return True
    if usuario_tem_permissao(usuario, db, "pode_editar_documento_juridico"):
        return True
    if tipo == "contrato":
        return usuario_tem_permissao(usuario, db, "pode_criar_projeto")
    if tipo == "tep":
        return usuario_tem_permissao(usuario, db, "pode_solicitar_tep")
    if tipo in ("nda", "uso_imagem", "aditivo"):
        return usuario_tem_permissao(usuario, db, "pode_responsavel_por_vendas")
    return False


def _pode_editar_livre(usuario, db: Session) -> bool:
    return eh_diretoria_de_projetos(usuario) or usuario_tem_permissao(
        usuario, db, "pode_editar_documento_juridico"
    )


def _projeto_visivel_ou_404(projeto_id: int, usuario, db: Session) -> None:
    if not pode_ver_projeto(projeto_id, usuario, db):
        raise HTTPException(status_code=404, detail="Projeto não encontrado")


@router.get("/projetos/{projeto_id}/documentos-contratuais/tipos-disponiveis")
def get_tipos_disponiveis(
    projeto_id: int,
    usuario=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _projeto_visivel_ou_404(projeto_id, usuario, db)
    tipos = AbrirDocumentoContratualUseCase(db).tipos_disponiveis(projeto_id)
    # Só oferece o que a pessoa também tem permissão de abrir — a rota de
    # abrir cobra de novo (nunca confia só no que a tela escondeu), mas
    # listar tipo que ela não pode escolher seria um botão morto.
    return {"tipos": [t for t in tipos if _pode_abrir_documento(usuario, db, t)]}


@router.get("/projetos/{projeto_id}/documentos-contratuais")
def listar_documentos_do_projeto(
    projeto_id: int,
    usuario=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _projeto_visivel_ou_404(projeto_id, usuario, db)
    return {"documentos": ListDocumentosContratuaisPorProjetoUseCase(db).execute(projeto_id)}


@router.post("/projetos/{projeto_id}/documentos-contratuais", status_code=201)
def abrir_documento(
    projeto_id: int,
    request: AbrirDocumentoContratualRequest,
    usuario=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _projeto_visivel_ou_404(projeto_id, usuario, db)
    if not _pode_abrir_documento(usuario, db, request.tipo):
        raise HTTPException(
            status_code=403, detail="Sem permissão para adicionar este tipo de documento."
        )
    try:
        documento = AbrirDocumentoContratualUseCase(db).execute(projeto_id, request.tipo)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return serializar_documento_contratual(documento, ultima_versao=0)


@router.get("/documentos-contratuais/{documento_id}")
def get_documento(
    documento_id: int,
    usuario=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    documento = GetDocumentoContratualUseCase(db).execute(documento_id)
    if not documento:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    _projeto_visivel_ou_404(documento["projeto_id"], usuario, db)
    return documento


@router.patch("/documentos-contratuais/{documento_id}")
def atualizar_dados(
    documento_id: int,
    request: AtualizarDadosRequest,
    usuario=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    documento = GetDocumentoContratualUseCase(db).execute(documento_id)
    if not documento:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    _projeto_visivel_ou_404(documento["projeto_id"], usuario, db)

    pode_editar_livre = _pode_editar_livre(usuario, db)
    if not pode_editar_livre and not _pode_abrir_documento(usuario, db, documento["tipo"]):
        raise HTTPException(status_code=403, detail="Sem permissão para esta ação.")

    try:
        atualizado = AtualizarDadosDocumentoContratualUseCase(db).execute(
            documento_id, request.dados, pode_editar_livre=pode_editar_livre
        )
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return serializar_documento_contratual(atualizado)


@router.post("/documentos-contratuais/{documento_id}/confirmar")
def confirmar_preenchimento(
    documento_id: int,
    usuario=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    documento = GetDocumentoContratualUseCase(db).execute(documento_id)
    if not documento:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    _projeto_visivel_ou_404(documento["projeto_id"], usuario, db)
    if not _pode_editar_livre(usuario, db) and not _pode_abrir_documento(
        usuario, db, documento["tipo"]
    ):
        raise HTTPException(status_code=403, detail="Sem permissão para confirmar este documento.")

    try:
        confirmado = ConfirmarPreenchimentoDocumentoContratualUseCase(db).execute(documento_id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return serializar_documento_contratual(confirmado)


@router.post("/documentos-contratuais/{documento_id}/gerar")
def gerar_documento(
    documento_id: int,
    usuario=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    documento = GetDocumentoContratualUseCase(db).execute(documento_id)
    if not documento:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    _projeto_visivel_ou_404(documento["projeto_id"], usuario, db)
    if not usuario_tem_permissao(usuario, db, "pode_gerar_documento_juridico"):
        raise HTTPException(status_code=403, detail="Sem permissão para gerar documentos jurídicos.")

    try:
        versao = GerarDocumentoContratualUseCase(db).execute(documento_id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {
        "id": versao.id,
        "documento_id": versao.documento_id,
        "versao": versao.versao,
        "status_arquivo": versao.status_arquivo,
        "criado_em": versao.criado_em,
    }
