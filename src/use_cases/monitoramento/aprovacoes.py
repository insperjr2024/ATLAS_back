"""⭐ A fila da diretoria — tudo que espera uma decisão dela, num lugar só.

O problema que isto resolve não é de dado, é de descoberta: as decisões da
diretoria estavam espalhadas por três telas diferentes, cada uma exigindo que
ela lembrasse de passar lá. O pedido de dias vivia num card da Visão geral, a
justificativa de atraso na aba Atrasos, e a classificação de entrega em lugar
nenhum. Fila que ninguém sabe que existe é fila parada — foi assim que dois
pedidos ficaram semanas represados sem ninguém notar.

⚠ **Nem toda ação restrita à diretoria é uma aprovação.** Criar formulário,
configurar coluna do kanban e excluir usuário também exigem `require_diretor_projetos`,
e nenhuma delas entra aqui: são coisas que ela FAZ quando quer, não coisas que
esperam por ela. O critério desta fila é ter alguém do outro lado bloqueado
enquanto ela não responde.

São SEIS, e cada uma tem um bloqueio concreto atrás:

1. **Pedidos de dias de ajuste** (§8) — o coordenador não consegue pintar
   além da janela enquanto não houver resposta.
2. **Atrasos sem justificativa** (§7.4) — o projeto fica vermelho no
   monitoramento sem que ninguém saiba o porquê.
3. **Solicitações de entrada em projeto** — alguém pediu para entrar e está
   parado esperando; o projeto segue com a vaga aberta.
4. **Bancas realizadas sem resultado** (§5.5) — a banca aconteceu e ninguém
   registrou o veredito.
5. **Exceções de choque de horário** (§8) — duas bancas no mesmo horário,
   e só a diretoria libera.
6. **Bancas fora da janela do escopo** (§13) — a data pretendida passa do
   vendido + ajustado, e só a diretoria autoriza.

⚠ Havia uma sétima, "entregas sem classificação", removida em 2026-08-12 junto
com o atraso de entrega nos insights: sem a métrica que separava interno de
agenda do cliente, a classificação deixou de mudar qualquer número.

⚠ **A fila mostra as seis SEMPRE**, mesmo vazias — quem abre precisa saber o
que esta tela cobre, e uma tela que só aparece quando há problema não ensina
ninguém a confiar nela. Quem decide isso é o front; o backend sempre devolve
as seis chaves.
"""

from datetime import date, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from src.models.projeto_model import ProjetoModel
from src.repositories.avaliacao_repository import AvaliacaoRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.candidatura_repository import CandidaturaRepository
from src.repositories.cronograma_reajuste_repository import CronogramaReajusteRepository
from src.repositories.dia_nao_letivo_repository import DiaNaoLetivoRepository
from src.repositories.justificativa_pedido_repository import JustificativaPedidoRepository
from src.repositories.escopo_repository import EscopoRepository
from src.repositories.frente_repository import FrenteRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_justificativa_atraso_repository import (
    ProjetoJustificativaAtrasoRepository,
)
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.banca.excecao_choque import ListarExcecoesChoquePendentesUseCase
from src.use_cases.banca.fora_janela import ListarForaJanelaPendentesUseCase
from src.use_cases.projeto_escopo.get_escopos_projeto import nome_do_escopo
from src.utils.apuracao_banca import apurar, eleitorado, votos_por_avaliador
from src.utils.atraso_monitoramento import calcular_atraso_projeto, justificativa_cobrindo
from src.utils.avaliacoes_pendentes import PRAZO_AVALIACAO_DIAS
from src.utils.calendario_variante import escolha_por_frente, filtrar_variante
from src.utils.janela_escopo import calcular_janela


def _agrupar_por(linhas, campo: str) -> dict:
    """Lista → {chave: [linhas]}. O par dos `get_by_bancas` em lote."""
    mapa: dict = {}
    for linha in linhas:
        mapa.setdefault(getattr(linha, campo), []).append(linha)
    return mapa


def _pedido_do_motivo(pedidos, motivo):
    """A data em que a diretoria cobrou ESTE motivo — ou `None`.

    Mesma régua de especificidade de `justificativa_cobrindo`, de trás para
    frente: um pedido geral do projeto cobre qualquer motivo; um pedido do
    escopo cobre os motivos daquele escopo; um pedido com tipo cobre só o
    mesmo tipo.
    """
    for p in pedidos:
        if p.projeto_escopo_id is not None and p.projeto_escopo_id != motivo.projeto_escopo_id:
            continue
        if p.tipo is not None and p.tipo != motivo.tipo:
            continue
        return p.solicitado_em
    return None


class ListarAprovacoesPendentesUseCase:
    """Monta a fila. Sem recorte de visão: a diretoria enxerga tudo (§3)."""

    def __init__(self, db: Session):
        self.db = db
        self.projeto_repository = ProjetoRepository(db)
        self.escopo_repository = ProjetoEscopoRepository(db)
        self.catalogo_repository = EscopoRepository(db)
        self.banca_repository = BancaRepository(db)
        self.reajuste_repository = CronogramaReajusteRepository(db)
        self.justificativa_repository = ProjetoJustificativaAtrasoRepository(db)
        self.usuario_repository = UsuarioRepository(db)
        self.candidatura_repository = CandidaturaRepository(db)
        self.avaliacao_repository = AvaliacaoRepository(db)
        self.dia_nao_letivo_repository = DiaNaoLetivoRepository(db)
        self.frente_repository = FrenteRepository(db)
        self.pedido_repository = JustificativaPedidoRepository(db)

    def execute(self, current_user=None, referencia: Optional[date] = None) -> dict:
        hoje = referencia or date.today()

        # Arquivado e finalizado saem da fila: decidir sobre projeto encerrado
        # não destrava ninguém, e a lista precisa caber numa tela.
        projetos = [
            p
            for p in self.db.query(ProjetoModel).all()
            if p.status != "finalizado" and not getattr(p, "arquivado_em", None)
        ]
        por_id = {p.id: p for p in projetos}
        escopos = self.escopo_repository.get_by_projetos(list(por_id))
        catalogo = {e.id: e for e in self.catalogo_repository.get_all()}
        nomes_escopo = {e.id: nome_do_escopo(e, catalogo) for e in escopos}
        nomes_usuario = {u.id: u.nome for u in self.usuario_repository.get_all()}

        # Uma vez, para as filas que medem dia útil (§5.4). Sem isto a
        # projeção do pedido de dias contaria feriado como dia de trabalho.
        #
        # Vêm os REGISTROS, e o corte por curso acontece dentro de cada fila:
        # uma frente pode ter mais de um calendário, e a fila mistura projetos
        # de cursos diferentes. Resolver aqui daria a todos o calendário de um.
        registros_nao_letivos = self.dia_nao_letivo_repository.get_all()
        frentes = self.frente_repository.get_all()

        def dias_do_projeto(projeto):
            escolhidos = escolha_por_frente(frentes, getattr(projeto, "calendario", None))
            return [d.data for d in filtrar_variante(registros_nao_letivos, escolhidos)]

        dias = self._dias_de_ajuste(escopos, por_id, nomes_escopo, nomes_usuario, dias_do_projeto)
        atrasos = self._atrasos_sem_justificativa(
            projetos, escopos, nomes_escopo, hoje, dias_do_projeto
        )
        entradas = self._solicitacoes_de_entrada(current_user)
        sem_resultado = self._bancas_sem_resultado(escopos, por_id, nomes_escopo, hoje)
        # ⭐ §8: quem quer marcar banca num horário já ocupado pede aqui, e a
        # diretoria decide. Antes o bloqueio existia sem via de exceção — a
        # regra era anunciada e não havia como cumpri-la.
        choques = ListarExcecoesChoquePendentesUseCase(self.db).execute()
        # ⭐ §13: mesma lógica, para banca fora da janela do escopo. Antes só
        # quem tinha `posicao == "diretor"` conseguia marcar, sozinho, na
        # mesma chamada — pedido e decisão eram o mesmo clique. Agora quem
        # marca pede aqui, e esta fila é onde a diretoria decide.
        fora_janela = ListarForaJanelaPendentesUseCase(self.db).execute()

        # ⚠ Havia aqui uma quinta fila, `entregas_sem_classificacao`: as
        # entregas atrasadas ainda não marcadas como atraso interno ou por
        # agenda do cliente. Removida em 2026-08-12, junto com o que lhe dava
        # sentido — o atraso de ENTREGA saiu dos insights, e com ele a métrica
        # que separava os dois tipos. A fila continuava cobrando da diretoria
        # uma classificação que não mudava mais número nenhum.
        return {
            "dias_de_ajuste": dias,
            "atrasos_sem_justificativa": atrasos,
            "solicitacoes_de_entrada": entradas,
            "bancas_sem_resultado": sem_resultado,
            "excecoes_de_choque": choques,
            "bancas_fora_da_janela": fora_janela,
            # O total é servido pronto porque o badge da aba precisa dele antes
            # de qualquer render — somar no front daria a mesma conta em dois
            # lugares, e é a que sai errada quando nasce uma fila nova.
            "total": (
                len(dias)
                + len(atrasos)
                + len(entradas)
                + len(sem_resultado)
                + len(choques)
                + len(fora_janela)
            ),
        }

    def _solicitacoes_de_entrada(self, current_user) -> List[dict]:
        """Quem pediu para entrar num projeto e ainda espera resposta.

        ⭐ Passa no critério da fila com folga: tem uma PESSOA parada do outro
        lado, e o projeto segue com a vaga aberta. Vivia só na tela "Vagas em
        projetos" — quem não passasse por lá não sabia que alguém esperava.

        Delega para `listar_para_decisao`, que é o mesmo caminho da tela de
        Vagas: o recorte de quem pode responder é regra de negócio e não pode
        ter duas implementações. Filtra só os pendentes — os já respondidos
        seguem visíveis lá, como histórico.

        ⚠ Chamava `listar_do_coordenador`, que a main renomeou e dividiu em
        dois quando a decisão sobre pedidos de vaga saiu do coordenador e foi
        para gerência e diretoria (2026-08-12): `listar_projetos_coordenados` é
        a visão SÓ-LEITURA do coordenador, e `listar_para_decisao` é a de quem
        pode responder. Esta aba é a fila de quem DECIDE, então é a segunda —
        usar a primeira encheria a fila da diretoria com pedidos que ela vê mas
        não pode responder.
        """
        if current_user is None:
            return []

        from src.use_cases.solicitacao_projeto.solicitacao_projeto import (
            SolicitacaoProjetoUseCase,
        )

        pedidos = SolicitacaoProjetoUseCase(self.db).listar_para_decisao(current_user)
        return [p for p in pedidos if p["status"] == "pendente"]

    def _bancas_sem_resultado(self, escopos, por_id, nomes_escopo, hoje: date) -> List[dict]:
        """§5.5: a banca aconteceu e ninguém registrou o veredito.

        ⭐ **Esta fila virou o bloqueio mais duro do sistema.** Enquanto não há
        veredito, a entrega ao cliente NÃO libera (`RegistrarEntregaEscopoUseCase`):
        o escopo fica parado esperando alguém agir. O caminho normal é o voto
        dos avaliadores, que apura sozinho; o que cai aqui é o que o voto não
        resolveu — ninguém votou e o prazo venceu — e só a diretoria destrava,
        registrando o resultado à mão.

        ⭐ **A urna vem junto.** Sem ela a linha dizia só "projeto — escopo,
        realizada em 22/07", e as duas situações que exigem respostas OPOSTAS
        ficavam idênticas na tela: *ninguém votou e o prazo venceu* (a
        diretoria precisa decidir no lugar deles) e *falta um voto e o prazo
        corre* (a diretoria precisa cobrar, não decidir). É a diferença entre
        registrar um veredito legítimo e atropelar uma votação em curso.

        Só bancas de escopo (as legadas, sem vínculo, não têm projeto para
        cobrar) e só de projeto vivo — o recorte de `execute`.
        """
        # `mapa_por_escopo` em vez de uma consulta por escopo: é a mesma
        # pergunta que `_atrasos_sem_justificativa` já faz em lote.
        bancas_por_escopo = self.banca_repository.mapa_por_escopo([e.id for e in escopos])
        por_banca: dict = {}
        for escopo in escopos:
            banca = bancas_por_escopo.get(escopo.id)
            if not banca or not banca.realizado_em or banca.resultado:
                continue
            # ⚠ Uma banca pode cobrir vários escopos, e é UMA linha na fila —
            # mas os escopos todos entram nela: a decisão destrava a entrega
            # de cada um, e mostrar só o primeiro escondia os outros.
            por_banca.setdefault(banca.id, [banca, []])[1].append(escopo)

        ids = list(por_banca)
        candidaturas = _agrupar_por(self.candidatura_repository.get_by_bancas(ids), "banca_id")
        avaliacoes = _agrupar_por(self.avaliacao_repository.get_by_bancas(ids), "banca_id")

        linhas = []
        for banca_id, (banca, escopos_da_banca) in por_banca.items():
            primeiro = escopos_da_banca[0]
            projeto = por_id.get(primeiro.projeto_id)
            prazo = (banca.realizado_em + timedelta(days=PRAZO_AVALIACAO_DIAS)).date()
            vencido = hoje > prazo

            submetidas = [
                a
                for a in avaliacoes.get(banca_id, [])
                if a.status == "submetida" and a.voto_aprovacao is not None
            ]
            votos = list(votos_por_avaliador(submetidas).values())
            esperados = eleitorado(candidaturas.get(banca_id, []), [v.avaliador_id for v in votos])
            apuracao = apurar([v.voto_aprovacao for v in votos], esperados, prazo_vencido=vencido)

            linhas.append(
                {
                    "banca_id": banca_id,
                    "projeto_id": primeiro.projeto_id,
                    "projeto_nome": projeto.nome if projeto else "",
                    # Mantido no singular para não quebrar quem já lê o campo;
                    # `escopos` abaixo é a lista completa.
                    "escopo_nome": nomes_escopo.get(primeiro.id, "escopo"),
                    "escopos": [
                        {"projeto_escopo_id": e.id, "nome": nomes_escopo.get(e.id, "escopo")}
                        for e in escopos_da_banca
                    ],
                    "realizado_em": banca.realizado_em,
                    "prazo_avaliacao_em": prazo,
                    "prazo_vencido": vencido,
                    # ⭐ O que a diretoria precisa saber ANTES de dar o veredito
                    # no lugar dos avaliadores.
                    "apuracao": {
                        "recebidos": apuracao.recebidos,
                        "esperados": apuracao.esperados,
                        "aprovacoes": apuracao.aprovacoes,
                        "reprovacoes": apuracao.reprovacoes,
                        "motivo": apuracao.motivo,
                    },
                }
            )
        # A mais antiga primeiro: é a que está esperando há mais tempo.
        return sorted(linhas, key=lambda x: x["realizado_em"])

    def _dias_de_ajuste(
        self, escopos, por_id, nomes_escopo, nomes_usuario, dias_do_projeto
    ) -> List[dict]:
        """§8: o coordenador pediu, a janela não cresce até ela responder.

        ⭐ **Vem com a projeção, não só com o estado.** A linha dizia
        "+5 dias sobre 8 vendidos" e deixava a conta para a diretoria fazer de
        cabeça — e a conta não é somar, é caminhar 13 dias ÚTEIS a partir da
        reunião inicial pulando feriado, prova e recesso. `fim_se_aprovar`
        responde a pergunta que a decisão faz de verdade: *até quando o escopo
        vai, se eu disser sim?*

        ⚠ Uma consulta em lote (`get_pendentes`) em vez de uma por escopo: o
        laço antigo fazia N consultas para achar, em geral, um pedido só.
        """
        pendentes = {p.projeto_escopo_id: p for p in self.reajuste_repository.get_pendentes()}
        linhas = []
        for escopo in escopos:
            pendente = pendentes.get(escopo.id)
            if not pendente:
                continue
            projeto = por_id.get(escopo.projeto_id)
            dias_nao_letivos = dias_do_projeto(projeto)
            janela_hoje = calcular_janela(
                escopo.data_inicio,
                escopo.dias_uteis_vendidos,
                escopo.dias_uteis_ajustados,
                dias_nao_letivos,
            )
            janela_se_aprovar = calcular_janela(
                escopo.data_inicio,
                escopo.dias_uteis_vendidos,
                escopo.dias_uteis_ajustados + pendente.dias_solicitados,
                dias_nao_letivos,
            )
            linhas.append(
                {
                    "id": pendente.id,
                    "projeto_id": escopo.projeto_id,
                    "projeto_nome": projeto.nome if projeto else "",
                    "escopo_nome": nomes_escopo.get(escopo.id, "escopo"),
                    "dias_solicitados": pendente.dias_solicitados,
                    "dias_vendidos": escopo.dias_uteis_vendidos,
                    "dias_ajustados": escopo.dias_uteis_ajustados,
                    "motivo": pendente.motivo,
                    "solicitado_por": pendente.solicitado_por,
                    "solicitado_por_nome": nomes_usuario.get(pendente.solicitado_por),
                    "criado_em": pendente.criado_em,
                    # O antes e o depois, lado a lado. `None` quando o escopo
                    # ainda não teve reunião inicial e não há janela nenhuma.
                    "fim_janela": janela_hoje.fim,
                    "fim_se_aprovar": janela_se_aprovar.fim,
                    "prazo_pedido_ajuste": janela_hoje.prazo_pedido_ajuste,
                }
            )
        return sorted(linhas, key=lambda x: x["criado_em"])

    def _atrasos_sem_justificativa(
        self, projetos, escopos, nomes_escopo, hoje: date, dias_do_projeto
    ) -> List[dict]:
        """§7.4: o alerta é automático, o porquê é ela quem digita.

        ⭐ **Os motivos vêm inteiros, não como frases.** A linha mandava
        `[m.descricao for m in atraso.motivos]` e virava um texto corrido —
        sem saber QUAL escopo atrasou nem quantos dias cada um, a diretoria
        não tinha como escrever uma nota específica sem abrir o projeto. Com o
        motivo estruturado, cada um vira uma linha com seu próprio botão de
        justificar, que é como a aba Atrasos já faz.

        ⚠ **Duas correções de régua entram aqui**, e as duas faziam esta fila
        discordar da aba Atrasos sobre o mesmo projeto:

        1. `dias_nao_letivos` passa a ser informado. Sem ele, feriado, prova e
           recesso contavam como dia útil só nesta fila (§5.4).
        2. A cobertura é POR MOTIVO (`justificativa_cobrindo`), não um set de
           `projeto_id`. Uma nota antiga sobre um escopo já entregue tirava da
           fila um atraso novo de outro escopo — que seguia vermelho ao lado.

        ⚠ A segunda faz a fila CRESCER: reaparece o que estava indevidamente
        coberto. É o comportamento correto, e não uma regressão.
        """
        por_projeto: dict = {}
        for e in escopos:
            por_projeto.setdefault(e.projeto_id, []).append(e)
        # `mapa_por_escopo` e não a lista: a banca passou a cobrir vários
        # escopos (tabela de junção), e a pergunta aqui é sempre "qual a banca
        # DESTE escopo".
        bancas = self.banca_repository.mapa_por_escopo([e.id for e in escopos])
        justificativas: dict = {}
        for j in self.justificativa_repository.get_by_projetos([p.id for p in projetos]):
            justificativas.setdefault(j.projeto_id, []).append(j)
        # §7.4: o que a diretoria JÁ cobrou e ainda não foi respondido. Sem
        # isto ela reabre a fila na semana seguinte sem saber se aquele atraso
        # já tinha sido perguntado — e pergunta de novo.
        pedidos: dict = {}
        for pedido in self.pedido_repository.get_abertos_por_projetos([p.id for p in projetos]):
            pedidos.setdefault(pedido.projeto_id, []).append(pedido)

        linhas = []
        for projeto in projetos:
            atraso = calcular_atraso_projeto(
                projeto.id,
                por_projeto.get(projeto.id, []),
                bancas,
                nomes_escopo,
                dias_nao_letivos=dias_do_projeto(projeto),
                referencia=hoje,
            )
            if not atraso.atrasado:
                continue

            das_do_projeto = justificativas.get(projeto.id, [])
            motivos = []
            for m in atraso.motivos:
                cobrindo = justificativa_cobrindo(m, das_do_projeto)
                motivos.append(
                    {
                        "tipo": m.tipo,
                        "descricao": m.descricao,
                        "dias": m.dias,
                        "escopo": m.escopo_nome,
                        "projeto_escopo_id": m.projeto_escopo_id,
                        "data_referencia": m.data_referencia,
                        "justificado": cobrindo is not None,
                        "justificativa_id": cobrindo.id if cobrindo else None,
                        # `None` = ninguém cobrou ainda; com data = esperando o
                        # coordenador desde então.
                        "pedido_em": _pedido_do_motivo(pedidos.get(projeto.id, []), m),
                    }
                )
            # Projeto com TODOS os motivos já respondidos sai da fila: não há o
            # que cobrar. Basta um descoberto para ele continuar aqui.
            pendentes = [m for m in motivos if not m["justificado"]]
            if not pendentes:
                continue

            linhas.append(
                {
                    "projeto_id": projeto.id,
                    "projeto_nome": projeto.nome,
                    "status": projeto.status,
                    "dias_totais": atraso.dias_totais,
                    # ⭐ O PIOR motivo isolado, nunca a soma: três escopos com
                    # 4 dias viravam "12" sem nada estar parado há 12 dias.
                    "pior_motivo": max((m["dias"] for m in motivos), default=0),
                    "motivos": motivos,
                }
            )
        # O pior primeiro, como na aba Atrasos; a soma é o desempate.
        return sorted(linhas, key=lambda x: (-x["pior_motivo"], -x["dias_totais"]))
