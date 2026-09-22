"""⭐ Pedir e decidir a entrada numa banca sem vaga livre pra quem pede (2026-09-18, a pedido).

⚠ **O beco sem saída que isto fecha.** A autoinscrição (`CreateCandidaturaUseCase`)
recusa com `codigo=CODIGO_BANCA_LOTADA` em dois casos: a banca já está no
teto, ou a(s) última(s) vaga(s) está(ão) reservada(s) pro piso por frente que
quem pede não cobre. Até aqui a recusa era o fim da linha — a pessoa via
"banca lotada" e não tinha o que fazer.

Agora, como no pedido de exceção de choque e no de fora da janela: quem quer
entrar pede, com justificativa, e a diretoria decide depois, na aba
Aprovações. **Aprovar CRIA a candidatura** — acima do teto normal, de
propósito: é o próprio ponto do pedido, e a banca fica com mais gente que o
máximo sem problema nenhum.

⚠ **Reusa `CreateCandidaturaUseCase` pra decidir se o pedido É de fato
necessário.** Em vez de duplicar a aritmética de vagas e composição (teto,
piso por frente reservado), o pedido TENTA a autoinscrição normal primeiro:
- deu certo → a pessoa já entrou, sem precisar de aprovação nenhuma (a vaga
  pode ter aberto entre a pessoa ver a tela e clicar);
- recusou com `CODIGO_BANCA_LOTADA` → é o caso certo, o pedido nasce;
- recusou por qualquer OUTRO motivo (já é candidata, é do próprio grupo,
  banca já realizada/cancelada/sem data) → não faz sentido pedir aprovação
  pra algo estruturalmente impossível, e o erro original sobe direto.
"""

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.middlewares.authorization import DIRETORIA_DE_PROJETOS
from src.repositories.banca_entrada_solicitacao_repository import (
    BancaEntradaSolicitacaoRepository,
)
from src.repositories.banca_escopo_repository import BancaEscopoRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.candidatura_repository import CandidaturaRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.candidatura.create_candidatura import (
    CreateCandidaturaRequest,
    CreateCandidaturaUseCase,
)
from src.utils.exceptions import CODIGO_BANCA_LOTADA, RegraDeNegocioError


class SolicitarEntradaBancaRequest(BaseModel):
    banca_id: int
    justificativa: str


class DecidirEntradaBancaRequest(BaseModel):
    aprovar: bool
    #: Obrigatória nos dois sentidos, mesmo padrão dos pedidos vizinhos: uma
    #: recusa sem motivo não ensina o que mudar, uma aprovação sem motivo
    #: apaga por que a diretoria abriu a vaga naquele caso.
    resposta: str


def _projeto_id_da_banca(db: Session, banca_id: int):
    """De qual projeto é esta banca — resolvido pela mesma via de
    `GetBancaDetalhesUseCase` (o primeiro escopo costurado a ela)."""
    escopo_repository = ProjetoEscopoRepository(db)
    ids = BancaEscopoRepository(db).get_escopo_ids(banca_id)
    for escopo_id in ids:
        escopo = escopo_repository.get_by_id(escopo_id)
        if escopo:
            return escopo.projeto_id
    return None


class SolicitarEntradaBancaUseCase:
    """Quem quer entrar pede — a autoinscrição recusou, e é ela quem sabe por quê."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = BancaEntradaSolicitacaoRepository(db)
        self.banca_repository = BancaRepository(db)
        self.usuario_repository = UsuarioRepository(db)

    def execute(self, request: SolicitarEntradaBancaRequest, solicitado_por: int):
        justificativa = (request.justificativa or "").strip()
        if not justificativa:
            raise RegraDeNegocioError("Solicitar entrada exige uma justificativa")

        banca = self.banca_repository.get_by_id(request.banca_id)
        if not banca:
            return None

        # ⭐ Tenta a autoinscrição normal primeiro — ver o docstring do módulo.
        try:
            candidatura = CreateCandidaturaUseCase(self.db).execute(
                CreateCandidaturaRequest(banca_id=request.banca_id),
                usuario_id=solicitado_por,
                eh_gestao=False,
            )
            return {"alocado_direto": True, "candidatura": candidatura}
        except RegraDeNegocioError as e:
            if e.codigo != CODIGO_BANCA_LOTADA:
                # Outro motivo (próprio grupo, já é candidata, banca
                # realizada/cancelada/sem data) — não é isto que este pedido
                # resolve, então a recusa original sobe direto.
                raise

        # Pedir de novo não enfileira duplicata: reescreve o pedido em
        # aberto, mesmo padrão dos pedidos vizinhos.
        pendente = self.repository.get_pendente_do_par(request.banca_id, solicitado_por)
        if pendente:
            atualizado = self.repository.update(pendente.id, justificativa=justificativa)
            return {"alocado_direto": False, "pedido": self._serializar(atualizado)}

        criado = self.repository.create(
            banca_id=request.banca_id,
            usuario_id=solicitado_por,
            justificativa=justificativa,
        )
        self._avisar_diretoria(criado, banca)
        return {"alocado_direto": False, "pedido": self._serializar(criado)}

    def _avisar_diretoria(self, pedido, banca) -> None:
        from src.utils.fuso import para_hora_local
        from src.utils.notificar import notificar

        solicitante = self.usuario_repository.get_by_id(pedido.usuario_id)
        nome = solicitante.nome if solicitante else "Alguém"
        quando = (
            f" em {para_hora_local(banca.data_hora):%d/%m/%Y às %H:%M}" if banca.data_hora else ""
        )
        mensagem = (
            f"{nome} pediu para entrar na banca de {banca.nome_projeto}{quando}, "
            "mesmo sem vaga livre."
        )
        for diretor in self.usuario_repository.get_por_posicoes(*DIRETORIA_DE_PROJETOS):
            notificar(self.db, diretor.id, mensagem, banca_id=pedido.banca_id)

    def _serializar(self, pedido):
        return {
            "id": pedido.id,
            "banca_id": pedido.banca_id,
            "status": pedido.status,
            "justificativa": pedido.justificativa,
        }


class DecidirEntradaBancaUseCase:
    """Só a diretoria decide — a rota cobra com `require_pode_aprovar_pedidos`."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = BancaEntradaSolicitacaoRepository(db)
        self.candidatura_repository = CandidaturaRepository(db)
        self.banca_repository = BancaRepository(db)

    def execute(self, pedido_id: int, request: DecidirEntradaBancaRequest, respondido_por: int):
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

        candidatura_criada = None
        if request.aprovar:
            # ⭐ Acima do teto, de propósito — é o próprio ponto do pedido.
            # Checa se a pessoa não entrou por outra via enquanto o pedido
            # esperava (alguém se desalocou e ela usou "Alocar-se" direto):
            # criar de novo bateria na constraint `uq_candidatura_banca_usuario`.
            ja_candidata = any(
                c.usuario_id == pedido.usuario_id
                for c in self.candidatura_repository.get_by_banca(pedido.banca_id)
            )
            if not ja_candidata:
                candidatura_criada = self.candidatura_repository.create(
                    banca_id=pedido.banca_id,
                    usuario_id=pedido.usuario_id,
                    criado_em=datetime.now(),
                    confirmado=False,
                )

        self._avisar_quem_pediu(atualizado)
        return {
            "id": atualizado.id,
            "status": atualizado.status,
            "resposta": atualizado.resposta,
            "candidatura_criada": candidatura_criada is not None,
        }

    def _avisar_quem_pediu(self, pedido) -> None:
        from src.utils.notificar import notificar

        banca = self.banca_repository.get_by_id(pedido.banca_id)
        nome_projeto = banca.nome_projeto if banca else "uma banca"
        veredito = "aprovado" if pedido.status == "aprovada" else "recusado"
        complemento = (
            " Você já está alocado — confira em Bancas."
            if pedido.status == "aprovada"
            else ""
        )
        mensagem = (
            f"Seu pedido para entrar na banca de {nome_projeto} foi {veredito}: "
            f"{pedido.resposta}.{complemento}"
        )
        notificar(self.db, pedido.usuario_id, mensagem, banca_id=pedido.banca_id)


class ListarEntradaBancaPendentesUseCase:
    """A fila da aba Aprovações, com o contexto que a decisão exige."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = BancaEntradaSolicitacaoRepository(db)
        self.banca_repository = BancaRepository(db)
        self.usuario_repository = UsuarioRepository(db)

    def execute(self):
        from src.repositories.banca_frente_repository import BancaFrenteRepository
        from src.repositories.frente_repository import FrenteRepository
        from src.utils.teto_banca import calcular_vagas_banca

        frente_repository = FrenteRepository(self.db)
        banca_frente_repository = BancaFrenteRepository(self.db)
        candidatura_repository = CandidaturaRepository(self.db)

        linhas = []
        for pedido in self.repository.get_pendentes():
            banca = self.banca_repository.get_by_id(pedido.banca_id)
            if not banca:
                continue
            solicitante = self.usuario_repository.get_by_id(pedido.usuario_id)
            vinculos = banca_frente_repository.get_by_banca(banca.id)
            frentes = [f for f in (frente_repository.get_by_id(v.frente_id) for v in vinculos) if f]
            vagas = calcular_vagas_banca(frentes, self.db)
            alocados = len(candidatura_repository.get_by_banca(banca.id))
            linhas.append(
                {
                    "id": pedido.id,
                    "banca_id": banca.id,
                    "projeto_id": _projeto_id_da_banca(self.db, banca.id),
                    "projeto_nome": banca.nome_projeto,
                    "data_hora": banca.data_hora,
                    "frentes": [f.nome for f in frentes],
                    "vagas": vagas,
                    "alocados": alocados,
                    "justificativa": pedido.justificativa,
                    "usuario_id": pedido.usuario_id,
                    "usuario_nome": solicitante.nome if solicitante else None,
                    "criado_em": pedido.criado_em,
                }
            )
        return linhas


class ListarMinhasEntradaBancaUseCase:
    """⭐ 2026-09-18, a pedido: o que a PRÓPRIA pessoa pediu e ainda espera
    decisão — pra `/bancas` trocar "Solicitar entrada" por "Aguardando
    aprovação" nas bancas que ela já pediu, sem repetir o pedido."""

    def __init__(self, db: Session):
        self.repository = BancaEntradaSolicitacaoRepository(db)

    def execute(self, usuario_id: int) -> list[dict]:
        return [
            {"id": p.id, "banca_id": p.banca_id, "criado_em": p.criado_em}
            for p in self.repository.get_pendentes_do_usuario(usuario_id)
        ]
