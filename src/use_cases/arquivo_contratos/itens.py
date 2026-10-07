from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.repositories.arquivo_contratos_repository import (
    ArquivoContratosItemRepository,
    ArquivoContratosPastaRepository,
)
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.arquivo_contratos.pastas import serializar_item
from src.utils.exceptions import RegraDeNegocioError
from src.utils.fuso import agora_utc

LIMITE_BYTES = 25 * 1024 * 1024
MIMES_ACEITOS = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "image/png",
    "image/jpeg",
}


def _validar_arquivo(conteudo: bytes, mime: Optional[str], nome: str) -> str:
    if not conteudo:
        raise RegraDeNegocioError("O arquivo está vazio.")
    if len(conteudo) > LIMITE_BYTES:
        raise RegraDeNegocioError("O arquivo passa de 25 MB.")
    mime = mime or "application/octet-stream"
    if mime not in MIMES_ACEITOS and not nome.lower().endswith((".pdf", ".docx", ".doc", ".png", ".jpg", ".jpeg")):
        raise RegraDeNegocioError("Só PDF, Word (.docx/.doc) e imagens (PNG/JPG).")
    return mime


class _Base:
    def __init__(self, db: Session):
        self.db = db
        self.itens = ArquivoContratosItemRepository(db)
        self.pastas = ArquivoContratosPastaRepository(db)
        self.usuarios = UsuarioRepository(db)

    def _nomes(self) -> dict:
        return {u.id: u.nome for u in self.usuarios.get_all()}

    def _item_ou_erro(self, item_id: int):
        item = self.itens.get_by_id(item_id)
        if not item:
            raise RegraDeNegocioError("Arquivo não encontrado")
        return item


class ImportarItemUseCase(_Base):
    def execute(self, pasta_id: int, conteudo: bytes, nome: str, mime: Optional[str], usuario_id: Optional[int]) -> dict:
        if not self.pastas.get_by_id(pasta_id):
            raise RegraDeNegocioError("Pasta não encontrada")
        nome = (nome or "").strip() or "arquivo"
        mime = _validar_arquivo(conteudo, mime, nome)
        item = self.itens.create(
            pasta_id=pasta_id,
            nome=nome[:255],
            mime=mime,
            tamanho=len(conteudo),
            conteudo=conteudo,
            origem="importado",
            criado_por=usuario_id,
        )
        return serializar_item(item, self._nomes())


class BaixarItemUseCase(_Base):
    def execute(self, item_id: int) -> tuple[bytes, str, str]:
        item = self._item_ou_erro(item_id)
        return bytes(item.conteudo), item.nome, item.mime


class EditarItemRequest(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=1, max_length=255)
    pasta_id: Optional[int] = None


class EditarItemUseCase(_Base):
    """Renomear e/ou mover."""

    def execute(self, item_id: int, request: EditarItemRequest) -> dict:
        item = self._item_ou_erro(item_id)
        campos = {}
        if request.nome is not None:
            campos["nome"] = request.nome.strip()
        if request.pasta_id is not None and request.pasta_id != item.pasta_id:
            if not self.pastas.get_by_id(request.pasta_id):
                raise RegraDeNegocioError("Pasta de destino não encontrada")
            campos["pasta_id"] = request.pasta_id
        if campos:
            campos["atualizado_em"] = agora_utc()
            item = self.itens.update(item_id, **campos)
        return serializar_item(item, self._nomes())


class SubstituirItemUseCase(_Base):
    """Troca o conteúdo mantendo o lugar; o nome segue o do arquivo novo."""

    def execute(self, item_id: int, conteudo: bytes, nome: str, mime: Optional[str]) -> dict:
        item = self._item_ou_erro(item_id)
        nome = (nome or "").strip() or item.nome
        mime = _validar_arquivo(conteudo, mime, nome)
        item = self.itens.update(
            item_id, conteudo=conteudo, tamanho=len(conteudo), mime=mime, nome=nome[:255], atualizado_em=agora_utc()
        )
        return serializar_item(item, self._nomes())


class ApagarItemUseCase(_Base):
    def execute(self, item_id: int) -> None:
        self._item_ou_erro(item_id)
        self.itens.delete(item_id)
