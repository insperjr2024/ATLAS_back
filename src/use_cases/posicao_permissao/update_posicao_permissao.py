from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.posicao_permissao_repository import PosicaoPermissaoRepository
from src.use_cases.posicao_permissao.get_posicao_permissao import serializar_posicao_permissao


class UpdatePosicaoPermissaoRequest(BaseModel):
    pode_criar_projeto: Optional[bool] = None
    pode_editar_equipe: Optional[bool] = None
    pode_gerir_membros: Optional[bool] = None
    pode_marcar_kickoff: Optional[bool] = None
    pode_definir_cronograma: Optional[bool] = None
    pode_criar_tarefa: Optional[bool] = None
    pode_mover_editar_tarefa: Optional[bool] = None
    pode_ver_proprios_projetos: Optional[bool] = None
    pode_ver_monitoramento: Optional[bool] = None
    pode_administrar_desempenho: Optional[bool] = None
    pode_editar_formularios_desempenho: Optional[bool] = None
    pode_administrar_configuracoes: Optional[bool] = None
    pode_ver_todos_projetos: Optional[bool] = None
    pode_ver_dashboard_bancas: Optional[bool] = None
    pode_ver_historico_projetos: Optional[bool] = None
    pode_ver_tarefas_gerais: Optional[bool] = None
    pode_ver_cronogramas_gerais: Optional[bool] = None
    pode_configurar_colunas: Optional[bool] = None
    pode_aprovar_pedidos: Optional[bool] = None
    pode_administrar_permissoes: Optional[bool] = None
    pode_gerir_calendarios_base: Optional[bool] = None


class UpdatePosicaoPermissaoUseCase:
    def __init__(self, db: Session):
        self.repository = PosicaoPermissaoRepository(db)

    def execute(self, posicao: str, request: UpdatePosicaoPermissaoRequest):
        data = request.model_dump(exclude_unset=True)
        registro = self.repository.update(posicao, **data)
        if not registro:
            return None
        return serializar_posicao_permissao(registro)
