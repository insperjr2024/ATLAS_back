"""Escrita de etapas e marcos do cronograma (§6.4).

⭐ **Sem cadeado.** Existia aqui uma trava de "cronograma oficializado": depois
de cravado, qualquer mudança virava uma solicitação de reajuste. Ela saiu — na
prática trancava o calendário inteiro atrás de uma fila e transformava em
rotina a exceção que o §5.6 pedia que fosse rara.

⭐ **A etapa não sai da janela do escopo.** Pintar além dela deixou de ser
"avisa e deixa passar": o calendário do escopo é o tempo que foi vendido, e
estender o trabalho para fora dele é uma renegociação de prazo, não um arrasto
de mouse. Quem precisa de mais dias pede à diretoria — e só nos **3 primeiros
dias úteis** depois da reunião inicial (§5.4), que é a janela em que dá para
perceber que o escopo foi vendido apertado.

⚠ **Exceção: depois da BANCA REALIZADA.** A partir do momento em que a banca do
escopo aconteceu, qualquer mudança no cronograma dele é entendida como
**ajustes** — e ajuste não é o trabalho vendido correndo, é o que veio depois
da avaliação. Por isso a janela para de valer ali, e não na entrega: entre a
banca e a entrega ao cliente é exatamente quando os ajustes acontecem.
"""

import re
from datetime import date
from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.cronograma_repository import (
    CronogramaEtapaRepository,
    CronogramaMarcoRepository,
)
from src.repositories.banca_repository import BancaRepository
from src.repositories.dia_nao_letivo_repository import DiaNaoLetivoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_status_historico_repository import (
    ProjetoStatusHistoricoRepository,
)
from src.utils.contagem_dias import derivar_janelas_pausa
from src.utils.exceptions import RegraDeNegocioError
from src.utils.janela_escopo import PRAZO_PEDIDO_AJUSTE_DIAS_UTEIS, calcular_janela


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


def _exigir_dentro_da_janela(db: Session, escopo, data_inicio: date, data_fim: date) -> None:
    """⭐ A etapa precisa caber na janela do escopo (vendidos + ajustados).

    O erro diz as três coisas que a pessoa precisa para decidir o que fazer:
    onde a janela termina, que o caminho é pedir dias, e se esse caminho ainda
    está aberto. Sem a terceira, quem já passou do prazo ficaria tentando pedir
    e levando outra recusa.

    ⚠ **Banca já realizada passa direto.** Depois que a banca do escopo
    aconteceu, mexer no cronograma dele é *ajuste* — não é mais o trabalho
    vendido correndo, e ele nasce fora da janela por definição. A entrega
    também libera, mas é consequência: o §5.5 só a permite depois da banca.
    """
    if escopo.data_entrega_real:
        return
    banca = BancaRepository(db).get_by_projeto_escopo(escopo.id)
    if banca and banca.realizado_em:
        return

    dias_nao_letivos = [d.data for d in DiaNaoLetivoRepository(db).get_all()]
    janelas_pausa = derivar_janelas_pausa(
        ProjetoStatusHistoricoRepository(db).get_by_projeto(escopo.projeto_id)
    )
    janela = calcular_janela(
        escopo.data_inicio,
        escopo.dias_uteis_vendidos,
        escopo.dias_uteis_ajustados,
        dias_nao_letivos,
        janelas_pausa=janelas_pausa,
    )

    if not janela.aberta:
        raise RegraDeNegocioError(
            "Este escopo ainda não teve reunião inicial — marque-a no calendário "
            "antes de pintar etapas, é ela que abre a janela do escopo"
        )

    if data_inicio >= janela.data_inicio and data_fim <= janela.fim:
        return

    saida = (
        f"Peça dias de ajuste à diretoria — o prazo vai até "
        f"{janela.prazo_pedido_ajuste.strftime('%d/%m/%Y')}."
        if janela.pedido_ajuste_aberto
        else (
            f"O prazo para pedir dias de ajuste era de {PRAZO_PEDIDO_AJUSTE_DIAS_UTEIS} "
            "dias úteis a partir da reunião inicial e já venceu — a janela deste "
            "escopo não muda mais."
        )
    )
    raise RegraDeNegocioError(
        f"A etapa precisa caber na janela do escopo, que vai de "
        f"{janela.data_inicio.strftime('%d/%m/%Y')} a {janela.fim.strftime('%d/%m/%Y')} "
        f"({janela.dias_vendidos} vendidos"
        + (f" + {janela.dias_ajustados} ajustados" if janela.dias_ajustados else "")
        + f"). {saida}"
    )


def _validar_cor(cor: str) -> None:
    """`cronograma_etapa.cor` é CHAR(7) — sem esta guarda, uma cor em outro
    formato vira 500 do MySQL ("Data too long") em vez de 422 legível."""
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", cor or ""):
        raise RegraDeNegocioError("A cor da etapa precisa estar no formato #RRGGBB")


class CreateEtapaUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = CronogramaEtapaRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)

    def execute(self, projeto_escopo_id: int, request: EtapaRequest, criado_por: int):
        escopo = self.escopo_repository.get_by_id(projeto_escopo_id)
        if not escopo:
            return None
        _validar_intervalo(request.data_inicio, request.data_fim)
        _validar_cor(request.cor)
        _exigir_dentro_da_janela(self.db, escopo, request.data_inicio, request.data_fim)

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
        self.db = db
        self.repository = CronogramaEtapaRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)

    def execute(self, etapa_id: int, request: EtapaIntervaloRequest):
        etapa = self.repository.get_by_id(etapa_id)
        if not etapa:
            return None
        _validar_intervalo(request.data_inicio, request.data_fim)
        # Arrastar é o caminho mais fácil de sair da janela sem perceber — a
        # trava tem de estar aqui, não só na criação.
        escopo = self.escopo_repository.get_by_id(etapa.projeto_escopo_id)
        if escopo:
            _exigir_dentro_da_janela(self.db, escopo, request.data_inicio, request.data_fim)

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

    def execute(self, etapa_id: int, request: EtapaDetalheRequest):
        etapa = self.repository.get_by_id(etapa_id)
        if not etapa:
            return None
        dados = request.dict(exclude_unset=True, exclude_none=True)
        if "cor" in dados:
            _validar_cor(dados["cor"])
        atualizada = self.repository.update(etapa_id, **dados)
        return {"id": atualizada.id, "nome": atualizada.nome}


class DeleteEtapaUseCase:
    def __init__(self, db: Session):
        self.repository = CronogramaEtapaRepository(db)

    def execute(self, etapa_id: int) -> bool:
        etapa = self.repository.get_by_id(etapa_id)
        if not etapa:
            return False
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

    `cronograma_oficializado_em` é só um marco informativo (aparece na tela
    como "oficializado em X") — não bloqueia edição depois. O fluxo de
    reajuste que travava isso foi removido a pedido do usuário (2026-08-06):
    o cronograma continua livre pra editar como quiser, oficializado ou não.
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
