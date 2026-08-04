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
from src.models.tarefa_model import ReuniaoSemanalModel, TarefaModel