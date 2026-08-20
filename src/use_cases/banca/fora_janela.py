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
        self._avisar_quem_pediu(atualizado)
        return {
            "id": atualizado.id,
            "status": atualizado.status,
            "resposta": atualizado.resposta,
        }

    def _avisar_quem_pediu(self, pedido) -> None:
        # ⚠ Aprovado, o pedido não marca a banca sozinho — quem pediu precisa
        # voltar e marcar. Sem o aviso, uma aprovação ficaria parada esperando
        # alguém adivinhar, mesmo motivo do pedido de choque.
        veredito = "aprovada" if pedido.status == "aprovada" else "recusada"
        complemento = (
            " Você já pode marcar a banca nessa data."
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
