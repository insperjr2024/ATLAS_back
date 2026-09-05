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

from src.utils.ambientacao import fim_da_ambientacao
from src.utils.banca_status import NAO_MARCADA, calcular_status_banca
from src.utils.dias_uteis import normalizar
from src.utils.tarefa_status import eh_vencida, janela_semana

# Os 5 tipos 🔄 do §6.6, mais "banca hoje" e o prazo do §5.3.
KICKOFF_PENDENTE = "kickoff_pendente"
TAREFA_VENCIDA = "tarefa_vencida"
BANCA_NAO_MARCADA = "banca_nao_marcada"
PROJETO_SEM_REUNIAO = "projeto_sem_reuniao"
BANCA_HOJE = "banca_hoje"
#: ⭐ O prazo do §5.3 vencendo: chegou o último dia da ambientação e o projeto
#: ainda não tem NENHUMA banca marcada. Irmão do `kickoff_pendente` — os dois
#: cobram um marco que devia existir e não existe, e os dois só somem quando
#: alguém marca a data.
AMBIENTACAO_SEM_BANCA = "ambientacao_sem_banca"

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
    #: Preenchido só quando o alerta é de PESSOAS específicas (os responsáveis
    #: pela tarefa). Vazio = vale para os papéis de `PAPEIS_DESTINATARIOS`.
    usuarios_alvo: List[int] = field(default_factory=list)
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
    responsaveis_por_tarefa: Optional[Dict[int, List[int]]] = None,
    dias_nao_letivos: Iterable[date] = (),
    hoje: Optional[date] = None,
) -> List[Condicao]:
    """Varre os projetos já carregados e devolve tudo que está em aberto.

    Os projetos entram **já recortados** por `aplicar_recorte_visao` — por isso
    não há filtro de permissão aqui. Quem chama garante que a pessoa enxerga
    esses projetos; esta função só olha o estado deles.

    `dias_nao_letivos` é o calendário do Insper, carregado **uma vez** por quem
    chama — só `ambientacao_sem_banca` depende dele, para achar o fim da janela.
    Devem ser os dias **globais** (`frente_id` nulo), a mesma régua da faixa do
    cronograma e da virada automática de status: a ambientação é do projeto
    inteiro, e um projeto sinérgico não pode acabá-la em datas diferentes
    conforme a frente que se olhe. Sem calendário nenhum a conta ainda fecha —
    só ignora feriados, e o alerta nasce um pouco cedo.
    """
    hoje = hoje or date.today()
    responsaveis_por_tarefa = responsaveis_por_tarefa or {}
    # Normalizado UMA vez: `somar_dias_uteis` roda por projeto, e um gerador
    # chegaria vazio no segundo.
    nao_letivos = normalizar(dias_nao_letivos)
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
            responsaveis_por_tarefa=responsaveis_por_tarefa,
            dias_nao_letivos=nao_letivos,
            hoje=hoje,
        ))

    # Maior buraco primeiro; o que não tem número vai para o fim.
    condicoes.sort(key=lambda c: (c.dias is None, -(c.dias or 0)))
    return condicoes



#: Sem dia padrão definido, a cobrança começa na quinta (ISO: 1=segunda).
DIA_PADRAO_DE_COBRANCA = 4


def _passou_o_dia_da_reuniao(projeto, hoje: date) -> bool:
    """A semana já passou do dia em que este projeto se reúne?

    ⭐ `>` e não `>=`: no PRÓPRIO dia da reunião ela ainda pode acontecer —
    cobrar às 9h de uma reunião marcada para as 18h é cobrar o futuro.

    `dia_reuniao_padrao` é 1=segunda … 7=domingo, a mesma convenção de
    `date.isoweekday()`.
    """
    dia = getattr(projeto, "dia_reuniao_padrao", None) or DIA_PADRAO_DE_COBRANCA
    return hoje.isoweekday() > dia


def _tem_banca_marcada(escopos, bancas_por_escopo) -> bool:
    """Algum destes escopos já tem data e hora de banca?

    ⭐ Escopo **entregue** conta como marcado, e por isso não é filtrado por
    quem chama: ele só chegou lá porque passou por uma banca. Excluí-lo faria o
    alerta renascer num projeto que já validou tudo que tinha para validar.
    """
    for escopo in escopos:
        banca = bancas_por_escopo.get(escopo.id)
        if banca is not None and banca.data_hora:
            return True
    return False


def _do_projeto(
    projeto,
    *,
    escopos,
    bancas_por_escopo,
    nomes_escopo,
    tarefas,
    encerra_por_coluna,
    tem_reuniao: bool,
    responsaveis_por_tarefa: Dict[int, List[int]],
    dias_nao_letivos,
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

    # ── Acabou a ambientação e a banca não foi cravada (§5.3) ────────────
    # *"Ao fim da ambientação, o coordenador crava o cronograma oficial do
    # escopo e a data e horário da banca."* Esse prazo passava em SILÊNCIO: o
    # `banca_nao_marcada` daqui de baixo só cobra escopo que já COMEÇOU, e quem
    # começa o escopo é a reunião inicial — marcada, na prática, junto com a
    # banca. Quem não marcava nenhuma das duas não tinha nem escopo iniciado
    # nem banca, então não disparava condição nenhuma, e o projeto saía da
    # ambientação para Em andamento sem ninguém ser avisado.
    #
    # A pergunta é do PROJETO, não do escopo, porque o marco do §5.3 é um só:
    # marcar a primeira banca já responde. A cobrança escopo a escopo continua
    # sendo do `banca_nao_marcada`, que entra quando cada um começa.
    escopos_vivos = [e for e in escopos if e.status != "cancelado"]
    tem_alguma_banca = _tem_banca_marcada(escopos_vivos, bancas_por_escopo)
    fim_ambientacao = fim_da_ambientacao(
        projeto.data_kickoff, projeto.dias_ambientacao, dias_nao_letivos
    )
    # ⏱ `>=`, não `>`: o alerta nasce NO último dia, que é o dia em que a banca
    # deveria estar sendo cravada — esperar o seguinte avisaria quando o prazo
    # já foi. É de propósito a régua CONTRÁRIA à de `ambientacao_encerrada`,
    # que vira o status só no dia seguinte para não roubar um dia útil de quem
    # comprou cinco: um cobra o prazo, o outro consome a janela.
    #
    # E não se apaga quando a janela passa: enquanto não houver banca, continua
    # cobrando. Projeto sem escopo vivo fica de fora — não há banca para marcar.
    if fim_ambientacao and hoje >= fim_ambientacao and escopos_vivos and not tem_alguma_banca:
        condicoes.append(
            Condicao(
                tipo=AMBIENTACAO_SEM_BANCA,
                projeto_id=projeto.id,
                projeto_nome=nome,
                titulo=f"{nome} terminou a ambientação sem banca marcada",
                # Sem janela na chave, como no kickoff: é o mesmo alerta até
                # alguém marcar a data.
                chave_dedup=f"{AMBIENTACAO_SEM_BANCA}:projeto={projeto.id}",
                # O cronograma é onde a banca se marca (§6.5) — a aba do
                # projeto abre já no lugar de resolver.
                rota=f"/projetos/{projeto.id}/cronograma",
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
                usuarios_alvo=list(responsaveis_por_tarefa.get(tarefa.id, [])),
                payload={"tarefa_id": tarefa.id},
            )
        )

    # ── Projeto sem reunião na semana (§6.4) ─────────────────────────────
    # Só depois do kickoff: cobrar reunião semanal de um projeto que ainda não
    # começou é ruído, e o alerta de kickoff já está lá.
    #
    # ⚠ **E só depois de o dia da reunião passar.** A condição disparava a
    # partir de segunda 00:00: na manhã de segunda, TODOS os projetos ativos
    # apareciam sem reunião — inclusive os que se reúnem na quinta. Era o que
    # enchia "Atenção agora" com 11 linhas idênticas e fazia o card ser lido
    # como ruído em vez de fila.
    #
    # Quem não definiu dia padrão só é cobrado a partir de quinta: dá a semana
    # quase inteira antes de virar alerta, e ainda sobra sexta para resolver.
    if projeto.data_kickoff and not tem_reuniao and _passou_o_dia_da_reuniao(projeto, hoje):
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
            cancelada_em=getattr(banca, "cancelada_em", None) if banca else None,
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
                    rota=f"/bancas?banca={banca.id}",
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
            if usuario_id in condicao.usuarios_alvo:
                resultado.append(condicao)
            continue
        if papel in PAPEIS_DESTINATARIOS.get(condicao.tipo, ()):
            resultado.append(condicao)
    return resultado
