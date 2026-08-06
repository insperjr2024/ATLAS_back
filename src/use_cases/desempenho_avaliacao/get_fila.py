from sqlalchemy.orm import Session

from src.repositories.desempenho_avaliacao_repository import DesempenhoAvaliacaoRepository
from src.repositories.desempenho_lote_projeto_repository import DesempenhoLoteProjetoRepository
from src.repositories.desempenho_lote_repository import DesempenhoLoteRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.desempenho_fila import calcular_pares_lote, deduplicar_pares
from src.utils.desempenho_lote import esta_aberto


class GetFilaUsuarioUseCase:
    """Quem `usuario_id` ainda precisa avaliar, olhando os lotes abertos (e os
    fechados há pouco tempo, regra 2.3-bis) cujo projeto ele integra hoje.
    Reaproveitada tanto pelo endpoint de fila do próprio usuário quanto para
    calcular a `proxima_pendencia` depois de submeter uma avaliação (regra
    2.4) — nesse segundo uso os itens fechados não atrapalham porque quem
    chama já filtra pelo `lote_id` que acabou de responder."""

    def __init__(self, db: Session):
        self.lote_repo = DesempenhoLoteRepository(db)
        self.lote_projeto_repo = DesempenhoLoteProjetoRepository(db)
        self.membro_repo = ProjetoMembroRepository(db)
        self.avaliacao_repo = DesempenhoAvaliacaoRepository(db)
        self.usuario_repo = UsuarioRepository(db)

    def execute(self, usuario_id: int) -> list[dict]:
        meus_projetos_ativos = {
            m.projeto_id for m in self.membro_repo.get_atuais_por_usuario(usuario_id)
        }
        resultado = []

        for lote in self.lote_repo.get_relevantes_para_fila():
            projeto_ids = self.lote_projeto_repo.get_projeto_ids(lote.id)
            if not (meus_projetos_ativos & set(projeto_ids)):
                continue

            membros = self.membro_repo.get_by_projetos(projeto_ids, apenas_atuais=True)
            agregados = deduplicar_pares(calcular_pares_lote(membros))
            lote_aberto = esta_aberto(lote.override_manual, lote.data_inicio, lote.data_fim)

            for (avaliador_id, avaliado_id), dados in agregados.items():
                if avaliador_id != usuario_id:
                    continue
                if self.avaliacao_repo.existe_par(lote.id, avaliador_id, avaliado_id):
                    continue
                avaliado = self.usuario_repo.get_by_id(avaliado_id)
                resultado.append(
                    {
                        "lote_id": lote.id,
                        "lote_nome": lote.nome,
                        "lote_tipo": lote.tipo,
                        "aberto": lote_aberto,
                        "avaliado_id": avaliado_id,
                        "avaliado_nome": avaliado.nome if avaliado else None,
                        "form_type": dados["form_type"],
                        "projeto_ids": dados["projeto_ids"],
                    }
                )
        return resultado
