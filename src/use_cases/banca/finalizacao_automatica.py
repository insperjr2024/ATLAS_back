"""§8/§6.5 — quando `data_hora` de uma banca chega (+ 15 min de folga), sem
ninguém clicar em nada (2026-09-04, a pedido: o botão "Registrar realização"
saiu de vez).

⚠ 2026-09-09, a pedido: dispara **15 min DEPOIS** do `data_hora`, não no
horário marcado — abrir a avaliação no minuto do início é cedo demais (a
apresentação mal começou), mas a primeira tentativa de 1h também não serviu:
o e-mail chegava com a banca ainda rolando e todo mundo reclamou. 15 min é o
meio-termo. `realizado_em` continua sendo o `data_hora` marcado, só o
gatilho é que espera.

Duas coisas disparam juntas, pela mesma passada do job:

1. A banca é dada como REALIZADA (`RegistrarRealizacaoBancaUseCase`, chamado
   por dentro) — o que, por sua vez, já dispara o que sempre dependia disso:
   o prazo de avaliação de banca (48h) e o aviso ao coordenador, ambos
   inalterados, só deixaram de esperar um clique.
2. Se a banca finaliza escopo(s) de um projeto, abre um lote de Avaliação de
   Desempenho tipo "finalização" pra equipe inteira (membros + coordenador),
   com 7 dias de prazo (`PRAZO_DESEMPENHO`) — e notifica todo mundo na hora.

⚠ **Não há mais confirmação humana de que a banca realmente aconteceu.** A
única saída é `banca.cancelada_em`, gravado ANTES desta rotina rodar — ver
`CancelarBancaUseCase`. Uma banca cancelada nunca chega aqui
(`BancaRepository.get_para_finalizacao_automatica` já a exclui).
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from src.repositories.banca_escopo_repository import BancaEscopoRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.candidatura_repository import CandidaturaRepository
from src.repositories.desempenho_lote_repository import DesempenhoLoteRepository
from src.repositories.escopo_repository import EscopoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.use_cases.banca.marcar_banca_escopo import (
    RegistrarRealizacaoBancaUseCase,
    RegistrarRealizacaoRequest,
)
from src.use_cases.desempenho_lote.create_lote import (
    CreateDesempenhoLoteRequest,
    CreateDesempenhoLoteUseCase,
)
from src.use_cases.desempenho_lote.get_pendencias import GetPendenciasLoteUseCase
from src.use_cases.notificacao.eventos import notificar_lote_desempenho
from src.use_cases.projeto_escopo.get_escopos_projeto import nome_do_escopo
from src.utils.fuso import agora_utc

#: 7 dias corridos pra responder a Avaliação do Escopo (2026-09-09, a
#: pedido — antes eram 48h, curto demais pra equipe inteira). Conta a
#: partir do INSTANTE em que o lote abre, não do calendário: 7*24h cravado,
#: sem depender de a abertura cair 00:05 ou 23:50. O lembrete de "falta 1
#: dia" está amarrado a `data_fim` (ver `rodar_lembrete_lote_finalizacao`),
#: então acompanha esta mudança sozinho.
PRAZO_DESEMPENHO = timedelta(days=7)

#: Folga entre o `data_hora` da banca e o gatilho da finalização automática
#: (2026-09-09, a pedido: nasceu como 1h e virou 15 min no mesmo dia — 1h
#: fazia o e-mail chegar com a banca ainda em andamento). A banca começa no
#: `data_hora`, mas não ACABA nele; 15 min é a margem mínima pra ela ter de
#: fato começado antes de abrir a avaliação.
ATRASO_FINALIZACAO = timedelta(minutes=15)

logger = logging.getLogger(__name__)


class FinalizacaoAutomaticaBancaUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.banca_repository = BancaRepository(db)
        self.candidatura_repository = CandidaturaRepository(db)
        self.banca_escopo_repository = BancaEscopoRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.catalogo_repository = EscopoRepository(db)
        self.projeto_repository = ProjetoRepository(db)
        self.lote_repository = DesempenhoLoteRepository(db)

    def execute(self, referencia: Optional[datetime] = None) -> list[dict]:
        # ⚠ UTC, não `datetime.now()` local (2026-09-09): `banca.data_hora`
        # é gravado em UTC pelo front. Comparar com hora local do servidor
        # atrasava a finalização em 3h — a banca do meio-dia só finalizava
        # às 15h.
        #
        # ⚠ `- ATRASO_FINALIZACAO`: só entra banca cujo `data_hora` já passou
        # há pelo menos 15 min — margem pra ela ter de fato começado.
        referencia = (referencia or agora_utc()) - ATRASO_FINALIZACAO
        candidatas = self.banca_repository.get_para_finalizacao_automatica(referencia)
        resumo = []
        for banca in candidatas:
            try:
                resumo.append(self._processar(banca))
            except Exception:
                # Uma banca com problema (composição impossível, escopo órfão)
                # não pode travar as outras 19 da mesma passada — a próxima
                # rodada do job tenta de novo, igual ao padrão do push de
                # alocação.
                logger.exception(
                    "Falha ao processar finalização automática da banca %s", banca.id
                )
        return [r for r in resumo if r]

    def _processar(self, banca) -> Optional[dict]:
        # ⚠ `forcar=True` + `eh_diretor_projetos=True` sempre: não há mais
        # humano nesta tela decidindo se vale a pena registrar abaixo do
        # mínimo de composição. A banca ACONTECEU pelo relógio; o job não tem
        # como julgar se "valeu a pena" — só um diretor olhando decidia isso,
        # e essa decisão saiu de cena junto com o botão.
        #
        # ⚠ `presentes` = todo mundo que se candidatou, de propósito. Sem
        # isto, `candidatura.confirmado` (default `False` no banco) nunca
        # seria tocado — `RegistrarRealizacaoBancaUseCase` só atualiza
        # presença quando `presentes` vem preenchido — e a tela de Presença
        # (`PresencaBancas.tsx`) passaria a marcar 100% de falta em toda
        # banca automática, para todo mundo, sempre. Sem humano para
        # apontar quem faltou, a suposição mais honesta é a mesma que o
        # antigo modal já usava por padrão: todo inscrito compareceu.
        candidatos = [c.usuario_id for c in self.candidatura_repository.get_by_banca(banca.id)]
        RegistrarRealizacaoBancaUseCase(self.db).execute(
            banca.id,
            RegistrarRealizacaoRequest(forcar=True, presentes=candidatos),
            eh_diretor_projetos=True,
        )

        lote_id = self._abrir_avaliacao_de_desempenho(banca)
        return {"banca_id": banca.id, "lote_desempenho_id": lote_id}

    def _abrir_avaliacao_de_desempenho(self, banca) -> Optional[int]:
        """Cria e notifica o lote de finalização — `None` quando a banca não
        tem escopo vinculado (banca legada) ou o(s) escopo(s) sumiram."""
        escopo_ids = self.banca_escopo_repository.get_escopo_ids(banca.id)
        if not escopo_ids:
            return None

        escopos = [e for e in (self.escopo_repository.get_by_id(i) for i in escopo_ids) if e]
        if not escopos:
            return None

        # Todos do MESMO projeto — garantido por `resolver_escopos` (uma
        # banca nunca junta escopos de projetos diferentes).
        projeto_id = escopos[0].projeto_id
        projeto = self.projeto_repository.get_by_id(projeto_id)
        if not projeto:
            return None

        catalogo_por_id = {
            e.escopo_id: self.catalogo_repository.get_by_id(e.escopo_id)
            for e in escopos
            if e.escopo_id
        }
        nomes_escopo = [nome_do_escopo(e, catalogo_por_id) for e in escopos]

        # UTC, mesma régua de `banca.data_hora` e de `criado_em` (`func.now()`).
        # `datetime.now()` cru aqui gravava a hora local do servidor (UTC no
        # Railway) e o e-mail do lote mostrava esse valor sem converter: um
        # lote aberto ao meio-dia dizia "responda até ... às 15:00". Quem
        # formata pra pessoa (`notificar_lote_desempenho`) agora converte.
        agora = agora_utc()
        lote_resultado = CreateDesempenhoLoteUseCase(self.db).execute(
            CreateDesempenhoLoteRequest(
                nome=f"Finalização - {projeto.nome} - {', '.join(nomes_escopo)}",
                tipo="finalizacao",
                data_inicio=agora,
                data_fim=agora + PRAZO_DESEMPENHO,
                projeto_ids=[projeto_id],
                banca_id=banca.id,
            )
        )
        lote_id = lote_resultado["id"]

        # Abrir de fato (mandar o aviso) é o mesmo passo de `AbrirLoteUseCase`
        # — só que o lote já nasce dentro da janela de datas, sem precisar de
        # `override_manual`: `esta_aberto()` já diz que sim.
        lote = self.lote_repository.get_by_id(lote_id)
        pendencias = GetPendenciasLoteUseCase(self.db).execute(lote_id) or []
        notificar_lote_desempenho(self.db, lote, pendencias)

        return lote_id
