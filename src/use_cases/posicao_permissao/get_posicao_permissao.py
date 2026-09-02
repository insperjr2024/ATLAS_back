from sqlalchemy.orm import Session

from src.repositories.posicao_permissao_repository import PosicaoPermissaoRepository


def serializar_posicao_permissao(registro) -> dict:
    """Num lugar só — a lista e o update devolvem a mesma forma, senão uma
    permissão nova nasce faltando em metade das telas."""
    return {
        "posicao": registro.posicao,
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
    }


class ListPosicaoPermissoesUseCase:
    def __init__(self, db: Session):
        self.repository = PosicaoPermissaoRepository(db)

    def execute(self):
        return [serializar_posicao_permissao(p) for p in self.repository.get_all()]
