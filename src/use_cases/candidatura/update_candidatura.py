from typing import Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.banca_frente_repository import BancaFrenteRepository
from src.repositories.candidatura_repository import CandidaturaRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.frente_repository import FrenteRepository
from src.use_cases.notificacao.eventos import notificar_escalacao_banca
from src.utils.banca_status import calcular_status_banca
from src.utils.exceptions import RegraDeNegocioError
from src.utils.fuso import agora_utc
from src.utils.piso_banca import calcular_piso_banca

#: A menos de tantos dias da banca, com a composição já completa, ninguém
#: sai sozinho (2026-09-09, a pedido): tão perto e sem buraco, uma saída
#: deixaria uma vaga sem tempo de tapar. A diretoria (`pode_gerir_membros`)
#: ainda resolve caso a caso.
PRAZO_TRAVA_DESALOCACAO_DIAS = 7


class UpdateCandidaturaRequest(BaseModel):
    banca_id: Optional[int] = None
    confirmado: Optional[bool] = None


class UpdateCandidaturaUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = CandidaturaRepository(db)
        self.banca_repository = BancaRepository(db)

    def execute(self, candidatura_id: int, request: UpdateCandidaturaRequest):
        data = request.dict(exclude_unset=True)
        confirmava_antes = getattr(self.repository.get_by_id(candidatura_id), "confirmado", None)
        candidatura = self.repository.update(candidatura_id, **data)
        if not candidatura:
            return None

        # Só na virada para confirmado: um PATCH que não mexe em `confirmado`
        # (ou que reconfirma o que já estava) não é notícia nenhuma.
        if candidatura.confirmado and not confirmava_antes:
            banca = self.banca_repository.get_by_id(candidatura.banca_id)
            if banca:
                notificar_escalacao_banca(
                    self.db,
                    banca.id,
                    candidatura.usuario_id,
                    banca.nome_projeto,
                    banca.data_hora,
                )

        return {
            "id": candidatura.id,
            "banca_id": candidatura.banca_id,
            "usuario_id": candidatura.usuario_id,
            "criado_em": candidatura.criado_em,
            "confirmado": candidatura.confirmado
        }


class DeleteCandidaturaUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = CandidaturaRepository(db)
        self.banca_repository = BancaRepository(db)
        self.banca_frente_repository = BancaFrenteRepository(db)
        self.frente_repository = FrenteRepository(db)

    def execute(self, candidatura_id: int, eh_gestao: bool = False) -> bool:
        candidatura = self.repository.get_by_id(candidatura_id)
        if not candidatura:
            return False

        banca = self.banca_repository.get_by_id(candidatura.banca_id)

        # Mesma virada do create: só a realização tranca. Antes da F5, uma
        # banca que escorregava deixava as pessoas presas na inscrição.
        if banca and calcular_status_banca(banca.data_hora, banca.realizado_em, cancelada_em=getattr(banca, "cancelada_em", None)) == "realizada":
            raise RegraDeNegocioError("Não é possível se desalocar: esta banca já foi realizada")

        # ⭐ Trava dos 7 dias (2026-09-09, a pedido). A menos de uma semana da
        # banca, com a composição já batendo o mínimo (as vagas que faltavam
        # preenchidas — na mão ou pelo push), sair sozinho deixa um buraco sem
        # tempo de tapar. A diretoria de projetos passa por cima.
        if banca and not eh_gestao and self._perto_e_completa(banca):
            raise RegraDeNegocioError(
                "Não dá mais para sair desta banca: ela é em menos de "
                f"{PRAZO_TRAVA_DESALOCACAO_DIAS} dias e a vaga já está preenchida. "
                "Fale com a diretoria de projetos."
            )

        return self.repository.delete(candidatura_id)

    def _perto_e_completa(self, banca) -> bool:
        if not banca.data_hora:
            return False
        # `data_hora` é UTC sem tzinfo; `agora_utc()` também. Faltam N dias:
        dias = (banca.data_hora - agora_utc()).total_seconds() / 86400
        if dias > PRAZO_TRAVA_DESALOCACAO_DIAS:
            return False

        vinculos = self.banca_frente_repository.get_by_banca(banca.id)
        frentes = [
            f for f in (self.frente_repository.get_by_id(v.frente_id) for v in vinculos) if f
        ]
        piso = calcular_piso_banca(banca, frentes, self.db)
        if piso <= 0:
            return False
        alocados = len(self.repository.get_by_banca(banca.id))
        return alocados >= piso