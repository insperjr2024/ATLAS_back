from sqlalchemy import delete
from sqlalchemy.orm import Session

from src.models.banca_escopo_model import BancaEscopoModel
from src.models.banca_model import BancaModel
from src.models.cronograma_etapa_model import CronogramaEtapaModel, CronogramaMarcoModel
from src.models.desempenho_lote_projeto_model import DesempenhoLoteProjetoModel
from src.models.justificativa_pedido_model import JustificativaPedidoModel
from src.models.notificacao_model import NotificacaoModel
from src.models.projeto_justificativa_atraso_model import ProjetoJustificativaAtrasoModel
from src.models.projeto_remarcacao_banca_model import ProjetoRemarcacaoBancaModel
from src.models.projeto_escopo_model import ProjetoEscopoModel
from src.models.projeto_frente_model import ProjetoFrenteModel
from src.models.projeto_membro_model import ProjetoMembroModel
from src.models.projeto_status_historico_model import ProjetoStatusHistoricoModel
from src.models.tarefa_coluna_model import TarefaColunaModel
from src.models.tarefa_comentario_model import TarefaComentarioModel
from src.models.tarefa_model import ReuniaoSemanalModel, TarefaModel
from src.repositories.projeto_repository import ProjetoRepository
from src.utils.exceptions import RegraDeNegocioError
from src.utils.storage import pasta_propostas


class DeleteProjetoPermanenteUseCase:
    """O "apagar pra sempre" que arquivar (§6.2) deliberadamente não é —
    exige que o projeto já esteja arquivado primeiro, como um degrau a mais
    antes do ponto sem volta.

    Sem ON DELETE CASCADE em `projeto.id` na maioria das tabelas filhas (o
    desenho existente é "nada se apaga sozinho"), então a limpeza é manual e
    em ordem: banca inteira primeiro (aí sim o banco cascateia
    banca_escopo/equipe_projeto/banca_frente/avaliacao+nota/candidatura/
    solicitacao_troca via ondelete=CASCADE), depois o resto de baixo pra
    cima, terminando no próprio projeto.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjetoRepository(db)

    def execute(self, projeto_id: int) -> dict:
        projeto = self.repository.get_by_id(projeto_id)
        if not projeto:
            return None
        if projeto.arquivado_em is None:
            raise RegraDeNegocioError("Só é possível apagar para sempre um projeto arquivado")

        escopo_ids = [
            row[0]
            for row in self.db.query(ProjetoEscopoModel.id)
            .filter(ProjetoEscopoModel.projeto_id == projeto_id)
            .all()
        ]
        tarefa_ids = [
            row[0] for row in self.db.query(TarefaModel.id).filter(TarefaModel.projeto_id == projeto_id).all()
        ]

        # ⚠ ANTES das bancas, e não junto do resto lá embaixo.
        #
        # `projeto_remarcacao_banca` aponta para `banca.id` além de
        # `projeto.id`, e nenhuma das duas chaves cascateia. Deixada para
        # depois, ela segura a exclusão da banca com
        # `projeto_remarcacao_banca_banca_id_fkey` — e um projeto que a
        # diretoria já remarcou banca alguma vez vira impossível de apagar.
        #
        # As outras duas são o histórico do §7.4 (a nota de atraso e o pedido
        # dela). Também `NO ACTION`, e também faltavam: qualquer projeto que
        # tenha passado pela fila de Aprovações do monitoramento levava
        # violação de chave ao ser apagado.
        self.db.execute(
            delete(ProjetoRemarcacaoBancaModel).where(ProjetoRemarcacaoBancaModel.projeto_id == projeto_id)
        )
        self.db.execute(delete(JustificativaPedidoModel).where(JustificativaPedidoModel.projeto_id == projeto_id))
        self.db.execute(
            delete(ProjetoJustificativaAtrasoModel).where(
                ProjetoJustificativaAtrasoModel.projeto_id == projeto_id
            )
        )

        if escopo_ids:
            banca_ids = [
                row[0]
                for row in self.db.query(BancaEscopoModel.banca_id)
                .filter(BancaEscopoModel.projeto_escopo_id.in_(escopo_ids))
                .distinct()
                .all()
            ]
            if banca_ids:
                self.db.execute(delete(BancaModel).where(BancaModel.id.in_(banca_ids)))

        if tarefa_ids:
            self.db.execute(delete(TarefaComentarioModel).where(TarefaComentarioModel.tarefa_id.in_(tarefa_ids)))
        self.db.execute(delete(TarefaModel).where(TarefaModel.projeto_id == projeto_id))

        if escopo_ids:
            self.db.execute(
                delete(CronogramaEtapaModel).where(CronogramaEtapaModel.projeto_escopo_id.in_(escopo_ids))
            )
        self.db.execute(delete(CronogramaMarcoModel).where(CronogramaMarcoModel.projeto_id == projeto_id))
        self.db.execute(delete(ReuniaoSemanalModel).where(ReuniaoSemanalModel.projeto_id == projeto_id))
        self.db.execute(delete(NotificacaoModel).where(NotificacaoModel.projeto_id == projeto_id))
        self.db.execute(
            delete(ProjetoStatusHistoricoModel).where(ProjetoStatusHistoricoModel.projeto_id == projeto_id)
        )
        self.db.execute(
            delete(DesempenhoLoteProjetoModel).where(DesempenhoLoteProjetoModel.projeto_id == projeto_id)
        )
        self.db.execute(delete(ProjetoMembroModel).where(ProjetoMembroModel.projeto_id == projeto_id))
        self.db.execute(delete(ProjetoFrenteModel).where(ProjetoFrenteModel.projeto_id == projeto_id))
        self.db.execute(delete(TarefaColunaModel).where(TarefaColunaModel.projeto_id == projeto_id))
        self.db.execute(delete(ProjetoEscopoModel).where(ProjetoEscopoModel.projeto_id == projeto_id))

        nome = projeto.nome
        anexo = projeto.anexo_proposta_path
        self.db.delete(projeto)
        self.db.commit()

        # Só depois do commit: se o unlink falhasse antes, o rollback deixaria
        # o registro intacto mas o arquivo já teria sumido do disco.
        if anexo:
            arquivo = pasta_propostas() / anexo
            if arquivo.exists():
                arquivo.unlink()

        return {"nome": nome}
