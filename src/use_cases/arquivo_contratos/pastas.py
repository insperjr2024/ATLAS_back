from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.repositories.arquivo_contratos_repository import (
    ArquivoContratosItemRepository,
    ArquivoContratosPastaRepository,
)
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.exceptions import RegraDeNegocioError


def serializar_pasta(p) -> dict:
    return {
        "id": p.id,
        "nome": p.nome,
        "pai_id": p.pai_id,
        "semestre_id": p.semestre_id,
        "projeto_id": p.projeto_id,
        "automatica": p.semestre_id is not None or p.projeto_id is not None,
        "criado_em": p.criado_em,
    }


def serializar_item(i, nomes: dict) -> dict:
    return {
        "id": i.id,
        "pasta_id": i.pasta_id,
        "nome": i.nome,
        "mime": i.mime,
        "tamanho": i.tamanho,
        "origem": i.origem,
        "documento_id": i.documento_id,
        "criado_por_nome": nomes.get(i.criado_por),
        "criado_em": i.criado_em,
        "atualizado_em": i.atualizado_em,
    }


class GetPastaUseCase:
    """O conteúdo de uma pasta (ou da raiz, com `pasta_id` nulo): o caminho
    até ela, as subpastas e os arquivos."""

    def __init__(self, db: Session):
        self.pastas = ArquivoContratosPastaRepository(db)
        self.itens = ArquivoContratosItemRepository(db)
        self.usuarios = UsuarioRepository(db)

    def execute(self, pasta_id: Optional[int]) -> dict:
        pasta = None
        if pasta_id is not None:
            pasta = self.pastas.get_by_id(pasta_id)
            if not pasta:
                raise RegraDeNegocioError("Pasta não encontrada")
        itens = self.itens.get_por_pasta(pasta_id) if pasta_id is not None else []
        nomes = {u.id: u.nome for u in self.usuarios.get_all()}
        return {
            "pasta": serializar_pasta(pasta) if pasta else None,
            "caminho": [serializar_pasta(p) for p in self.pastas.caminho(pasta_id)],
            "subpastas": [serializar_pasta(p) for p in self.pastas.get_filhas(pasta_id)],
            "itens": [serializar_item(i, nomes) for i in itens],
        }


class BuscarUseCase:
    def __init__(self, db: Session):
        self.pastas = ArquivoContratosPastaRepository(db)
        self.itens = ArquivoContratosItemRepository(db)
        self.usuarios = UsuarioRepository(db)

    def execute(self, termo: str) -> list[dict]:
        termo = (termo or "").strip()
        if len(termo) < 2:
            return []
        nomes = {u.id: u.nome for u in self.usuarios.get_all()}
        saida = []
        for item in self.itens.buscar(termo):
            dados = serializar_item(item, nomes)
            dados["caminho"] = " / ".join(p.nome for p in self.pastas.caminho(item.pasta_id))
            saida.append(dados)
        return saida


class PastaRequest(BaseModel):
    nome: str = Field(min_length=1, max_length=200)
    pai_id: Optional[int] = None


class CriarPastaUseCase:
    def __init__(self, db: Session):
        self.pastas = ArquivoContratosPastaRepository(db)

    def execute(self, request: PastaRequest, usuario_id: Optional[int]) -> dict:
        if request.pai_id is not None and not self.pastas.get_by_id(request.pai_id):
            raise RegraDeNegocioError("Pasta de destino não encontrada")
        pasta = self.pastas.create(nome=request.nome.strip(), pai_id=request.pai_id, criado_por=usuario_id)
        return serializar_pasta(pasta)


class RenomearPastaRequest(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=1, max_length=200)
    pai_id: Optional[int] = None
    mover: bool = False


class EditarPastaUseCase:
    """Renomear e/ou mover (`mover=True` com `pai_id`, nulo = raiz)."""

    def __init__(self, db: Session):
        self.pastas = ArquivoContratosPastaRepository(db)

    def execute(self, pasta_id: int, request: RenomearPastaRequest) -> dict:
        pasta = self.pastas.get_by_id(pasta_id)
        if not pasta:
            raise RegraDeNegocioError("Pasta não encontrada")
        campos = {}
        if request.nome is not None:
            campos["nome"] = request.nome.strip()
        if request.mover:
            if request.pai_id == pasta_id or (
                request.pai_id is not None and self.pastas.eh_descendente(request.pai_id, pasta_id)
            ):
                raise RegraDeNegocioError("Uma pasta não pode ir pra dentro dela mesma.")
            if request.pai_id is not None and not self.pastas.get_by_id(request.pai_id):
                raise RegraDeNegocioError("Pasta de destino não encontrada")
            if pasta.semestre_id is not None:
                raise RegraDeNegocioError("A pasta de uma gestão fica na raiz.")
            campos["pai_id"] = request.pai_id
        if campos:
            pasta = self.pastas.update(pasta_id, **campos)
        return serializar_pasta(pasta)


class ApagarPastaUseCase:
    """Pasta com conteúdo só vai com `recursivo=True` (a tela pergunta antes):
    subpastas e arquivos caem em cascata."""

    def __init__(self, db: Session):
        self.pastas = ArquivoContratosPastaRepository(db)

    def execute(self, pasta_id: int, recursivo: bool = False) -> None:
        pasta = self.pastas.get_by_id(pasta_id)
        if not pasta:
            raise RegraDeNegocioError("Pasta não encontrada")
        if self.pastas.tem_conteudo(pasta_id) and not recursivo:
            raise RegraDeNegocioError("A pasta tem conteúdo. Confirme que quer apagar tudo que está dentro.")
        self.pastas.delete(pasta_id)
