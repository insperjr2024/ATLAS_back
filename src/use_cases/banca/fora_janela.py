"""⭐ Pedir e decidir a autorização para marcar banca fora da janela do
escopo (§13).

⚠ **O atalho que isto fecha.** Marcar banca fora da janela do escopo era
decisão da diretoria, mas na prática era um ato só: só quem tinha
`posicao == "diretor"` conseguia marcar, e marcava sozinho, na mesma
chamada que gravava a data — pedido e decisão eram a mesma pessoa no
mesmo clique, sem outro ator envolvido.

Agora são dois atos separados, como no pedido de exceção de choque (§8) e
no pedido de dias de ajuste (§8): **quem marca pede**, com justificativa,
**a diretoria decide** depois, na aba Aprovações.

⭐ **Aprovar MARCA a banca**, não apenas libera. Antes a aprovação só abria a
porta e quem pediu tinha de voltar ao cronograma e repetir o gesto — e enquanto
não voltasse, a autorização ficava parada valendo para uma data que se
aproximava sozinha. Duas coisas davam errado nesse vão: o pedido aprovado
vencia sem nunca virar banca, e a data pretendida podia ser ocupada por outra
banca no meio do caminho. Como o pedido já carrega tudo o que a marcação
precisa (escopo, data/hora e justificativa), não havia o que esperar da pessoa.

⚠ **Se a marcação falhar, o pedido VOLTA a pendente.** Um choque de horário que
nasceu depois do pedido, ou a banca tendo acontecido no meio tempo, derruba a
marcação — e carimbar "aprovada" mesmo assim daria uma autorização que não
produziu banca nenhuma e sumiria da fila sem ninguém notar.

⚠ **Não mexe em `dias_uteis_ajustados`.** Isso é o pedido de dias de ajuste
(`cronograma_reajuste_solicitacao`), que só cabe nos 3 primeiros dias úteis
da janela (§8) — praticamente nunca o caso de uma banca que precisa de data
fora dela, que costuma surgir bem depois disso. Este pedido autoriza só
UMA marcação (este escopo, esta data); a janela do escopo não muda, e os
dias além dela continuam contando como atraso do projeto mesmo aprovado.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.banca_fora_janela_repository import BancaForaJanelaRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.dia_nao_letivo_repository import DiaNaoLetivoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.projeto_status_historico_repository import (
    ProjetoStatusHistoricoRepository,
)
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.contagem_dias import derivar_janelas_pausa
from src.utils.exceptions import RegraDeNegocioError
from src.utils.janela_escopo import calcular_janela, dentro_da_janela
from src.utils.notificar import notificar
from src.middlewares.authorization import DIRETORIA, DIRETORIA_DE_PESSOAS, DIRETORIA_DE_PROJETOS


class SolicitarForaJanelaRequest(BaseModel):
    projeto_escopo_id: int
    data_hora_pretendida: datetime
    justificativa: str


class DecidirForaJanelaRequest(BaseModel):
    aprovar: bool
    #: Obrigatória nos dois sentidos, mesmo padrão do pedido de choque: uma
    #: recusa sem motivo não ensina o que mudar, uma aprovação sem motivo
    #: apaga por que o §13 foi aberto naquele caso.
    resposta: str


def _janela_do_escopo(db: Session, escopo):
    """Mesmo cálculo de `MarcarBancaEscopoUseCase._janela_do_escopo` — duas
    cópias porque importar a classe inteira aqui só por este método criaria
    um acoplamento maior do que o ganho de não repetir 8 linhas."""
    dias_nao_letivos = [d.data for d in DiaNaoLetivoRepository(db).get_all()]
    janelas_pausa = derivar_janelas_pausa(
        ProjetoStatusHistoricoRepository(db).get_by_projeto(escopo.projeto_id)
    )
    return calcular_janela(
        escopo.data_inicio,
        escopo.dias_uteis_vendidos,
        escopo.dias_uteis_ajustados,
        dias_nao_letivos,
        janelas_pausa=janelas_pausa,
    )


class SolicitarForaJanelaUseCase:
    """Quem quer marcar a banca pede a autorização — não a diretoria por ele."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = BancaForaJanelaRepository(db)
        self.banca_repository = BancaRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.projeto_repository = ProjetoRepository(db)
        self.usuario_repository = UsuarioRepository(db)

    def execute(self, request: SolicitarForaJanelaRequest, solicitado_por: int):
        justificativa = (request.justificativa or "").strip()
        if not justificativa:
            raise RegraDeNegocioError("Marcar fora da janela exige uma justificativa")

        escopo = self.escopo_repository.get_by_id(request.projeto_escopo_id)
        if not escopo:
            return None

        # ⚠ Só faz sentido pedir se a data REALMENTE cai fora da janela. Sem
        # esta checagem a fila da diretoria encheria de pedidos para datas
        # que já cabiam — cada um seria uma decisão sobre nada.
        janela = _janela_do_escopo(self.db, escopo)
        if dentro_da_janela(request.data_hora_pretendida, janela):
            raise RegraDeNegocioError(
                "Esta data está dentro da janela do escopo — a autorização não é necessária"
            )

        if self.repository.get_aprovada(escopo.id, request.data_hora_pretendida):
            raise RegraDeNegocioError(
                "Esta data já foi autorizada para este escopo — basta marcar a banca"
            )

        # Pedir de novo não enfileira duplicata: reescreve o pedido em aberto,
        # mesmo padrão do pedido de exceção de choque.
        pendente = self.repository.get_pendente_do_par(escopo.id, request.data_hora_pretendida)
        if pendente:
            atualizado = self.repository.update(pendente.id, justificativa=justificativa)
            return self._serializar(atualizado)

        banca_do_escopo = self.banca_repository.get_by_projeto_escopo(escopo.id)
        criado = self.repository.create(
            projeto_escopo_id=escopo.id,
            banca_id=banca_do_escopo.id if banca_do_escopo else None,
            data_hora_pretendida=request.data_hora_pretendida,
            justificativa=justificativa,
            solicitado_por=solicitado_por,
        )
        self._avisar_diretoria(criado, escopo)
        return self._serializar(criado)

    def _avisar_diretoria(self, pedido, escopo) -> None:
        projeto = self.projeto_repository.get_by_id(escopo.projeto_id)
        nome = projeto.nome if projeto else "um projeto"
        mensagem = (
            f"{nome} pediu autorização para marcar banca fora da janela, em "
            f"{pedido.data_hora_pretendida:%d/%m/%Y às %H:%M}."
        )
        for diretor in self.usuario_repository.get_por_posicoes(*DIRETORIA_DE_PROJETOS):
            notificar(self.db, diretor.id, mensagem, banca_id=pedido.banca_id)

    def _serializar(self, pedido):
        return {
            "id": pedido.id,
            "projeto_escopo_id": pedido.projeto_escopo_id,
            "data_hora_pretendida": pedido.data_hora_pretendida,
            "status": pedido.status,
            "justificativa": pedido.justificativa,
        }


class DecidirForaJanelaUseCase:
    """Só a diretoria decide (§13) — a rota cobra com `require_diretor_projetos`."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = BancaForaJanelaRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.projeto_repository = ProjetoRepository(db)

    def execute(self, pedido_id: int, request: DecidirForaJanelaRequest, respondido_por: int):
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

        # ⚠ **A ordem importa e não é livre.** `_exigir_janela` da marcação
        # pergunta a `fora_janela_liberada` se existe autorização APROVADA para
        # este par (escopo, data) — então o status precisa já estar gravado
        # quando a marcação roda. Marcar antes de aprovar cairia na própria
        # trava que este pedido existe para destravar.
        banca = None
        if request.aprovar:
            try:
                banca = self._marcar_a_banca(atualizado, respondido_por)
            except RegraDeNegocioError:
                # Volta para a fila em vez de ficar aprovado sem banca —
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
            # A tela da diretora confirma o que a decisão produziu — aprovar
            # sem dizer que a banca foi marcada parece não ter feito nada.
            "banca_marcada_em": banca.get("data_hora") if banca else None,
            "banca_id": banca.get("id") if banca else None,
        }

    def _marcar_a_banca(self, pedido, respondido_por: int) -> dict:
        """Grava a banca na data autorizada, no MESMO caminho que o cronograma
        usa (`MarcarBancaEscopoUseCase`).

        📐 Reusar o use case inteiro, e não escrever em `banca` direto, é o que
        mantém a marcação completa: choque de horário, vínculos de escopo,
        frentes, sessão da banca, histórico de remarcação e o aviso a quem foi
        escalado. Uma gravação "simples" aqui pularia os seis.

        ⚠ **`escopo_ids` vai `None` de propósito**: significa "não mexer nos
        vínculos atuais". O pedido guarda um escopo só, e forçar a lista faria
        a aprovação DESVINCULAR os outros escopos que a banca já cobrisse.
        """
        # Import local: `marcar_banca_escopo` importa `fora_janela_liberada`
        # deste módulo. No topo, os dois se fechariam num ciclo.
        from src.use_cases.banca.marcar_banca_escopo import (
            MarcarBancaEscopoRequest,
            MarcarBancaEscopoUseCase,
        )

        resultado = MarcarBancaEscopoUseCase(self.db).execute(
            pedido.projeto_escopo_id,
            MarcarBancaEscopoRequest(
                data_hora=pedido.data_hora_pretendida,
                # A mesma justificativa do pedido: é o texto que o §13 quer no
                # histórico, e cobrar outro da diretora seria pedir que ela
                # reescrevesse o motivo de quem pediu.
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
        # ⭐ Amarra o pedido à banca que ele produziu. Nascendo antes da banca,
        # `banca_id` costuma ser nulo; sem isto o vínculo nunca se fecharia.
        if resultado.get("id") and not pedido.banca_id:
            self.repository.update(pedido.id, banca_id=resultado["id"])
        return resultado

    def _avisar_quem_pediu(self, pedido, banca=None) -> None:
        # ⚠ O aviso mudou junto com a decisão. Enquanto aprovar só liberava, ele
        # dizia "você já pode marcar a banca nessa data" — e era essa frase que
        # segurava o fluxo, porque a marcação dependia de alguém voltar. Agora a
        # aprovação já marca, e repetir a frase antiga faria a pessoa voltar ao
        # cronograma para refazer um gesto que produziria um "nada mudou".
        veredito = "aprovada" if pedido.status == "aprovada" else "recusada"
        complemento = (
            " A banca já foi marcada nesta data — confira no cronograma do projeto."
            if pedido.status == "aprovada"
            else ""
        )
        mensagem = (
            f"Seu pedido para marcar banca fora da janela em "
            f"{pedido.data_hora_pretendida:%d/%m/%Y às %H:%M} foi {veredito}: "
            f"{pedido.resposta}.{complemento}"
        )
        notificar(self.db, pedido.solicitado_por, mensagem, banca_id=pedido.banca_id)


class ListarForaJanelaPendentesUseCase:
    """A fila da aba Aprovações, com o contexto que a decisão exige."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = BancaForaJanelaRepository(db)
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
            projeto = self.projeto_repository.get_by_id(escopo.projeto_id) if escopo else None
            solicitante = self.usuario_repository.get_by_id(pedido.solicitado_por)
            janela = _janela_do_escopo(self.db, escopo) if escopo else None
            linhas.append(
                {
                    "id": pedido.id,
                    "projeto_id": projeto.id if projeto else None,
                    "projeto_nome": projeto.nome if projeto else "—",
                    "projeto_escopo_id": pedido.projeto_escopo_id,
                    "escopo_nome": nome_do_escopo(escopo, catalogo) if escopo else None,
                    "data_hora_pretendida": pedido.data_hora_pretendida,
                    # O contexto que faz a decisão ser possível sem sair da
                    # tela: até quando ia a janela, e quanto ela ultrapassa.
                    "fim_janela": janela.fim if janela else None,
                    "justificativa": pedido.justificativa,
                    "solicitado_por": pedido.solicitado_por,
                    "solicitado_por_nome": solicitante.nome if solicitante else None,
                    "criado_em": pedido.criado_em,
                }
            )
        return linhas


def fora_janela_liberada(db: Session, projeto_escopo_id: Optional[int], data_hora: datetime) -> bool:
    """Existe autorização APROVADA para este escopo, nesta data?

    Função de módulo pelo mesmo motivo de `excecao_choque.excecao_liberada`:
    quem pergunta é `MarcarBancaEscopoUseCase._exigir_janela`, dentro de
    outro use case — importar a classe inteira ali só para esta leitura
    amarraria os dois sem necessidade.
    """
    if projeto_escopo_id is None:
        return False
    return BancaForaJanelaRepository(db).get_aprovada(projeto_escopo_id, data_hora) is not None
