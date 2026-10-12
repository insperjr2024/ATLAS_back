"""Avaliação do Escopo: em qual lote ela entra, sobre quais escopos e pra quem.

Nasceu na finalização (2026-09-09): cada participante do projeto responde
sobre o escopo que acabou de passar pela banca. Em 2026-10-05, a pedido, a
periódica ganhou a mesma opção, com outro recorte: o que se avalia é o
escopo EM ANDAMENTO (já começou, ainda não passou pela banca nem foi
entregue). Escopo não iniciado não conta.

É UMA resposta POR ESCOPO, não por pessoa: quem está num projeto com dois
escopos em andamento responde duas vezes. E cada um só avalia o escopo da
PRÓPRIA frente: num projeto sinérgico com um escopo de Direito e outro de
Business, a pessoa de Direito não opina sobre o de Business. Quem não tem
frente cadastrada avalia todos os escopos dos projetos dele, em vez de
sumir da fila sem explicação.

Cada tipo de lote tem o seu formulário (`(finalizacao, escopo)` e
`(periodico, escopo)`). O da periódica nasce como cópia do da finalização
(migration `a9d4e7c2b185`) e dali em diante cada um é editado por conta
própria na tela de Formulários. Os dois seguem a régua de sempre: sem
seções e critérios cadastrados, a avaliação fica invisível.

Estas funções são a fonte única pra `get_fila`, `get_pendencias` e
`create_avaliacao`, antes cada um repetia o `if lote.tipo == "finalizacao"`
por conta própria.
"""

from datetime import date, datetime
from typing import Dict, Iterable, List, Optional, Set

from src.utils.desempenho_formulario_lote import formulario_do_lote

#: Papel "de mentira" do formulário da Avaliação do Escopo. Não é papel de
#: pessoa; entra na fila como auto-avaliação (avaliador == avaliado).
FORM_TYPE_ESCOPO = "escopo"

#: Os tipos de lote que podem carregar a Avaliação do Escopo.
TIPOS_COM_AVALIACAO_DE_ESCOPO = ("finalizacao", "periodico")

#: O status do escopo vendido que a PERIÓDICA avalia.
STATUS_ESCOPO_EM_ANDAMENTO = "em_andamento"


def formulario_escopo_do_lote(lote, formulario_repo, criterio_repo, lote_formulario_repo=None):
    """O formulário da Avaliação do Escopo que vale para `lote`, ou `None`
    quando o lote não a inclui, o formulário não existe ou ainda não tem
    critério nenhum. Com `lote_formulario_repo`, respeita a versão congelada
    do lote (`utils/desempenho_formulario_lote.py`)."""
    if lote.tipo not in TIPOS_COM_AVALIACAO_DE_ESCOPO:
        return None
    if not getattr(lote, "inclui_avaliacao_de_escopo", True):
        return None
    if lote_formulario_repo is not None:
        formulario = formulario_do_lote(formulario_repo, lote_formulario_repo, lote, FORM_TYPE_ESCOPO)
    else:
        formulario = formulario_repo.vigente(lote.tipo, FORM_TYPE_ESCOPO)
    if not formulario or not criterio_repo.get_by_formulario(formulario.id):
        return None
    return formulario


def escopos_avaliaveis_no_lote(
    lote, projeto_ids: Iterable[int], projeto_escopo_repo, banca_escopo_repo
) -> list:
    """Os escopos vendidos (`projeto_escopo`) sobre os quais a Avaliação do
    Escopo deste lote fala.

    Lote com banca (finalização automática): os escopos que a banca cobriu.
    Sem banca (periódica, ou finalização aberta à mão): os escopos em
    andamento dos projetos do lote.
    """
    ids = list(projeto_ids)
    if getattr(lote, "banca_id", None):
        return projeto_escopo_repo.get_by_ids(banca_escopo_repo.get_escopo_ids(lote.banca_id))
    if not ids:
        return []
    escopos = projeto_escopo_repo.get_by_projetos(ids)
    # Periódica: em andamento NA DATA DO LOTE, a mesma régua de
    # `membros_da_periodica` (2026-10-12). A finalização aberta à mão segue
    # pelo status de hoje, como sempre foi.
    if getattr(lote, "tipo", None) == "periodico":
        referencia = data_de_referencia(lote)
        return [pe for pe in escopos if em_andamento_em(pe, referencia)]
    return [pe for pe in escopos if pe.status == STATUS_ESCOPO_EM_ANDAMENTO]


def data_de_referencia(lote) -> date:
    """O dia em que a periódica olha os escopos: a abertura do lote. Congelar
    num dia é o que impede a fila de mudar no meio do lote (um escopo que
    começa ou termina depois não muda quem avalia quem) e o que deixa limpar
    lotes antigos sem apagar resposta que valia quando foi dada."""
    quando = getattr(lote, "data_inicio", None) or getattr(lote, "criado_em", None) or datetime.now()
    return quando.date() if isinstance(quando, datetime) else quando


def em_andamento_em(escopo, quando: date) -> bool:
    """O escopo vendido estava rodando em `quando`?

    Começou: tem `data_inicio` (a primeira reunião) até esse dia. Não
    terminou: sem `data_entrega_real` (nem confirmação de entrega) até esse
    dia. Cancelado nunca conta. Escopo com zero dias úteis não tem
    `data_inicio`, então fica de fora sozinho.
    """
    if escopo.status in ("cancelado", "nao_iniciado"):
        return False
    inicio = getattr(escopo, "data_inicio", None)
    if not inicio or inicio > quando:
        return False
    fim = getattr(escopo, "data_entrega_real", None)
    if fim is None and escopo.status == "entregue":
        confirmado = getattr(escopo, "entrega_confirmada_em", None)
        fim = confirmado.date() if isinstance(confirmado, datetime) else confirmado
        if fim is None:
            # Entregue sem data nenhuma: terminou, só não se sabe quando.
            return False
    return not (fim and fim <= quando)


def membros_da_periodica(lote, membros: list, escopos: list, frentes: Dict[int, Set[int]]) -> list:
    """Quem entra na avaliação periódica de `lote` (2026-10-12, a pedido).

    Na periódica só se avalia o trabalho de quem está num escopo EM
    ANDAMENTO (`em_andamento_em`, na data do lote). Escopo que não começou ou
    que já foi entregue não gera avaliação, e a frente dele sai da conta:
    ninguém da frente avalia nem é avaliado por esse projeto. Ex.: CONEXÕES I
    com o escopo de Tech parado em zero dias, o pessoal de Tech some da fila
    e das pendências; quem é de Business e de Tech continua, por Business.

    Por projeto:
    - sem escopo cadastrado: todo mundo continua (não há como saber);
    - nenhum escopo em andamento: ninguém do projeto entra;
    - senão, fica quem tem pelo menos uma frente com escopo em andamento, ou
      quem não tem frente ligada a escopo nenhum do projeto (alocado de
      outra frente, ou sem frente cadastrada), que não tem por que sumir.

    Outros tipos de lote (finalização) passam direto, sem filtro.
    """
    if getattr(lote, "tipo", None) != "periodico":
        return membros
    referencia = data_de_referencia(lote)
    do_projeto: Dict[int, Set[int]] = {}
    ativas: Dict[int, Set[int]] = {}
    for pe in escopos:
        do_projeto.setdefault(pe.projeto_id, set()).add(pe.frente_id)
        if em_andamento_em(pe, referencia):
            ativas.setdefault(pe.projeto_id, set()).add(pe.frente_id)

    def entra(membro) -> bool:
        frentes_do_projeto = do_projeto.get(membro.projeto_id)
        if not frentes_do_projeto:
            return True
        ativas_do_projeto = ativas.get(membro.projeto_id, set())
        if not ativas_do_projeto:
            return False
        minhas = (frentes.get(membro.usuario_id) or set()) & frentes_do_projeto
        return not minhas or bool(minhas & ativas_do_projeto)

    return [m for m in membros if entra(m)]


def frentes_por_usuario(usuario_frente_repo) -> Dict[int, Set[int]]:
    """`usuario_id -> {frente_id}`, de uma vez, pra não consultar por pessoa."""
    out: Dict[int, Set[int]] = {}
    for uf in usuario_frente_repo.get_all():
        out.setdefault(uf.usuario_id, set()).add(uf.frente_id)
    return out


def escopos_da_pessoa(
    usuario_id: int, escopos: list, membros: list, frentes: Optional[Set[int]]
) -> list:
    """Dentre `escopos`, os que `usuario_id` avalia: dos projetos em que ela
    está (`membros`) e da frente dela. Sem frente cadastrada, todos os dos
    projetos dela."""
    meus_projetos = {m.projeto_id for m in membros if m.usuario_id == usuario_id}
    return [
        pe
        for pe in escopos
        if pe.projeto_id in meus_projetos and (not frentes or pe.frente_id in frentes)
    ]


def nome_do_escopo_vendido(escopo, catalogo_por_id: Dict[int, str]) -> str:
    """O rótulo do escopo na fila: o "Outro" digitado, ou o nome do catálogo."""
    if escopo.nome_customizado:
        return escopo.nome_customizado
    return catalogo_por_id.get(escopo.escopo_id, f"escopo {escopo.id}")


def ids_dos_formularios_de_escopo(formulario_repo) -> Set[int]:
    """Os ids de TODOS os formulários `papel="escopo"`, de qualquer tipo,
    vigentes ou congelados. É o que relatório e listagem usam pra separar a
    auto-avaliação do escopo das avaliações entre pessoas."""
    return {f.id for f in formulario_repo.get_por_papel(FORM_TYPE_ESCOPO)}


def catalogo_de_escopos(escopo_repo, escopos: List) -> Dict[int, str]:
    """`escopo_id (catálogo) -> nome` só pros escopos vendidos passados."""
    out: Dict[int, str] = {}
    for pe in escopos:
        if pe.escopo_id and pe.escopo_id not in out:
            cat = escopo_repo.get_by_id(pe.escopo_id)
            if cat:
                out[pe.escopo_id] = cat.nome
    return out
