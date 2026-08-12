"""Serialização dos escopos vendidos, com a contagem do §5.4 já calculada.

O front nunca recalcula dias — recebe `consumidos`/`restantes` prontos. É o
mesmo princípio de `kickoff_pendente` em `serializar_projeto_resumo`: regra
derivada mora no backend, para as telas não divergirem entre si.
"""

from datetime import date
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from src.repositories.banca_escopo_repository import BancaEscopoRepository
from src.repositories.banca_repository import BancaRepository
from src.repositories.cronograma_repository import CronogramaEtapaRepository
from src.repositories.cronograma_reajuste_repository import CronogramaReajusteRepository
from src.repositories.dia_nao_letivo_repository import DiaNaoLetivoRepository
from src.repositories.escopo_repository import EscopoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.repositories.projeto_justificativa_atraso_repository import (
    ProjetoJustificativaAtrasoRepository,
)
from src.repositories.projeto_status_historico_repository import ProjetoStatusHistoricoRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.banca_status import calcular_status_banca
from src.utils.contagem_dias import calcular_contagem_projeto
from src.utils.janela_escopo import calcular_janela


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
        self.historico_repository = ProjetoStatusHistoricoRepository(db)
        self.dia_nao_letivo_repository = DiaNaoLetivoRepository(db)
        self.catalogo_repository = EscopoRepository(db)
        self.banca_repository = BancaRepository(db)
        self.banca_escopo_repository = BancaEscopoRepository(db)
        self.reajuste_repository = CronogramaReajusteRepository(db)
        self.etapa_repository = CronogramaEtapaRepository(db)
        self.usuario_repository = UsuarioRepository(db)
        self.justificativa_repository = ProjetoJustificativaAtrasoRepository(db)

    def execute(self, projeto_id: int, referencia: Optional[date] = None) -> List[dict]:
        escopos = self.repository.get_by_projeto(projeto_id)
        if not escopos:
            return []

        # Carrega o banco UMA vez e passa para as funções puras — é o contrato
        # que `dias_uteis.py` estabelece no docstring.
        historico = self.historico_repository.get_by_projeto(projeto_id)
        dias_nao_letivos = [d.data for d in self.dia_nao_letivo_repository.get_all()]
        catalogo = {e.id: e for e in self.catalogo_repository.get_all()}
        bancas = self.banca_repository.mapa_por_escopo([e.id for e in escopos])
        # Uma banca pode cobrir vários escopos — a tela mostra isso em cada
        # linha ("esta banca também avalia X"), então os ids vêm junto.
        escopos_da_banca = self.banca_escopo_repository.get_escopo_ids_por_banca(
            {b.id for b in bancas.values()}
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
        )
        janelas = {
            e.id: calcular_janela(
                e.data_inicio,
                e.dias_uteis_vendidos,
                e.dias_uteis_ajustados,
                dias_nao_letivos,
                referencia=referencia,
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
        "prazo_pedido_ajuste": janela.prazo_pedido_ajuste if janela else None,
        "pedido_ajuste_aberto": janela.pedido_ajuste_aberto if janela else False,
        # 🔒 A trava do §5.5 na forma que a tela precisa: o cadeado abre
        # quando a banca do escopo é REALIZADA.
        "banca": (
            {
                "id": banca.id,
                "data_hora": banca.data_hora,
                "realizado_em": banca.realizado_em,
                "resultado": banca.resultado,
                "status": calcular_status_banca(banca.data_hora, banca.realizado_em),
                # Todos os escopos que esta banca cobre, este incluído.
                "escopo_ids": (escopos_da_banca or {}).get(banca.id, [escopo.id]),
            }
            if banca
            else None
        ),
        "entrega_liberada": bool(banca and banca.realizado_em),
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
