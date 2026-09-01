from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.escopo_repository import EscopoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_frente_repository import ProjetoFrenteRepository
from src.repositories.dia_nao_letivo_repository import DiaNaoLetivoRepository
from src.repositories.frente_repository import FrenteRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.semestre_repository import SemestreRepository
from src.utils.exceptions import RegraDeNegocioError


class EscopoVendidoRequest(BaseModel):
    """Um escopo vendido no cadastro do projeto (§6.3).

    "Outro" = `escopo_id` vazio + `nome_customizado` digitado.
    """

    escopo_id: Optional[int] = None
    nome_customizado: Optional[str] = None
    frente_id: int
    dias_uteis_vendidos: int
    data_entrega_planejada: Optional[str] = None
    #: ⭐ O calendário acadêmico que este escopo segue — a base de contagem dos
    #: dias úteis dele. É o rótulo de um calendário que EXISTE na frente do
    #: escopo (`dia_nao_letivo.variante`).
    #:
    #: Nulo é uma resposta legítima e não "não escolhi": é o calendário da
    #: frente que tem um só (Business, Direito, Processos), que não tem rótulo
    #: para digitar. Quem obriga a escolher é `validar_calendario_do_escopo`,
    #: que recusa o nulo justamente quando a frente TEM calendários nomeados.
    calendario: Optional[str] = None


def validar_escopo_vendido(
    request: EscopoVendidoRequest,
    frentes_do_projeto: List[int],
    catalogo_repository: EscopoRepository,
) -> None:
    """As invariantes que o banco não consegue impor (o MySQL da stack ignora
    CHECK em silêncio), então elas moram aqui — em um lugar só, usado tanto
    pela criação do projeto quanto pela adição avulsa de escopo."""
    tem_catalogo = request.escopo_id is not None
    tem_customizado = bool(request.nome_customizado and request.nome_customizado.strip())

    if tem_catalogo and tem_customizado:
        raise RegraDeNegocioError(
            "Escolha um escopo do catálogo OU digite um nome customizado — não os dois"
        )
    if not tem_catalogo and not tem_customizado:
        raise RegraDeNegocioError("Escolha um escopo do catálogo ou digite o nome de um 'Outro'")

    if tem_catalogo and not catalogo_repository.get_by_id(request.escopo_id):
        raise RegraDeNegocioError(f"Escopo {request.escopo_id} não encontrado no catálogo")

    if request.dias_uteis_vendidos <= 0:
        raise RegraDeNegocioError("Os dias úteis vendidos precisam ser maiores que zero")

    # O escopo tem que ser de uma das frentes do projeto — senão um projeto
    # Business acabaria com um escopo de Direito pendurado.
    if request.frente_id not in frentes_do_projeto:
        raise RegraDeNegocioError(
            "O escopo precisa ser de uma das frentes do projeto"
        )


def calendarios_da_frente(db: Session, frente_id: int) -> List[Optional[str]]:
    """Os calendários que existem naquela frente, do ponto de vista do cadastro.

    `[None]` = a frente tem um calendário só, o dela inteira, e não há rótulo a
    escolher. Uma lista de nomes = a frente cobre cursos com datas diferentes
    (a Tech cobre engenharias e Ciência da Computação) e o escopo precisa dizer
    qual segue.

    Sai da própria carga, como `listar_variantes`: um calendário existe
    enquanto tiver dia dentro. Sem gestão ativa não há carga nenhuma, e aí a
    única resposta possível é `[None]` — travar o cadastro do projeto porque o
    calendário do semestre ainda não subiu seria pior do que contar só feriado.
    """
    semestre = SemestreRepository(db).get_ativo()
    if not semestre:
        return [None]
    nomes = DiaNaoLetivoRepository(db).listar_variantes(semestre.id, frente_id)
    return list(nomes) if nomes else [None]


def validar_calendario_do_escopo(db: Session, frente_id: int, calendario: Optional[str]):
    """§5.4: todo escopo declara em qual calendário os dias dele são contados.

    ⚠ **Obrigatório, e é o ponto da mudança de 2026-08-31.** Antes existia
    `projeto.calendario`, opcional, e o resultado foi que ninguém escolheu: os
    22 projetos em produção estavam todos nulos e a plataforma contava a união
    dos dias de todas as frentes — um escopo de Business parava na semana de
    avaliação da Tech.

    Devolve o rótulo já normalizado, para o chamador gravar o que foi validado
    e não o que veio na requisição.
    """
    escolhido = (calendario or "").strip() or None
    disponiveis = calendarios_da_frente(db, frente_id)

    if escolhido is None and disponiveis != [None]:
        nomes = ", ".join(sorted(n for n in disponiveis if n))
        raise RegraDeNegocioError(
            "Escolha o calendário que este escopo segue: a frente dele tem mais de um "
            f"({nomes}), e as datas de avaliação de um não são as do outro."
        )
    if escolhido is not None and escolhido not in disponiveis:
        frente = FrenteRepository(db).get_by_id(frente_id)
        nome = frente.nome if frente else frente_id
        raise RegraDeNegocioError(
            f"A frente {nome} não tem um calendário chamado {escolhido}. "
            "Carregue o calendário em Calendários base antes de apontar para ele."
        )
    return escolhido


class CreateEscopoProjetoUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjetoEscopoRepository(db)
        self.projeto_repository = ProjetoRepository(db)
        self.frente_repository = ProjetoFrenteRepository(db)
        self.catalogo_repository = EscopoRepository(db)

    def execute(self, projeto_id: int, request: EscopoVendidoRequest):
        if not self.projeto_repository.get_by_id(projeto_id):
            return None

        frentes = [f.frente_id for f in self.frente_repository.get_by_projeto(projeto_id)]
        validar_escopo_vendido(request, frentes, self.catalogo_repository)
        calendario = validar_calendario_do_escopo(
            self.db, request.frente_id, request.calendario
        )

        # Avulso vai pro fim da lista que já existe — quem quiser no meio
        # reordena depois pelas setinhas na tela do projeto.
        existentes = self.repository.get_by_projeto(projeto_id)
        proxima_ordem = max((e.ordem for e in existentes), default=-1) + 1

        escopo = self.repository.create(
            projeto_id=projeto_id,
            escopo_id=request.escopo_id,
            nome_customizado=(request.nome_customizado or "").strip() or None,
            frente_id=request.frente_id,
            calendario=calendario,
            dias_uteis_vendidos=request.dias_uteis_vendidos,
            data_entrega_planejada=request.data_entrega_planejada,
            status="nao_iniciado",
            ordem=proxima_ordem,
        )
        return {"id": escopo.id, "projeto_id": escopo.projeto_id}
