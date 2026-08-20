from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from src.models.projeto_model import ProjetoModel
from src.repositories.banca_remarcacao_repository import BancaRemarcacaoRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.banca_sessao_repository import BancaSessaoRepository
from src.repositories.cronograma_reajuste_repository import CronogramaReajusteRepository
from src.repositories.dia_nao_letivo_repository import DiaNaoLetivoRepository
from src.repositories.entrega_alteracao_repository import EntregaAlteracaoRepository
from src.repositories.escopo_repository import EscopoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_frente_repository import ProjetoFrenteRepository
from src.repositories.projeto_membro_repository import ProjetoMembroRepository
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.projeto_justificativa_atraso_repository import (
    ProjetoJustificativaAtrasoRepository,
)
from src.repositories.projeto_remarcacao_banca_repository import ProjetoRemarcacaoBancaRepository
from src.repositories.projeto_status_historico_repository import ProjetoStatusHistoricoRepository
from src.repositories.tarefa_repository import ReuniaoSemanalRepository
from src.use_cases.projeto_escopo.get_escopos_projeto import nome_do_escopo
from src.utils.ambientacao import fim_da_ambientacao


def serializar_projeto_resumo(
    projeto, frente_repo: ProjetoFrenteRepository, membro_repo: ProjetoMembroRepository, proxima_banca=None
):
    """A forma enxuta, usada nos cards da lista (§6.2)."""
    frentes = frente_repo.get_by_projeto(projeto.id)
    membros = membro_repo.get_by_projeto(projeto.id, apenas_atuais=True)
    coordenador = next((m for m in membros if m.papel == "coordenador"), None)

    return {
        "id": projeto.id,
        "nome": projeto.nome,
        "cliente": projeto.cliente,
        "criado_em": projeto.criado_em,
        "status": projeto.status,
        "frente_ids": [f.frente_id for f in frentes],
        "sinergico": len(frentes) > 1,
        "coordenador_id": coordenador.usuario_id if coordenador else None,
        "consultor_ids": [m.usuario_id for m in membros if m.papel == "consultor"],
        # Teto de consultores: a tela de vagas compara com quantos já entraram.
        "max_consultores": projeto.max_consultores,
        "data_kickoff": projeto.data_kickoff,
        "kickoff_pendente": projeto.data_kickoff is None and projeto.status not in ("finalizado",),
        # `None` = ambientação começa no kickoff, o caso normal. Só não-nulo
        # quando o coordenador corrigiu que ela começou antes dele.
        "data_inicio_ambientacao": projeto.data_inicio_ambientacao,
        "arquivado_em": projeto.arquivado_em,
        # "Limpar histórico" (§4): corte de exibição da timeline, não exclusão.
        "historico_oculto_ate": projeto.historico_oculto_ate,
        # §6.2: a banca mais próxima AINDA NÃO REALIZADA de qualquer escopo
        # deste projeto — `None` se nenhuma estiver marcada ou todas já
        # aconteceram.
        "proxima_banca": proxima_banca.data_hora if proxima_banca else None,
    }


def serializar_projeto_completo(
    projeto,
    frente_repo: ProjetoFrenteRepository,
    membro_repo: ProjetoMembroRepository,
    escopos=None,
    fim_ambientacao=None,
):
    """A forma completa, usada na página do projeto (§6.4, aba Visão geral)."""
    resumo = serializar_projeto_resumo(projeto, frente_repo, membro_repo)
    membros = membro_repo.get_by_projeto(projeto.id, apenas_atuais=True)
    return {
        **resumo,
        # 🤖 O último dia de ambientação (§5.3). Vem do backend porque depende
        # de dia útil, e o front não recalcula isso — é ele que a tela usa para
        # avisar quando o projeto vira Em andamento sozinho. `None` = sem
        # janela (sem kickoff ou com zero dias), e aí a saída é manual.
        "fim_ambientacao": fim_ambientacao,
        # Já vêm com a contagem do §5.4 calculada — o front só desenha a barra.
        "escopos": escopos or [],
        "descricao": projeto.descricao,
        "link_proposta": projeto.link_proposta,
        "anexo_proposta_nome": projeto.anexo_proposta_nome,
        "dias_ambientacao": projeto.dias_ambientacao,
        # ⭐ **DERIVADA, não digitada.** "Entrega ao cliente" e "entrega do
        # escopo" são a MESMA coisa: o cliente recebe quando o escopo é
        # entregue. A do projeto é a do último escopo entregue — não existe uma
        # terceira data, e a coluna `projeto.data_entrega_cliente` deixou de ser
        # lida justamente para não haver duas versões da mesma promessa.
        #
        # ⚠ Diferente da banca, a entrega **não** precisa caber na janela do
        # escopo: a janela é o tempo de TRABALHO vendido, e a apresentação ao
        # cliente costuma ser dias depois da banca (§5.5).
        "data_entrega_cliente": max(
            (e["data_entrega_real"] for e in (escopos or []) if e.get("data_entrega_real")),
            default=None,
        ),
        # ⭐ A PROMESSA, ao lado do fato. As duas convivem de propósito: é a
        # diferença entre elas que responde "entregamos ao cliente no prazo?"
        # no nível do projeto — algo que até aqui só existia por escopo.
        "data_entrega_prevista_cliente": projeto.data_entrega_prevista_cliente,
        "dia_reuniao_padrao": projeto.dia_reuniao_padrao,
        "criado_por": projeto.criado_por,
        "equipe": [
            {"usuario_id": m.usuario_id, "papel": m.papel, "entrou_em": m.entrou_em}
            for m in membros
        ],
    }


class GetProjetoUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjetoRepository(db)
        self.frente_repository = ProjetoFrenteRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)

    def execute(self, projeto_id: int):
        from src.use_cases.projeto_escopo.get_escopos_projeto import ListEscoposProjetoUseCase

        projeto = self.repository.get_by_id(projeto_id)
        if not projeto:
            return None
        escopos = ListEscoposProjetoUseCase(self.db).execute(projeto_id)
        return serializar_projeto_completo(
            projeto,
            self.frente_repository,
            self.membro_repository,
            escopos,
            fim_ambientacao=self._fim_ambientacao(projeto),
        )

    def _fim_ambientacao(self, projeto):
        """Mesma régua da faixa do cronograma e da virada automática: dias não
        letivos GLOBAIS, porque a ambientação é do projeto inteiro."""
        inicio = projeto.data_inicio_ambientacao or projeto.data_kickoff
        if not inicio or projeto.dias_ambientacao <= 0:
            return None
        limite = inicio + timedelta(days=365)
        nao_letivos = [
            d.data
            for d in DiaNaoLetivoRepository(self.db).get_por_intervalo(inicio, limite)
            if d.frente_id is None
        ]
        return fim_da_ambientacao(inicio, projeto.dias_ambientacao, nao_letivos)


class ListProjetosUseCase:
    """A lista recortada pela visão (§3) — quem decide o que aparece é o
    `aplicar_recorte_visao`, não esta classe."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjetoRepository(db)
        self.frente_repository = ProjetoFrenteRepository(db)
        self.membro_repository = ProjetoMembroRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.banca_repository = BancaRepository(db)

    def execute(self, current_user, frente_id: Optional[int] = None, incluir_arquivados: bool = False):
        from src.middlewares.authorization import aplicar_recorte_visao

        query = aplicar_recorte_visao(self.db.query(ProjetoModel), current_user, self.db, frente_id)
        if not incluir_arquivados:
            query = query.filter(ProjetoModel.arquivado_em.is_(None))
        projetos = query.all()

        # §6.2: a banca mais próxima ainda não realizada, por projeto — busca
        # em bloco (escopos de todos os projetos, depois bancas de todos os
        # escopos) pra não virar uma query por card.
        escopos = self.escopo_repository.get_by_projetos([p.id for p in projetos])
        projeto_por_escopo = {e.id: e.projeto_id for e in escopos}
        # Banca ↔ escopo é muitos-para-muitos (uma banca cobre vários escopos)
        # — `mapa_por_escopo` já devolve por escopo, que é a chave que temos.
        banca_por_escopo = self.banca_repository.mapa_por_escopo(list(projeto_por_escopo))
        proxima_por_projeto = {}
        for escopo_id, banca in banca_por_escopo.items():
            if banca.data_hora is None or banca.realizado_em is not None:
                continue
            projeto_id = projeto_por_escopo.get(escopo_id)
            atual = proxima_por_projeto.get(projeto_id)
            if projeto_id and (atual is None or banca.data_hora < atual.data_hora):
                proxima_por_projeto[projeto_id] = banca

        return [
            serializar_projeto_resumo(
                p, self.frente_repository, self.membro_repository, proxima_por_projeto.get(p.id)
            )
            for p in projetos
        ]


class GetHistoricoProjetoUseCase:
    """§13: *"toda decisão, autorizada ou negada, entra na aba Histórico"*.

    ⭐ **Composto na leitura, sem tabela de eventos.** São CINCO fontes que já
    existem — mudanças de status, remarcações de banca, decisões sobre dias de
    ajuste, alterações de data de entrega e justificativas de atraso (§7.4) — e
    cada uma continua sendo a dona do seu dado. Uma tabela genérica de eventos
    exigiria escrever duas vezes em cada fluxo, e a segunda escrita é a que
    alguém esquece.

    Cada linha sai no mesmo formato (`tipo`, `em`, `por`, `titulo`, `detalhe`)
    para a tela renderizar uma lista só, ordenada do mais recente para o mais
    antigo. **Os campos `alterado_em`/`alterado_por` saem junto em toda linha**,
    e não só nas de status: é o formato que a outra metade da tela já lê, e
    mantê-lo custa duas chaves por linha.

    ⚠ **Duas tabelas de remarcação.** `banca_remarcacao` e
    `projeto_remarcacao_banca` nasceram em paralelo, em branches diferentes,
    para a mesma coisa — cada uma com uma coluna que a outra não tem
    (`autorizado_por` de um lado, `projeto_id`/`projeto_escopo_id` do outro).
    Aqui as duas são lidas e o par é deduplicado por (banca, data anterior,
    data nova), senão a mesma remarcação apareceria duas vezes na tela.
    Unificar as tabelas é dívida registrada, não conserto de merge.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjetoStatusHistoricoRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.banca_repository = BancaRepository(db)
        self.sessao_repository = BancaSessaoRepository(db)
        self.remarcacao_repository = BancaRemarcacaoRepository(db)
        self.remarcacao_projeto_repository = ProjetoRemarcacaoBancaRepository(db)
        self.reajuste_repository = CronogramaReajusteRepository(db)
        self.catalogo_repository = EscopoRepository(db)
        self.entrega_repository = EntregaAlteracaoRepository(db)
        self.justificativa_repository = ProjetoJustificativaAtrasoRepository(db)
        self.reuniao_repository = ReuniaoSemanalRepository(db)
        self.projeto_repository = ProjetoRepository(db)

    def execute(self, projeto_id: int, incluir_ocultos: bool = False):
        linhas = self._status(projeto_id)

        escopos = self.escopo_repository.get_by_projeto(projeto_id)
        catalogo = {e.id: e for e in self.catalogo_repository.get_all()}
        nomes = {e.id: nome_do_escopo(e, catalogo) for e in escopos}

        linhas += self._remarcacoes(projeto_id, escopos, nomes)
        linhas += self._sessoes_de_banca(escopos, nomes)
        linhas += self._decisoes_de_ajuste(escopos, nomes)
        linhas += self._alteracoes_de_entrega(projeto_id, nomes)
        linhas += self._justificativas_de_atraso(projeto_id, nomes)
        linhas += self._reunioes(projeto_id, nomes)

        # ⭐ "Limpar histórico" (§4) corta TODAS as fontes pelo mesmo carimbo —
        # senão uma nota de atraso de antes do corte continuaria aparecendo com
        # as transições de status ao redor dela já escondidas. Aplicado aqui, no
        # fim, para valer também para as fontes que a main ainda não tinha.
        if not incluir_ocultos:
            projeto = self.projeto_repository.get_by_id(projeto_id)
            corte = projeto.historico_oculto_ate if projeto else None
            if corte:
                linhas = [l for l in linhas if l["em"] and l["em"] > corte]

        # `datetime.min` para a linha sem data nunca derrubar a ordenação.
        linhas.sort(key=lambda l: l["em"] or datetime.min, reverse=True)
        return linhas

    def _justificativas_de_atraso(self, projeto_id: int, nomes):
        """§7.4: por que o projeto atrasou, na palavra de quem conduziu.

        Fonte que vinha só da main. Sai no envelope de todos — `titulo` e
        `detalhe` prontos —, mas mantém `motivo_tipo` e `projeto_escopo_id`,
        que a tela de Atrasos lê para agrupar.
        """
        return [
            {
                "id": f"justificativa:{j.id}",
                "tipo": "justificativa_atraso",
                "em": j.registrado_em,
                "por": j.registrado_por,
                "titulo": f"Atraso justificado — {nomes.get(j.projeto_escopo_id) or 'projeto'}",
                "detalhe": j.texto,
                "projeto_escopo_id": j.projeto_escopo_id,
                "motivo_tipo": j.tipo,
                "registrado_por": j.registrado_por,
                "alterado_em": j.registrado_em,
                "alterado_por": j.registrado_por,
            }
            for j in self.justificativa_repository.get_by_projeto(projeto_id)
        ]

    def _status(self, projeto_id: int):
        return [
            {
                "id": h.id,
                "tipo": "status",
                "em": h.alterado_em,
                "por": h.alterado_por,
                "titulo": f"Status: {h.status_anterior or '—'} → {h.status_novo}",
                "detalhe": None,
                # Mantidos porque a tela já os lê para desenhar o ícone.
                "status_anterior": h.status_anterior,
                "status_novo": h.status_novo,
                "alterado_por": h.alterado_por,
                "alterado_em": h.alterado_em,
            }
            for h in self.repository.get_by_projeto(projeto_id)
        ]

    def _sessoes_de_banca(self, escopos, nomes):
        """⭐ Que a banca aconteceu, e no que ela deu (§8, §9).

        A fonte que faltava. O histórico já contava que a banca foi remarcada,
        mas não que ela **ocorreu** nem qual foi o veredito — justamente o
        evento que destrava a entrega ao cliente (§5.5). Quem abria a aba via a
        discussão sobre datas e nada sobre o resultado.

        ⚠ **Uma linha por SESSÃO, não por banca.** É o que torna a segunda
        tentativa visível: antes, remarcar uma banca reprovada apagava
        `realizado_em` e `resultado` da linha única, e a reprovação sumia sem
        deixar rastro. Cada tentativa arquivada vira uma linha própria, com o
        número na frente — "2ª banca" só faz sentido se a 1ª ainda estiver lá.

        Sessão ainda não realizada não entra: um agendamento futuro não é
        acontecimento, e o cronograma já mostra a data.
        """
        bancas = self.banca_repository.mapa_por_escopo([e.id for e in escopos])
        if not bancas:
            return []

        # ⚠ **Uma banca pode cobrir VÁRIOS escopos** (a banca sinérgica do §8).
        # `mapa_por_escopo` é `{escopo: banca}`, então montar `{banca: escopo}`
        # direto guarda só o ÚLTIMO — e o histórico dizia "Banca realizada —
        # Desenvolvimento Web", omitindo o segundo escopo que a mesma banca
        # avaliou. Quem lesse a timeline concluiria que o outro escopo nunca
        # passou por banca.
        escopos_por_banca: dict = {}
        for eid, b in bancas.items():
            escopos_por_banca.setdefault(b.id, []).append(eid)

        def nomear(banca_id: int) -> str:
            cobertos = [nomes.get(eid) for eid in escopos_por_banca.get(banca_id, [])]
            cobertos = [n for n in cobertos if n]
            if not cobertos:
                return "escopo"
            # Ordenado para a linha não mudar de texto entre dois carregamentos.
            return " + ".join(sorted(cobertos))

        nome_por_banca = {bid: nomear(bid) for bid in escopos_por_banca}
        # O primeiro escopo continua sendo a âncora do link na tela — a linha
        # leva a um escopo só, mesmo nomeando os dois.
        escopo_por_banca = {bid: eids[0] for bid, eids in escopos_por_banca.items()}

        rotulo_resultado = {
            "aprovada": "aprovada",
            "nao_aprovada": "não aprovada",
        }

        linhas = []
        sessoes = self.sessao_repository.get_by_bancas([b.id for b in bancas.values()])
        for banca_id, lista in sessoes.items():
            for s in lista:
                if not s.realizado_em:
                    continue
                escopo = nome_por_banca.get(banca_id) or "escopo"
                # "Banca" na primeira, "2ª banca" da segunda em diante: numerar
                # a primeira sugeriria que houve outra antes dela.
                titulo_banca = "Banca" if s.numero <= 1 else f"{s.numero}ª banca"
                veredito = rotulo_resultado.get(s.resultado or "")
                linhas.append(
                    {
                        "id": f"banca-sessao:{s.id}",
                        "tipo": "banca_realizada",
                        "em": s.realizado_em,
                        "por": None,
                        "titulo": f"{titulo_banca} realizada — {escopo}",
                        "detalhe": (
                            f"Resultado: {veredito}."
                            if veredito
                            else "Ainda sem resultado — aguardando o voto dos avaliadores."
                        ),
                        "projeto_escopo_id": escopo_por_banca.get(banca_id),
                        "alterado_em": s.realizado_em,
                        "alterado_por": None,
                    }
                )
        return linhas

    def _remarcacoes(self, projeto_id: int, escopos, nomes):
        """§9: a data antiga de cada banca remarcada, com a justificativa.

        Sem esta fonte, "de 06/08 para 20/08" existiria só na notificação — que
        some assim que é lida.
        """
        bancas = self.banca_repository.mapa_por_escopo([e.id for e in escopos])
        nome_por_banca = {b.id: nomes.get(eid) for eid, b in bancas.items()}
        escopo_por_banca = {b.id: eid for eid, b in bancas.items()}

        # ⚠ **Duas tabelas para o mesmo evento.** As branches criaram
        # `banca_remarcacao` e `projeto_remarcacao_banca` em paralelo, e cada
        # uma guarda algo que a outra não tem. Ler só uma esconderia as
        # remarcações gravadas pela outra — inclusive as que já estão no banco.
        # A chave natural do evento é (banca, de, para): mesma remarcação vista
        # por duas tabelas colapsa numa linha, e os campos se somam.
        por_evento: dict = {}

        def somar(chave, linha):
            atual = por_evento.get(chave)
            if atual is None:
                por_evento[chave] = linha
                return
            # Nunca sobrescreve o que já está preenchido: o objetivo é a UNIÃO
            # das duas fontes, não a última a falar.
            for campo, valor in linha.items():
                if atual.get(campo) in (None, "") and valor not in (None, ""):
                    atual[campo] = valor

        for r in self.remarcacao_repository.get_by_bancas({b.id for b in bancas.values()}):
            somar(
                (r.banca_id, r.data_anterior, r.data_nova),
                {
                    "id": f"remarcacao:{r.id}",
                    "tipo": "banca_remarcada",
                    "em": r.criado_em,
                    "por": r.remarcado_por,
                    "titulo": (
                        f"Banca remarcada — {nome_por_banca.get(r.banca_id) or 'escopo'}: "
                        f"{_quando(r.data_anterior)} → {_quando(r.data_nova)}"
                    ),
                    "detalhe": r.justificativa,
                    # Preenchido só quando a diretoria precisou liberar a exceção
                    # do §13 (fora da janela, ou em cima da hora).
                    "autorizado_por": r.autorizado_por,
                    "projeto_escopo_id": escopo_por_banca.get(r.banca_id),
                    "data_anterior": r.data_anterior,
                    "data_nova": r.data_nova,
                    "justificativa": r.justificativa,
                    "registrado_por": r.remarcado_por,
                    "alterado_em": r.criado_em,
                    "alterado_por": r.remarcado_por,
                },
            )

        for r in self.remarcacao_projeto_repository.get_by_projeto(projeto_id):
            somar(
                (r.banca_id, r.data_anterior, r.data_nova),
                {
                    "id": f"remarcacao-projeto:{r.id}",
                    "tipo": "banca_remarcada",
                    "em": r.registrado_em,
                    "por": r.registrado_por,
                    "titulo": (
                        f"Banca remarcada — {nome_por_banca.get(r.banca_id) or 'escopo'}: "
                        f"{_quando(r.data_anterior)} → {_quando(r.data_nova)}"
                    ),
                    "detalhe": r.justificativa,
                    "autorizado_por": None,
                    "projeto_escopo_id": r.projeto_escopo_id,
                    "data_anterior": r.data_anterior,
                    "data_nova": r.data_nova,
                    "justificativa": r.justificativa,
                    "registrado_por": r.registrado_por,
                    "alterado_em": r.registrado_em,
                    "alterado_por": r.registrado_por,
                },
            )

        return list(por_evento.values())

    def _decisoes_de_ajuste(self, escopos, nomes):
        """§8: os pedidos de dias — **duas linhas por pedido**.

        ⭐ O pedido e a decisão são eventos separados: momentos diferentes,
        pessoas diferentes, textos diferentes. Espremer os dois numa linha só
        perdia o que o coordenador escreveu — sobrava a justificativa da
        diretoria e sumia o motivo que a provocou. Numa timeline cronológica,
        "pediu" e "respondeu" pertencem a lugares distintos.

        Pedido pendente também entra, e é a única fonte que mostra algo antes
        de estar resolvido: enquanto a diretoria não decide, o histórico já
        explica por que a janela pode mudar.
        """
        linhas = []
        for escopo in escopos:
            for s in self.reajuste_repository.get_by_escopo(escopo.id):
                nome = nomes.get(escopo.id) or "escopo"

                # 1 · O pedido, com o texto do coordenador.
                linhas.append(
                    {
                        "id": f"pedido-dias:{s.id}",
                        "tipo": "pedido_de_dias",
                        "em": s.criado_em,
                        "por": s.solicitado_por,
                        "titulo": f"Pediu +{s.dias_solicitados} dias de ajuste — {nome}",
                        "detalhe": s.motivo,
                        "aguardando": s.status == "pendente",
                        # A tela ordena e agrupa por `alterado_em`; sem ele a
                        # linha entra como undefined e derruba o `localeCompare`.
                        "alterado_em": s.criado_em,
                        "alterado_por": s.solicitado_por,
                    }
                )

                # 2 · A decisão, com o texto da diretoria. Só depois de haver uma.
                if s.status == "pendente":
                    continue
                aprovado = s.status == "aprovado"
                veredito = "aprovados" if aprovado else "negados"
                linhas.append(
                    {
                        "id": f"ajuste:{s.id}",
                        "tipo": "dias_de_ajuste",
                        "em": s.respondido_em,
                        "por": s.respondido_por,
                        "titulo": f"+{s.dias_solicitados} dias de ajuste {veredito} — {nome}",
                        "detalhe": s.resposta_justificativa,
                        "aprovado": aprovado,
                        "alterado_em": s.respondido_em,
                        "alterado_por": s.respondido_por,
                    }
                )
        return linhas

    def _reunioes(self, projeto_id: int, nomes):
        """As anotações das reuniões (§6.4).

        Só as que TÊM texto. Uma reunião registrada sem observação já aparece
        na aba de reuniões e no calendário; repeti-la aqui vazia encheria a
        timeline de linhas que não contam nada. O que o histórico existe para
        guardar é o que foi combinado.
        """
        linhas = []
        for r in self.reuniao_repository.get_by_projeto(projeto_id):
            texto = (r.observacoes or "").strip()
            if not texto:
                continue
            alvo = nomes.get(r.projeto_escopo_id) if r.projeto_escopo_id else None
            # `criado_em` e não `data_reuniao`: a timeline conta quando a nota
            # foi escrita. O dia da reunião entra no título, que é onde ele
            # importa para quem lê.
            linhas.append(
                {
                    "id": f"reuniao:{r.id}",
                    "tipo": "reuniao",
                    "em": r.criado_em,
                    "por": r.registrado_por,
                    "titulo": (
                        f"Reunião de {r.data_reuniao.strftime('%d/%m/%Y')}"
                        + (f" — {alvo}" if alvo else "")
                    ),
                    "detalhe": texto,
                    "alterado_em": r.criado_em,
                    "alterado_por": r.registrado_por,
                }
            )
        return linhas

    def _alteracoes_de_entrega(self, projeto_id: int, nomes):
        """§13: cada vez que uma data de entrega prometida mudou.

        A primeira marcação também entra (com `data_anterior` nula): ela é o
        "de onde veio" da promessa, e sem ela o Histórico começaria a contar a
        história pela metade.
        """
        linhas = []
        for a in self.entrega_repository.get_by_projeto(projeto_id):
            alvo = nomes.get(a.projeto_escopo_id) if a.projeto_escopo_id else "cliente"
            rotulo = "Entrega registrada" if a.data_anterior is None else "Entrega alterada"
            linhas.append(
                {
                    "id": f"entrega:{a.id}",
                    "tipo": "entrega_alterada",
                    "em": a.criado_em,
                    "por": a.alterado_por,
                    "titulo": (
                        f"{rotulo} — {alvo or 'escopo'}: "
                        f"{_quando(a.data_anterior)} → {_quando(a.data_nova)}"
                    ),
                    "detalhe": a.justificativa,
                    # Preenchido quando a diretoria autorizou a mudança (§13).
                    "autorizado_por": a.autorizado_por,
                    "alterado_em": a.criado_em,
                    "alterado_por": a.alterado_por,
                }
            )
        return linhas


def _quando(valor) -> str:
    """A data como a tela lê. Banca tem hora; entrega é dia inteiro.

    Sem o `isinstance`, a entrega de 15/09 apareceria como "15/09/2026 00:00" —
    uma hora que ninguém marcou e que sugere precisão que o dado não tem.
    """
    if not valor:
        return "sem data"
    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y %H:%M")
    return valor.strftime("%d/%m/%Y")
