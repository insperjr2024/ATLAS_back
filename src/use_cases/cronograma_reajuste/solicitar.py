"""⭐ O pedido de **dias de ajuste** (§8) — o único fluxo de aprovação que
sobrou no cronograma.

Antes este arquivo pedia a reabertura de um cronograma oficializado. A
oficialização acabou; o que restou é a decisão que de fato precisa de
diretoria: *este escopo ganha mais dias?*

Quatro regras, e todas as quatro estão aqui e não no router, porque juntas
formam UMA regra de negócio ("o pedido é válido?") e espalhá-las faria a rota
responder 403 num caso e 422 no outro para o mesmo problema:

1. **Só o coordenador pede** — o papel NO PROJETO, não a posição na plataforma.
2. **Só nos 3 primeiros dias úteis da janela**, e vale a data do PEDIDO (§20.1).
3. **Quantos pedidos precisar** dentro do prazo — o total é a soma dos
   aprovados (+5 e depois +5 = 10 dias ajustados).
4. **Um pendente por vez**, senão a diretora responderia dois pedidos que se
   somam sem ver o efeito combinado.
"""

from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.cronograma_reajuste_repository import CronogramaReajusteRepository
from src.repositories.dia_nao_letivo_repository import DiaNaoLetivoRepository
from src.repositories.escopo_repository import EscopoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.notificacao.eventos import notificar_reajuste_solicitado
from src.utils.exceptions import RegraDeNegocioError
from src.utils.janela_escopo import PRAZO_PEDIDO_AJUSTE_DIAS_UTEIS, calcular_janela

#: Teto por pedido. Não é regra do briefing — é uma trava contra o dedo
#: escorregando no teclado ("+300 dias"), que a diretora aprovaria sem
#: perceber e que ninguém teria como desfazer depois.
MAXIMO_DIAS_POR_PEDIDO = 90


class SolicitarReajusteRequest(BaseModel):
    #: Quantos dias úteis extras. Aprovar SOMA isto em `dias_uteis_ajustados`.
    dias_solicitados: int
    motivo: str


def serializar_solicitacao(s) -> dict:
    return {
        "id": s.id,
        "projeto_escopo_id": s.projeto_escopo_id,
        "solicitado_por": s.solicitado_por,
        "dias_solicitados": s.dias_solicitados,
        "motivo": s.motivo,
        "status": s.status,
        "respondido_por": s.respondido_por,
        "resposta_justificativa": s.resposta_justificativa,
        "criado_em": s.criado_em,
        "respondido_em": s.respondido_em,
    }


def nome_do_escopo(escopo, catalogo_repository: EscopoRepository) -> str:
    if escopo.nome_customizado:
        return escopo.nome_customizado
    do_catalogo = catalogo_repository.get_by_id(escopo.escopo_id) if escopo.escopo_id else None
    return do_catalogo.nome if do_catalogo else f"escopo {escopo.id}"


class SolicitarReajusteUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = CronogramaReajusteRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.catalogo_repository = EscopoRepository(db)
        self.usuario_repository = UsuarioRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)
        self.dia_nao_letivo_repository = DiaNaoLetivoRepository(db)

    def execute(
        self, projeto_escopo_id: int, request: SolicitarReajusteRequest, current_user
    ) -> dict:
        escopo = self.escopo_repository.get_by_id(projeto_escopo_id)
        if not escopo:
            raise RegraDeNegocioError("Escopo não encontrado")

        self._exigir_coordenador(escopo, current_user)
        self._exigir_prazo_aberto(escopo)

        if request.dias_solicitados < 1:
            raise RegraDeNegocioError("Peça pelo menos 1 dia de ajuste")
        if request.dias_solicitados > MAXIMO_DIAS_POR_PEDIDO:
            raise RegraDeNegocioError(
                f"Um pedido de ajuste vai até {MAXIMO_DIAS_POR_PEDIDO} dias úteis. "
                "Para mais que isso, fale com a diretoria."
            )
        if not (request.motivo or "").strip():
            raise RegraDeNegocioError("Descreva por que os dias vendidos não dão conta")
        if self.repository.get_pendente_do_escopo(projeto_escopo_id):
            raise RegraDeNegocioError(
                "Já existe um pedido de dias pendente para este escopo — "
                "espere a resposta da diretoria antes de pedir de novo"
            )

        solicitacao = self.repository.create(
            projeto_escopo_id=projeto_escopo_id,
            solicitado_por=current_user.id,
            dias_solicitados=request.dias_solicitados,
            motivo=request.motivo.strip(),
        )

        nome_escopo = nome_do_escopo(escopo, self.catalogo_repository)
        for diretor in self.usuario_repository.get_por_posicao("diretor"):
            notificar_reajuste_solicitado(
                self.db, diretor.id, escopo.projeto_id, escopo.id, nome_escopo, current_user.nome
            )

        return serializar_solicitacao(solicitacao)

    def _exigir_coordenador(self, escopo, current_user) -> None:
        """§8: só o coordenador pede — e é o papel NO PROJETO que vale.

        Diretor e gerente não pedem porque não é deles a informação: quem sabe
        que os dias não dão conta é quem está conduzindo o escopo. O diretor,
        aliás, não precisaria pedir — ele decide.
        """
        eh_coordenador = any(
            m.usuario_id == current_user.id and m.papel == "coordenador"
            for m in self.membro_repository.get_by_projeto(escopo.projeto_id, apenas_atuais=True)
        )
        if not eh_coordenador:
            raise RegraDeNegocioError(
                "Só o coordenador do projeto pede dias de ajuste (§8)"
            )

    def _exigir_prazo_aberto(self, escopo) -> None:
        """Os 3 dias úteis do §8, contando a reunião inicial como dia 1.

        Escopo sem reunião inicial não tem janela e portanto não tem prazo
        correndo — pedir dias antes de começar não faz sentido, o próprio
        início ainda pode mudar.
        """
        janela = self._janela(escopo)

        if not janela.aberta:
            raise RegraDeNegocioError(
                "Este escopo ainda não teve reunião inicial — a janela dele nem começou"
            )
        if not janela.pedido_ajuste_aberto:
            raise RegraDeNegocioError(
                f"O prazo para pedir dias de ajuste era de {PRAZO_PEDIDO_AJUSTE_DIAS_UTEIS} "
                f"dias úteis a partir da reunião inicial e venceu em "
                f"{janela.prazo_pedido_ajuste.strftime('%d/%m/%Y')}. "
                "A partir daqui, o que passar da janela é atraso do projeto."
            )

    def _janela(self, escopo, referencia: Optional[object] = None):
        dias_nao_letivos = [d.data for d in self.dia_nao_letivo_repository.get_all()]
        return calcular_janela(
            escopo.data_inicio,
            escopo.dias_uteis_vendidos,
            escopo.dias_uteis_ajustados,
            dias_nao_letivos,
            referencia=referencia,
        )
