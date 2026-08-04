"""Editar, iniciar e entregar um escopo vendido.

🔒 A trava do §5.5 mora em `RegistrarEntregaEscopoUseCase`: "nenhum escopo é
apresentado ao cliente sem antes passar pela banca — a plataforma deve
IMPEDIR esse pulo". O front esconde o botão; quem barra é este use case.
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.banca_repository import BancaRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.utils.exceptions import RegraDeNegocioError


class UpdateEscopoProjetoRequest(BaseModel):
    nome_customizado: Optional[str] = None
    dias_uteis_vendidos: Optional[int] = None
    data_entrega_planejada: Optional[date] = None


class UpdateEscopoProjetoUseCase:
    def __init__(self, db: Session):
        self.repository = ProjetoEscopoRepository(db)

    def execute(self, escopo_id: int, request: UpdateEscopoProjetoRequest):
        dados = request.dict(exclude_unset=True)
        if "dias_uteis_vendidos" in dados and dados["dias_uteis_vendidos"] is not None:
            if dados["dias_uteis_vendidos"] <= 0:
                raise RegraDeNegocioError("Os dias úteis vendidos precisam ser maiores que zero")
        escopo = self.repository.update(escopo_id, **dados)
        return {"id": escopo.id} if escopo else None


class IniciarEscopoRequest(BaseModel):
    data_inicio: date


class IniciarEscopoUseCase:
    """⭐ É este endpoint que faz a contagem RECOMEÇAR (§5.4).

    "A contagem só recomeça quando o coordenador marca a reunião inicial do
    próximo escopo" — marcar essa reunião é preencher `data_inicio` aqui.
    """

    def __init__(self, db: Session):
        self.repository = ProjetoEscopoRepository(db)

    def execute(self, escopo_id: int, request: IniciarEscopoRequest):
        escopo = self.repository.get_by_id(escopo_id)
        if not escopo:
            return None
        if escopo.data_entrega_real:
            raise RegraDeNegocioError("Este escopo já foi entregue")

        atualizado = self.repository.update(
            escopo_id, data_inicio=request.data_inicio, status="em_andamento"
        )
        return {"id": atualizado.id, "data_inicio": atualizado.data_inicio, "status": atualizado.status}


class RegistrarEntregaEscopoRequest(BaseModel):
    data_entrega_real: date


class RegistrarEntregaEscopoUseCase:
    """🔒 A trava do §5.5 — o coração da costura F4×F5.

    O campo que a trava lê (`banca.resultado`) nasceu na migration 5; o campo
    que ela protege (`projeto_escopo.data_entrega_real`) nasceu na 4. É por
    isso que as duas fatias são uma só.
    """

    def __init__(self, db: Session):
        self.repository = ProjetoEscopoRepository(db)
        self.banca_repository = BancaRepository(db)

    def execute(self, escopo_id: int, request: RegistrarEntregaEscopoRequest):
        escopo = self.repository.get_by_id(escopo_id)
        if not escopo:
            return None

        if not escopo.data_inicio:
            raise RegraDeNegocioError("Este escopo ainda não foi iniciado")

        banca = self.banca_repository.get_by_projeto_escopo(escopo_id)
        if not banca:
            raise RegraDeNegocioError(
                "A entrega só é liberada depois da banca do escopo ser aprovada — "
                "este escopo ainda não tem banca marcada"
            )
        if banca.resultado != "aprovada":
            raise RegraDeNegocioError(
                "A entrega só é liberada depois da banca do escopo ser aprovada"
            )

        atualizado = self.repository.update(
            escopo_id, data_entrega_real=request.data_entrega_real, status="entregue"
        )
        return {
            "id": atualizado.id,
            "data_entrega_real": atualizado.data_entrega_real,
            "status": atualizado.status,
        }


class ClassificarAtrasoEntregaRequest(BaseModel):
    #: interno = atraso do time · externo = agenda do cliente (§7.4)
    tipo_atraso_entrega: str


class ClassificarAtrasoEntregaUseCase:
    """§7.4: a entrega ao cliente pode escorregar por agenda dele. Marcar se o
    atraso foi interno ou externo é o que evita penalizar o time pelo que não
    é dele — e por isso é decisão só da diretoria."""

    def __init__(self, db: Session):
        self.repository = ProjetoEscopoRepository(db)

    def execute(self, escopo_id: int, request: ClassificarAtrasoEntregaRequest):
        if request.tipo_atraso_entrega not in ("interno", "externo"):
            raise RegraDeNegocioError("O tipo de atraso precisa ser 'interno' ou 'externo'")
        escopo = self.repository.update(
            escopo_id, tipo_atraso_entrega=request.tipo_atraso_entrega
        )
        return {"id": escopo.id, "tipo_atraso_entrega": escopo.tipo_atraso_entrega} if escopo else None


class DeleteEscopoProjetoUseCase:
    def __init__(self, db: Session):
        self.repository = ProjetoEscopoRepository(db)
        self.banca_repository = BancaRepository(db)

    def execute(self, escopo_id: int) -> bool:
        if self.banca_repository.get_by_projeto_escopo(escopo_id):
            raise RegraDeNegocioError(
                "Não é possível remover um escopo que já tem banca marcada"
            )
        return self.repository.delete(escopo_id)
