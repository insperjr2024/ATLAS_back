from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.escopo_repository import EscopoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_frente_repository import ProjetoFrenteRepository
from src.repositories.projeto_repository import ProjetoRepository
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


class CreateEscopoProjetoUseCase:
    def __init__(self, db: Session):
        self.repository = ProjetoEscopoRepository(db)
        self.projeto_repository = ProjetoRepository(db)
        self.frente_repository = ProjetoFrenteRepository(db)
        self.catalogo_repository = EscopoRepository(db)

    def execute(self, projeto_id: int, request: EscopoVendidoRequest):
        if not self.projeto_repository.get_by_id(projeto_id):
            return None

        frentes = [f.frente_id for f in self.frente_repository.get_by_projeto(projeto_id)]
        validar_escopo_vendido(request, frentes, self.catalogo_repository)

        # Avulso vai pro fim da lista que já existe — quem quiser no meio
        # reordena depois pelas setinhas na tela do projeto.
        existentes = self.repository.get_by_projeto(projeto_id)
        proxima_ordem = max((e.ordem for e in existentes), default=-1) + 1

        escopo = self.repository.create(
            projeto_id=projeto_id,
            escopo_id=request.escopo_id,
            nome_customizado=(request.nome_customizado or "").strip() or None,
            frente_id=request.frente_id,
            dias_uteis_vendidos=request.dias_uteis_vendidos,
            data_entrega_planejada=request.data_entrega_planejada,
            status="nao_iniciado",
            ordem=proxima_ordem,
        )
        return {"id": escopo.id, "projeto_id": escopo.projeto_id}
