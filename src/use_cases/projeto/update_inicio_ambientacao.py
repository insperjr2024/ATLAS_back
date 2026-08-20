"""Corrige o início real da ambientação, quando ela começou antes do kickoff.

⭐ O padrão continua sendo "ambientação = kickoff" (`UpdateKickoffUseCase` não
muda) — isto aqui é a EXCEÇÃO, pra quando o time já estava em campo antes do
kickoff formal. Só o coordenador DESTE projeto (ou a diretoria) corrige, só
pra ANTECIPAR, e nunca mais que `dias_ambientacao` dias úteis antes do
próprio kickoff: o kickoff não pode cair fora da janela de ambientação que
ele mesmo abre.

Mesmo padrão de `ConfirmarEntregaEscopoUseCase._exigir_quem_pode`: é vínculo
com o projeto, não permissão de posição, então a checagem mora aqui (com a
equipe à mão), não em `middlewares/authorization.py`.
"""

from datetime import date, timedelta
from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.dia_nao_letivo_repository import DiaNaoLetivoRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.use_cases.projeto.encerrar_ambientacao import EncerrarAmbientacaoUseCase
from src.utils.dias_uteis import contar_dias_uteis
from src.utils.exceptions import RegraDeNegocioError


class UpdateInicioAmbientacaoRequest(BaseModel):
    #: `None` limpa a correção — a ambientação volta a contar do kickoff, o
    #: padrão de sempre.
    data_inicio_ambientacao: Optional[date] = None


class UpdateInicioAmbientacaoUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjetoRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)
        self.dia_nao_letivo_repository = DiaNaoLetivoRepository(db)

    def execute(
        self,
        projeto_id: int,
        request: UpdateInicioAmbientacaoRequest,
        current_user,
        eh_diretor_projetos: bool = False,
    ):
        projeto = self.repository.get_by_id(projeto_id)
        if not projeto:
            return None

        self._exigir_quem_pode(projeto_id, current_user, eh_diretor_projetos)

        nova_data = request.data_inicio_ambientacao
        if nova_data is not None:
            self._validar(projeto, nova_data)

        self.repository.update(projeto_id, data_inicio_ambientacao=nova_data)
        # A correção pode encurtar a janela o bastante pra ambientação já ter
        # acabado — mesmo motivo de `UpdateKickoffUseCase` rechecar na hora,
        # em vez de esperar a passada da meia-noite.
        EncerrarAmbientacaoUseCase(self.db).executar_para(projeto_id)

        atualizado = self.repository.get_by_id(projeto_id)
        return {
            "id": atualizado.id,
            "data_inicio_ambientacao": atualizado.data_inicio_ambientacao,
            "status": atualizado.status,
        }

    def _exigir_quem_pode(self, projeto_id: int, current_user, eh_diretor_projetos: bool) -> None:
        if eh_diretor_projetos:
            return
        membros = self.membro_repository.get_by_projeto(projeto_id, apenas_atuais=True)
        usuario_id = getattr(current_user, "id", None)
        eh_coordenador = any(
            m.usuario_id == usuario_id and m.papel == "coordenador" for m in membros
        )
        if not eh_coordenador:
            raise RegraDeNegocioError(
                "Só o coordenador do projeto ou a diretoria editam o início da ambientação"
            )

    def _validar(self, projeto, nova_data: date) -> None:
        if not projeto.data_kickoff:
            raise RegraDeNegocioError(
                "Marque o kickoff antes de corrigir o início da ambientação"
            )
        if nova_data > projeto.data_kickoff:
            raise RegraDeNegocioError(
                "O início da ambientação só pode ser antecipado, nunca adiado além do kickoff"
            )

        limite_busca = projeto.data_kickoff - timedelta(days=365)
        nao_letivos = [
            d.data
            for d in self.dia_nao_letivo_repository.get_por_intervalo(
                limite_busca, projeto.data_kickoff
            )
            if d.frente_id is None
        ]
        # Mesma régua de `somar_dias_uteis`: o kickoff conta como o 1º dia da
        # janela quando ela nasce dele, então [nova_data, kickoff] fechado não
        # pode ter mais dias úteis do que a ambientação inteira dura — é o que
        # garante que o kickoff continua DENTRO da janela que ele abriu.
        dias_ate_o_kickoff = contar_dias_uteis(nova_data, projeto.data_kickoff, nao_letivos)
        limite_dias = max(projeto.dias_ambientacao, 1)
        if dias_ate_o_kickoff > limite_dias:
            raise RegraDeNegocioError(
                f"O início da ambientação não pode ficar mais de {limite_dias} "
                "dias úteis antes do kickoff"
            )
