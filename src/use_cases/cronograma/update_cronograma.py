"""Escrita de etapas e marcos, e a oficialização do cronograma (§6.4, §5.3)."""

import re
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.banca_repository import BancaRepository
from src.repositories.cronograma_repository import (
    CronogramaEtapaRepository,
    CronogramaMarcoRepository,
)
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.utils.cronograma_guard import exigir_cronograma_editavel
from src.utils.exceptions import RegraDeNegocioError


class EtapaRequest(BaseModel):
    nome: str
    cor: str
    data_inicio: date
    data_fim: date


class EtapaIntervaloRequest(BaseModel):
    """O que o arrasto manda: só o intervalo. Um gesto = uma requisição."""

    data_inicio: date
    data_fim: date


class EtapaDetalheRequest(BaseModel):
    """Nome/cor/status/ordem — sem tocar nas datas."""

    nome: Optional[str] = None
    cor: Optional[str] = None
    status: Optional[str] = None
    ordem: Optional[int] = None


def _validar_intervalo(data_inicio: date, data_fim: date) -> None:
    if data_fim < data_inicio:
        raise RegraDeNegocioError("A data de fim não pode ser anterior à de início")


def _validar_cor(cor: str) -> None:
    """`cronograma_etapa.cor` é CHAR(7) — sem esta guarda, uma cor em outro
    formato vira 500 do MySQL ("Data too long") em vez de 422 legível."""
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", cor or ""):
        raise RegraDeNegocioError("A cor da etapa precisa estar no formato #RRGGBB")


class CreateEtapaUseCase:
    def __init__(self, db: Session):
        self.repository = CronogramaEtapaRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)

    def execute(self, projeto_escopo_id: int, request: EtapaRequest, criado_por: int):
        escopo = self.escopo_repository.get_by_id(projeto_escopo_id)
        if not escopo:
            return None
        exigir_cronograma_editavel(escopo)
        _validar_intervalo(request.data_inicio, request.data_fim)
        _validar_cor(request.cor)

        etapa = self.repository.create(
            projeto_escopo_id=projeto_escopo_id,
            nome=request.nome.strip(),
            cor=request.cor,
            data_inicio=request.data_inicio,
            data_fim=request.data_fim,
            ordem=self.repository.proxima_ordem(projeto_escopo_id),
            criado_por=criado_por,
        )
        return {"id": etapa.id, "nome": etapa.nome, "cor": etapa.cor}


class UpdateEtapaIntervaloUseCase:
    """⭐ O que o arrasto chama. O intervalo SUBSTITUI o anterior — arrastar
    um trecho maior aumenta, menor diminui, em outro lugar move."""

    def __init__(self, db: Session):
        self.repository = CronogramaEtapaRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)

    def execute(self, etapa_id: int, request: EtapaIntervaloRequest):
        etapa = self.repository.get_by_id(etapa_id)
        if not etapa:
            return None
        exigir_cronograma_editavel(self.escopo_repository.get_by_id(etapa.projeto_escopo_id))
        _validar_intervalo(request.data_inicio, request.data_fim)

        atualizada = self.repository.update(
            etapa_id, data_inicio=request.data_inicio, data_fim=request.data_fim
        )
        return {
            "id": atualizada.id,
            "data_inicio": atualizada.data_inicio,
            "data_fim": atualizada.data_fim,
        }


class UpdateEtapaDetalheUseCase:
    def __init__(self, db: Session):
        self.repository = CronogramaEtapaRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)

    def execute(self, etapa_id: int, request: EtapaDetalheRequest):
        etapa = self.repository.get_by_id(etapa_id)
        if not etapa:
            return None
        exigir_cronograma_editavel(self.escopo_repository.get_by_id(etapa.projeto_escopo_id))
        dados = request.dict(exclude_unset=True, exclude_none=True)
        if "cor" in dados:
            _validar_cor(dados["cor"])
        atualizada = self.repository.update(etapa_id, **dados)
        return {"id": atualizada.id, "nome": atualizada.nome}


class DeleteEtapaUseCase:
    def __init__(self, db: Session):
        self.repository = CronogramaEtapaRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)

    def execute(self, etapa_id: int) -> bool:
        etapa = self.repository.get_by_id(etapa_id)
        if not etapa:
            return False
        exigir_cronograma_editavel(self.escopo_repository.get_by_id(etapa.projeto_escopo_id))
        return self.repository.delete(etapa_id)


class MarcoRequest(BaseModel):
    tipo: str  # reuniao_alinhamento | visita_presencial
    data: date
    projeto_escopo_id: Optional[int] = None
    nota: Optional[str] = None


class CreateMarcoUseCase:
    def __init__(self, db: Session):
        self.repository = CronogramaMarcoRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)

    def execute(self, projeto_id: int, request: MarcoRequest, criado_por: int):
        if request.tipo not in ("reuniao_alinhamento", "visita_presencial"):
            # Banca, entrega e kickoff NÃO são marcos gravados — são lidos de
            # onde já vivem. Gravá-los aqui criaria segunda fonte da verdade.
            raise RegraDeNegocioError(
                "Marco só pode ser 'reuniao_alinhamento' ou 'visita_presencial'. "
                "Banca, entrega e kickoff são lidos das suas próprias tabelas"
            )
        if request.projeto_escopo_id:
            escopo = self.escopo_repository.get_by_id(request.projeto_escopo_id)
            if not escopo or escopo.projeto_id != projeto_id:
                raise RegraDeNegocioError("O escopo informado não é deste projeto")

        marco = self.repository.create(
            projeto_id=projeto_id,
            projeto_escopo_id=request.projeto_escopo_id,
            tipo=request.tipo,
            data=request.data,
            nota=(request.nota or "").strip() or None,
            criado_por=criado_por,
        )
        return {"id": marco.id, "tipo": marco.tipo, "data": marco.data}


class DeleteMarcoUseCase:
    def __init__(self, db: Session):
        self.repository = CronogramaMarcoRepository(db)

    def execute(self, marco_id: int) -> bool:
        return self.repository.delete(marco_id)


class OficializarCronogramaUseCase:
    """§5.3: ao fim da ambientação, o coordenador CRAVA o cronograma.

    Depois disso, mudança vira solicitação de reajuste (§5.6). A saída dessa
    trava é o reajuste aprovado LIMPAR `cronograma_oficializado_em` — sem
    coluna extra e sem estado "meio aberto".
    """

    def __init__(self, db: Session):
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.etapa_repository = CronogramaEtapaRepository(db)
        self.banca_repository = BancaRepository(db)

    def execute(self, projeto_escopo_id: int):
        escopo = self.escopo_repository.get_by_id(projeto_escopo_id)
        if not escopo:
            return None
        if escopo.cronograma_oficializado_em:
            raise RegraDeNegocioError("Este cronograma já foi oficializado")

        if not self.etapa_repository.get_by_escopo(projeto_escopo_id):
            raise RegraDeNegocioError("Pinte pelo menos uma etapa antes de oficializar")
        if not self.banca_repository.get_by_projeto_escopo(projeto_escopo_id):
            raise RegraDeNegocioError("Marque a banca do escopo antes de oficializar")

        atualizado = self.escopo_repository.update(
            projeto_escopo_id, cronograma_oficializado_em=datetime.now()
        )
        return {
            "id": atualizado.id,
            "cronograma_oficializado_em": atualizado.cronograma_oficializado_em,
        }
