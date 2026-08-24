"""Serialização dos escopos vendidos, com a contagem do §5.4 já calculada.

O front nunca recalcula dias — recebe `consumidos`/`restantes` prontos. É o
mesmo princípio de `kickoff_pendente` em `serializar_projeto_resumo`: regra
derivada mora no backend, para as telas não divergirem entre si.
"""

from datetime import date
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from src.repositories.banca_escopo_repository import BancaEscopoRepository
from src.repositories.banca_sessao_repository import BancaSessaoRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.cronograma_repository import CronogramaEtapaRepository
from src.repositories.cronograma_reajuste_repository import CronogramaReajusteRepository
from src.repositories.dia_nao_letivo_repository import DiaNaoLetivoRepository
from src.repositories.escopo_repository import EscopoRepository
from src.repositories.frente_repository import FrenteRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_justificativa_atraso_repository import (
    ProjetoJustificativaAtrasoRepository,
)
from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.projeto_status_historico_repository import ProjetoStatusHistoricoRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.banca_status import calcular_status_banca
from src.utils.calendario_variante import (
    apenas_globais,
    escolha_por_frente,
    filtrar_variante,
)
from src.utils.contagem_dias import calcular_contagem_projeto, derivar_janelas_pausa
from src.utils.janela_escopo import (
    calcular_janela,
    prazo_pelo_kickoff,
    primeiro_escopo_id,
)


def nome_do_escopo(escopo, catalogo_por_id: Dict[int, object]) -> str:
    """"Outro" = nome digitado; senão, o nome do catálogo.

    Derivado na leitura, nunca gravado duas vezes — renomear o catálogo não
    deixa cópias velhas para trás.
    """
    if escopo.nome_customizado:
        return escopo.nome_customizado
    do_catalogo = catalogo_por_id.get(escopo.escopo_id)
    return do_catalogo.nome if do_catalogo else "(escopo removido)"


class ListTodosEscoposVendidosUseCase:
    """Só `{id, projeto_id, nome}` de TODOS os projetos — sem a contagem de
    dias (cara, e não faz sentido fora do contexto de um projeto só).

    Existe para a página Bancas resolver `banca.projeto_escopo_ids` em nomes:
    ela lista bancas de todos os projetos ao mesmo tempo, então não dá pra
    pedir escopo por escopo com `GET /projetos/{id}/escopos` (que exige saber
    o projeto e checa o recorte de visão dele). Bancas já é global — quem
    pode ver a lista de bancas já vê projeto e escopo de qualquer uma."""

    def __init__(self, db: Session):
        self.repository = ProjetoEscopoRepository(db)
        self.catalogo_repository = EscopoRepository(db)

    def execute(self) -> List[dict]:
        escopos = self.repository.get_all()
        catalogo = {e.id: e for e in self.catalogo_repository.get_all()}
        return [
            {"id": e.id, "projeto_id": e.projeto_id, "nome": nome_do_escopo(e, catalogo)}
            for e in escopos
        ]


class ListEscoposProjetoUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjetoEscopoRepository(db)
        self.projeto_repository = ProjetoRepository(db)
        self.historico_repository = ProjetoStatusHistoricoRepository(db)
        self.dia_nao_letivo_repository = DiaNaoLetivoRepository(db)
        self.frente_repository = FrenteRepository(db)
        self.catalogo_repository = EscopoRepository(db)
        self.banca_repository = BancaRepository(db)
        self.banca_escopo_repository = BancaEscopoRepository(db)
        self.sessao_repository = BancaSessaoRepository(db)
        self.reajuste_repository = CronogramaReajusteRepository(db)
        self.etapa_repository = CronogramaEtapaRepository(db)
        self.usuario_repository = UsuarioRepository(db)
        self.justificativa_repository = ProjetoJustificativaAtrasoRepository(db)

    def execute(self, projeto_id: int, referencia: Optional[date] = None) -> List[dict]:
        escopos = self.repository.get_by_projeto(projeto_id)
        if not escopos:
            return []

        # ⭐ Arquivar também para a contagem, do mesmo jeito que Pausado —
        # mas arquivar não é um STATUS (é `arquivado_em`, um timestamp à
        # parte, que não passa por `projeto_status_historico`), então não
        # dá pra reaproveitar `derivar_janelas_pausa`. O jeito mais simples e
        # sem risco de descontar a mesma janela duas vezes é travar a
        # REFERÊNCIA no dia do arquivamento: tudo daqui pra baixo já enxerga
        # "hoje" como aquele dia, e o resto da conta (pausas inclusive)
        # continua funcionando sem mudar mais nada.
        projeto = self.projeto_repository.get_by_id(projeto_id)
        referencia = referencia or date.today()
        if projeto and projeto.arquivado_em:
            referencia = min(referencia, projeto.arquivado_em.date())

        # Carrega o banco UMA vez e passa para as funções puras — é o contrato
        # que `dias_uteis.py` estabelece no docstring.
        historico = self.historico_repository.get_by_projeto(projeto_id)
        dias_nao_letivos_registros = self.dia_nao_letivo_repository.get_all()
        # Uma frente pode ter mais de um calendário, e este projeto segue um
        # só. Sem o corte, um time de Ciência da Computação contaria como
        # parada a semana de provas das engenharias, que está na mesma frente.
        escolhidos = escolha_por_frente(
            self.frente_repository.get_all(),
            getattr(projeto, "calendario", None) if projeto else None,
        )
        dias_nao_letivos_registros = filtrar_variante(dias_nao_letivos_registros, escolhidos)
        dias_nao_letivos = [d.data for d in dias_nao_letivos_registros]
        catalogo = {e.id: e for e in self.catalogo_repository.get_all()}
        bancas = self.banca_repository.mapa_por_escopo([e.id for e in escopos])
        # Uma banca pode cobrir vários escopos — a tela mostra isso em cada
        # linha ("esta banca também avalia X"), então os ids vêm junto.
        escopos_da_banca = self.banca_escopo_repository.get_escopo_ids_por_banca(
            {b.id for b in bancas.values()}
        )
        # ⭐ As TENTATIVAS de cada banca (§9). O cronograma precisa delas para
        # pintar a 1ª e a 2ª banca em dias diferentes: a linha de `banca` só
        # guarda a tentativa CORRENTE, então uma banca reprovada e remarcada
        # some do dia em que de fato aconteceu.
        sessoes_por_banca = self.sessao_repository.get_by_bancas(
            [b.id for b in bancas.values()]
        )

        # As etapas entram na conta por causa das correalho pós-entrega (§11):
        # é o que foi PINTADO depois da entrega, e não dá para saber isso sem
        # olhar os intervalos.
        etapas_por_escopo = {}
        for etapa in self.etapa_repository.get_by_escopos([e.id for e in escopos]):
            etapas_por_escopo.setdefault(etapa.projeto_escopo_id, []).append(etapa)

        contagens = calcular_contagem_projeto(
            escopos,
            historico,
            dias_nao_letivos,
            referencia=referencia,
            etapas_por_escopo=etapas_por_escopo,
            bancas_por_escopo=bancas,
            # As tentativas: é a PRIMEIRA realização que congela a contagem e
            # abre as correções (§11), não a tentativa corrente.
            sessoes_por_banca=sessoes_por_banca,
        )
        # ⚠ Com as janelas de pausa, como no use case que DECIDE o pedido
        # (`solicitar._janela`): sem elas, o prazo servido aqui vencia antes
        # do prazo que o backend de fato aplica num projeto que já esteve
        # ⏸ Pausado — o botão sumia da tela com o pedido ainda aberto.
        janelas_pausa = derivar_janelas_pausa(historico)

        # ⭐ §8: o PRIMEIRO escopo vendido pede dias até o último dia da
        # ambientação (o kickoff); os demais, nos 3 dias úteis da reunião
        # inicial deles. Mesma decisão de `solicitar._prazo_do_kickoff` — aqui
        # ela só é servida à tela, que é quem some com o botão.
        primeiro_id = primeiro_escopo_id(escopos)
        prazo_kickoff = (
            prazo_pelo_kickoff(
                projeto.status,
                projeto.data_inicio_ambientacao or projeto.data_kickoff,
                projeto.dias_ambientacao,
                # O recorte GLOBAL: a ambientação é do projeto inteiro, e dia
                # global não pertence a frente nem a calendário de curso.
                [d.data for d in apenas_globais(dias_nao_letivos_registros)],
            )
            if projeto
            else None
        )
        janelas = {
            e.id: calcular_janela(
                e.data_inicio,
                e.dias_uteis_vendidos,
                e.dias_uteis_ajustados,
                dias_nao_letivos,
                referencia=referencia,
                janelas_pausa=janelas_pausa,
                prazo_do_kickoff=prazo_kickoff if e.id == primeiro_id else None,
            )
            for e in escopos
        }

        # §8: pedido pendente do escopo, pra tela decidir entre "Pedir dias" e
        # "Aguardando a diretoria" sem precisar perguntar de novo.
        pendentes = {
            e.id: self.reajuste_repository.get_pendente_do_escopo(e.id) for e in escopos
        }
        nomes_usuario = {u.id: u.nome for u in self.usuario_repository.get_all()}

        # §7.4/§10: a nota do atraso de JANELA de cada escopo — a mais recente,
        # que é a que a tela mostra. Uma consulta só para o projeto inteiro; as
        # anteriores continuam no Histórico, que é o registro completo.
        justificativas = {}
        for j in self.justificativa_repository.get_by_projeto(projeto_id):
            if j.tipo == "escopo" and j.projeto_escopo_id is not None:
                atual = justificativas.get(j.projeto_escopo_id)
                if atual is None or j.registrado_em > atual.registrado_em:
                    justificativas[j.projeto_escopo_id] = j

        return [
            serializar_escopo(
                e,
                contagens[e.id],
                catalogo,
                bancas.get(e.id),
                escopos_da_banca,
                sessoes_por_banca,
                pendentes.get(e.id),
                nomes_usuario,
                janelas.get(e.id),
                justificativas.get(e.id),
            )
            for e in escopos
        ]


def serializar_escopo(
    escopo,
    contagem,
    catalogo_por_id,
    banca=None,
    escopos_da_banca=None,
    sessoes_por_banca=None,
    reajuste_pendente=None,
    nomes_usuario=None,
    janela=None,
    justificativa_atraso=None,
) -> dict:
    return {
        "id": escopo.id,
        "projeto_id": escopo.projeto_id,
        "escopo_id": escopo.escopo_id,
        "nome_customizado": escopo.nome_customizado,
        "nome": nome_do_escopo(escopo, catalogo_por_id),
        "frente_id": escopo.frente_id,
        "ordem": escopo.ordem,
        "dias_uteis_vendidos": escopo.dias_uteis_vendidos,
        "dias_uteis_ajustados": escopo.dias_uteis_ajustados,
        "status": escopo.status,
        "data_inicio": escopo.data_inicio,
        "data_entrega_planejada": escopo.data_entrega_planejada,
        "data_entrega_real": escopo.data_entrega_real,
        "tipo_atraso_entrega": escopo.tipo_atraso_entrega,
        # A contagem do §5.4, calculada — o front só desenha a barra.
        "consumidos": contagem.consumidos,
        "restantes": contagem.restantes,
        "estourou": contagem.estourou,
        "em_contagem": contagem.em_contagem,
        # ⭐ Os cinco números do escopo (§15): vendidos · ajustados ·
        # consumidos · atraso · correções. Derivados aqui para as telas nunca
        # divergirem entre si — mesmo princípio de `consumidos`.
        "atraso": contagem.atraso,
        # ⭐ §7.4: o "porquê" do atraso acima, escrito por quem conduz o
        # projeto. `None` = ainda não justificado, e é isso que faz o card
        # "Escopos vendidos" pedir a nota em vez de só mostrar o número.
        #
        # Só a MAIS RECENTE: a tela responde "este atraso está explicado?", que
        # é pergunta de uma resposta só. O histórico completo das notas fica no
        # Histórico do projeto, que é onde ele serve.
        "justificativa_atraso": (
            {
                "id": justificativa_atraso.id,
                "texto": justificativa_atraso.texto,
                "registrado_por": (nomes_usuario or {}).get(
                    justificativa_atraso.registrado_por
                ),
                "registrado_em": justificativa_atraso.registrado_em,
            }
            if justificativa_atraso
            else None
        ),
        "correcoes": contagem.correcoes,
        # A janela do §5, para o calendário desenhar a faixa e o banner saber
        # quando avisar.
        "fim_janela": contagem.fim_janela_prevista,
        # ⭐ O prazo do §8 já vem decidido pela `janela`: último dia da
        # ambientação no primeiro escopo, 3 dias úteis da reunião inicial nos
        # demais. Não há mais um OU com a ambientação aqui — a exceção virou a
        # própria régua, e duplicá-la era o que fazia a tela e
        # `solicitar._exigir_prazo_aberto` discordarem sobre o mesmo escopo.
        "prazo_pedido_ajuste": janela.prazo_pedido_ajuste if janela else None,
        "pedido_ajuste_aberto": janela.pedido_ajuste_aberto if janela else False,
        # 🔒 A trava do §5.5 na forma que a tela precisa: o cadeado abre
        # quando a banca do escopo é APROVADA pelos avaliadores.
        "banca": (
            {
                "id": banca.id,
                "data_hora": banca.data_hora,
                "realizado_em": banca.realizado_em,
                "resultado": banca.resultado,
                "status": calcular_status_banca(banca.data_hora, banca.realizado_em),
                # Todos os escopos que esta banca cobre, este incluído.
                "escopo_ids": (escopos_da_banca or {}).get(banca.id, [escopo.id]),
                # ⭐ Cada TENTATIVA, da primeira à atual (§9).
                #
                # `banca.data_hora` é só a tentativa CORRENTE. Sem esta lista, a
                # banca que foi reprovada e remarcada desaparecia do dia em que
                # aconteceu — o cronograma mostrava só a data nova, como se a
                # primeira nunca tivesse existido.
                "sessoes": [
                    {
                        "id": s.id,
                        "numero": s.numero,
                        "data_hora": s.data_hora,
                        "realizado_em": s.realizado_em,
                        "resultado": s.resultado,
                        # `encerrada_em` preenchido = tentativa arquivada; a
                        # corrente é a única sem ele.
                        "encerrada_em": s.encerrada_em,
                    }
                    for s in sorted(
                        (sessoes_por_banca or {}).get(banca.id, []),
                        key=lambda x: x.numero,
                    )
                ],
            }
            if banca
            else None
        ),
        # ⚠ Espelha `update_escopo_projeto`: se divergirem, a tela mostra o
        # cadeado aberto e o clique volta 422 — o pior dos dois mundos.
        "entrega_liberada": bool(banca and banca.realizado_em and banca.resultado == "aprovada"),
        # ⭐ O carimbo da confirmação (§5.5) — é ela, não a data, que move o
        # status para "entregue". A tela usa isto para saber se ainda falta o
        # ato: data marcada + banca aprovada + sem confirmação = botão aparece.
        "entrega_confirmada_em": escopo.entrega_confirmada_em,
        "entrega_confirmada_por": (nomes_usuario or {}).get(escopo.entrega_confirmada_por),
        "reajuste_pendente": (
            {
                "id": reajuste_pendente.id,
                "dias_solicitados": reajuste_pendente.dias_solicitados,
                "motivo": reajuste_pendente.motivo,
                "solicitado_por": reajuste_pendente.solicitado_por,
                "solicitado_por_nome": (nomes_usuario or {}).get(reajuste_pendente.solicitado_por),
                "criado_em": reajuste_pendente.criado_em,
            }
            if reajuste_pendente
            else None
        ),
    }
