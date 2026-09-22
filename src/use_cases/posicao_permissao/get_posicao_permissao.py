from sqlalchemy.orm import Session

from src.repositories.posicao_permissao_repository import PosicaoPermissaoRepository


def serializar_posicao_permissao(registro) -> dict:
    """Num lugar só — a lista e o update devolvem a mesma forma, senão uma
    permissão nova nasce faltando em metade das telas."""
    return {
        "posicao": registro.posicao,
        "nome": registro.nome,
        "e_padrao": registro.e_padrao,
        "pode_criar_projeto": registro.pode_criar_projeto,
        "pode_editar_equipe": registro.pode_editar_equipe,
        "pode_gerir_membros": registro.pode_gerir_membros,
        "pode_marcar_kickoff": registro.pode_marcar_kickoff,
        "pode_definir_cronograma": registro.pode_definir_cronograma,
        "pode_criar_tarefa": registro.pode_criar_tarefa,
        "pode_mover_editar_tarefa": registro.pode_mover_editar_tarefa,
        "pode_ver_proprios_projetos": registro.pode_ver_proprios_projetos,
        "pode_ver_monitoramento": registro.pode_ver_monitoramento,
        "pode_administrar_desempenho": registro.pode_administrar_desempenho,
        "pode_editar_formularios_desempenho": registro.pode_editar_formularios_desempenho,
        "pode_administrar_configuracoes": registro.pode_administrar_configuracoes,
        "pode_ver_todos_projetos": registro.pode_ver_todos_projetos,
        "pode_ver_dashboard_bancas": registro.pode_ver_dashboard_bancas,
        "pode_ver_historico_projetos": registro.pode_ver_historico_projetos,
        "pode_ver_tarefas_gerais": registro.pode_ver_tarefas_gerais,
        "pode_ver_cronogramas_gerais": registro.pode_ver_cronogramas_gerais,
        "pode_configurar_colunas": registro.pode_configurar_colunas,
        "pode_aprovar_pedidos": registro.pode_aprovar_pedidos,
        "pode_administrar_permissoes": registro.pode_administrar_permissoes,
        "pode_gerir_calendarios_base": registro.pode_gerir_calendarios_base,
        "pode_responsavel_por_vendas": registro.pode_responsavel_por_vendas,
        "pode_coordenar_vendas": registro.pode_coordenar_vendas,
        "pode_aprovar_contrato_internamente": registro.pode_aprovar_contrato_internamente,
        "pode_editar_identidade_institucional": registro.pode_editar_identidade_institucional,
        "pode_elaborar_contratos_proprios": registro.pode_elaborar_contratos_proprios,
        "pode_elaborar_qualquer_contrato": registro.pode_elaborar_qualquer_contrato,
    }


class ListPosicaoPermissoesUseCase:
    def __init__(self, db: Session):
        self.repository = PosicaoPermissaoRepository(db)

    def execute(self):
        return [serializar_posicao_permissao(p) for p in self.repository.get_all()]
