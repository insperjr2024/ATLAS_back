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

from typing import Dict, Iterable, List, Optional, Set

#: Papel "de mentira" do formulário da Avaliação do Escopo. Não é papel de
#: pessoa; entra na fila como auto-avaliação (avaliador == avaliado).
FORM_TYPE_ESCOPO = "escopo"

#: Os tipos de lote que podem carregar a Avaliação do Escopo.
TIPOS_COM_AVALIACAO_DE_ESCOPO = ("finalizacao", "periodico")

#: O status do escopo vendido que a PERIÓDICA avalia.
STATUS_ESCOPO_EM_ANDAMENTO = "em_andamento"


def formulario_escopo_do_lote(lote, formulario_repo, criterio_repo):
    """O formulário da Avaliação do Escopo que vale para `lote`, ou `None`
    quando o lote não a inclui, o formulário não existe ou ainda não tem
    critério nenhum."""
    if lote.tipo not in TIPOS_COM_AVALIACAO_DE_ESCOPO:
        return None
    if not getattr(lote, "inclui_avaliacao_de_escopo", True):
        return None
    formulario = formulario_repo.first_by(tipo=lote.tipo, papel=FORM_TYPE_ESCOPO)
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
    return [
        pe
        for pe in projeto_escopo_repo.get_by_projetos(ids)
        if pe.status == STATUS_ESCOPO_EM_ANDAMENTO
    ]


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
    """Os ids de TODOS os formulários `papel="escopo"`, de qualquer tipo. É o
    que relatório e listagem usam pra separar a auto-avaliação do escopo das
    avaliações entre pessoas."""
    ids: Set[int] = set()
    for tipo in TIPOS_COM_AVALIACAO_DE_ESCOPO:
        formulario = formulario_repo.first_by(tipo=tipo, papel=FORM_TYPE_ESCOPO)
        if formulario:
            ids.add(formulario.id)
    return ids


def catalogo_de_escopos(escopo_repo, escopos: List) -> Dict[int, str]:
    """`escopo_id (catálogo) -> nome` só pros escopos vendidos passados."""
    out: Dict[int, str] = {}
    for pe in escopos:
        if pe.escopo_id and pe.escopo_id not in out:
            cat = escopo_repo.get_by_id(pe.escopo_id)
            if cat:
                out[pe.escopo_id] = cat.nome
    return out
