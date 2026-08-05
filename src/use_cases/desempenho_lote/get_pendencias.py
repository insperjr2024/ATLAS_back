from typing import Optional

from sqlalchemy.orm import Session

from src.repositories.desempenho_avaliacao_repository import DesempenhoAvaliacaoRepository
from src.repositories.desempenho_lote_projeto_repository import DesempenhoLoteProjetoRepository
from src.repositories.desempenho_lote_repository import DesempenhoLoteRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.desempenho_fila import calcular_pares_lote, deduplicar_pares


class GetPendenciasLoteUseCase:
    def __init__(self, db: Session):
        self.lote_repo = DesempenhoLoteRepository(db)
        self.lote_projeto_repo = DesempenhoLoteProjetoRepository(db)
        self.membro_repo = ProjetoMembroRepository(db)
        self.avaliacao_repo = DesempenhoAvaliacaoRepository(db)
        self.usuario_repo = UsuarioRepository(db)
        self.projeto_repo = ProjetoRepository(db)

    def execute(self, lote_id: int) -> Optional[list[dict]]:
        lote = self.lote_repo.get_by_id(lote_id)
        if not lote:
            return None

        projeto_ids = self.lote_projeto_repo.get_projeto_ids(lote_id)
        membros = self.membro_repo.get_by_projetos(projeto_ids, apenas_atuais=True)
        agregados = deduplicar_pares(calcular_pares_lote(membros))

        usuario_ids = {uid for par in agregados for uid in par}
        nomes = {u.id: u.nome for u in self.usuario_repo.get_all() if u.id in usuario_ids}
        nomes_projeto = {p.id: p.nome for p in self.projeto_repo.get_all() if p.id in projeto_ids}

        resultado = []
        for (avaliador_id, avaliado_id), dados in agregados.items():
            resultado.append(
                {
                    "avaliador_id": avaliador_id,
                    "avaliador_nome": nomes.get(avaliador_id),
                    "avaliado_id": avaliado_id,
                    "avaliado_nome": nomes.get(avaliado_id),
                    "form_type": dados["form_type"],
                    "projeto_ids": dados["projeto_ids"],
                    "projeto_nomes": [nomes_projeto.get(pid) for pid in dados["projeto_ids"]],
                    "respondida": self.avaliacao_repo.existe_par(lote_id, avaliador_id, avaliado_id),
                }
            )
        return resultado
