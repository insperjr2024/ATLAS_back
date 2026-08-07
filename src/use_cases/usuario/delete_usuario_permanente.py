from sqlalchemy import delete, or_, update
from sqlalchemy.orm import Session

from src.models.avaliacao_model import AvaliacaoModel
from src.models.banca_model import BancaModel
from src.models.candidatura_model import CandidaturaModel
from src.models.cronograma_etapa_model import CronogramaEtapaModel, CronogramaMarcoModel
from src.models.desempenho_avaliacao_model import DesempenhoAvaliacaoModel
from src.models.desempenho_lote_finalizado_model import DesempenhoLoteFinalizadoModel
from src.models.desempenho_mentoria_model import DesempenhoMentoriaModel
from src.models.desempenho_pdi_envio_model import DesempenhoPdiEnvioModel
from src.models.equipe_projeto_model import EquipeProjetoModel
from src.models.grade_horaria_model import GradeHorariaModel
from src.models.projeto_membro_model import ProjetoMembroModel
from src.models.projeto_model import ProjetoModel
from src.models.projeto_status_historico_model import ProjetoStatusHistoricoModel
from src.models.solicitacao_troca_model import SolicitacaoTrocaModel
from src.models.tarefa_comentario_model import TarefaComentarioModel
from src.models.tarefa_model import ReuniaoSemanalModel, TarefaModel
from src.models.token_recuperacao_model import TokenRecuperacaoModel
from src.models.usuario_frente_model import UsuarioFrenteModel
from src.models.usuario_posicao_historico_model import UsuarioPosicaoHistoricoModel
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.exceptions import RegraDeNegocioError


class DeleteUsuarioPermanenteUseCase:
    """Apaga de vez um usuário desligado — o "arquivar não é excluir" do §10
    deliberadamente não é isto: aqui É excluir, cascata completa, sem volta.

    Só aceita quem já está `desligado` (não `ex_membro` nem `ativo`) — o
    mesmo degrau a mais que `DeleteProjetoPermanenteUseCase` exige do
    projeto já arquivado.

    Diferente de projeto, `usuario.id` é referenciado por ~15 tabelas sem
    `ON DELETE CASCADE` (a exceção é `notificacao`, que já cascata). Duas
    categorias:

    - **É dela**: tarefa que ela é responsável, banca que ela coordenou,
      avaliação que ela fez, candidatura, mentoria, PDI etc. — a linha é
      apagada (bancas cascateiam por `ondelete=CASCADE` tudo que pende
      delas: banca_escopo, equipe_projeto, banca_frente, avaliacao+nota,
      candidatura, solicitacao_troca).
    - **É metadado de outra coisa**: quem CRIOU um projeto ou tarefa (não
      quem é responsável), quem REGISTROU uma reunião, quem ALTEROU um
      histórico — a coluna é nullable (`projeto.criado_por`,
      `tarefa.criado_por`, `reuniao_semanal.registrado_por` viraram
      nullable só para isto) e só é zerada; o projeto/tarefa/reunião de
      outras pessoas sobrevive.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repository = UsuarioRepository(db)

    def execute(self, usuario_id: int) -> dict:
        usuario = self.repository.get_by_id(usuario_id)
        if not usuario:
            return None
        if usuario.status != "desligado":
            raise RegraDeNegocioError("Só é possível apagar para sempre um usuário desligado")

        # 1) Bancas que ela coordenou — cascata do banco cuida do resto.
        self.db.execute(delete(BancaModel).where(BancaModel.coordenador_id == usuario_id))

        # 2) Tarefas de que ela é RESPONSÁVEL — comentário primeiro (sem
        # cascade), tarefa depois. Tarefa CRIADA por ela mas de outro
        # responsável não é tocada aqui (vira nulo no passo 4).
        tarefa_ids = [
            row[0]
            for row in self.db.query(TarefaModel.id)
            .filter(TarefaModel.responsavel_id == usuario_id)
            .all()
        ]
        if tarefa_ids:
            self.db.execute(delete(TarefaComentarioModel).where(TarefaComentarioModel.tarefa_id.in_(tarefa_ids)))
            self.db.execute(delete(TarefaModel).where(TarefaModel.id.in_(tarefa_ids)))

        # 3) O resto do que é DELA — apaga a linha inteira.
        self.db.execute(delete(DesempenhoLoteFinalizadoModel).where(DesempenhoLoteFinalizadoModel.usuario_id == usuario_id))
        self.db.execute(delete(TokenRecuperacaoModel).where(TokenRecuperacaoModel.usuario_id == usuario_id))
        self.db.execute(delete(EquipeProjetoModel).where(EquipeProjetoModel.usuario_id == usuario_id))
        self.db.execute(delete(GradeHorariaModel).where(GradeHorariaModel.usuario_id == usuario_id))
        self.db.execute(delete(TarefaComentarioModel).where(TarefaComentarioModel.autor_id == usuario_id))
        self.db.execute(delete(ProjetoMembroModel).where(ProjetoMembroModel.usuario_id == usuario_id))
        self.db.execute(delete(AvaliacaoModel).where(AvaliacaoModel.avaliador_id == usuario_id))
        self.db.execute(
            delete(DesempenhoAvaliacaoModel).where(
                or_(
                    DesempenhoAvaliacaoModel.avaliador_id == usuario_id,
                    DesempenhoAvaliacaoModel.avaliado_id == usuario_id,
                )
            )
        )
        self.db.execute(delete(UsuarioFrenteModel).where(UsuarioFrenteModel.usuario_id == usuario_id))
        self.db.execute(
            delete(UsuarioPosicaoHistoricoModel).where(UsuarioPosicaoHistoricoModel.usuario_id == usuario_id)
        )
        self.db.execute(
            delete(DesempenhoMentoriaModel).where(
                or_(
                    DesempenhoMentoriaModel.mentor_id == usuario_id,
                    DesempenhoMentoriaModel.mentorado_id == usuario_id,
                )
            )
        )
        self.db.execute(delete(CandidaturaModel).where(CandidaturaModel.usuario_id == usuario_id))
        self.db.execute(
            delete(DesempenhoPdiEnvioModel).where(
                or_(
                    DesempenhoPdiEnvioModel.mentorado_id == usuario_id,
                    DesempenhoPdiEnvioModel.enviado_por == usuario_id,
                )
            )
        )
        self.db.execute(delete(SolicitacaoTrocaModel).where(SolicitacaoTrocaModel.usuario_original_id == usuario_id))

        # 4) O que é METADADO de coisa de outras pessoas — some só o autor.
        self.db.execute(
            update(BancaModel)
            .where(BancaModel.excecao_choque_por == usuario_id)
            .values(excecao_choque_por=None)
        )
        self.db.execute(
            update(UsuarioPosicaoHistoricoModel)
            .where(UsuarioPosicaoHistoricoModel.alterado_por == usuario_id)
            .values(alterado_por=None)
        )
        self.db.execute(
            update(ProjetoStatusHistoricoModel)
            .where(ProjetoStatusHistoricoModel.alterado_por == usuario_id)
            .values(alterado_por=None)
        )
        self.db.execute(
            update(CronogramaEtapaModel).where(CronogramaEtapaModel.criado_por == usuario_id).values(criado_por=None)
        )
        self.db.execute(
            update(CronogramaMarcoModel).where(CronogramaMarcoModel.criado_por == usuario_id).values(criado_por=None)
        )
        self.db.execute(
            update(SolicitacaoTrocaModel)
            .where(SolicitacaoTrocaModel.confirmada_por == usuario_id)
            .values(confirmada_por=None)
        )
        self.db.execute(
            update(ProjetoModel).where(ProjetoModel.criado_por == usuario_id).values(criado_por=None)
        )
        self.db.execute(update(TarefaModel).where(TarefaModel.criado_por == usuario_id).values(criado_por=None))
        self.db.execute(
            update(ReuniaoSemanalModel)
            .where(ReuniaoSemanalModel.registrado_por == usuario_id)
            .values(registrado_por=None)
        )

        nome = usuario.nome
        self.db.delete(usuario)
        self.db.commit()

        return {"nome": nome}
