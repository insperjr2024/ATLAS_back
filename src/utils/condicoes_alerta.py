"""As 🔄 condições que viram alerta — detectadas, nunca gravadas.

Duas telas fazem a mesma pergunta e precisam da mesma resposta: o
"⚠ atenção agora" do monitoramento (§7.1) e a central de notificações (§6.6).
Se cada uma implementasse "este projeto está sem reunião esta semana" à sua
maneira, divergiriam no primeiro caso de borda — o mesmo argumento que já
levou `atraso_monitoramento.py` a existir.

**Por que detectar em vez de gravar.** Uma condição é um estado que dura
enquanto o problema durar: "o Alfa está sem kickoff" deixa de ser verdade no
instante em que alguém marca o kickoff. Gravar linha exigiria dois jobs — um
para criar, outro para apagar quando o problema fosse resolvido — e sem o
segundo o consultor conclui a tarefa às 10h e o sino continua cobrando até o
dia seguinte. Derivando na leitura, o alerta some sozinho. É o mesmo princípio
de `tarefa_status.eh_vencida`.

**Zero acesso a banco aqui.** Todas as funções recebem o que já foi carregado
e devolvem dataclasses. É o que permite testá-las sem subir Postgres, como
`tests/use_cases/test_marco_sem_tarefa.py` já faz.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, Iterable, List, Optional, Set

from src.utils.banca_status import NAO_MARCADA, calcular_status_banca
from src.utils.tarefa_status import eh_vencida, janela_semana

# Os 5 tipos 🔄 do §6.6 mais "banca hoje".
KICKOFF_PENDENTE = "kickoff_pendente"
TAREFA_VENCIDA = "tarefa_vencida"
BANCA_NAO_MARCADA = "banca_nao_marcada"
PROJETO_SEM_REUNIAO = "projeto_sem_reuniao"
BANCA_HOJE = "banca_hoje"

#: Quem, DENTRO da equipe do projeto, recebe cada condição individualmente.
#: Fora daqui ninguém recebe individual — liderança vê o agregado (ver
#: `listar_notificacoes`). `tarefa_vencida` não aparece porque o destinatário
#: dela não é um papel, é o responsável pela tarefa.
PAPEIS_DESTINATARIOS = {
    # §5.2 é literal: "a equipe entra no projeto e vê um alerta de kickoff
    # pendente" — equipe, não só quem marca.
    KICKOFF_PENDENTE: ("coordenador", "consultor"),
    # Quem crava a banca (§5.3) e quem registra a reunião (§6.4) é a
    # coordenação. Mandar para o consultor seria cobrá-lo de algo que ele não
    # tem como resolver.
    BANCA_NAO_MARCADA: ("coordenador",),
    PROJETO_SEM_REUNIAO: ("coordenador",),
    BANCA_HOJE: ("coordenador", "consultor"),
}

#: As que chegam à liderança somadas numa linha só. O diretor enxerga TODOS os
#: projetos: uma linha por tarefa vencida da consultoria inteira transforma o
#: sino em lixo eletrônico na primeira semana.
AGREGAVEIS_PARA_LIDERANCA = (
    KICKOFF_PENDENTE,
    TAREFA_VENCIDA,
    BANCA_NAO_MARCADA,
    PROJETO_SEM_REUNIAO,
)


@dataclass(frozen=True)
class Condicao:
    """Um problema em aberto, com o texto já pronto para a tela."""

    tipo: str
    projeto_id: int
    projeto_nome: str
    #: O texto do item. Escrito aqui, e não no front, porque o e-mail da fase 2
    #: vai precisar exatamente do mesmo.
    titulo: str
    #: Identidade estável do alerta — o que o `lida_em` marca e o que impede o
    #: mesmo problema de virar duas notificações. Carrega a janela quando ela
    #: importa: `projeto_sem_reuniao:projeto=1:semana=2026-W32` faz a semana
    #: seguinte gerar chave nova, e o alerta volta a aparecer.
    chave_dedup: str
    #: Onde clicar. As abas do projeto são sub-rotas justamente para isto.
    rota: str
    #: Tamanho do buraco, para ordenar. `None` quando não se aplica.
    dias: Optional[int] = None
    #: Preenchido só quando o alerta é de UMA pessoa (o responsável pela
    #: tarefa). `None` = vale para os papéis de `PAPEIS_DESTINATARIOS`.
    usuario_alvo: Optional[int] = None
    payload: dict = field(default_factory=dict)


def detectar_condicoes(
    projetos,
    *,
    escopos_por_projeto: Dict[int, list],
    bancas_por_escopo: Dict[int, object],
    nomes_escopo: Dict[int, str],
    tarefas_por_projeto: Dict[int, list],
    encerra_por_coluna: Dict[int, bool],
    projetos_com_reuniao: Set[int],
    hoje: Optional[date] = None,
) -> List[Condicao]:
    """Varre os projetos já carregados e devolve tudo que está em aberto.

    Os projetos entram **já recortados** por `aplicar_recorte_visao` — por isso
    não há filtro de permissão aqui. Quem chama garante que a pessoa enxerga
    esses projetos; esta função só olha o estado deles.
    """
    hoje = hoje or date.today()
    condicoes: List[Condicao] = []

    for projeto in projetos:
        if projeto.status == "finalizado":
            continue
        condicoes.extend(_do_projeto(
            projeto,
            escopos=escopos_por_projeto.get(projeto.id, []),
            bancas_por_escopo=bancas_por_escopo,
            nomes_escopo=nomes_escopo,
            tarefas=tarefas_por_projeto.get(projeto.id, []),
            encerra_por_coluna=encerra_por_coluna,
            tem_reuniao=projeto.id in projetos_com_reuniao,
            hoje=hoje,
        ))

    # Maior buraco primeiro; o que não tem número vai para o fim.
    condicoes.sort(key=lambda c: (c.dias is None, -(c.dias or 0)))
    return condicoes


def _do_projeto(
    projeto,
    *,
    escopos,
    bancas_por_escopo,
    nomes_escopo,
    tarefas,
    encerra_por_coluna,
    tem_reuniao: bool,
    hoje: date,
) -> List[Condicao]:
    condicoes: List[Condicao] = []
    nome = projeto.nome

    # ── Kickoff pendente (§5.2) ──────────────────────────────────────────
    if not projeto.data_kickoff:
        condicoes.append(
            Condicao(
                tipo=KICKOFF_PENDENTE,
                projeto_id=projeto.id,
                projeto_nome=nome,
                titulo=f"{nome} está sem kickoff",
                # Sem janela na chave: o alerta é o mesmo até alguém marcar a
                # data. Dispensou uma vez, não volta a incomodar.
                chave_dedup=f"{KICKOFF_PENDENTE}:projeto={projeto.id}",
                rota=f"/projetos/{projeto.id}",
            )
        )

    # ── Tarefa vencida (§6.4) ────────────────────────────────────────────
    for tarefa in tarefas:
        if not eh_vencida(tarefa.prazo, encerra_por_coluna.get(tarefa.coluna_id, False), hoje):
            continue
        # ⚠ Dias CORRIDOS, não úteis. É a régua que o "⚠ atenção agora" já
        # usava para tarefa (`atraso_monitoramento` cuida do atraso de banca,
        # que é em dias úteis). Uniformizar as duas é uma decisão de produto —
        # fazê-la de carona neste refactor mudaria o monitoramento em silêncio.
        dias = (hoje - tarefa.prazo).days
        condicoes.append(
            Condicao(
                tipo=TAREFA_VENCIDA,
                projeto_id=projeto.id,
                projeto_nome=nome,
                titulo=f'"{tarefa.titulo}" venceu há {dias} dia(s) — {nome}',
                # Por TAREFA: concluir aquela tarefa faz o alerta dela sumir
                # sem mexer nas outras.
                chave_dedup=f"{TAREFA_VENCIDA}:tarefa={tarefa.id}",
                rota=f"/projetos/{projeto.id}/tarefas",
                dias=dias,
                usuario_alvo=tarefa.responsavel_id,
                payload={"tarefa_id": tarefa.id},
            )
        )

    # ── Projeto sem reunião na semana (§6.4) ─────────────────────────────
    # Só depois do kickoff: cobrar reunião semanal de um projeto que ainda não
    # começou é ruído, e o alerta de kickoff já está lá.
    if projeto.data_kickoff and not tem_reuniao:
        inicio, _fim = janela_semana(hoje)
        ano, semana, _ = inicio.isocalendar()
        condicoes.append(
            Condicao(
                tipo=PROJETO_SEM_REUNIAO,
                projeto_id=projeto.id,
                projeto_nome=nome,
                titulo=f"{nome} sem reunião registrada esta semana",
                # A semana entra na chave: dispensar esta semana não silencia a
                # próxima.
                chave_dedup=f"{PROJETO_SEM_REUNIAO}:projeto={projeto.id}:semana={ano}-W{semana:02d}",
                rota=f"/projetos/{projeto.id}",
            )
        )

    # ── Banca não marcada e banca hoje (§5.5, §8) ────────────────────────
    bancas_hoje_vistas = set()
    for escopo in escopos:
        if escopo.status in ("cancelado", "entregue"):
            continue
        banca = bancas_por_escopo.get(escopo.id)
        nome_escopo = nomes_escopo.get(escopo.id, "escopo")
        status = calcular_status_banca(
            banca.data_hora if banca else None,
            banca.realizado_em if banca else None,
            datetime.combine(hoje, datetime.max.time()),
        )

        # O escopo precisa ter COMEÇADO para a banca ser cobrável: sem a
        # reunião inicial não existe janela, e sem janela não há onde a banca
        # caber (§9) — cobrá-la antes disso seria cobrar o passo errado.
        if status == NAO_MARCADA and escopo.data_inicio:
            condicoes.append(
                Condicao(
                    tipo=BANCA_NAO_MARCADA,
                    projeto_id=projeto.id,
                    projeto_nome=nome,
                    titulo=f"{nome} — {nome_escopo} está sem banca marcada",
                    chave_dedup=f"{BANCA_NAO_MARCADA}:escopo={escopo.id}",
                    rota=f"/projetos/{projeto.id}/cronograma",
                    payload={"projeto_escopo_id": escopo.id},
                )
            )
            continue

        if banca and banca.data_hora and banca.data_hora.date() == hoje and not banca.realizado_em:
            # Uma banca que cobre três escopos aparece em três chaves do mapa —
            # sem isto o consultor receberia o mesmo lembrete três vezes.
            if banca.id in bancas_hoje_vistas:
                continue
            bancas_hoje_vistas.add(banca.id)
            hora = banca.data_hora.strftime("%H:%M")
            condicoes.append(
                Condicao(
                    tipo=BANCA_HOJE,
                    projeto_id=projeto.id,
                    projeto_nome=nome,
                    titulo=f"Banca de {nome} hoje às {hora}",
                    # A data entra na chave para uma banca remarcada voltar a
                    # avisar no dia novo.
                    chave_dedup=f"{BANCA_HOJE}:banca={banca.id}:data={hoje.isoformat()}",
                    rota=f"/bancas/{banca.id}",
                    dias=0,
                    payload={"banca_id": banca.id},
                )
            )

    return condicoes


def para_papel(condicoes: Iterable[Condicao], papel: str, usuario_id: int) -> List[Condicao]:
    """Filtra o que uma pessoa da EQUIPE recebe individualmente.

    A regra de desempate: **o individual sempre ganha do agregado.** A tarefa
    vencida cujo responsável é a própria coordenadora chega a ela como item
    próprio; o agregado do projeto conta só as dos outros. Sem isso, ela veria
    a mesma tarefa duas vezes.
    """
    resultado = []
    for condicao in condicoes:
        if condicao.tipo == TAREFA_VENCIDA:
            if condicao.usuario_alvo == usuario_id:
                resultado.append(condicao)
            continue
        if papel in PAPEIS_DESTINATARIOS.get(condicao.tipo, ()):
            resultado.append(condicao)
    return resultado
