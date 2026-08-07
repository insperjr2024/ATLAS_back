"""O núcleo da Prioridade 1: Projeto → equipe → status (§4, §6.3, §6.4)."""

from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from src.database.database import get_db
from src.middlewares.authorization import (
    exigir_acesso_ao_projeto,
    require_diretor,
    require_gestao,
    require_lideranca,
    require_pode_criar_projeto,
    require_pode_editar_equipe,
    require_pode_marcar_kickoff,
    require_pode_ver_proprios_projetos,
)
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.use_cases.projeto_escopo.create_escopo_projeto import (
    CreateEscopoProjetoUseCase,
    EscopoVendidoRequest,
)
from src.use_cases.projeto_escopo.get_escopos_projeto import (
    ListEscoposProjetoUseCase,
    ListTodosEscoposVendidosUseCase,
)
from src.use_cases.projeto_escopo.update_escopo_projeto import (
    ClassificarAtrasoEntregaRequest,
    ClassificarAtrasoEntregaUseCase,
    DeleteEscopoProjetoUseCase,
    RegistrarEntregaEscopoRequest,
    RegistrarEntregaEscopoUseCase,
    UpdateEscopoProjetoRequest,
    UpdateEscopoProjetoUseCase,
)
from src.middlewares.validate_user_auth_token import get_current_user
from src.use_cases.projeto.arquivar_projeto import ArquivarProjetoUseCase, DesarquivarProjetoUseCase
from src.use_cases.projeto.create_projeto import CreateProjetoUseCase, CreateProjetoRequest
from src.use_cases.projeto.delete_projeto import DeleteProjetoPermanenteUseCase
from src.use_cases.projeto.get_projeto import (
    GetHistoricoProjetoUseCase,
    GetProjetoUseCase,
    ListProjetosUseCase,
)
from src.use_cases.projeto.ocultar_historico import (
    MostrarHistoricoCompletoUseCase,
    OcultarHistoricoUseCase,
)
from src.use_cases.projeto.update_equipe_projeto import (
    UpdateEquipeProjetoUseCase,
    UpdateEquipeProjetoRequest,
)
from src.use_cases.projeto.update_kickoff import (
    UpdateKickoffRequest,
    UpdateKickoffUseCase,
)
from src.use_cases.projeto.update_descricao import UpdateDescricaoRequest, UpdateDescricaoUseCase
from src.use_cases.projeto.update_configuracoes import (
    UpdateDiaReuniaoPadraoRequest,
    UpdateDiaReuniaoPadraoUseCase,
    UpdateDiasAmbientacaoRequest,
    UpdateDiasAmbientacaoUseCase,
)
from src.use_cases.projeto.excluir_justificativa_atraso import ExcluirJustificativaAtrasoUseCase
from src.use_cases.projeto.excluir_remarcacao_banca import ExcluirRemarcacaoBancaUseCase
from src.use_cases.projeto.registrar_justificativa_atraso import (
    RegistrarJustificativaAtrasoRequest,
    RegistrarJustificativaAtrasoUseCase,
)
from src.use_cases.projeto.update_status import UpdateStatusRequest, UpdateStatusUseCase
from src.use_cases.projeto.upload_anexo_proposta import UploadAnexoPropostaUseCase
from src.repositories.projeto_repository import ProjetoRepository
from src.utils.exceptions import RegraDeNegocioError
from src.utils.storage import pasta_propostas

router = APIRouter(tags=["projetos"], dependencies=[Depends(get_current_user)])


@router.post("/projetos")
def create_projeto(request: CreateProjetoRequest, current_user=Depends(require_pode_criar_projeto), db: Session = Depends(get_db)):
    try:
        return CreateProjetoUseCase(db).execute(request, criado_por=current_user.id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/projetos")
def list_projetos(
    frente_id: Optional[int] = None,
    incluir_arquivados: bool = False,
    current_user=Depends(require_pode_ver_proprios_projetos),
    db: Session = Depends(get_db),
):
    return ListProjetosUseCase(db).execute(current_user, frente_id=frente_id, incluir_arquivados=incluir_arquivados)


@router.get("/projetos/{projeto_id}")
def get_projeto(projeto_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    result = GetProjetoUseCase(db).execute(projeto_id)
    if not result:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return result


@router.put("/projetos/{projeto_id}/equipe")
def update_equipe(projeto_id: int, request: UpdateEquipeProjetoRequest, current_user=Depends(require_pode_editar_equipe), db: Session = Depends(get_db)):
    # `require_gestao` só diz "é diretor ou gerente" — sem o recorte, um
    # gerente de Business editava a equipe de um projeto de Direito.
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    try:
        result = UpdateEquipeProjetoUseCase(db).execute(projeto_id, request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return result


@router.patch("/projetos/{projeto_id}/kickoff")
def update_kickoff(projeto_id: int, request: UpdateKickoffRequest, current_user=Depends(require_pode_marcar_kickoff), db: Session = Depends(get_db)):
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    result = UpdateKickoffUseCase(db).execute(projeto_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return result


# ⭐ Não há rota de "entrega ao cliente" do projeto: ela é a entrega do ESCOPO
# (`PATCH /escopos-projeto/{id}/entrega`), e a do projeto é derivada da última.
# Entrega ao cliente e entrega do escopo são a mesma coisa (§5.5).


@router.patch("/projetos/{projeto_id}/descricao")
def update_descricao(projeto_id: int, request: UpdateDescricaoRequest, current_user=Depends(require_pode_editar_equipe), db: Session = Depends(get_db)):
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    result = UpdateDescricaoUseCase(db).execute(projeto_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return result


@router.patch("/projetos/{projeto_id}/dias-ambientacao")
def update_dias_ambientacao(projeto_id: int, request: UpdateDiasAmbientacaoRequest, current_user=Depends(require_pode_editar_equipe), db: Session = Depends(get_db)):
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    result = UpdateDiasAmbientacaoUseCase(db).execute(projeto_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return result


@router.patch("/projetos/{projeto_id}/dia-reuniao-padrao")
def update_dia_reuniao_padrao(projeto_id: int, request: UpdateDiaReuniaoPadraoRequest, current_user=Depends(require_pode_editar_equipe), db: Session = Depends(get_db)):
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    result = UpdateDiaReuniaoPadraoUseCase(db).execute(projeto_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return result


@router.patch("/projetos/{projeto_id}/status")
def update_status(projeto_id: int, request: UpdateStatusRequest, current_user=Depends(require_lideranca), db: Session = Depends(get_db)):
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    try:
        result = UpdateStatusUseCase(db).execute(projeto_id, request, alterado_por=current_user.id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return result


@router.get("/projetos/{projeto_id}/historico")
def get_historico(
    projeto_id: int,
    incluir_ocultos: bool = False,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    return GetHistoricoProjetoUseCase(db).execute(projeto_id, incluir_ocultos=incluir_ocultos)


@router.patch("/projetos/{projeto_id}/historico/ocultar")
def ocultar_historico(projeto_id: int, current_user=Depends(require_gestao), db: Session = Depends(get_db)):
    """"Limpar histórico" (§4): some da timeline, nada é apagado — ver OcultarHistoricoUseCase."""
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    result = OcultarHistoricoUseCase(db).execute(projeto_id)
    if not result:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return {"id": result.id, "historico_oculto_ate": result.historico_oculto_ate}


@router.patch("/projetos/{projeto_id}/historico/mostrar-tudo")
def mostrar_historico_completo(
    projeto_id: int, current_user=Depends(require_gestao), db: Session = Depends(get_db)
):
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    result = MostrarHistoricoCompletoUseCase(db).execute(projeto_id)
    if not result:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return {"id": result.id, "historico_oculto_ate": result.historico_oculto_ate}


@router.post("/projetos/{projeto_id}/justificativa-atraso")
def registrar_justificativa_atraso(
    projeto_id: int,
    request: RegistrarJustificativaAtrasoRequest,
    current_user=Depends(require_diretor),
    db: Session = Depends(get_db),
):
    """§7.4 — só a diretoria registra o porquê de um atraso."""
    try:
        result = RegistrarJustificativaAtrasoUseCase(db).execute(
            projeto_id, request, registrado_por=current_user.id
        )
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return result


@router.delete("/projetos/{projeto_id}/justificativa-atraso/{justificativa_id}", status_code=204)
def excluir_justificativa_atraso(
    projeto_id: int,
    justificativa_id: int,
    current_user=Depends(require_diretor),
    db: Session = Depends(get_db),
):
    """§7.4 — não é edição de rotina, é pra corrigir engano/teste."""
    sucesso = ExcluirJustificativaAtrasoUseCase(db).execute(projeto_id, justificativa_id)
    if not sucesso:
        raise HTTPException(status_code=404, detail="Justificativa não encontrada")


@router.delete("/projetos/{projeto_id}/remarcacao-banca/{remarcacao_id}", status_code=204)
def excluir_remarcacao_banca(
    projeto_id: int,
    remarcacao_id: int,
    current_user=Depends(require_diretor),
    db: Session = Depends(get_db),
):
    """§5.6 — mesma lógica: correção de engano/teste, não rotina."""
    sucesso = ExcluirRemarcacaoBancaUseCase(db).execute(projeto_id, remarcacao_id)
    if not sucesso:
        raise HTTPException(status_code=404, detail="Remarcação não encontrada")


@router.patch("/projetos/{projeto_id}/arquivar")
def arquivar_projeto(projeto_id: int, current_user=Depends(require_gestao), db: Session = Depends(get_db)):
    """Arquivar não é excluir — some das listagens, nada é apagado."""
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    try:
        result = ArquivarProjetoUseCase(db).execute(projeto_id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return {"id": result.id, "arquivado_em": result.arquivado_em}


@router.patch("/projetos/{projeto_id}/desarquivar")
def desarquivar_projeto(projeto_id: int, current_user=Depends(require_gestao), db: Session = Depends(get_db)):
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    try:
        result = DesarquivarProjetoUseCase(db).execute(projeto_id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return {"id": result.id, "arquivado_em": result.arquivado_em}


@router.delete("/projetos/{projeto_id}")
def deletar_projeto_permanente(
    projeto_id: int, current_user=Depends(require_diretor), db: Session = Depends(get_db)
):
    """Apagar de vez — só um projeto já arquivado, e sem volta. Restrito à
    diretoria: mais pesado que arquivar, que já é diretor+gerente."""
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    try:
        result = DeleteProjetoPermanenteUseCase(db).execute(projeto_id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if result is None:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return result


@router.post("/projetos/{projeto_id}/anexo-proposta")
def upload_anexo_proposta(
    projeto_id: int,
    arquivo: UploadFile = File(...),
    current_user=Depends(require_gestao),
    db: Session = Depends(get_db),
):
    """A proposta é ou link (mandado na criação), ou este PDF — nunca os dois."""
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    try:
        return UploadAnexoPropostaUseCase(db).execute(projeto_id, arquivo)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/projetos/{projeto_id}/anexo-proposta")
def download_anexo_proposta(projeto_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    projeto = ProjetoRepository(db).get_by_id(projeto_id)
    if not projeto or not projeto.anexo_proposta_path:
        raise HTTPException(status_code=404, detail="Anexo não encontrado")
    caminho = pasta_propostas() / projeto.anexo_proposta_path
    if not caminho.exists():
        raise HTTPException(status_code=404, detail="Anexo não encontrado")
    return FileResponse(
        caminho,
        media_type="application/pdf",
        filename=projeto.anexo_proposta_nome or "proposta.pdf",
    )


# ------------------------------------------------------------------ escopos (F4)
#
# Rotas de detalhe são chaveadas por `escopo_id`; o acesso é resolvido subindo
# escopo → projeto, em `_projeto_do_escopo`. A regra mora nos use cases.


def _projeto_do_escopo(escopo_id: int, current_user, db: Session) -> int:
    escopo = ProjetoEscopoRepository(db).get_by_id(escopo_id)
    if not escopo:
        raise HTTPException(status_code=404, detail="Escopo não encontrado")
    exigir_acesso_ao_projeto(escopo.projeto_id, current_user, db)
    return escopo.projeto_id


@router.get("/projetos/{projeto_id}/escopos")
def list_escopos(projeto_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    return ListEscoposProjetoUseCase(db).execute(projeto_id)


@router.get("/escopos-projeto")
def list_todos_escopos_vendidos(db: Session = Depends(get_db)):
    """Nome de todo escopo vendido, de todos os projetos — usado pela página
    Bancas pra resolver `projeto_escopo_ids`. Sem recorte de visão de
    propósito: bancas já são globais (§8), então o escopo/projeto de
    qualquer uma também é."""
    return ListTodosEscoposVendidosUseCase(db).execute()


@router.post("/projetos/{projeto_id}/escopos")
def create_escopo(projeto_id: int, request: EscopoVendidoRequest, current_user=Depends(require_gestao), db: Session = Depends(get_db)):
    exigir_acesso_ao_projeto(projeto_id, current_user, db)
    try:
        result = CreateEscopoProjetoUseCase(db).execute(projeto_id, request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return result


@router.patch("/escopos-projeto/{escopo_id}")
def update_escopo(escopo_id: int, request: UpdateEscopoProjetoRequest, current_user=Depends(require_gestao), db: Session = Depends(get_db)):
    _projeto_do_escopo(escopo_id, current_user, db)
    try:
        return UpdateEscopoProjetoUseCase(db).execute(escopo_id, request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.delete("/escopos-projeto/{escopo_id}", status_code=204)
def delete_escopo(escopo_id: int, current_user=Depends(require_gestao), db: Session = Depends(get_db)):
    _projeto_do_escopo(escopo_id, current_user, db)
    try:
        DeleteEscopoProjetoUseCase(db).execute(escopo_id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


# ⭐ A reunião inicial do escopo (§5.4) mora em
# `POST /projetos/{id}/reunioes`, com `projeto_escopo_id` — registrar a reunião
# no calendário É o que faz a contagem começar. Não há endpoint para digitar
# `data_inicio` direto.


@router.patch("/escopos-projeto/{escopo_id}/entrega")
def registrar_entrega_escopo(escopo_id: int, request: RegistrarEntregaEscopoRequest, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    """🔒 Travada até a banca do escopo ser realizada (§5.5).

    Marcar é livre para quem está no projeto; ALTERAR uma entrega já registrada
    é decisão da diretoria (§13) — o gate mora no use case, porque ele depende
    de a data já existir.
    """
    _projeto_do_escopo(escopo_id, current_user, db)
    try:
        return RegistrarEntregaEscopoUseCase(db).execute(
            escopo_id,
            request,
            eh_diretor=getattr(current_user, "posicao", None) == "diretor",
            current_user=current_user,
        )
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.patch("/escopos-projeto/{escopo_id}/atraso-entrega")
def classificar_atraso(escopo_id: int, request: ClassificarAtrasoEntregaRequest, current_user=Depends(require_diretor), db: Session = Depends(get_db)):
    """Interno x externo (§7.4) — só a diretoria classifica."""
    _projeto_do_escopo(escopo_id, current_user, db)
    try:
        return ClassificarAtrasoEntregaUseCase(db).execute(escopo_id, request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
