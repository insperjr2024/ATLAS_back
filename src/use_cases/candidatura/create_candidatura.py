from sqlalchemy.orm import Session
from typing import Optional

from pydantic import BaseModel
from datetime import datetime, timedelta
from src.repositories.candidatura_repository import CandidaturaRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.configuracao_repository import ConfiguracaoRepository
from src.repositories.banca_escopo_repository import BancaEscopoRepository
from src.repositories.equipe_projeto_repository import EquipeProjetoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.banca_frente_repository import BancaFrenteRepository
from src.repositories.frente_repository import FrenteRepository
from src.utils.avaliacoes_pendentes import PRAZO_AVALIACAO_DIAS
from src.utils.banca_status import aceita_inscricao, calcular_status_banca
from src.utils.teto_banca import calcular_vagas_banca
from src.utils.composicao_banca import ComposicaoBancaChecker
from src.utils.equipe_banca import membros_da_banca
from src.utils.exceptions import CODIGO_BANCA_LOTADA, RegraDeNegocioError


def _descrever_pendencias(status) -> str:
    """"1 liderança de Business, 2 membros de Direito" — o que ainda falta pro
    piso, pra dizer à pessoa por que a vaga está reservada."""
    partes = []
    for d in status.deficits:
        if d.lideranca_faltando:
            partes.append(f"{d.lideranca_faltando} liderança de {d.frente_nome}")
        if d.piso_faltando:
            plural = "membros" if d.piso_faltando > 1 else "membro"
            partes.append(f"{d.piso_faltando} {plural} de {d.frente_nome}")
    return ", ".join(partes) or "a composição por frente"


class CreateCandidaturaRequest(BaseModel):
    banca_id: int
    confirmado: bool = False
    #: Alocar OUTRA pessoa. Só a diretoria — o router faz a checagem, porque é
    #: lá que se sabe quem está chamando. Sem isto, cada um só se inscreve.
    usuario_id: Optional[int] = None


class CreateCandidaturaUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = CandidaturaRepository(db)
        self.banca_repository = BancaRepository(db)
        self.configuracao_repository = ConfiguracaoRepository(db)
        self.equipe_projeto_repository = EquipeProjetoRepository(db)
        self.banca_escopo_repository = BancaEscopoRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)
        self.banca_frente_repository = BancaFrenteRepository(db)
        self.frente_repository = FrenteRepository(db)

    def execute(self, request: CreateCandidaturaRequest, usuario_id: int, eh_gestao: bool = False):
        banca = self.banca_repository.get_by_id(request.banca_id)
        if not banca:
            raise RegraDeNegocioError("Banca não encontrada")

        # Quem fecha a inscrição é a REALIZAÇÃO, não o calendário: uma banca
        # `atrasada` (venceu e não aconteceu) continua aceitando gente, porque
        # ela ainda vai acontecer. Antes da F5 a data passada bloqueava.
        status = calcular_status_banca(banca.data_hora, banca.realizado_em, cancelada_em=getattr(banca, "cancelada_em", None))
        # ⚠ `eh_gestao` só passa por cima do "já foi realizada" (2026-09-15, a
        # pedido) — diretoria/quem gere membros às vezes precisa corrigir a
        # ficha de uma banca que já aconteceu (trocar quem avaliou, por
        # exemplo). Cancelada e sem data continuam travadas pra todo mundo:
        # não tem "consertar" candidatura de banca que não vai acontecer.
        if not aceita_inscricao(status) and not (eh_gestao and status == "realizada"):
            if status == "realizada":
                raise RegraDeNegocioError("Não é possível se candidatar: esta banca já foi realizada")
            if status == "cancelada":
                raise RegraDeNegocioError("Não é possível se candidatar: esta banca foi cancelada")
            raise RegraDeNegocioError("Não é possível se candidatar: esta banca ainda não tem data marcada")

        # ⚠ Mesmo pra gestão, adicionar só faz sentido enquanto a pessoa ainda
        # teria como avaliar (2026-09-15, a pedido): passado o prazo de
        # `PRAZO_AVALIACAO_DIAS` da realização, ninguém mais submete avaliação
        # nenhuma (`submeter_avaliacao.py` usa a MESMA régua, sempre a partir
        # de `realizado_em`) — adicionar depois disso seria só um registro
        # morto. Remover não tem essa trava — ver `DeleteCandidaturaUseCase`,
        # que continua liberado pra gestão não importa há quanto tempo a
        # banca aconteceu.
        if eh_gestao and status == "realizada" and banca.realizado_em:
            prazo = banca.realizado_em + timedelta(days=PRAZO_AVALIACAO_DIAS)
            if datetime.now() > prazo:
                raise RegraDeNegocioError(
                    f"Não é possível adicionar: o prazo de {PRAZO_AVALIACAO_DIAS} dias para "
                    "avaliar esta banca já passou, então não há mais o que essa pessoa fazer aqui."
                )

        # Ninguém avalia o próprio grupo: nem quem coordena, nem quem está na
        # equipe do projeto desta banca.
        #
        # ⚠ Antes isto lia só `equipe_projeto`, a tabela legada preenchida à
        # mão na tela de bancas. Banca marcada pelo CRONOGRAMA não escreve
        # nela, e os consultores do projeto conseguiam se inscrever na própria
        # banca. `membros_da_banca` junta as duas fontes.
        if usuario_id in membros_da_banca(
            banca,
            self.banca_escopo_repository,
            self.escopo_repository,
            self.membro_repository,
            self.equipe_projeto_repository,
        ):
            raise RegraDeNegocioError("Você não pode se candidatar à banca do seu próprio grupo")

        candidaturas_existentes = self.repository.get_by_banca(request.banca_id)

        # ⚠ Nada impedia a MESMA pessoa virar candidata duas vezes da mesma
        # banca (2026-09-16) — um duplo-clique em "Alocar-se", ou a gestão
        # adicionando quem já estava lá, criava outra linha igual sem erro
        # nenhum. Foi assim que uma consultora apareceu 4x na ficha do
        # GELATTO. Vale pra gestão também: não existe motivo legítimo para
        # duas candidaturas da mesma pessoa na mesma banca.
        if any(c.usuario_id == usuario_id for c in candidaturas_existentes):
            raise RegraDeNegocioError("Esta pessoa já é candidata desta banca.")

        # ⭐ O único teto é o TOTAL da banca, da COMBINAÇÃO de frentes dela
        # (2026-09-02): a de Direito sozinha e a de Business + Tech + Processos
        # cabiam o mesmo tanto de gente. Quem não configurou cai no global.
        #
        # ⚠ Não há mais teto POR FRENTE (2026-09-03): o piso tem de ser gente
        # daquela frente, mas completar acima dele, até estas `vagas`, é
        # "tanto faz a frente". O que mostra o piso faltando é `GET /bancas`.
        vinculos_frente = self.banca_frente_repository.get_by_banca(banca.id)
        vagas = calcular_vagas_banca(
            [f for f in (self.frente_repository.get_by_id(v.frente_id) for v in vinculos_frente) if f],
            self.db,
        )

        # ⚠ Não vale para a gestão (2026-09-16, a pedido — mesmo motivo da
        # reserva de vaga logo abaixo): "a diretoria pode TUDO". É o próprio
        # caminho pra corrigir uma banca que ficou lotada com composição
        # errada (alguém saiu depois de cobrir um piso, e não sobrou vaga
        # pra repor) — sem isto, a diretoria fica de mãos atadas exatamente
        # no caso que mais precisa dela.
        if len(candidaturas_existentes) >= vagas and not eh_gestao:
            # ⚠ `codigo` (2026-09-18): é a recusa que `SolicitarEntradaBancaUseCase`
            # reconhece pra virar pedido em vez de erro sem saída — ver
            # `use_cases/banca/entrada_solicitacao.py`.
            raise RegraDeNegocioError("Não é possível se candidatar: banca lotada", codigo=CODIGO_BANCA_LOTADA)

        # ⭐ As últimas vagas ficam RESERVADAS para os pisos por frente ainda
        # não cobertos (2026-09-04, a pedido): se falta 1 liderança de Business
        # e sobra 1 vaga, só quem cobre essa cota entra. Antes o piso por
        # frente era só MOSTRADO (`GET /bancas`); o único freio na inscrição
        # era o total da banca.
        #
        # A conta: COM esta pessoa dentro, quantas vagas sobram vs. quanto de
        # piso ainda falta. Se sobra menos vaga do que falta piso, a inscrição
        # tornaria a composição impossível — recusa. Quem REDUZ o déficit
        # (a liderança de Business que faltava) passa, porque aí `falta_depois`
        # cai junto.
        #
        # ⚠ Não vale para a gestão (2026-09-16, a pedido): "a diretoria pode
        # TUDO, mesmo que não cubra o piso mínimo" — essa reserva existe pra
        # proteger a AUTO-inscrição de alguém tomar uma vaga que não é dela;
        # quando é a diretoria quem está alocando (`eh_gestao`), a decisão já
        # é dela, a composição é problema que ela mesma está resolvendo.
        if vinculos_frente and not eh_gestao:
            from src.use_cases.configuracao.composicao_banca import (
                ResolverComposicaoUseCase,
            )

            regras = ResolverComposicaoUseCase(self.db).para(
                [v.frente_id for v in vinculos_frente]
            )
            checker = ComposicaoBancaChecker(self.db)
            ids_com_essa = {
                c.usuario_id for c in candidaturas_existentes
            } | {usuario_id}
            status_depois = checker.verificar(banca, regras, ids_com_essa)
            falta_depois = sum(
                d.piso_faltando + d.lideranca_faltando for d in status_depois.deficits
            )
            vagas_livres_depois = vagas - (len(candidaturas_existentes) + 1)
            if vagas_livres_depois < falta_depois:
                # ⚠ Mesmo `codigo` do teto cheio acima — as duas recusas são
                # "não há vaga PRA VOCÊ agora", e a interface reage às duas
                # do mesmo jeito (oferece "Solicitar entrada").
                raise RegraDeNegocioError(
                    "Esta vaga está reservada para completar a composição: "
                    f"falta {_descrever_pendencias(status_depois)}. Só quem cobre "
                    "essa cota pode se inscrever agora.",
                    codigo=CODIGO_BANCA_LOTADA,
                )

        # ⚠ 2026-09-16, a pedido: quem a gestão adiciona numa banca JÁ
        # REALIZADA nasce como presente, não como "faltou". Desde que o
        # botão manual de registrar realização saiu (2026-09-04), não existe
        # mais humano pra marcar presença depois do fato — sem isto, a
        # pessoa ficava com `confirmado=False` pra sempre (a finalização
        # automática, que já presume presente todo mundo que era candidato
        # na hora, já passou por essa banca e não roda de novo) e aparecia
        # com "· faltou" na ficha, contando errado nas estatísticas de
        # presença, mesmo continuando livre pra preencher a avaliação (isso
        # nunca foi bloqueado por `confirmado`).
        confirmado = True if (eh_gestao and status == "realizada") else request.confirmado
        candidatura = self.repository.create(
            banca_id=request.banca_id,
            usuario_id=usuario_id,
            criado_em=datetime.now(),
            confirmado=confirmado
        )
        return {
            "id": candidatura.id,
            "banca_id": candidatura.banca_id,
            "usuario_id": candidatura.usuario_id,
            "criado_em": candidatura.criado_em,
            "confirmado": candidatura.confirmado
        }