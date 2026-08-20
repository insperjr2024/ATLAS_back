"""🤖 Ambientação → Em andamento, sem ninguém clicar (§4 + §5.3).

A ambientação é a única transição do ciclo de vida que tem **data para
acabar**: ela é kickoff + N dias úteis, e esse fim é calculável. Todas as
outras dependem de alguém decidir (o trabalho terminou? a banca validou?) e
continuam manuais — este arquivo não abre precedente para virar as demais.

Por que é uma escrita e não um estado derivado na leitura: `projeto.status` é
campo gravado com histórico (`projeto_status_historico`), e é dele que saem o
monitoramento (§7.2), os filtros de listagem e a barra do topo da tela. Derivar
"na verdade este projeto já está em andamento" só na hora de servir deixaria o
banco dizendo uma coisa e a tela outra — e o histórico, que é o que conta a
vida do projeto, nunca registraria a passagem.

A linha do histórico sai com `alterado_por` **nulo**, que é a convenção já
usada no sistema para "🤖 o sistema mudou sozinho" — a tela do Histórico lê
isso e escreve "pelo sistema" em vez de um nome.
"""

import logging
from datetime import date
from typing import List, Optional

from sqlalchemy.orm import Session

from src.models.projeto_model import ProjetoModel
from src.repositories.dia_nao_letivo_repository import DiaNaoLetivoRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.projeto_status_historico_repository import ProjetoStatusHistoricoRepository
from src.utils.ambientacao import ambientacao_encerrada

logger = logging.getLogger(__name__)


class EncerrarAmbientacaoUseCase:
    """Vira para Em andamento todo projeto cuja ambientação já acabou.

    ⏸ **Projeto pausado não é tocado**, mesmo que a data tenha passado: pausar
    é parar o relógio (é o que `contagem_dias.py` faz com os dias), e virar o
    status de quem está parado desfaria a decisão de quem pausou. Ele sai da
    pausa para Ambientação e a próxima passada o pega.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjetoRepository(db)
        self.historico_repository = ProjetoStatusHistoricoRepository(db)
        self.dia_nao_letivo_repository = DiaNaoLetivoRepository(db)

    def execute(self, referencia: Optional[date] = None) -> List[int]:
        """Devolve os ids virados — vazio é o caso normal do dia a dia."""
        referencia = referencia or date.today()
        em_ambientacao = self.repository.filter_by(status="ambientacao")
        return [
            p.id for p in em_ambientacao if self._encerrar_se_acabou(p, referencia)
        ]

    def executar_para(self, projeto_id: int, referencia: Optional[date] = None) -> bool:
        """A mesma regra para UM projeto — usada logo depois de mexer no que a
        janela depende (entrar em Ambientação, corrigir o kickoff, mudar os dias
        de ambientação), para a virada não esperar a passada da madrugada."""
        projeto = self.repository.get_by_id(projeto_id)
        if not projeto or projeto.status != "ambientacao":
            return False
        return self._encerrar_se_acabou(projeto, referencia or date.today())

    def _encerrar_se_acabou(self, projeto: ProjetoModel, referencia: date) -> bool:
        # `data_inicio_ambientacao` substitui o kickoff como início da janela
        # quando o coordenador corrigiu (ambientação começou antes do
        # kickoff, ver `UpdateInicioAmbientacaoUseCase`). `None` é o caso
        # normal: a janela conta do próprio kickoff, como sempre contou.
        inicio = projeto.data_inicio_ambientacao or projeto.data_kickoff

        # Os dias não letivos GLOBAIS, sem recorte de frente: a ambientação é
        # do projeto inteiro, e um projeto sinérgico não pode sair de
        # Ambientação em datas diferentes conforme a frente que se olhe. É o
        # mesmo recorte que pinta a faixa no cronograma.
        nao_letivos = [
            d.data
            for d in self.dia_nao_letivo_repository.get_por_intervalo(inicio, referencia)
            if d.frente_id is None
        ] if inicio else []

        if not ambientacao_encerrada(
            inicio, projeto.dias_ambientacao, nao_letivos, referencia
        ):
            return False

        self.repository.update(projeto.id, status="em_andamento")
        self.historico_repository.create(
            projeto_id=projeto.id,
            status_anterior="ambientacao",
            status_novo="em_andamento",
            # 🤖 Sem autor: foi o calendário, não uma pessoa.
            alterado_por=None,
        )
        logger.info(
            "Ambientação encerrada automaticamente: projeto %s (%s)", projeto.id, projeto.nome
        )
        return True
