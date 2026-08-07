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
from src.repositories.escopo_repository import EscopoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.tarefa_repository import ReuniaoSemanalRepository
from src.use_cases.notificacao.eventos import notificar_entrega, notificar_entrega_alterada
from src.utils.exceptions import RegraDeNegocioError


def _nome_escopo(escopo, catalogo_repository) -> str:
    """Mesma régua do resto do sistema: "Outro" tem nome customizado e não tem
    linha de catálogo (§4).

    Função de módulo, não método: os dois use cases daqui precisam dela, e o
    de entrega já a tinha copiada.
    """
    if escopo.nome_customizado:
        return escopo.nome_customizado
    do_catalogo = catalogo_repository.get_by_id(escopo.escopo_id) if escopo.escopo_id else None
    return do_catalogo.nome if do_catalogo else "escopo"


class UpdateEscopoProjetoRequest(BaseModel):
    nome_customizado: Optional[str] = None
    dias_uteis_vendidos: Optional[int] = None
    data_entrega_planejada: Optional[date] = None
    ordem: Optional[int] = None


class UpdateEscopoProjetoUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjetoEscopoRepository(db)
        self.projeto_repository = ProjetoRepository(db)
        self.catalogo_repository = EscopoRepository(db)

    def execute(self, escopo_id: int, request: UpdateEscopoProjetoRequest):
        dados = request.dict(exclude_unset=True)
        if "dias_uteis_vendidos" in dados and dados["dias_uteis_vendidos"] is not None:
            if dados["dias_uteis_vendidos"] <= 0:
                raise RegraDeNegocioError("Os dias úteis vendidos precisam ser maiores que zero")

        # A data ANTES do update: o aviso só faz sentido dizendo de onde para
        # onde, e depois de gravar ela já se perdeu.
        anterior = self.repository.get_by_id(escopo_id)
        data_antiga = anterior.data_entrega_planejada if anterior else None

        escopo = self.repository.update(escopo_id, **dados)
        if not escopo:
            return None

        # Só quando a data de entrega REALMENTE mudou — este endpoint também
        # edita nome e dias vendidos, e nenhum dos dois é notícia.
        if "data_entrega_planejada" in dados and data_antiga != escopo.data_entrega_planejada:
            projeto = self.projeto_repository.get_by_id(escopo.projeto_id)
            if projeto:
                notificar_entrega_alterada(
                    self.db,
                    projeto,
                    data_antiga,
                    escopo.data_entrega_planejada,
                    nome_escopo=_nome_escopo(escopo, self.catalogo_repository),
                    escopo_id=escopo.id,
                )

        return {"id": escopo.id}


# ⭐ Não existe mais um "iniciar escopo" digitado à parte. A `data_inicio` do
# §5.4 nasce da reunião inicial registrada no calendário de reuniões semanais
# (`use_cases/tarefa/tarefas.py`), que é a única porta que a escreve — ter duas
# faria a contagem depender de qual delas foi usada por último.


class RegistrarEntregaEscopoRequest(BaseModel):
    data_entrega_real: date


class RegistrarEntregaEscopoUseCase:
    """🔒 A trava do §5.5 — o coração da costura F4×F5.

    O campo que a trava lê (`banca.resultado`) nasceu na migration 5; o campo
    que ela protege (`projeto_escopo.data_entrega_real`) nasceu na 4. É por
    isso que as duas fatias são uma só.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjetoEscopoRepository(db)
        self.banca_repository = BancaRepository(db)
        self.projeto_repository = ProjetoRepository(db)
        self.catalogo_repository = EscopoRepository(db)

    def execute(self, escopo_id: int, request: RegistrarEntregaEscopoRequest):
        escopo = self.repository.get_by_id(escopo_id)
        if not escopo:
            return None

        if not escopo.data_inicio:
            raise RegraDeNegocioError("Este escopo ainda não foi iniciado")

        # 🔒 A trava do §5.5: nada vai ao cliente sem passar por banca.
        #
        # O que ela lê é a banca ter ACONTECIDO, não um veredito de aprovação —
        # a diretoria decidiu que aprovar/rejeitar não faz parte do processo.
        # A regra que o case pede continua de pé: sem banca realizada, sem
        # entrega. O que saiu foi o passo extra depois dela.
        banca = self.banca_repository.get_by_projeto_escopo(escopo_id)
        if not banca:
            raise RegraDeNegocioError(
                "A entrega só é liberada depois da banca do escopo acontecer — "
                "este escopo ainda não tem banca marcada"
            )
        if not banca.realizado_em:
            raise RegraDeNegocioError(
                "A entrega só é liberada depois da banca do escopo ser realizada"
            )

        atualizado = self.repository.update(
            escopo_id, data_entrega_real=request.data_entrega_real, status="entregue"
        )

        # Depois da trava, nunca antes: notificar uma entrega que o §5.5 acabou
        # de barrar avisaria a diretoria de algo que não aconteceu.
        projeto = self.projeto_repository.get_by_id(atualizado.projeto_id)
        if projeto:
            notificar_entrega(self.db, projeto, escopo_id, _nome_escopo(atualizado, self.catalogo_repository))

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
        self.db = db
        self.repository = ProjetoEscopoRepository(db)
        self.banca_repository = BancaRepository(db)

    def execute(self, escopo_id: int) -> bool:
        if self.banca_repository.get_by_projeto_escopo(escopo_id):
            raise RegraDeNegocioError(
                "Não é possível remover um escopo que já tem banca marcada"
            )
        # As reuniões daquele escopo não somem junto: elas ACONTECERAM, e o
        # §7.2 conta "projeto sem reunião na semana" pela ausência de linha.
        # Elas voltam a ser reuniões gerais do projeto — e, sem a FK pendurada,
        # o delete não esbarra na integridade referencial.
        reuniao_repository = ReuniaoSemanalRepository(self.db)
        for reuniao in reuniao_repository.get_by_escopo(escopo_id):
            reuniao_repository.update(reuniao.id, projeto_escopo_id=None)
        return self.repository.delete(escopo_id)
