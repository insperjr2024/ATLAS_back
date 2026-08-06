from sqlalchemy.orm import Session

from src.repositories.cronograma_reajuste_repository import CronogramaReajusteRepository
from src.repositories.escopo_repository import EscopoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.cronograma_reajuste.solicitar import nome_do_escopo


class ListarReajustesPendentesUseCase:
    """A fila só existe pra diretoria (§5.6: "o gerente não aprova
    reajustes") — o router já restringe com `require_pode_aprovar_reajuste`."""

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
                    "motivo": s.motivo,
                    "criado_em": s.criado_em,
                }
            )
        return resultado
