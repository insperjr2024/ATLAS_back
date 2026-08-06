from src.models.cargo_model import CargoModel
from src.models.escopo_model import EscopoModel
from src.models.usuario_model import UsuarioModel
from src.models.banca_model import BancaModel
from src.models.candidatura_model import CandidaturaModel
from src.models.semestre_model import SemestreModel
from src.models.formulario_model import FormularioModel
from src.models.pergunta_model import PerguntaModel
from src.models.avaliacao_model import AvaliacaoModel
from src.models.avaliacao_nota_model import AvaliacaoNotaModel
from src.models.frente_model import FrenteModel
from src.models.equipe_projeto_model import EquipeProjetoModel
from src.models.usuario_frente_model import UsuarioFrenteModel
from src.models.banca_frente_model import BancaFrenteModel
from src.models.banca_escopo_model import BancaEscopoModel
from src.models.configuracao_model import ConfiguracaoModel

# Prioridade 1 — todo model novo precisa entrar aqui, senão o `alembic
# revision --autogenerate` não o enxerga e gera uma migration vazia.
from src.models.dia_nao_letivo_model import DiaNaoLetivoModel
from src.models.usuario_posicao_historico_model import UsuarioPosicaoHistoricoModel
from src.models.projeto_model import ProjetoModel
from src.models.projeto_frente_model import ProjetoFrenteModel
from src.models.projeto_membro_model import ProjetoMembroModel
from src.models.projeto_status_historico_model import ProjetoStatusHistoricoModel
from src.models.projeto_escopo_model import ProjetoEscopoModel
from src.models.cronograma_etapa_model import CronogramaEtapaModel, CronogramaMarcoModel
from src.models.tarefa_coluna_model import TarefaColunaModel
from src.models.tarefa_comentario_model import TarefaComentarioModel
from src.models.tarefa_model import ReuniaoSemanalModel, TarefaModel

# Avaliação de Desempenho — periódica/finalização de consultores e
# coordenadores. Não confundir com formulario/pergunta/avaliacao/
# avaliacao_nota acima, que são feedback de banca (outra feature).
from src.models.desempenho_lote_model import DesempenhoLoteModel
from src.models.desempenho_lote_projeto_model import DesempenhoLoteProjetoModel
from src.models.desempenho_lote_finalizado_model import DesempenhoLoteFinalizadoModel
from src.models.desempenho_formulario_model import DesempenhoFormularioModel
from src.models.desempenho_formulario_secao_model import DesempenhoFormularioSecaoModel
from src.models.desempenho_criterio_model import DesempenhoCriterioModel
from src.models.desempenho_avaliacao_model import DesempenhoAvaliacaoModel
from src.models.desempenho_avaliacao_nota_model import DesempenhoAvaliacaoNotaModel
from src.models.desempenho_mentoria_model import DesempenhoMentoriaModel
from src.models.desempenho_pdi_pasta_model import DesempenhoPdiPastaModel
from src.models.desempenho_pdi_item_model import DesempenhoPdiItemModel
from src.models.desempenho_pdi_envio_model import DesempenhoPdiEnvioModel

# Notificação e troca de candidatura de banca (§6, §8).
from src.models.notificacao_model import NotificacaoModel
from src.models.solicitacao_troca_model import SolicitacaoTrocaModel

# Recuperação de senha — o token de uso único do "esqueci minha senha".
from src.models.token_recuperacao_model import TokenRecuperacaoModel
