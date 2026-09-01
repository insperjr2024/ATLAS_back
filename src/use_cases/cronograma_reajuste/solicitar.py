"""⭐ O pedido de **dias de ajuste** (§8) — o único fluxo de aprovação que
sobrou no cronograma.

Antes este arquivo pedia a reabertura de um cronograma oficializado. A
oficialização acabou; o que restou é a decisão que de fato precisa de
diretoria: *este escopo ganha mais dias?*

Quatro regras, e todas as quatro estão aqui e não no router, porque juntas
formam UMA regra de negócio ("o pedido é válido?") e espalhá-las faria a rota
responder 403 num caso e 422 no outro para o mesmo problema:

1. **Pede o coordenador do projeto ou a diretoria de projetos** — para o
   coordenador vale o papel NO PROJETO, não a posição na plataforma.
2. **Só dentro do prazo**, e vale a data do PEDIDO (§20.1). O prazo tem duas
   réguas, conforme a posição do escopo na lista *Escopos vendidos*:
   o **primeiro escopo** pede até o último dia da ambientação (o kickoff),
   mesmo sem reunião inicial; **os demais**, nos 3 primeiros dias úteis da
   reunião inicial deles, porque não existe ambientação para um segundo
   escopo. Ver `utils/janela_escopo.py`.
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
from src.repositories.projeto_status_historico_repository import (
    ProjetoStatusHistoricoRepository,
)
from src.repositories.escopo_repository import EscopoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.notificacao.eventos import notificar_reajuste_solicitado
from src.utils.calendario_variante import apenas_globais
from src.utils.contagem_dias import derivar_janelas_pausa
from src.utils.exceptions import RegraDeNegocioError
from src.utils.janela_escopo import (
    PRAZO_PEDIDO_AJUSTE_DIAS_UTEIS,
    calcular_janela,
    prazo_pelo_kickoff,
    primeiro_escopo_id,
)
from src.middlewares.authorization import (
    DIRETORIA,
    DIRETORIA_DE_PESSOAS,
    DIRETORIA_DE_PROJETOS,
    eh_diretoria_de_projetos,
)

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
        self.historico_repository = ProjetoStatusHistoricoRepository(db)
        self.projeto_repository = ProjetoRepository(db)

    def execute(
        self, projeto_escopo_id: int, request: SolicitarReajusteRequest, current_user
    ) -> dict:
        escopo = self.escopo_repository.get_by_id(projeto_escopo_id)
        if not escopo:
            raise RegraDeNegocioError("Escopo não encontrado")

        self._exigir_quem_pode(escopo, current_user)
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
        for diretor in self.usuario_repository.get_por_posicoes(*DIRETORIA_DE_PROJETOS):
            # Quem pediu não é avisado do próprio pedido — desde 2026-08-31 a
            # diretora de projetos também pede, e sem isto ela receberia uma
            # notificação para ir ver o que ela mesma acabou de escrever.
            if diretor.id == current_user.id:
                continue
            notificar_reajuste_solicitado(
                self.db, diretor.id, escopo.projeto_id, escopo.id, nome_escopo, current_user.nome
            )

        return serializar_solicitacao(solicitacao)

    def _exigir_quem_pode(self, escopo, current_user) -> None:
        """§8: pede o coordenador DO PROJETO ou a diretoria de projetos.

        Para o coordenador vale o papel NO PROJETO (2026-08-31: em qualquer
        um dos escopos dele — um projeto pode ter mais de um coordenador, e
        nenhum deles é dono de um escopo específico), porque quem sabe que os
        dias não dão conta é quem está conduzindo.

        ⚠ **A diretoria de projetos entra por fora da equipe** (2026-08-31, a
        pedido). Ela enxerga o portfólio inteiro, então pede em qualquer
        projeto, sem estar na equipe dele. Antes era barrada aqui com o
        argumento de que "ela decide, não pede" — na prática ela precisava
        abrir o pedido pelo coordenador para deixar a decisão registrada no
        Histórico (§13), e o caminho não existia.

        ⚠ Isso a deixa **aprovar o próprio pedido**: quem responde é
        `require_diretor_projetos` (ver `responder.py`), a mesma posição. Não
        há trava contra isso, e é deliberado — a alternativa seria travar a
        única posição que pode decidir. O registro no Histórico é o que
        preserva a rastreabilidade.

        Gerente e consultor continuam de fora: nem conduzem o escopo nem
        decidem sobre ele.
        """
        if eh_diretoria_de_projetos(current_user):
            return
        eh_coordenador = any(
            m.usuario_id == current_user.id and m.papel == "coordenador"
            for m in self.membro_repository.get_by_projeto(escopo.projeto_id, apenas_atuais=True)
        )
        if not eh_coordenador:
            raise RegraDeNegocioError(
                "Só o coordenador do projeto ou a diretoria de projetos "
                "pedem dias de ajuste (§8)"
            )

    def _exigir_prazo_aberto(self, escopo) -> None:
        """O prazo do §8, nas suas duas réguas.

        - **Primeiro escopo vendido**: vale até o ÚLTIMO DIA DA AMBIENTAÇÃO, e
          vale mesmo sem reunião inicial. É na ambientação que a equipe conhece
          o projeto e descobre que os dias vendidos não fecham; exigir a
          largada para deixar pedir era matar o pedido exatamente quando ele
          nasce, e deixar o prazo correr DEPOIS dela era negociar prazo com o
          time já produzindo.
        - **Os demais**: 3 dias úteis contados da reunião inicial deles. Um
          segundo escopo entra num projeto cuja ambientação já aconteceu
          semanas atrás — pendurar o prazo dele naquela data seria nascer
          vencido —, e sem reunião inicial ele não tem prazo correndo: pedir
          dias antes de começar não faz sentido, o próprio início ainda pode
          mudar.
        """
        prazo_do_kickoff = self._prazo_do_kickoff(escopo)
        janela = self._janela(escopo, prazo_do_kickoff=prazo_do_kickoff)

        if janela.pedido_ajuste_aberto:
            return

        if janela.prazo_pedido_ajuste is None:
            raise RegraDeNegocioError(
                "Este escopo ainda não teve reunião inicial — a janela dele nem começou"
            )
        vencido_em = janela.prazo_pedido_ajuste.strftime("%d/%m/%Y")
        if prazo_do_kickoff is not None:
            raise RegraDeNegocioError(
                "O prazo para pedir dias de ajuste do primeiro escopo ia até o "
                f"último dia da ambientação e venceu em {vencido_em}. "
                "A partir daqui, o que passar da janela é atraso do projeto."
            )
        raise RegraDeNegocioError(
            f"O prazo para pedir dias de ajuste era de {PRAZO_PEDIDO_AJUSTE_DIAS_UTEIS} "
            f"dias úteis a partir da reunião inicial e venceu em {vencido_em}. "
            "A partir daqui, o que passar da janela é atraso do projeto."
        )

    def _prazo_do_kickoff(self, escopo):
        """O último dia da ambientação, quando é ELE o prazo deste escopo.

        `None` = o escopo não é o primeiro da lista *Escopos vendidos*, ou o
        projeto não tem ambientação para servir de prazo — nos dois casos
        valem os 3 dias úteis da reunião inicial.

        Dias não letivos GLOBAIS (`frente_id` nulo), a mesma régua da virada
        automática: a ambientação é do projeto inteiro, não de uma frente
        (ver `EncerrarAmbientacaoUseCase`).
        """
        projeto = self.projeto_repository.get_by_id(escopo.projeto_id)
        if not projeto:
            return None
        escopos = self.escopo_repository.get_by_projeto(escopo.projeto_id)
        if primeiro_escopo_id(escopos) != escopo.id:
            return None
        nao_letivos_globais = [
            d.data for d in apenas_globais(self.dia_nao_letivo_repository.get_all())
        ]
        return prazo_pelo_kickoff(
            projeto.status,
            projeto.data_inicio_ambientacao or projeto.data_kickoff,
            projeto.dias_ambientacao,
            nao_letivos_globais,
        )

    def _janela(self, escopo, referencia: Optional[object] = None, prazo_do_kickoff=None):
        dias_nao_letivos = [
            d.data for d in self.dia_nao_letivo_repository.get_do_escopo(escopo)
        ]
        # ⚠ **A pausa desloca o prazo do pedido, não só o fim da janela.**
        #
        # O prazo é de 3 dias úteis a partir da reunião inicial. Sem as janelas
        # de pausa, esses dias corriam com o projeto ⏸ Pausado — e o
        # coordenador perdia o direito de pedir dias de ajuste por causa de uma
        # pausa que a diretoria mesma decretou.
        #
        # Além disso, `calcular_contagem_escopo` já desconta a pausa: a mesma
        # resposta trazia duas janelas do mesmo escopo calculadas com
        # calendários diferentes. Mesmo padrão de `marcar_banca_escopo._janela`.
        #
        # ⚠ Vale para os 3 dias úteis; o prazo do primeiro escopo é uma DATA
        # (o fim da ambientação) e a pausa não a desloca — pelo mesmo motivo
        # que não desloca a virada automática de status.
        janelas_pausa = derivar_janelas_pausa(
            self.historico_repository.get_by_projeto(escopo.projeto_id)
        )
        return calcular_janela(
            escopo.data_inicio,
            escopo.dias_uteis_vendidos,
            escopo.dias_uteis_ajustados,
            dias_nao_letivos,
            referencia=referencia,
            janelas_pausa=janelas_pausa,
            prazo_do_kickoff=prazo_do_kickoff,
        )
