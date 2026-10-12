"""Comunicado manual: a diretoria escolhe QUEM recebe e escreve o que quiser.

Tudo que existe de notificacao (sino, e-mail pelo Resend em thread de fundo,
opt-out total, repescagem de e-mail perdido) ja resolvia o "como entregar".
O que faltava era o "pra quem", escolhido por uma pessoa em vez de por um
evento. Entao um comunicado e so mais um tipo de notificacao (`comunicado`),
com a lista de destinatarios resolvida por um segmento:

    zero_bancas .......... quem esta na conta de carga com 0 bancas
    bancas_acima_de ...... quem tem pelo menos N bancas
    pendentes_do_lote .... quem ainda nao respondeu tudo num lote de Desempenho
    inscritos_da_banca ... quem se inscreveu numa banca (ou so quem confirmou)
    por_posicao .......... todo mundo ativo numa ou mais posicoes (base ou cargo extra)
    todos ................ todo mundo ativo
    manual ............... ids escolhidos um a um

Os dois primeiros reusam `GetCargaBancasUseCase` (o mesmo recorte que a
diretoria ve na tabela "Carga de bancas por pessoa"), o terceiro reusa
`GetPendenciasLoteUseCase`. Nada de regra nova de quem-conta-como-o-que: se a
tela diz que a pessoa tem 0 bancas, o comunicado vai pra ela.

A previa (`ResolverDestinatariosUseCase`) e o envio (`EnviarComunicadoUseCase`)
resolvem a lista pelo MESMO caminho, de proposito: o que a diretoria viu na
tela e exatamente o que sai. `excluir_ids` e quem foi desmarcado na previa.

Sem dedup entre envios: cada comunicado ganha um id proprio na chave, entao
mandar o mesmo texto duas vezes manda duas vezes. E manual, a intencao e de
quem clicou. O tipo fica FORA de `TIPOS_NOTIFICACAO_OPCIONAIS`: e pedido
direto de alguem da diretoria, so o desligamento total de e-mail silencia.
"""

from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.repositories.banca_repository import BancaRepository
from src.repositories.candidatura_repository import CandidaturaRepository
from src.repositories.desempenho_lote_repository import DesempenhoLoteRepository
from src.repositories.notificacao_repository import NotificacaoRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.banca.get_carga_bancas import FiltroCargaBancas, GetCargaBancasUseCase
from src.use_cases.desempenho_lote.get_pendencias import GetPendenciasLoteUseCase
from src.use_cases.notificacao.registrar_notificacao import registrar_varios
from src.utils.exceptions import RegraDeNegocioError

SegmentoComunicado = Literal[
    "zero_bancas",
    "bancas_acima_de",
    "pendentes_do_lote",
    "inscritos_da_banca",
    "por_posicao",
    "todos",
    "manual",
]

#: `notificacao.titulo` e String(255); o assunto do e-mail ganha o prefixo
#: "[ATLAS] " por cima, entao sobra folga.
ASSUNTO_MAX = 200
#: `notificacao.corpo` virou TEXT na migration `b8e4c2a6d930`; o teto aqui e
#: so pra ninguem colar um documento inteiro num e-mail.
MENSAGEM_MAX = 4000

TIPO_COMUNICADO = "comunicado"

_ROTULO_FILTRO_BANCAS = {
    "todas": "já atendidas + futuras",
    "realizadas": "só já atendidas",
    "futuras": "só futuras",
}


class FiltroComunicado(BaseModel):
    segmento: SegmentoComunicado
    #: Pros segmentos de carga: o mesmo recorte do select da tabela.
    filtro_bancas: FiltroCargaBancas = "todas"
    #: `bancas_acima_de`: "pelo menos N".
    minimo_bancas: Optional[int] = Field(default=None, ge=1)
    lote_id: Optional[int] = None
    banca_id: Optional[int] = None
    #: `inscritos_da_banca`: so quem confirmou presenca, em vez de todo inscrito.
    so_confirmados: bool = False
    posicoes: list[str] = Field(default_factory=list)
    usuario_ids: list[int] = Field(default_factory=list)
    #: Quem foi desmarcado na previa. Vale pra qualquer segmento.
    excluir_ids: list[int] = Field(default_factory=list)


class ComunicadoRequest(FiltroComunicado):
    assunto: str = Field(min_length=1, max_length=ASSUNTO_MAX)
    mensagem: str = Field(min_length=1, max_length=MENSAGEM_MAX)


class ResolverDestinatariosUseCase:
    """A previa: quem receberia, com um `detalhe` por pessoa quando o
    segmento tem um numero pra mostrar (quantas bancas, quantas pendencias)."""

    def __init__(self, db: Session):
        self.usuario_repository = UsuarioRepository(db)
        self.candidatura_repository = CandidaturaRepository(db)
        self.banca_repository = BancaRepository(db)
        self.lote_repository = DesempenhoLoteRepository(db)
        self.carga_use_case = GetCargaBancasUseCase(db)
        self.pendencias_use_case = GetPendenciasLoteUseCase(db)

    def execute(self, filtro: FiltroComunicado) -> dict:
        rotulo, ids, detalhes = self._resolver(filtro)

        # So ativo recebe, em qualquer segmento: ex-membro e desligado ficam
        # fora mesmo que ainda constem numa candidatura antiga ou num lote.
        ativos = {u.id: u for u in self.usuario_repository.get_ativos() if getattr(u, "ativo", True)}
        excluir = set(filtro.excluir_ids)
        destinatarios = []
        for usuario_id in dict.fromkeys(ids):
            usuario = ativos.get(usuario_id)
            if usuario is None or usuario_id in excluir:
                continue
            destinatarios.append(
                {
                    "usuario_id": usuario.id,
                    "nome": usuario.nome,
                    "posicao": usuario.posicao,
                    "email": usuario.email_insper,
                    "detalhe": detalhes.get(usuario_id),
                }
            )
        destinatarios.sort(key=lambda d: d["nome"])
        return {"rotulo": rotulo, "destinatarios": destinatarios}

    def _resolver(self, filtro: FiltroComunicado) -> tuple[str, list[int], dict[int, str]]:
        segmento = filtro.segmento

        if segmento == "zero_bancas":
            linhas = self.carga_use_case.execute(filtro.filtro_bancas)
            ids = [linha["usuario_id"] for linha in linhas if linha["quantidade_bancas"] == 0]
            return f"Quem está com 0 bancas ({_ROTULO_FILTRO_BANCAS[filtro.filtro_bancas]})", ids, {}

        if segmento == "bancas_acima_de":
            if filtro.minimo_bancas is None:
                raise RegraDeNegocioError("Informe o mínimo de bancas.")
            linhas = self.carga_use_case.execute(filtro.filtro_bancas)
            escolhidas = [linha for linha in linhas if linha["quantidade_bancas"] >= filtro.minimo_bancas]
            detalhes = {linha["usuario_id"]: _plural(linha["quantidade_bancas"], "banca") for linha in escolhidas}
            return (
                f"Quem tem {filtro.minimo_bancas} ou mais bancas ({_ROTULO_FILTRO_BANCAS[filtro.filtro_bancas]})",
                [linha["usuario_id"] for linha in escolhidas],
                detalhes,
            )

        if segmento == "pendentes_do_lote":
            if filtro.lote_id is None:
                raise RegraDeNegocioError("Informe o lote de avaliação.")
            lote = self.lote_repository.get_by_id(filtro.lote_id)
            pendencias = self.pendencias_use_case.execute(filtro.lote_id)
            if lote is None or pendencias is None:
                raise RegraDeNegocioError("Lote de avaliação não encontrado.")
            contagem: dict[int, int] = {}
            for p in pendencias:
                if not p["respondida"]:
                    contagem[p["avaliador_id"]] = contagem.get(p["avaliador_id"], 0) + 1
            detalhes = {uid: _plural(n, "pendência") for uid, n in contagem.items()}
            return f'Quem ainda não respondeu "{lote.nome}"', list(contagem), detalhes

        if segmento == "inscritos_da_banca":
            if filtro.banca_id is None:
                raise RegraDeNegocioError("Informe a banca.")
            banca = self.banca_repository.get_by_id(filtro.banca_id)
            if banca is None:
                raise RegraDeNegocioError("Banca não encontrada.")
            candidaturas = self.candidatura_repository.get_by_banca(filtro.banca_id)
            if filtro.so_confirmados:
                candidaturas = [c for c in candidaturas if c.confirmado]
            quem = "Quem confirmou presença" if filtro.so_confirmados else "Inscritos"
            return f"{quem} na banca de {banca.nome_projeto}", [c.usuario_id for c in candidaturas], {}

        if segmento == "por_posicao":
            if not filtro.posicoes:
                raise RegraDeNegocioError("Escolha pelo menos uma posição.")
            pessoas = self.usuario_repository.get_ativos_por_posicoes_ou_cargo_extra(filtro.posicoes)
            return f"Posições: {', '.join(filtro.posicoes)}", [u.id for u in pessoas], {}

        if segmento == "todos":
            return "Todo mundo ativo", [u.id for u in self.usuario_repository.get_ativos()], {}

        if segmento == "manual":
            if not filtro.usuario_ids:
                raise RegraDeNegocioError("Escolha pelo menos uma pessoa.")
            return "Pessoas escolhidas à mão", list(filtro.usuario_ids), {}

        raise RegraDeNegocioError("Segmento desconhecido.")


class EnviarComunicadoUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.resolver = ResolverDestinatariosUseCase(db)

    def execute(self, request: ComunicadoRequest, remetente) -> dict:
        assunto = request.assunto.strip()
        mensagem = request.mensagem.strip()
        if not assunto or not mensagem:
            raise RegraDeNegocioError("Assunto e mensagem são obrigatórios.")

        resolvido = self.resolver.execute(request)
        ids = [d["usuario_id"] for d in resolvido["destinatarios"]]
        if not ids:
            raise RegraDeNegocioError("Nenhum destinatário neste recorte.")

        # Id proprio por disparo: e o que faz dois envios iguais virarem duas
        # notificacoes (e dois e-mails), e o que agrupa as linhas de um mesmo
        # comunicado no banco (`payload.comunicado_id`).
        comunicado_id = uuid4().hex[:12]
        corpo = f"{mensagem}\n\nEnviado por {remetente.nome}."
        registrar_varios(
            self.db,
            ids,
            tipo=TIPO_COMUNICADO,
            titulo=assunto,
            corpo=corpo,
            rota="/notificacoes",
            payload={
                "comunicado_id": comunicado_id,
                "remetente_id": remetente.id,
                "remetente_nome": remetente.nome,
                "segmento": request.segmento,
                "rotulo": resolvido["rotulo"],
            },
            chave_dedup=f"comunicado:{comunicado_id}",
        )
        return {"comunicado_id": comunicado_id, "enviados": len(ids), "rotulo": resolvido["rotulo"]}


class ListarComunicadosUseCase:
    """O histórico da aba Comunicados: um item por disparo, montado das
    próprias notificações (cada destinatário é uma linha com o mesmo
    `payload.comunicado_id`). Não precisa de tabela própria."""

    LIMITE = 100

    def __init__(self, db: Session):
        self.notificacao_repository = NotificacaoRepository(db)
        self.usuario_repository = UsuarioRepository(db)

    def execute(self) -> list[dict]:
        por_id: dict[str, dict] = {}
        for linha in self.notificacao_repository.get_por_tipo(TIPO_COMUNICADO):
            payload = linha.payload or {}
            cid = payload.get("comunicado_id")
            if not cid:
                continue
            item = por_id.get(cid)
            if item is None:
                item = por_id[cid] = {
                    "comunicado_id": cid,
                    "assunto": linha.titulo,
                    "mensagem": linha.corpo,
                    "remetente_id": payload.get("remetente_id"),
                    "remetente_nome": payload.get("remetente_nome"),
                    "rotulo": payload.get("rotulo"),
                    "enviado_em": linha.criado_em,
                    "destinatarios": [],
                    "emails_enviados": 0,
                    "lidas": 0,
                }
            item["destinatarios"].append(linha.usuario_id)
            item["emails_enviados"] += 1 if linha.email_enviado_em else 0
            item["lidas"] += 1 if linha.lida_em else 0
            # A mais antiga do grupo é o instante do disparo.
            if linha.criado_em and (item["enviado_em"] is None or linha.criado_em < item["enviado_em"]):
                item["enviado_em"] = linha.criado_em

        nomes = {u.id: u.nome for u in self.usuario_repository.get_all()}
        itens = sorted(por_id.values(), key=lambda i: i["enviado_em"] or 0, reverse=True)[: self.LIMITE]
        for item in itens:
            ids = item.pop("destinatarios")
            item["total"] = len(ids)
            item["destinatarios"] = sorted(nomes.get(i, f"Usuário {i}") for i in ids)
            if not item["remetente_nome"] and item["remetente_id"]:
                item["remetente_nome"] = nomes.get(item["remetente_id"])
        return itens


def _plural(n: int, singular: str) -> str:
    return f"{n} {singular}" if n == 1 else f"{n} {singular}s"
