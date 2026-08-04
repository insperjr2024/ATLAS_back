"""Tarefas do kanban (§6.4) e reuniões semanais.

⚠ Nenhuma checagem de POSIÇÃO aqui, de propósito: o §3 dá "criar tarefa" e
"mover e editar tarefa" aos **quatro** perfis. A trava é só "você enxerga
este projeto" (`exigir_acesso_ao_projeto` na rota), que já recorta gerente
por frente e coord/consultor por alocação.
"""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.tarefa_repository import ReuniaoSemanalRepository, TarefaRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.exceptions import RegraDeNegocioError
from src.utils.tarefa_status import eh_vencida, janela_semana

STATUS_VALIDOS = ("a_fazer", "em_andamento", "validacao", "concluido", "cancelado")


def serializar_tarefa(tarefa, hoje: Optional[date] = None) -> dict:
    return {
        "id": tarefa.id,
        "projeto_id": tarefa.projeto_id,
        "projeto_escopo_id": tarefa.projeto_escopo_id,
        "titulo": tarefa.titulo,
        "responsavel_id": tarefa.responsavel_id,
        "prazo": tarefa.prazo,
        "status": tarefa.status,
        "criado_por": tarefa.criado_por,
        "criado_em": tarefa.criado_em,
        "movida_em": tarefa.movida_em,
        # 🧮 Derivado, nunca gravado.
        "vencida": eh_vencida(tarefa.prazo, tarefa.status, hoje),
    }


class CreateTarefaRequest(BaseModel):
    titulo: str
    responsavel_id: int
    prazo: date
    projeto_escopo_id: Optional[int] = None
    status: str = "a_fazer"


class UpdateTarefaRequest(BaseModel):
    titulo: Optional[str] = None
    responsavel_id: Optional[int] = None
    prazo: Optional[date] = None
    status: Optional[str] = None
    projeto_escopo_id: Optional[int] = None


class ListTarefasUseCase:
    def __init__(self, db: Session):
        self.repository = TarefaRepository(db)

    def execute(self, projeto_id: int) -> List[dict]:
        hoje = date.today()
        return [serializar_tarefa(t, hoje) for t in self.repository.get_by_projeto(projeto_id)]


class CreateTarefaUseCase:
    def __init__(self, db: Session):
        self.repository = TarefaRepository(db)
        self.projeto_repository = ProjetoRepository(db)
        self.usuario_repository = UsuarioRepository(db)

    def execute(self, projeto_id: int, request: CreateTarefaRequest, criado_por: int):
        if not self.projeto_repository.get_by_id(projeto_id):
            return None
        if request.status not in STATUS_VALIDOS:
            raise RegraDeNegocioError(f"Status inválido. Use um de: {', '.join(STATUS_VALIDOS)}")
        if not request.titulo.strip():
            raise RegraDeNegocioError("A tarefa precisa de um título")
        if not self.usuario_repository.get_by_id(request.responsavel_id):
            raise RegraDeNegocioError("Responsável não encontrado")

        tarefa = self.repository.create(
            projeto_id=projeto_id,
            projeto_escopo_id=request.projeto_escopo_id,
            titulo=request.titulo.strip(),
            responsavel_id=request.responsavel_id,
            prazo=request.prazo,
            status=request.status,
            criado_por=criado_por,
        )
        return serializar_tarefa(tarefa)


class UpdateTarefaUseCase:
    def __init__(self, db: Session):
        self.repository = TarefaRepository(db)

    def execute(self, tarefa_id: int, request: UpdateTarefaRequest):
        tarefa = self.repository.get_by_id(tarefa_id)
        if not tarefa:
            return None

        dados = request.dict(exclude_unset=True)
        if "status" in dados:
            if dados["status"] not in STATUS_VALIDOS:
                raise RegraDeNegocioError(
                    f"Status inválido. Use um de: {', '.join(STATUS_VALIDOS)}"
                )
            # `movida_em` só é tocado quando o status MUDA de fato — é o que
            # torna a "última movimentação" do §7.2 significativa. Renomear a
            # tarefa não pode fingir atividade.
            if dados["status"] != tarefa.status:
                dados["movida_em"] = datetime.now()

        atualizada = self.repository.update(tarefa_id, **dados)
        return serializar_tarefa(atualizada)


class DeleteTarefaUseCase:
    def __init__(self, db: Session):
        self.repository = TarefaRepository(db)

    def execute(self, tarefa_id: int) -> bool:
        return self.repository.delete(tarefa_id)


# ------------------------------------------------------------------ reuniões


class ReuniaoRequest(BaseModel):
    data_reuniao: date


def serializar_reuniao(reuniao) -> dict:
    return {
        "id": reuniao.id,
        "projeto_id": reuniao.projeto_id,
        "data_reuniao": reuniao.data_reuniao,
        "registrado_por": reuniao.registrado_por,
    }


class ListReunioesUseCase:
    def __init__(self, db: Session):
        self.repository = ReuniaoSemanalRepository(db)

    def execute(self, projeto_id: int) -> dict:
        reunioes = self.repository.get_by_projeto(projeto_id)
        inicio, fim = janela_semana()
        return {
            "reunioes": [serializar_reuniao(r) for r in reunioes],
            "semana_atual": {"inicio": inicio, "fim": fim},
            # 🧮 "Sem reunião esta semana" = ausência de linha na janela.
            "tem_reuniao_esta_semana": any(
                inicio <= r.data_reuniao <= fim for r in reunioes
            ),
        }


class CreateReuniaoUseCase:
    def __init__(self, db: Session):
        self.repository = ReuniaoSemanalRepository(db)
        self.projeto_repository = ProjetoRepository(db)

    def execute(self, projeto_id: int, request: ReuniaoRequest, registrado_por: int):
        if not self.projeto_repository.get_by_id(projeto_id):
            return None
        if self.repository.get_por_data(projeto_id, request.data_reuniao):
            raise RegraDeNegocioError("Já existe uma reunião registrada neste dia")

        reuniao = self.repository.create(
            projeto_id=projeto_id,
            data_reuniao=request.data_reuniao,
            registrado_por=registrado_por,
        )
        return serializar_reuniao(reuniao)


class UpdateReuniaoUseCase:
    """Mover a reunião de dia (registrou quarta, aconteceu quinta)."""

    def __init__(self, db: Session):
        self.repository = ReuniaoSemanalRepository(db)

    def execute(self, reuniao_id: int, request: ReuniaoRequest):
        reuniao = self.repository.get_by_id(reuniao_id)
        if not reuniao:
            return None
        existente = self.repository.get_por_data(reuniao.projeto_id, request.data_reuniao)
        if existente and existente.id != reuniao_id:
            raise RegraDeNegocioError("Já existe uma reunião registrada neste dia")
        return serializar_reuniao(
            self.repository.update(reuniao_id, data_reuniao=request.data_reuniao)
        )


class DeleteReuniaoUseCase:
    def __init__(self, db: Session):
        self.repository = ReuniaoSemanalRepository(db)

    def execute(self, reuniao_id: int) -> bool:
        return self.repository.delete(reuniao_id)
