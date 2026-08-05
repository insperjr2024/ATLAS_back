"""Marcar a banca de um escopo — pelo cronograma ou pela tela de Bancas.

⚠ **Não existe sincronização aqui, e é de propósito.** O §8 fala em "os dois
lados conversam e ficam sincronizados (uma data só)" — a resposta certa a isso
NÃO é uma rotina de sync entre duas tabelas, é haver uma linha só. Marcar a
banca pelo cronograma escreve em `banca`, exatamente a mesma linha que
`/bancas` lê. Mudou de um lado, o outro vê no próximo load. Não é
sincronização: é a mesma linha lida duas vezes.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.banca_frente_repository import BancaFrenteRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.utils.banca_status import calcular_status_banca
from src.utils.exceptions import RegraDeNegocioError


class MarcarBancaEscopoRequest(BaseModel):
    data_hora: datetime
    #: Remarcar exige justificativa da diretoria (§5.6) — nunca é silenciosa.
    justificativa: Optional[str] = None


class MarcarBancaEscopoUseCase:
    def __init__(self, db: Session):
        self.repository = BancaRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.projeto_repository = ProjetoRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)
        self.banca_frente_repository = BancaFrenteRepository(db)

    def execute(self, escopo_id: int, request: MarcarBancaEscopoRequest, eh_diretor: bool = False):
        escopo = self.escopo_repository.get_by_id(escopo_id)
        if not escopo:
            return None

        projeto = self.projeto_repository.get_by_id(escopo.projeto_id)
        existente = self.repository.get_by_projeto_escopo(escopo_id)

        self._checar_choque(request.data_hora, ignorar_banca_id=existente.id if existente else None)

        if existente:
            # §5.6: remarcação nunca é silenciosa — data antiga preservada no
            # histórico (F11) e justificativa obrigatória, digitada pela
            # diretoria. O gerente não remarca.
            if not eh_diretor:
                raise RegraDeNegocioError(
                    "Esta banca já tem data. Remarcar é decisão da diretoria (§5.6)"
                )
            if not (request.justificativa or "").strip():
                raise RegraDeNegocioError("Remarcar uma banca exige justificativa")
            banca = self.repository.update(existente.id, data_hora=request.data_hora)
        else:
            coordenador = next(
                (
                    m
                    for m in self.membro_repository.get_by_projeto(escopo.projeto_id, apenas_atuais=True)
                    if m.papel == "coordenador"
                ),
                None,
            )
            if not coordenador:
                raise RegraDeNegocioError("O projeto precisa ter um coordenador para marcar a banca")

            banca = self.repository.create(
                # `nome_projeto` e `escopo_id` continuam gravados por
                # compatibilidade com o módulo legado, mas quem manda é a FK.
                nome_projeto=projeto.nome,
                escopo_id=escopo.escopo_id,
                coordenador_id=coordenador.usuario_id,
                data_hora=request.data_hora,
                projeto_escopo_id=escopo_id,
            )
        self._garantir_frente(banca.id, escopo.frente_id)

        return {
            "id": banca.id,
            "projeto_escopo_id": banca.projeto_escopo_id,
            "frente_id": escopo.frente_id,
            "data_hora": banca.data_hora,
            "status": calcular_status_banca(banca.data_hora, banca.realizado_em),
        }

    def _garantir_frente(self, banca_id: int, frente_id: int) -> None:
        """⭐ A banca é da frente **do escopo**, não de todas as frentes do
        projeto.

        Um projeto sinérgico de Business + Direito tem duas bancas: a de
        Análise Mercadológica é banca de Business, a de Revisão Contratual é
        de Direito. Vincular cada uma a todas as frentes faria a composição
        do §8 cobrar o piso de Business (3 pessoas) numa banca de Direito
        (que pede 1) e escalaria gente da frente errada no push automático.

        Roda também na remarcação, de propósito: banca criada por fora deste
        fluxo (o módulo legado, um seed) chega aqui sem vínculo nenhum, e
        marcar a data é a oportunidade de acertar isso. Idempotente.
        """
        atuais = self.banca_frente_repository.get_by_banca(banca_id)
        if any(bf.frente_id == frente_id for bf in atuais):
            return
        self.banca_frente_repository.create(banca_id=banca_id, frente_id=frente_id)

    def _checar_choque(self, data_hora: datetime, ignorar_banca_id: Optional[int]) -> None:
        """§8: o sistema bloqueia duas bancas no mesmo horário; a exceção só é
        liberada pela diretoria, gravando `excecao_choque_por`."""
        for outra in self.repository.get_por_data_hora(data_hora):
            if outra.id == ignorar_banca_id:
                continue
            if outra.excecao_choque_por is not None:
                continue
            raise RegraDeNegocioError(
                f"Já existe uma banca marcada para este horário ({outra.nome_projeto}). "
                "A exceção de choque só é liberada pela diretoria"
            )


class RegistrarRealizacaoRequest(BaseModel):
    realizado_em: Optional[datetime] = None
    #: Quem de fato compareceu — confirma as candidaturas listadas.
    presentes: Optional[list[int]] = None


class RegistrarRealizacaoBancaUseCase:
    """⭐ Marcar que a banca ACONTECEU (§8).

    É esta escrita que separa "a data passou" de "a banca aconteceu" — e sem
    ela, a partir da F5, a banca fica `atrasada` para sempre. Passou a ser
    passo obrigatório da rotina.
    """

    def __init__(self, db: Session):
        self.repository = BancaRepository(db)
        from src.repositories.candidatura_repository import CandidaturaRepository

        self.candidatura_repository = CandidaturaRepository(db)

    def execute(self, banca_id: int, request: RegistrarRealizacaoRequest):
        banca = self.repository.get_by_id(banca_id)
        if not banca:
            return None
        if not banca.data_hora:
            raise RegraDeNegocioError("Uma banca sem data não pode ser marcada como realizada")

        realizado_em = request.realizado_em or banca.data_hora
        banca = self.repository.update(banca_id, realizado_em=realizado_em)

        if request.presentes is not None:
            presentes = set(request.presentes)
            for candidatura in self.candidatura_repository.get_by_banca(banca_id):
                self.candidatura_repository.update(
                    candidatura.id, confirmado=candidatura.usuario_id in presentes
                )

        return {
            "id": banca.id,
            "realizado_em": banca.realizado_em,
            "status": calcular_status_banca(banca.data_hora, banca.realizado_em),
        }


class RegistrarResultadoRequest(BaseModel):
    resultado: str  # "aprovada" | "nao_aprovada"


class RegistrarResultadoBancaUseCase:
    """🔒 O resultado é o que libera ou trava a entrega ao cliente (§8)."""

    def __init__(self, db: Session):
        self.repository = BancaRepository(db)

    def execute(self, banca_id: int, request: RegistrarResultadoRequest):
        if request.resultado not in ("aprovada", "nao_aprovada"):
            raise RegraDeNegocioError("O resultado precisa ser 'aprovada' ou 'nao_aprovada'")

        banca = self.repository.get_by_id(banca_id)
        if not banca:
            return None
        # Não há resultado de banca que não aconteceu.
        if not banca.realizado_em:
            raise RegraDeNegocioError(
                "Registre primeiro que a banca foi realizada, depois o resultado"
            )

        banca = self.repository.update(banca_id, resultado=request.resultado)
        return {"id": banca.id, "resultado": banca.resultado}


class LiberarExcecaoChoqueRequest(BaseModel):
    nota: str


class LiberarExcecaoChoqueUseCase:
    """§8: a exceção de choque de horário só é liberada pela diretoria."""

    def __init__(self, db: Session):
        self.repository = BancaRepository(db)

    def execute(self, banca_id: int, request: LiberarExcecaoChoqueRequest, liberado_por: int):
        if not (request.nota or "").strip():
            raise RegraDeNegocioError("A exceção de choque exige uma justificativa")
        banca = self.repository.update(
            banca_id, excecao_choque_por=liberado_por, excecao_choque_nota=request.nota.strip()
        )
        return {"id": banca.id, "excecao_choque_por": banca.excecao_choque_por} if banca else None
