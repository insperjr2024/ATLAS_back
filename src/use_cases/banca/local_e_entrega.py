"""Local da banca e anexo da entrega (2026-09-10, a pedido).

Quem mexe: só quem é do PROJETO que a banca avalia — `membros_da_banca`
(coordenador da banca + equipe atual dos projetos dos escopos cobertos). Os
avaliadores escalados NÃO entram: eles julgam, não organizam.

- **Local**: texto livre, editável até 1h antes da banca. Depois tranca.
- **Entrega**: link OU arquivo, a qualquer momento (antes ou depois).
"""

from datetime import timedelta
from typing import Set

from fastapi import UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.banca_escopo_repository import BancaEscopoRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.equipe_projeto_repository import EquipeProjetoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.utils.equipe_banca import membros_da_banca
from src.utils.exceptions import RegraDeNegocioError
from src.utils.fuso import agora_utc

#: Registrar/alterar o local trava esta janela antes da banca.
PRAZO_LOCAL_HORAS = 1


class LocalBancaRequest(BaseModel):
    local: str


class EntregaLinkBancaRequest(BaseModel):
    link: str

#: Teto do arquivo da entrega — mesmo do anexo de proposta.
LIMITE_ARQUIVO_BYTES = 10 * 1024 * 1024


def pessoas_do_projeto_da_banca(db: Session, banca) -> Set[int]:
    """Os ids que podem registrar local/entrega: o time do projeto que a
    banca avalia (mais o coordenador da banca)."""
    return membros_da_banca(
        banca,
        BancaEscopoRepository(db),
        ProjetoEscopoRepository(db),
        ProjetoMembroRepository(db),
        EquipeProjetoRepository(db),
    )


def _banca_ou_erro(db: Session, banca_id: int):
    banca = BancaRepository(db).get_by_id(banca_id)
    if not banca:
        raise RegraDeNegocioError("Banca não encontrada")
    return banca


def _exigir_do_projeto(db: Session, banca, usuario_id: int) -> None:
    if usuario_id not in pessoas_do_projeto_da_banca(db, banca):
        raise RegraDeNegocioError(
            "Só quem é do projeto avaliado por esta banca pode registrar isto."
        )


class RegistrarLocalBancaUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = BancaRepository(db)

    def execute(self, banca_id: int, local: str, usuario_id: int) -> dict:
        banca = _banca_ou_erro(self.db, banca_id)
        _exigir_do_projeto(self.db, banca, usuario_id)

        if getattr(banca, "cancelada_em", None):
            raise RegraDeNegocioError("Esta banca foi cancelada.")

        if banca.data_hora is not None:
            faltando = banca.data_hora - agora_utc()
            if faltando < timedelta(hours=PRAZO_LOCAL_HORAS):
                raise RegraDeNegocioError(
                    f"O local não pode mais ser alterado: falta menos de "
                    f"{PRAZO_LOCAL_HORAS}h para a banca."
                )

        texto = (local or "").strip()
        if not texto:
            raise RegraDeNegocioError("Escreva onde a banca vai acontecer.")
        if len(texto) > 500:
            raise RegraDeNegocioError("O local não pode passar de 500 caracteres.")

        self.repository.update(banca_id, local=texto)
        return {"id": banca_id, "local": texto}


class RegistrarEntregaLinkBancaUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = BancaRepository(db)

    def execute(self, banca_id: int, link: str, usuario_id: int) -> dict:
        banca = _banca_ou_erro(self.db, banca_id)
        _exigir_do_projeto(self.db, banca, usuario_id)

        url = (link or "").strip()
        if not url:
            raise RegraDeNegocioError("Cole o link da entrega.")
        if not url.startswith(("http://", "https://")):
            raise RegraDeNegocioError("O link precisa começar com http:// ou https://.")
        if len(url) > 1000:
            raise RegraDeNegocioError("O link é longo demais.")

        # Link E arquivo não convivem — o novo link apaga o arquivo anterior.
        self.repository.update(
            banca_id,
            entrega_link=url,
            entrega_arquivo_nome=None,
            entrega_arquivo_conteudo=None,
        )
        return {"id": banca_id, "entrega_link": url, "entrega_arquivo_nome": None}


class SubirEntregaArquivoBancaUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = BancaRepository(db)

    def execute(self, banca_id: int, arquivo: UploadFile, usuario_id: int) -> dict:
        banca = _banca_ou_erro(self.db, banca_id)
        _exigir_do_projeto(self.db, banca, usuario_id)

        conteudo = arquivo.file.read()
        if not conteudo:
            raise RegraDeNegocioError("O arquivo está vazio.")
        if len(conteudo) > LIMITE_ARQUIVO_BYTES:
            raise RegraDeNegocioError("O arquivo passa de 10 MB.")

        nome = (arquivo.filename or "entrega").strip()[:255]
        self.repository.update(
            banca_id,
            entrega_arquivo_nome=nome,
            entrega_arquivo_conteudo=conteudo,
            entrega_link=None,
        )
        return {"id": banca_id, "entrega_arquivo_nome": nome, "entrega_link": None}


class RemoverEntregaBancaUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = BancaRepository(db)

    def execute(self, banca_id: int, usuario_id: int) -> None:
        banca = _banca_ou_erro(self.db, banca_id)
        _exigir_do_projeto(self.db, banca, usuario_id)
        self.repository.update(
            banca_id,
            entrega_link=None,
            entrega_arquivo_nome=None,
            entrega_arquivo_conteudo=None,
        )
