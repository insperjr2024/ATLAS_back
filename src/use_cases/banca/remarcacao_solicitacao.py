"""⭐ Pedir e decidir a remarcação de uma banca que já tem data (§13, 2026-09-10).

⚠ **O atalho que isto fecha.** Remarcar uma banca dentro da janela e com folga
era LIVRE para quem edita o projeto: bastava justificativa e a data trocava na
hora. Virou rotina silenciosa — o coordenador do ENSINO remarcou a banca e
ninguém da diretoria aprovou nada.

Agora são dois atos separados, como no pedido de banca fora da janela
(`fora_janela`) e no de exceção de choque (`excecao_choque`): **quem conduz o
projeto pede**, com justificativa; **a diretoria decide** depois, na aba
Aprovações.

⭐ **Aprovar REMARCA a banca**, não só libera. O pedido já carrega escopo,
data/hora e justificativa — tudo o que `MarcarBancaEscopoUseCase` precisa —,
então a aprovação chama a marcação no MESMO caminho do cronograma, com
`eh_diretor_projetos=True`. Reusar o use case inteiro é o que mantém a
marcação completa: choque de horário, vínculos de escopo, frentes, sessão da
banca, histórico de remarcação e o aviso a quem foi escalado.

⚠ **Se a marcação falhar, o pedido VOLTA a pendente** — um choque que nasceu
depois, ou a banca tendo acontecido no meio tempo. Carimbar "aprovada" mesmo
assim daria uma autorização que não produziu remarcação nenhuma.

⚠ **Isto NÃO substitui o pedido de fora da janela.** Se a data nova também cai
fora da janela do escopo, a marcação (lá dentro) ainda exige a autorização de
fora da janela como sempre — são duas decisões: "o adiamento pode?" (aqui) e
"a janela pode ser furada?" (`fora_janela`).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.middlewares.authorization import DIRETORIA_DE_PROJETOS
from src.repositories.banca_remarcacao_solicitacao_repository import (
    BancaRemarcacaoSolicitacaoRepository,
)
from src.repositories.banca_repository import BancaRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.banca.excecao_choque import liberar_choque
from src.utils.exceptions import RegraDeNegocioError
from src.utils.fuso import normalizar_utc, para_hora_local
from src.utils.notificar import notificar


class SolicitarRemarcacaoRequest(BaseModel):
    projeto_escopo_id: int
    data_hora_pretendida: datetime
    justificativa: str


class DecidirRemarcacaoRequest(BaseModel):
    aprovar: bool
    #: Obrigatória nos dois sentidos, mesmo padrão dos outros pedidos: uma
    #: recusa sem motivo não ensina o que mudar, uma aprovação sem motivo apaga
    #: por que a remarcação foi aceita.
    resposta: str
    #: ⭐ Autorizar TAMBÉM o choque de horário (§8), quando a data pedida
    #: esbarra na banca de outro projeto. Nasce `False`; a tela o liga num
    #: segundo clique, depois de a recusa dizer com qual banca conflita.
    autorizar_choque: bool = False


class SolicitarRemarcacaoUseCase:
    """Quem conduz o projeto pede a remarcação — não a diretoria por ele."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = BancaRemarcacaoSolicitacaoRepository(db)
        self.banca_repository = BancaRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.projeto_repository = ProjetoRepository(db)
        self.usuario_repository = UsuarioRepository(db)

    def execute(self, request: SolicitarRemarcacaoRequest, solicitado_por: int):
        justificativa = (request.justificativa or "").strip()
        if not justificativa:
            raise RegraDeNegocioError("Remarcar uma banca exige justificativa")

        escopo = self.escopo_repository.get_by_id(request.projeto_escopo_id)
        if not escopo:
            return None

        banca = self.banca_repository.get_by_projeto_escopo(escopo.id)
        if not banca or not banca.data_hora:
            raise RegraDeNegocioError(
                "Este escopo ainda não tem banca marcada — não há o que remarcar."
            )
        if getattr(banca, "cancelada_em", None) is not None:
            raise RegraDeNegocioError("Esta banca foi cancelada.")
        if banca.realizado_em is not None:
            raise RegraDeNegocioError(
                "Esta banca já aconteceu — marcar outra data é uma segunda "
                "banca, não uma remarcação."
            )

        pretendida = normalizar_utc(request.data_hora_pretendida)
        if pretendida == banca.data_hora:
            raise RegraDeNegocioError(
                "A data pedida é a mesma que já está marcada."
            )

        # Pedir de novo não enfileira duplicata: reescreve o pedido em aberto,
        # mesmo padrão de `SolicitarForaJanelaUseCase`.
        pendente = self.repository.get_pendente_da_banca(banca.id)
        if pendente:
            atualizado = self.repository.update(
                pendente.id,
                projeto_escopo_id=escopo.id,
                data_hora_anterior=banca.data_hora,
                data_hora_pretendida=pretendida,
                justificativa=justificativa,
            )
            return self._serializar(atualizado)

        criado = self.repository.create(
            banca_id=banca.id,
            projeto_escopo_id=escopo.id,
            data_hora_anterior=banca.data_hora,
            data_hora_pretendida=pretendida,
            justificativa=justificativa,
            solicitado_por=solicitado_por,
        )
        self._avisar_diretoria(criado, escopo)
        return self._serializar(criado)

    def _avisar_diretoria(self, pedido, escopo) -> None:
        projeto = self.projeto_repository.get_by_id(escopo.projeto_id)
        nome = projeto.nome if projeto else "um projeto"
        # As duas datas são UTC (`banca.data_hora` / `normalizar_utc`) —
        # `para_hora_local` pro aviso não sair 3h adiantado.
        mensagem = (
            f"{nome} pediu para remarcar a banca de "
            f"{para_hora_local(pedido.data_hora_anterior):%d/%m/%Y às %H:%M} para "
            f"{para_hora_local(pedido.data_hora_pretendida):%d/%m/%Y às %H:%M}."
        )
        for diretor in self.usuario_repository.get_por_posicoes(*DIRETORIA_DE_PROJETOS):
            notificar(self.db, diretor.id, mensagem, banca_id=pedido.banca_id)

    def _serializar(self, pedido):
        return {
            "id": pedido.id,
            "banca_id": pedido.banca_id,
            "projeto_escopo_id": pedido.projeto_escopo_id,
            "data_hora_anterior": pedido.data_hora_anterior,
            "data_hora_pretendida": pedido.data_hora_pretendida,
            "status": pedido.status,
            "justificativa": pedido.justificativa,
        }


class DecidirRemarcacaoUseCase:
    """Só a diretoria decide (§13) — a rota cobra com `require_pode_aprovar_pedidos`."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = BancaRemarcacaoSolicitacaoRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)

    def execute(
        self, pedido_id: int, request: DecidirRemarcacaoRequest, respondido_por: int
    ):
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

        banca = None
        if request.aprovar:
            try:
                banca = self._remarcar_a_banca(
                    atualizado, respondido_por, autorizar_choque=request.autorizar_choque
                )
            except RegraDeNegocioError:
                # Volta para a fila em vez de ficar aprovado sem remarcação —
                # ver a docstring do módulo.
                self.repository.update(
                    pedido_id,
                    status="pendente",
                    resposta=None,
                    respondido_por=None,
                    respondido_em=None,
                )
                raise

        self._avisar_quem_pediu(atualizado, banca)
        return {
            "id": atualizado.id,
            "status": atualizado.status,
            "resposta": atualizado.resposta,
            "banca_id": atualizado.banca_id,
            "banca_marcada_em": banca.get("data_hora") if banca else None,
        }

    def _remarcar_a_banca(
        self, pedido, respondido_por: int, *, autorizar_choque: bool = False
    ) -> dict:
        """Grava a data nova no MESMO caminho do cronograma (`MarcarBancaEscopoUseCase`).

        📐 Reusar o use case inteiro, e não escrever em `banca` direto, é o que
        mantém a remarcação completa: choque de horário, vínculos de escopo,
        frentes, sessão da banca, `banca_remarcacao` e o aviso a quem foi
        escalado (`notificar_banca_remarcada`).

        ⚠ **`escopo_ids` vai `None` de propósito**: "não mexer nos vínculos
        atuais". O pedido guarda um escopo só, e forçar a lista faria a
        aprovação DESVINCULAR os outros escopos que a banca já cobrisse.
        """
        # Import local: `marcar_banca_escopo` importa deste pacote em cadeia; no
        # topo os dois se fechariam num ciclo (mesmo motivo de `fora_janela`).
        from src.use_cases.banca.marcar_banca_escopo import (
            MarcarBancaEscopoRequest,
            MarcarBancaEscopoUseCase,
        )

        if autorizar_choque:
            liberar_choque(
                self.db,
                projeto_escopo_id=pedido.projeto_escopo_id,
                data_hora=pedido.data_hora_pretendida,
                solicitado_por=pedido.solicitado_por,
                respondido_por=respondido_por,
                justificativa=pedido.justificativa,
                resposta=pedido.resposta,
            )

        resultado = MarcarBancaEscopoUseCase(self.db).execute(
            pedido.projeto_escopo_id,
            MarcarBancaEscopoRequest(
                data_hora=pedido.data_hora_pretendida,
                justificativa=pedido.justificativa,
                escopo_ids=None,
            ),
            eh_diretor_projetos=True,
            registrado_por=respondido_por,
        )
        if not resultado:
            raise RegraDeNegocioError(
                "O escopo deste pedido não existe mais — recuse o pedido para "
                "tirá-lo da fila."
            )
        return resultado

    def _avisar_quem_pediu(self, pedido, banca=None) -> None:
        veredito = "aprovada" if pedido.status == "aprovada" else "recusada"
        complemento = (
            " A banca já foi remarcada nesta data — confira no cronograma do projeto."
            if pedido.status == "aprovada"
            else ""
        )
        mensagem = (
            f"Seu pedido para remarcar a banca para "
            f"{para_hora_local(pedido.data_hora_pretendida):%d/%m/%Y às %H:%M} foi "
            f"{veredito}: {pedido.resposta}.{complemento}"
        )
        notificar(self.db, pedido.solicitado_por, mensagem, banca_id=pedido.banca_id)


class ListarRemarcacoesPendentesUseCase:
    """A fila da aba Aprovações, com o contexto que a decisão exige."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = BancaRemarcacaoSolicitacaoRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.projeto_repository = ProjetoRepository(db)
        self.usuario_repository = UsuarioRepository(db)

    def execute(self):
        from src.repositories.escopo_repository import EscopoRepository
        from src.use_cases.projeto_escopo.get_escopos_projeto import nome_do_escopo

        catalogo = {e.id: e for e in EscopoRepository(self.db).get_all()}

        linhas = []
        for pedido in self.repository.get_pendentes():
            escopo = self.escopo_repository.get_by_id(pedido.projeto_escopo_id)
            projeto = (
                self.projeto_repository.get_by_id(escopo.projeto_id) if escopo else None
            )
            solicitante = self.usuario_repository.get_by_id(pedido.solicitado_por)
            linhas.append(
                {
                    "id": pedido.id,
                    "banca_id": pedido.banca_id,
                    "projeto_id": projeto.id if projeto else None,
                    "projeto_nome": projeto.nome if projeto else "—",
                    "projeto_escopo_id": pedido.projeto_escopo_id,
                    "escopo_nome": nome_do_escopo(escopo, catalogo) if escopo else None,
                    "data_hora_anterior": pedido.data_hora_anterior,
                    "data_hora_pretendida": pedido.data_hora_pretendida,
                    "justificativa": pedido.justificativa,
                    "solicitado_por": pedido.solicitado_por,
                    "solicitado_por_nome": solicitante.nome if solicitante else None,
                    "criado_em": pedido.criado_em,
                }
            )
        return linhas
