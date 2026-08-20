from sqlalchemy.orm import Session

from src.repositories.cronograma_reajuste_repository import CronogramaReajusteRepository
from src.repositories.escopo_repository import EscopoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.cronograma_reajuste.solicitar import nome_do_escopo


class ListarReajustesPendentesUseCase:
    """A fila de pedidos de DIAS DE AJUSTE (§8), só para a diretoria — o
    gerente não decide, e o router já restringe com
    `require_diretor_projetos`.

    Traz `dias_solicitados` e a janela atual do escopo porque a decisão não faz
    sentido sem os dois: aprovar "+10" muda de significado conforme o escopo
    tenha 20 dias vendidos ou 60."""

    def __init__(self, db: Session):
        self.repository = CronogramaReajusteRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.catalogo_repository = EscopoRepository(db)
        self.projeto_repository = ProjetoRepository(db)
        self.usuario_repository = UsuarioRepository(db)

    def execute(self) -> list[dict]:
        resultado = []
        for s in self.repository.get_pendentes():
            escopo = self.escopo_repository.get_by_id(s.projeto_escopo_id)
            projeto = self.projeto_repository.get_by_id(escopo.projeto_id) if escopo else None
            solicitante = self.usuario_repository.get_by_id(s.solicitado_por)
            resultado.append(
                {
                    "id": s.id,
                    "projeto_escopo_id": s.projeto_escopo_id,
                    "projeto_id": projeto.id if projeto else None,
                    "projeto_nome": projeto.nome if projeto else None,
                    "escopo_nome": nome_do_escopo(escopo, self.catalogo_repository) if escopo else None,
                    "solicitado_por": s.solicitado_por,
                    "solicitado_por_nome": solicitante.nome if solicitante else None,
                    "dias_solicitados": s.dias_solicitados,
                    # A janela de hoje, para a diretora ver contra o que está
                    # somando: "+10 sobre 20 vendidos" é outra decisão que
                    # "+10 sobre 20 vendidos e 15 já ajustados".
                    "dias_uteis_vendidos": escopo.dias_uteis_vendidos if escopo else None,
                    "dias_uteis_ajustados": escopo.dias_uteis_ajustados if escopo else None,
                    "motivo": s.motivo,
                    "criado_em": s.criado_em,
                }
            )
        return resultado
