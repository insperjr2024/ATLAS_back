"""Marcar a banca de um escopo — pelo cronograma ou pela tela de Bancas.

⚠ **Não existe sincronização aqui, e é de propósito.** O §8 fala em "os dois
lados conversam e ficam sincronizados (uma data só)" — a resposta certa a isso
NÃO é uma rotina de sync entre duas tabelas, é haver uma linha só. Marcar a
banca pelo cronograma escreve em `banca`, exatamente a mesma linha que
`/bancas` lê. Mudou de um lado, o outro vê no próximo load. Não é
sincronização: é a mesma linha lida duas vezes.
"""

from datetime import datetime, timedelta
from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.banca_escopo_repository import BancaEscopoRepository
from src.repositories.banca_frente_repository import BancaFrenteRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.escopo_repository import EscopoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.use_cases.notificacao.eventos import notificar_banca_remarcada
from src.utils.avaliacoes_pendentes import PRAZO_AVALIACAO_DIAS
from src.utils.banca_status import calcular_status_banca
from src.utils.exceptions import RegraDeNegocioError
from src.utils.notificar import notificar


class MarcarBancaEscopoRequest(BaseModel):
    data_hora: datetime
    #: Remarcar exige justificativa da diretoria (§5.6) — nunca é silenciosa.
    justificativa: Optional[str] = None
    #: ⭐ O conjunto COMPLETO de escopos que esta banca cobre, escolhido por
    #: quem marca. O escopo da URL entra sempre, mesmo que não venha na lista.
    #: `None` = não mexer nos vínculos atuais (é o que as chamadas antigas
    #: fazem: marcam a banca do escopo da URL e pronto).
    escopo_ids: Optional[List[int]] = None


class MarcarBancaEscopoUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = BancaRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.projeto_repository = ProjetoRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)
        self.banca_frente_repository = BancaFrenteRepository(db)
        self.banca_escopo_repository = BancaEscopoRepository(db)
        self.catalogo_repository = EscopoRepository(db)

    def execute(self, escopo_id: int, request: MarcarBancaEscopoRequest, eh_diretor: bool = False):
        escopo = self.escopo_repository.get_by_id(escopo_id)
        if not escopo:
            return None

        projeto = self.projeto_repository.get_by_id(escopo.projeto_id)
        existente = self.repository.get_by_projeto_escopo(escopo_id)
        escopos_cobertos = self._resolver_escopos(escopo, request, existente)

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
            data_anterior = existente.data_hora
            banca = self.repository.update(existente.id, data_hora=request.data_hora)
            # Depois do update e só se a data realmente mudou: salvar a mesma
            # data (por causa de outra edição na mesma request) não é remarcação.
            if data_anterior != banca.data_hora:
                notificar_banca_remarcada(
                    self.db, projeto, banca.id, self._nome(escopo), data_anterior, banca.data_hora
                )
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
                # compatibilidade com o módulo legado, mas quem manda é o
                # vínculo em `banca_escopo`.
                nome_projeto=projeto.nome,
                escopo_id=escopo.escopo_id,
                coordenador_id=coordenador.usuario_id,
                data_hora=request.data_hora,
            )

        self.banca_escopo_repository.definir(banca.id, [e.id for e in escopos_cobertos])
        self._garantir_frentes(banca.id, [e.frente_id for e in escopos_cobertos])

        return {
            "id": banca.id,
            "projeto_escopo_ids": [e.id for e in escopos_cobertos],
            "frente_ids": sorted({e.frente_id for e in escopos_cobertos}),
            "data_hora": banca.data_hora,
            "status": calcular_status_banca(banca.data_hora, banca.realizado_em),
        }

    def _resolver_escopos(self, escopo, request: MarcarBancaEscopoRequest, existente):
        """Quais escopos esta banca vai cobrir — e se pode cobri-los.

        Uma banca pode juntar vários escopos do MESMO projeto (inclusive de
        frentes diferentes). O que ela não pode é roubar escopo que já tem
        banca própria: como o escopo continua tendo no máximo uma, juntá-lo
        aqui apagaria em silêncio a data que já estava marcada nele.
        """
        if request.escopo_ids is None:
            atuais = (
                self.banca_escopo_repository.get_escopo_ids(existente.id) if existente else []
            )
            pedidos = set(atuais) | {escopo.id}
        else:
            pedidos = set(request.escopo_ids) | {escopo.id}

        escopos = []
        for pedido_id in sorted(pedidos):
            alvo = escopo if pedido_id == escopo.id else self.escopo_repository.get_by_id(pedido_id)
            if not alvo:
                raise RegraDeNegocioError(f"Escopo {pedido_id} não encontrado")
            if alvo.projeto_id != escopo.projeto_id:
                raise RegraDeNegocioError(
                    "Uma banca só pode cobrir escopos do mesmo projeto"
                )
            dono = self.banca_escopo_repository.get_banca_id(alvo.id)
            if dono is not None and (existente is None or dono != existente.id):
                raise RegraDeNegocioError(
                    f"O escopo '{self._nome(alvo)}' já tem banca marcada — "
                    "desmarque a dele antes de juntar os dois"
                )
            escopos.append(alvo)
        return escopos

    def _nome(self, escopo) -> str:
        if escopo.nome_customizado:
            return escopo.nome_customizado
        do_catalogo = self.catalogo_repository.get_by_id(escopo.escopo_id) if escopo.escopo_id else None
        return do_catalogo.nome if do_catalogo else f"escopo {escopo.id}"

    def _garantir_frentes(self, banca_id: int, frente_ids: List[int]) -> None:
        """⭐ A banca é das frentes **dos escopos que ela cobre**, não de todas
        as frentes do projeto.

        Uma banca só de Análise Mercadológica é banca de Business; se a mesma
        banca também cobrir Revisão Contratual, ela passa a ser de Business +
        Direito e a composição do §8 cobra o piso das duas. É a consequência
        esperada de juntar os escopos — quem junta está dizendo que uma banca
        só avalia os dois trabalhos.

        Roda também na remarcação, de propósito: banca criada por fora deste
        fluxo (o módulo legado, um seed) chega aqui sem vínculo nenhum, e
        marcar a data é a oportunidade de acertar isso. Idempotente.

        Só adiciona: frente escalada à mão por outro caminho não é removida
        daqui, porque pode já ter gente inscrita por ela.
        """
        atuais = {bf.frente_id for bf in self.banca_frente_repository.get_by_banca(banca_id)}
        for frente_id in sorted(set(frente_ids) - atuais):
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
        self.db = db
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

        candidaturas = self.candidatura_repository.get_by_banca(banca_id)
        if request.presentes is not None:
            presentes = set(request.presentes)
            for candidatura in candidaturas:
                self.candidatura_repository.update(
                    candidatura.id, confirmado=candidatura.usuario_id in presentes
                )
            avisar = presentes
        else:
            # Sem lista de presença, avisa todo mundo que era candidato — não
            # deixar de notificar por falta de dado é melhor que silenciar.
            avisar = {c.usuario_id for c in candidaturas}

        self._notificar_prazo_avaliacao(banca, avisar)

        return {
            "id": banca.id,
            "realizado_em": banca.realizado_em,
            "status": calcular_status_banca(banca.data_hora, banca.realizado_em),
        }

    def _notificar_prazo_avaliacao(self, banca, usuario_ids) -> None:
        prazo = banca.realizado_em + timedelta(days=PRAZO_AVALIACAO_DIAS)
        mensagem = (
            f"A banca de {banca.nome_projeto} foi realizada. Você tem até "
            f"{prazo:%d/%m/%Y} para enviar sua avaliação."
        )
        for usuario_id in usuario_ids:
            notificar(
                self.db, usuario_id, mensagem, banca_id=banca.id, tipo="avaliacao_pendente"
            )


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
