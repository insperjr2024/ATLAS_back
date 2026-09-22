"""§ Contratos — abrir, preencher, confirmar, gerar, exportar e aprovar
documentos jurídicos.

⭐ 2026-09-16 — Fase 1 cobriu o ciclo "abrir → preencher → confirmar → gerar
rascunho". ⭐ 2026-09-18 (Fase 2) — o resto do ciclo: exportar pro cliente
aprovar (o lado público, sem login, mora em `aprovacao_contratual.py`),
marcar como assinado e arquivar.

⚠ Permissão de ABRIR um documento é por TIPO, não uma caixa só: o Contrato
de Prestação usa a mesma permissão de criar projeto (é a venda que traz os
dados dele); NDA/Uso de Imagem/Aditivo usam `pode_responsavel_por_vendas`
(BDR, Coordenador/Diretor de Vendas, Diretora de Projetos — quem já pode
"vender"/tocar comercial do projeto). Diretoria de projetos, quem tem
`pode_editar_documento_juridico` (o Jurídico) e quem tem `pode_elaborar_
contratos_proprios`/`pode_elaborar_qualquer_contrato` sempre podem, qualquer
tipo — inclusive TEP (⭐ 2026-09-22, a pedido: `pode_solicitar_tep` foi
removida, essas caixas já cobriam o mesmo caso).
"""

import os
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Any, Dict, Optional

from src.database.database import get_db
from src.middlewares.authorization import (
    eh_diretoria_de_projetos,
    pode_ver_projeto,
    usuario_tem_permissao,
)
from src.middlewares.validate_user_auth_token import get_current_user
from src.repositories.documento_contratual_versao_repository import (
    DocumentoContratualVersaoRepository,
)
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.projeto_vendedor_repository import ProjetoVendedorRepository
from src.repositories.solicitacao_alteracao_contratual_repository import (
    SolicitacaoAlteracaoContratualRepository,
)
from src.use_cases.documento_contratual.abrir_documento import AbrirDocumentoContratualUseCase
from src.use_cases.documento_contratual.analisar_solicitacao import (
    AnalisarSolicitacaoAlteracaoUseCase,
)
from src.use_cases.documento_contratual.aprovar_internamente import (
    AprovarInternamenteDocumentoContratualUseCase,
)
from src.use_cases.documento_contratual.atualizar_dados import (
    AtualizarDadosDocumentoContratualUseCase,
)
from src.use_cases.documento_contratual.criar_institucional import (
    CriarDocumentoInstitucionalRequest,
    CriarDocumentoInstitucionalUseCase,
)
from src.use_cases.documento_contratual.confirmar_preenchimento import (
    ConfirmarPreenchimentoDocumentoContratualUseCase,
)
from src.use_cases.documento_contratual.deletar_documento import (
    DeletarDocumentoContratualUseCase,
)
from src.use_cases.documento_contratual.editar_texto import (
    EditarTextoDocumentoContratualUseCase,
    GetParagrafosEditaveisUseCase,
)
from src.use_cases.documento_contratual.exportar_aprovacao import (
    ExportarAprovacaoDocumentoContratualUseCase,
)
from src.use_cases.documento_contratual.extrair_coleta import ExtrairColetaUseCase
from src.use_cases.documento_contratual.gerar_documento import GerarDocumentoContratualUseCase
from src.use_cases.documento_contratual.identidade_institucional import (
    AtualizarIdentidadeInstitucionalUseCase,
    GetIdentidadeInstitucionalUseCase,
)
from src.use_cases.documento_contratual.painel import PainelContratualUseCase
from src.use_cases.documento_contratual.sugerir_dias_excecao import SugerirDiasExcecaoUseCase
from src.use_cases.documento_contratual.get_documento import (
    GetDocumentoContratualUseCase,
    ListDocumentosContratuaisPorProjetoUseCase,
    serializar_documento_contratual_completo,
)
from src.use_cases.documento_contratual.marcar_assinado import (
    MarcarAssinadoDocumentoContratualUseCase,
)
from src.use_cases.documento_contratual.reanexar_documento import (
    ReanexarDocumentoContratualUseCase,
)
from src.utils.erro_http import erro_de_regra
from src.utils.exceptions import RegraDeNegocioError

router = APIRouter(tags=["documentos contratuais"], dependencies=[Depends(get_current_user)])


class AbrirDocumentoContratualRequest(BaseModel):
    tipo: str


class AtualizarDadosRequest(BaseModel):
    dados: Dict[str, Any]


class EditarTextoRequest(BaseModel):
    edicoes: Dict[int, str]


class AtualizarIdentidadeRequest(BaseModel):
    dados: Dict[str, Any]


def _e_vendedor_do_projeto(usuario, db: Session, projeto_id: Optional[int]) -> bool:
    if not projeto_id:
        return False
    vendedores = ProjetoVendedorRepository(db).get_by_projeto(projeto_id)
    return any(v.usuario_id == usuario.id for v in vendedores)


def _pode_elaborar_por_caixa_nova(usuario, db: Session, projeto_id: Optional[int]) -> bool:
    """⭐ 2026-09-22 — a pedido: duas caixas novas pra quem não é diretoria/
    Jurídico mas precisa abrir/preencher/confirmar/gerar um documento
    jurídico. `pode_elaborar_qualquer_contrato` é irrestrita; `pode_
    elaborar_contratos_proprios` só vale nos projetos em que a PRÓPRIA
    pessoa é vendedora."""
    if usuario_tem_permissao(usuario, db, "pode_elaborar_qualquer_contrato"):
        return True
    if usuario_tem_permissao(usuario, db, "pode_elaborar_contratos_proprios") and _e_vendedor_do_projeto(
        usuario, db, projeto_id
    ):
        return True
    return False


def _pode_abrir_documento(usuario, db: Session, tipo: str, projeto_id: Optional[int] = None) -> bool:
    if eh_diretoria_de_projetos(usuario):
        return True
    if usuario_tem_permissao(usuario, db, "pode_editar_documento_juridico"):
        return True
    if _pode_elaborar_por_caixa_nova(usuario, db, projeto_id):
        return True
    if tipo == "contrato":
        return usuario_tem_permissao(usuario, db, "pode_criar_projeto")
    if tipo in ("nda", "uso_imagem", "aditivo"):
        return usuario_tem_permissao(usuario, db, "pode_responsavel_por_vendas")
    return False


def _pode_editar_livre(usuario, db: Session) -> bool:
    return eh_diretoria_de_projetos(usuario) or usuario_tem_permissao(
        usuario, db, "pode_editar_documento_juridico"
    )


def _pode_aprovar_internamente(usuario, db: Session) -> bool:
    """⭐ 2026-09-22 — a pedido: caixa própria, separada de `pode_editar_
    documento_juridico` (que continua sendo edição de texto pós-confirmação).
    Aprovar internamente é a revisão jurídica de verdade — fecha a etapa e
    libera exportar pro cliente."""
    return usuario_tem_permissao(usuario, db, "pode_aprovar_contrato_internamente")


def _pode_gerar_documento(usuario, db: Session, projeto_id: Optional[int] = None) -> bool:
    return eh_diretoria_de_projetos(usuario) or _pode_elaborar_por_caixa_nova(usuario, db, projeto_id)


def _pode_marcar_assinado(usuario, db: Session) -> bool:
    return eh_diretoria_de_projetos(usuario) or usuario_tem_permissao(
        usuario, db, "pode_marcar_documento_assinado"
    )


def _pode_enviar_ao_cliente(usuario, db: Session, documento: dict) -> bool:
    """⭐ 2026-09-21 — a pedido: separado de `_pode_gerar_documento`. Quem
    manda pro cliente depende do TIPO do documento — o vendedor do projeto
    no Contrato de Prestação (ele que negociou, ele que sabe o WhatsApp
    certo), diretoria de projetos ou coordenador do projeto no TEP. Continua
    exigindo que o documento já esteja `aprovado_internamente`
    (`STATUS_EXPORTACAO_PERMITIDA`) — isto só decide QUEM, não QUANDO."""
    if eh_diretoria_de_projetos(usuario):
        return True
    if usuario_tem_permissao(usuario, db, "pode_editar_documento_juridico"):
        return True
    if usuario_tem_permissao(usuario, db, "pode_elaborar_qualquer_contrato"):
        return True
    projeto_id = documento["projeto_id"]
    if documento["tipo"] == "contrato":
        return _e_vendedor_do_projeto(usuario, db, projeto_id)
    if documento["tipo"] == "tep":
        membro = ProjetoMembroRepository(db).get_atual_do_usuario_no_projeto(projeto_id, usuario.id)
        return bool(membro and membro.papel == "coordenador")
    # NDA/Uso de Imagem/Aditivo: sem pedido específico ainda, mantém o
    # comportamento de antes (Jurídico/diretoria/elaboração própria).
    return _pode_gerar_documento(usuario, db, projeto_id)


def _projeto_visivel_ou_404(projeto_id: Optional[int], usuario, db: Session) -> None:
    # ⭐ 2026-09-21 — institucional (`projeto_id` nulo, sem projeto de
    # entrega por trás) não tem projeto pra checar visibilidade contra — a
    # permissão de cada ação (gerar, aprovar, exportar...) já é quem decide
    # quem pode mexer nesse documento, aqui não há nada a mais a validar.
    if projeto_id is None:
        return
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
    return {"tipos": [t for t in tipos if _pode_abrir_documento(usuario, db, t, projeto_id)]}


@router.get("/projetos/{projeto_id}/documentos-contratuais")
def listar_documentos_do_projeto(
    projeto_id: int,
    usuario=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _projeto_visivel_ou_404(projeto_id, usuario, db)
    return {"documentos": ListDocumentosContratuaisPorProjetoUseCase(db).execute(projeto_id)}


@router.post("/documentos-contratuais/institucional")
def criar_documento_institucional(
    request: CriarDocumentoInstitucionalRequest,
    usuario=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Contrato institucional (Agro etc.) — mesma permissão de abrir aquele
    TIPO de documento num projeto normal; aqui não há projeto pra checar
    `pode_ver_projeto` contra."""
    if not _pode_abrir_documento(usuario, db, request.tipo):
        raise HTTPException(status_code=403, detail="Sem permissão para abrir este tipo de documento.")
    try:
        documento = CriarDocumentoInstitucionalUseCase(db).execute(request)
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)
    return serializar_documento_contratual_completo(db, documento, ultima_versao=None)


@router.get("/projetos/{projeto_id}/documentos-contratuais/sugerir-dias-excecao")
def sugerir_dias_excecao(
    projeto_id: int,
    inicio: date,
    fim: date,
    usuario=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dias tipo "prova" do calendário acadêmico da(s) frente(s) do projeto,
    dentro do intervalo do contrato — só sugestão, quem preenche decide o
    que de fato entra como dia de exceção (ver `SugerirDiasExcecaoUseCase`)."""
    _projeto_visivel_ou_404(projeto_id, usuario, db)
    try:
        dias = SugerirDiasExcecaoUseCase(db).execute(projeto_id, inicio, fim)
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)
    return {"dias": dias}


@router.get("/documentos-contratuais/coleta-dados/modelo")
def baixar_modelo_coleta_dados(usuario=Depends(get_current_user)):
    """O .docx em branco pra mandar ao cliente preencher — mesmos rótulos que
    `extrair_coleta.py` reconhece na volta. Arquivo estático do próprio
    deploy (não conteúdo gerado por usuário), então `FileResponse` é seguro
    aqui — ao contrário do documento gerado (ver docstring do model de
    versão), ele nasce de novo a cada deploy, não depende do disco persistir.
    """
    caminho = os.path.join(
        os.path.dirname(__file__), "..", "documentos_contratuais", "templates", "coleta_dados.docx"
    )
    if not os.path.exists(caminho):
        raise HTTPException(status_code=404, detail="Modelo não encontrado.")
    return FileResponse(
        caminho,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="Coleta de Dados - Modelo.docx",
    )


@router.post("/projetos/{projeto_id}/documentos-contratuais/extrair-coleta")
async def extrair_coleta(
    projeto_id: int,
    tipo: str,
    arquivo: UploadFile = File(...),
    usuario=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _projeto_visivel_ou_404(projeto_id, usuario, db)
    if not _pode_abrir_documento(usuario, db, tipo, projeto_id):
        raise HTTPException(status_code=403, detail="Sem permissão para preencher este tipo de documento.")

    conteudo = await arquivo.read()
    try:
        return ExtrairColetaUseCase(db).execute(projeto_id, tipo, conteudo)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/projetos/{projeto_id}/documentos-contratuais", status_code=201)
def abrir_documento(
    projeto_id: int,
    request: AbrirDocumentoContratualRequest,
    usuario=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _projeto_visivel_ou_404(projeto_id, usuario, db)
    if not _pode_abrir_documento(usuario, db, request.tipo, projeto_id):
        raise HTTPException(
            status_code=403, detail="Sem permissão para adicionar este tipo de documento."
        )
    try:
        documento = AbrirDocumentoContratualUseCase(db).execute(projeto_id, request.tipo)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return serializar_documento_contratual_completo(db, documento, ultima_versao=0)


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


@router.get("/documentos-contratuais/{documento_id}/arquivo")
def download_arquivo(
    documento_id: int,
    formato: str = "pdf",
    usuario=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Baixa o .pdf ou .docx da ÚLTIMA versão gerada — o mesmo arquivo que a
    tela de aprovação do cliente mostra, e o que o Repositório lista depois
    de assinado (nenhuma versão nova nasce depois de aprovado pelo cliente).
    """
    documento = GetDocumentoContratualUseCase(db).execute(documento_id)
    if not documento:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    _projeto_visivel_ou_404(documento["projeto_id"], usuario, db)
    if formato not in ("pdf", "docx"):
        raise HTTPException(status_code=422, detail='Formato deve ser "pdf" ou "docx".')

    versao = DocumentoContratualVersaoRepository(db).ultima_versao_obj(documento_id)
    if not versao:
        raise HTTPException(status_code=404, detail="Nenhum arquivo gerado ainda.")
    conteudo = versao.pdf_conteudo if formato == "pdf" else versao.docx_conteudo
    if not conteudo:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")

    media_type = "application/pdf" if formato == "pdf" else (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    nome = f"{documento['tipo']}_v{versao.versao}.{formato}"
    return Response(
        content=conteudo,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


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
    if not pode_editar_livre and not _pode_abrir_documento(
        usuario, db, documento["tipo"], documento["projeto_id"]
    ):
        raise HTTPException(status_code=403, detail="Sem permissão para esta ação.")

    try:
        atualizado = AtualizarDadosDocumentoContratualUseCase(db).execute(
            documento_id, request.dados, pode_editar_livre=pode_editar_livre
        )
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return serializar_documento_contratual_completo(db, atualizado)


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
        usuario, db, documento["tipo"], documento["projeto_id"]
    ):
        raise HTTPException(status_code=403, detail="Sem permissão para confirmar este documento.")

    try:
        confirmado = ConfirmarPreenchimentoDocumentoContratualUseCase(db).execute(
            documento_id, confirmado_por=usuario.id
        )
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)

    return serializar_documento_contratual_completo(db, confirmado)


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
    if not _pode_gerar_documento(usuario, db, documento["projeto_id"]):
        raise HTTPException(status_code=403, detail="Sem permissão para gerar documentos jurídicos.")

    try:
        versao = GerarDocumentoContratualUseCase(db).execute(documento_id)
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)
    return {
        "id": versao.id,
        "documento_id": versao.documento_id,
        "versao": versao.versao,
        "status_arquivo": versao.status_arquivo,
        "criado_em": versao.criado_em,
    }


@router.post("/documentos-contratuais/{documento_id}/aprovar-internamente")
def aprovar_internamente(
    documento_id: int,
    usuario=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    documento = GetDocumentoContratualUseCase(db).execute(documento_id)
    if not documento:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    _projeto_visivel_ou_404(documento["projeto_id"], usuario, db)
    if not _pode_aprovar_internamente(usuario, db):
        raise HTTPException(status_code=403, detail="Sem permissão para aprovar documentos jurídicos.")

    try:
        aprovado = AprovarInternamenteDocumentoContratualUseCase(db).execute(
            documento_id, aprovado_por=usuario.id
        )
    except RegraDeNegocioError as e:
        raise erro_de_regra(e)
    ultima_versao = DocumentoContratualVersaoRepository(db).ultima_versao(documento_id)
    return serializar_documento_contratual_completo(db, aprovado, ultima_versao=ultima_versao)


@router.post("/documentos-contratuais/{documento_id}/exportar-aprovacao")
def exportar_aprovacao(
    documento_id: int,
    usuario=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    documento = GetDocumentoContratualUseCase(db).execute(documento_id)
    if not documento:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    _projeto_visivel_ou_404(documento["projeto_id"], usuario, db)
    if not _pode_enviar_ao_cliente(usuario, db, documento):
        raise HTTPException(status_code=403, detail="Sem permissão para exportar documentos jurídicos.")

    try:
        return ExportarAprovacaoDocumentoContratualUseCase(db).execute(documento_id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/documentos-contratuais/{documento_id}/recusar-assinatura-tep")
def recusar_assinatura_tep(
    documento_id: int,
    usuario=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    documento = GetDocumentoContratualUseCase(db).execute(documento_id)
    if not documento:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    _projeto_visivel_ou_404(documento["projeto_id"], usuario, db)
    if not _pode_enviar_ao_cliente(usuario, db, documento):
        raise HTTPException(status_code=403, detail="Sem permissão para exportar documentos jurídicos.")

    try:
        return ExportarAprovacaoDocumentoContratualUseCase(db).recusar_assinatura_tep(documento_id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/documentos-contratuais/{documento_id}/marcar-assinado")
def marcar_assinado(
    documento_id: int,
    usuario=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    documento = GetDocumentoContratualUseCase(db).execute(documento_id)
    if not documento:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    _projeto_visivel_ou_404(documento["projeto_id"], usuario, db)
    if not _pode_marcar_assinado(usuario, db):
        raise HTTPException(status_code=403, detail="Sem permissão para marcar documentos como assinados.")

    try:
        atualizado = MarcarAssinadoDocumentoContratualUseCase(db).execute(documento_id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=409, detail=str(e))
    ultima_versao = DocumentoContratualVersaoRepository(db).ultima_versao(documento_id)
    return serializar_documento_contratual_completo(db, atualizado, ultima_versao=ultima_versao)


@router.post("/documentos-contratuais/{documento_id}/considerar-aceito-por-prazo")
def considerar_aceito_por_prazo(
    documento_id: int,
    usuario=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    documento = GetDocumentoContratualUseCase(db).execute(documento_id)
    if not documento:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    _projeto_visivel_ou_404(documento["projeto_id"], usuario, db)
    if not _pode_marcar_assinado(usuario, db):
        raise HTTPException(status_code=403, detail="Sem permissão para marcar documentos como assinados.")

    try:
        atualizado = MarcarAssinadoDocumentoContratualUseCase(db).considerar_aceito_por_prazo(
            documento_id
        )
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=409, detail=str(e))
    ultima_versao = DocumentoContratualVersaoRepository(db).ultima_versao(documento_id)
    return serializar_documento_contratual_completo(db, atualizado, ultima_versao=ultima_versao)


@router.get("/documentos-contratuais/{documento_id}/solicitacoes-alteracao")
def listar_solicitacoes_alteracao(
    documento_id: int,
    usuario=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    documento = GetDocumentoContratualUseCase(db).execute(documento_id)
    if not documento:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    _projeto_visivel_ou_404(documento["projeto_id"], usuario, db)

    solicitacoes = SolicitacaoAlteracaoContratualRepository(db).list_by_documento(documento_id)
    return {
        "solicitacoes": [
            {
                "id": s.id,
                "documento_id": s.documento_id,
                "versao_id": s.versao_id,
                "texto": s.texto,
                "trechos": s.trechos or [],
                "status": s.status,
                "criado_em": s.criado_em,
            }
            for s in solicitacoes
        ]
    }


@router.patch("/solicitacoes-alteracao-contratual/{solicitacao_id}/analisar")
def analisar_solicitacao(
    solicitacao_id: int,
    usuario=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    solicitacao = SolicitacaoAlteracaoContratualRepository(db).get_by_id(solicitacao_id)
    if not solicitacao:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada")
    documento = GetDocumentoContratualUseCase(db).execute(solicitacao.documento_id)
    if not documento:
        raise HTTPException(status_code=404, detail="Solicitação não encontrada")
    _projeto_visivel_ou_404(documento["projeto_id"], usuario, db)
    if not _pode_editar_livre(usuario, db):
        raise HTTPException(status_code=403, detail="Sem permissão para analisar esta solicitação.")

    try:
        analisada = AnalisarSolicitacaoAlteracaoUseCase(db).execute(solicitacao_id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {
        "id": analisada.id,
        "documento_id": analisada.documento_id,
        "status": analisada.status,
    }


@router.get("/documentos-contratuais/{documento_id}/paragrafos-editaveis")
def get_paragrafos_editaveis(
    documento_id: int,
    usuario=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    documento = GetDocumentoContratualUseCase(db).execute(documento_id)
    if not documento:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    _projeto_visivel_ou_404(documento["projeto_id"], usuario, db)
    if not _pode_editar_livre(usuario, db):
        raise HTTPException(status_code=403, detail="Sem permissão para editar este documento.")

    try:
        return {"paragrafos": GetParagrafosEditaveisUseCase(db).execute(documento_id)}
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.patch("/documentos-contratuais/{documento_id}/texto")
def editar_texto(
    documento_id: int,
    request: EditarTextoRequest,
    usuario=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    documento = GetDocumentoContratualUseCase(db).execute(documento_id)
    if not documento:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    _projeto_visivel_ou_404(documento["projeto_id"], usuario, db)
    if not _pode_editar_livre(usuario, db):
        raise HTTPException(status_code=403, detail="Sem permissão para editar este documento.")

    try:
        return EditarTextoDocumentoContratualUseCase(db).execute(documento_id, request.edicoes)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/documentos-contratuais/{documento_id}/reanexar")
async def reanexar_documento(
    documento_id: int,
    arquivo: UploadFile = File(...),
    usuario=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    documento = GetDocumentoContratualUseCase(db).execute(documento_id)
    if not documento:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    _projeto_visivel_ou_404(documento["projeto_id"], usuario, db)
    if not _pode_editar_livre(usuario, db):
        raise HTTPException(status_code=403, detail="Sem permissão para editar este documento.")

    docx_bytes = await arquivo.read()
    try:
        versao = ReanexarDocumentoContratualUseCase(db).execute(documento_id, docx_bytes)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {
        "id": versao.id,
        "documento_id": versao.documento_id,
        "versao": versao.versao,
        "status_arquivo": versao.status_arquivo,
        "criado_em": versao.criado_em,
    }


@router.delete("/documentos-contratuais/{documento_id}", status_code=204)
def deletar_documento(
    documento_id: int,
    usuario=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    documento = GetDocumentoContratualUseCase(db).execute(documento_id)
    if not documento:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    _projeto_visivel_ou_404(documento["projeto_id"], usuario, db)
    if not _pode_editar_livre(usuario, db) and not _pode_abrir_documento(
        usuario, db, documento["tipo"], documento["projeto_id"]
    ):
        raise HTTPException(status_code=403, detail="Sem permissão para apagar este documento.")

    try:
        DeletarDocumentoContratualUseCase(db).execute(documento_id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/identidade-institucional")
def get_identidade_institucional(
    usuario=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not eh_diretoria_de_projetos(usuario) and not usuario_tem_permissao(
        usuario, db, "pode_editar_identidade_institucional"
    ):
        raise HTTPException(status_code=403, detail="Sem permissão para ver a identidade institucional.")
    identidade = GetIdentidadeInstitucionalUseCase(db).execute()
    if not identidade:
        raise HTTPException(status_code=404, detail="Identidade institucional não configurada")
    return _serializar_identidade(identidade)


@router.patch("/identidade-institucional")
def atualizar_identidade_institucional(
    request: AtualizarIdentidadeRequest,
    usuario=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not eh_diretoria_de_projetos(usuario) and not usuario_tem_permissao(
        usuario, db, "pode_editar_identidade_institucional"
    ):
        raise HTTPException(status_code=403, detail="Sem permissão para editar a identidade institucional.")
    try:
        atualizado = AtualizarIdentidadeInstitucionalUseCase(db).execute(request.dados)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _serializar_identidade(atualizado)


def _serializar_identidade(identidade) -> dict:
    return {
        campo: getattr(identidade, campo)
        for campo in (
            "presidente_nome", "presidente_cpf", "presidente_rg", "presidente_orgao_emissor",
            "presidente_endereco_rua", "presidente_endereco_numero", "presidente_endereco_complemento",
            "presidente_endereco_bairro", "presidente_endereco_cidade", "presidente_endereco_estado",
            "presidente_endereco_cep",
            "presidente_estado_civil", "presidente_nacionalidade",
            "presidente_profissao", "presidente_email", "presidente_telefone",
            "testemunha1_nome", "testemunha1_cpf", "testemunha1_email", "testemunha1_telefone",
            "testemunha2_nome", "testemunha2_cpf", "testemunha2_email", "testemunha2_telefone",
        )
    }


@router.get("/contratos-painel")
def get_painel_contratual(
    usuario=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Sem gate de permissão aqui: o use case já filtra por LINHA (vendedor/
    # coordenador do projeto, diretoria, Jurídico, ou a caixa `pode_ver_
    # painel_contratos`) — quem não se encaixa em nenhum desses recebe lista
    # vazia, não 403. Um 403 exigiria refazer a mesma conta só pra decidir
    # se deixa passar, e a resposta seria a mesma (nada pra ver).
    return {"itens": PainelContratualUseCase(db).execute(usuario)}
