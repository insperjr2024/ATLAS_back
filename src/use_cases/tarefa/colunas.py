"""As colunas do kanban, configuráveis pela diretoria.

Eram um ENUM de 5 valores no banco. Viraram dados para a área montar o
próprio fluxo — criar, renomear, recolorir e reordenar sem migration.

🔒 Só a diretoria escreve (§3: "gerir" é da diretoria). Todo mundo lê: o
kanban de qualquer projeto precisa das colunas para desenhar o board.
"""

import re
from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.models.tarefa_model import TarefaModel
from src.repositories.tarefa_coluna_repository import TarefaColunaRepository
from src.utils.exceptions import RegraDeNegocioError

#: Mínimo de colunas que precisam sobrar. Um kanban sem coluna aberta não
#: tem onde uma tarefa nova nascer.
MINIMO_COLUNAS = 1


def _validar_cor(cor: str) -> None:
    """A coluna é CHAR(7): sem esta guarda, um formato diferente vira 500 do
    MySQL ("Data too long") em vez de 422 legível."""
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", cor or ""):
        raise RegraDeNegocioError("A cor precisa estar no formato #RRGGBB")


def serializar_coluna(coluna) -> dict:
    return {
        "id": coluna.id,
        "chave": coluna.chave,
        "nome": coluna.nome,
        "cor": coluna.cor,
        "ordem": coluna.ordem,
        "encerra_tarefa": coluna.encerra_tarefa,
    }


class ListColunasUseCase:
    def __init__(self, db: Session):
        self.repository = TarefaColunaRepository(db)

    def execute(self) -> List[dict]:
        return [serializar_coluna(c) for c in self.repository.listar()]


class CreateColunaRequest(BaseModel):
    nome: str
    cor: str
    #: ⭐ Tarefa que chega aqui está encerrada — não fica vencida nem conta
    #: como trabalho ativo no monitoramento.
    encerra_tarefa: bool = False


class CreateColunaUseCase:
    def __init__(self, db: Session):
        self.repository = TarefaColunaRepository(db)

    def execute(self, request: CreateColunaRequest):
        nome = (request.nome or "").strip()
        if not nome:
            raise RegraDeNegocioError("A coluna precisa de um nome")
        _validar_cor(request.cor)
        if any(c.nome.lower() == nome.lower() for c in self.repository.listar()):
            raise RegraDeNegocioError(f"Já existe uma coluna chamada '{nome}'")

        coluna = self.repository.create(
            # `chave` fica vazia: é o slug das 5 originais, usado pela
            # migration e pelo seed. Coluna criada aqui não precisa dele.
            chave=None,
            nome=nome,
            cor=request.cor.upper(),
            ordem=self.repository.proxima_ordem(),
            encerra_tarefa=request.encerra_tarefa,
        )
        return serializar_coluna(coluna)


class UpdateColunaRequest(BaseModel):
    nome: Optional[str] = None
    cor: Optional[str] = None
    ordem: Optional[int] = None
    encerra_tarefa: Optional[bool] = None


class UpdateColunaUseCase:
    def __init__(self, db: Session):
        self.repository = TarefaColunaRepository(db)

    def execute(self, coluna_id: int, request: UpdateColunaRequest):
        coluna = self.repository.get_by_id(coluna_id)
        if not coluna:
            return None

        dados = request.dict(exclude_unset=True, exclude_none=True)
        if "cor" in dados:
            _validar_cor(dados["cor"])
            dados["cor"] = dados["cor"].upper()
        if "nome" in dados:
            dados["nome"] = dados["nome"].strip()
            if not dados["nome"]:
                raise RegraDeNegocioError("A coluna precisa de um nome")
            if any(
                c.id != coluna_id and c.nome.lower() == dados["nome"].lower()
                for c in self.repository.listar()
            ):
                raise RegraDeNegocioError(f"Já existe uma coluna chamada '{dados['nome']}'")

        # ⚠ Virar `encerra_tarefa` muda o passado: tarefas que já estavam
        # nesta coluna passam (ou deixam) de contar como vencidas. É o
        # comportamento certo — a coluna define o que "encerrada" significa —
        # mas vale o alerta na tela, não uma trava aqui.
        return serializar_coluna(self.repository.update(coluna_id, **dados))


class ReordenarColunasRequest(BaseModel):
    #: Os ids na ordem desejada, da esquerda para a direita.
    ids: List[int]


class ReordenarColunasUseCase:
    def __init__(self, db: Session):
        self.repository = TarefaColunaRepository(db)

    def execute(self, request: ReordenarColunasRequest):
        existentes = {c.id for c in self.repository.listar()}
        if set(request.ids) != existentes:
            raise RegraDeNegocioError(
                "A reordenação precisa listar exatamente as colunas existentes"
            )
        for posicao, coluna_id in enumerate(request.ids):
            self.repository.update(coluna_id, ordem=posicao)
        return [serializar_coluna(c) for c in self.repository.listar()]


class DeleteColunaUseCase:
    """Apagar uma coluna é o caminho que mais quebra o board — daí as travas."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = TarefaColunaRepository(db)

    def execute(self, coluna_id: int, mover_para: Optional[int] = None) -> bool:
        coluna = self.repository.get_by_id(coluna_id)
        if not coluna:
            return False

        colunas = self.repository.listar()
        if len(colunas) <= MINIMO_COLUNAS:
            raise RegraDeNegocioError("O kanban precisa de pelo menos uma coluna")

        tarefas = (
            self.db.query(TarefaModel).filter(TarefaModel.coluna_id == coluna_id).all()
        )
        if tarefas:
            # Nunca apagar tarefa junto: ou a diretoria diz para onde elas
            # vão, ou a exclusão para aqui.
            if mover_para is None:
                raise RegraDeNegocioError(
                    f"Esta coluna tem {len(tarefas)} tarefa(s). Escolha para qual "
                    "coluna movê-las antes de excluir."
                )
            destino = self.repository.get_by_id(mover_para)
            if not destino or destino.id == coluna_id:
                raise RegraDeNegocioError("Coluna de destino inválida")
            for tarefa in tarefas:
                tarefa.coluna_id = mover_para
            self.db.commit()

        return self.repository.delete(coluna_id)
