"""⭐ Pedir e decidir a exceção de choque de horário (§8).

⚠ **O buraco que isto fecha.** O §8 bloqueia duas bancas no mesmo horário e diz
que a exceção é da diretoria. O bloqueio existia; o caminho para pedir a
exceção, não. Quem esbarrava no choque recebia *"a exceção só é liberada pela
diretoria"* e não tinha o que fazer — nem sendo diretor, porque a rota que
gravava a liberação não tinha nenhum chamador na interface. Regra sem via de
cumprimento vira regra contornada por fora do sistema.

Agora são dois atos separados, como no pedido de dias de ajuste (§5.6):
**quem marca pede** com justificativa, **a diretoria decide** na aba Aprovações.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.banca_excecao_choque_repository import BancaExcecaoChoqueRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.exceptions import RegraDeNegocioError
from src.utils.notificar import notificar


class SolicitarExcecaoChoqueRequest(BaseModel):
    projeto_escopo_id: int
    data_hora_pretendida: datetime
    justificativa: str


class DecidirExcecaoChoqueRequest(BaseModel):
    aprovar: bool
    #: Obrigatória nos DOIS sentidos. Uma recusa sem motivo deixa quem pediu
    #: sem saber o que mudar; uma aprovação sem motivo apaga por que a regra do
    #: §8 foi aberta naquele caso.
    resposta: str


class SolicitarExcecaoChoqueUseCase:
    """Quem quer marcar a banca pede a exceção — não a diretoria por ele."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = BancaExcecaoChoqueRepository(db)
        self.banca_repository = BancaRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.projeto_repository = ProjetoRepository(db)
        self.usuario_repository = UsuarioRepository(db)

    def execute(self, request: SolicitarExcecaoChoqueRequest, solicitado_por: int):
        justificativa = (request.justificativa or "").strip()
        if not justificativa:
            raise RegraDeNegocioError("A exceção de choque exige uma justificativa")

        escopo = self.escopo_repository.get_by_id(request.projeto_escopo_id)
        if not escopo:
            return None

        # ⚠ Só faz sentido pedir exceção se HÁ choque. Sem esta checagem a fila
        # da diretoria encheria de pedidos para horários livres — e cada um
        # deles seria uma decisão sobre nada.
        conflitantes = [
            b
            for b in self.banca_repository.get_por_data_hora(request.data_hora_pretendida)
        ]
        banca_do_escopo = self.banca_repository.get_by_projeto_escopo(escopo.id)
        conflitantes = [
            b for b in conflitantes if not banca_do_escopo or b.id != banca_do_escopo.id
        ]
        if not conflitantes:
            raise RegraDeNegocioError(
                "Não há outra banca neste horário — a exceção não é necessária"
            )

        if self.repository.get_aprovada(escopo.id, request.data_hora_pretendida):
            raise RegraDeNegocioError(
                "Este horário já foi liberado para este escopo — basta marcar a banca"
            )

        # Pedir de novo não enfileira duplicata: reescreve o pedido em aberto.
        # Quem clica duas vezes, ou melhora o argumento, não deveria criar duas
        # decisões para a diretoria tomar.
        pendente = self.repository.get_pendente_do_par(escopo.id, request.data_hora_pretendida)
        if pendente:
            atualizado = self.repository.update(pendente.id, justificativa=justificativa)
            return self._serializar(atualizado)

        criado = self.repository.create(
            projeto_escopo_id=escopo.id,
            banca_id=banca_do_escopo.id if banca_do_escopo else None,
            data_hora_pretendida=request.data_hora_pretendida,
            banca_conflitante_id=conflitantes[0].id,
            justificativa=justificativa,
            solicitado_por=solicitado_por,
        )
        self._avisar_diretoria(criado, conflitantes[0], escopo)
        return self._serializar(criado)

    def _avisar_diretoria(self, pedido, conflitante, escopo) -> None:
        projeto = self.projeto_repository.get_by_id(escopo.projeto_id)
        nome = projeto.nome if projeto else "um projeto"
        mensagem = (
            f"{nome} pediu exceção para marcar banca em "
            f"{pedido.data_hora_pretendida:%d/%m/%Y às %H:%M}, que já tem a banca de "
            f"{conflitante.nome_projeto}."
        )
        for diretor in self.usuario_repository.get_por_posicao("diretor"):
            notificar(self.db, diretor.id, mensagem, banca_id=pedido.banca_id)

    def _serializar(self, pedido):
        return {
            "id": pedido.id,
            "projeto_escopo_id": pedido.projeto_escopo_id,
            "data_hora_pretendida": pedido.data_hora_pretendida,
            "status": pedido.status,
            "justificativa": pedido.justificativa,
        }


class DecidirExcecaoChoqueUseCase:
    """Só a diretoria decide (§8) — a rota cobra com `require_diretor`."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = BancaExcecaoChoqueRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.projeto_repository = ProjetoRepository(db)

    def execute(self, pedido_id: int, request: DecidirExcecaoChoqueRequest, respondido_por: int):
        resposta = (request.resposta or "").strip()
        if not resposta:
            raise RegraDeNegocioError("Escreva o motivo da decisão")

        pedido = self.repository.get_by_id(pedido_id)
        if not pedido:
            return None
        if pedido.status != "pendente":
            raise RegraDeNegocioError("Este pedido já foi respondido")

        atualizado = self.repository.update(
            pedido_id,
            status="aprovada" if request.aprovar else "recusada",
            resposta=resposta,
            respondido_por=respondido_por,
            respondido_em=datetime.now(),
        )
        self._avisar_quem_pediu(atualizado)
        return {
            "id": atualizado.id,
            "status": atualizado.status,
            "resposta": atualizado.resposta,
        }

    def _avisar_quem_pediu(self, pedido) -> None:
        # ⚠ Avisar é essencial aqui, e não conveniência: aprovado, o pedido não
        # marca a banca sozinho — quem pediu precisa voltar e marcar. Sem o
        # aviso, uma aprovação ficaria parada esperando alguém adivinhar.
        veredito = "aprovada" if pedido.status == "aprovada" else "recusada"
        complemento = (
            " Você já pode marcar a banca nesse horário."
            if pedido.status == "aprovada"
            else ""
        )
        mensagem = (
            f"Sua exceção de choque para {pedido.data_hora_pretendida:%d/%m/%Y às %H:%M} "
            f"foi {veredito}: {pedido.resposta}.{complemento}"
        )
        notificar(self.db, pedido.solicitado_por, mensagem, banca_id=pedido.banca_id)


class ListarExcecoesChoquePendentesUseCase:
    """A fila da aba Aprovações, com o contexto que a decisão exige."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = BancaExcecaoChoqueRepository(db)
        self.banca_repository = BancaRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.projeto_repository = ProjetoRepository(db)
        self.usuario_repository = UsuarioRepository(db)

    def execute(self):
        # O catálogo, uma vez: `nome_do_escopo` precisa dele para resolver o
        # escopo de catálogo, e "Outro" tem nome customizado (§4).
        from src.repositories.escopo_repository import EscopoRepository
        from src.use_cases.projeto_escopo.get_escopos_projeto import nome_do_escopo

        catalogo = {e.id: e for e in EscopoRepository(self.db).get_all()}

        linhas = []
        for pedido in self.repository.get_pendentes():
            escopo = self.escopo_repository.get_by_id(pedido.projeto_escopo_id)
            projeto = self.projeto_repository.get_by_id(escopo.projeto_id) if escopo else None
            conflitante = (
                self.banca_repository.get_by_id(pedido.banca_conflitante_id)
                if pedido.banca_conflitante_id
                else None
            )
            solicitante = self.usuario_repository.get_by_id(pedido.solicitado_por)
            linhas.append(
                {
                    "id": pedido.id,
                    "projeto_id": projeto.id if projeto else None,
                    "projeto_nome": projeto.nome if projeto else "—",
                    "projeto_escopo_id": pedido.projeto_escopo_id,
                    # ⚠ Era a única das cinco filas sem o nome do escopo: a
                    # linha dizia só o projeto, e um projeto sinérgico tem
                    # banca por escopo — sem ele não dava para saber QUAL.
                    "escopo_nome": nome_do_escopo(escopo, catalogo) if escopo else None,
                    "data_hora_pretendida": pedido.data_hora_pretendida,
                    # O contexto que faz a decisão ser possível sem sair da
                    # tela: com QUEM está chocando.
                    "conflita_com": conflitante.nome_projeto if conflitante else "outra banca",
                    "justificativa": pedido.justificativa,
                    "solicitado_por": pedido.solicitado_por,
                    "solicitado_por_nome": solicitante.nome if solicitante else None,
                    "criado_em": pedido.criado_em,
                }
            )
        return linhas


def checar_choque(
    db: Session,
    data_hora: datetime,
    *,
    banca_repository,
    ignorar_banca_id: Optional[int] = None,
    projeto_escopo_id: Optional[int] = None,
) -> None:
    """§8: duas bancas no mesmo horário não passam — salvo exceção APROVADA.

    ⭐ **Função de módulo porque são TRÊS as portas que gravam `data_hora`**, e
    a regra vivia só numa delas. Enquanto ela era método de
    `MarcarBancaEscopoUseCase`, `POST /bancas` criava banca em horário ocupado
    sem checagem nenhuma e `PATCH /bancas/{id}` movia uma banca legada para
    cima de outra — a regra era anunciada e contornável por duas rotas
    documentadas. Uma regra de negócio que depende de cada rota lembrar dela
    não é uma regra: é uma convenção.

    ⚠ `projeto_escopo_id` só existe quando a banca está costurada a um escopo
    vendido. Sem ele não há exceção possível (o pedido é do par escopo+horário),
    e o choque bloqueia — conservador de propósito: a banca legada não tem
    projeto de onde derivar quem pediria a exceção.

    ⚠ Limitação conhecida: a comparação é por `data_hora` EXATA. Bancas não têm
    duração gravada, então 14h e 14h30 não são tratadas como conflito.

    `banca_repository` vem de fora em vez de ser construído aqui: os testes do
    repo trocam as classes de repositório no MÓDULO do use case
    (`monkeypatch.setattr(modulo, "BancaRepository", Fake)`), e um import
    direto aqui dentro passaria por baixo do dublê e iria ao banco real.
    """
    for outra in banca_repository.get_por_data_hora(data_hora):
        if outra.id == ignorar_banca_id:
            continue
        # A flag legada continua sendo respeitada para não invalidar as
        # exceções já concedidas no banco; nada novo a escreve.
        if outra.excecao_choque_por is not None:
            continue
        if excecao_liberada(db, projeto_escopo_id, data_hora):
            continue
        raise RegraDeNegocioError(
            f"Já existe uma banca marcada para este horário ({outra.nome_projeto}). "
            "Peça uma exceção de choque à diretoria para marcar mesmo assim"
        )


def excecao_liberada(db: Session, projeto_escopo_id: Optional[int], data_hora: datetime) -> bool:
    """Existe exceção APROVADA para este escopo neste horário?

    Função de módulo porque quem pergunta é `_checar_choque`, dentro de outro
    use case — importar a classe inteira ali só para esta leitura amarraria os
    dois sem necessidade.
    """
    if projeto_escopo_id is None:
        return False
    return BancaExcecaoChoqueRepository(db).get_aprovada(projeto_escopo_id, data_hora) is not None
