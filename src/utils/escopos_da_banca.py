"""Quais escopos uma banca pode cobrir — a regra, em um lugar só.

Uma banca junta vários escopos do MESMO projeto (inclusive de frentes
diferentes). O que ela não pode é roubar escopo que já tem banca própria:
como o escopo continua tendo no máximo uma (`banca_escopo` tem UNIQUE em
`projeto_escopo_id`), juntá-lo apagaria em silêncio a data já marcada nele.

⭐ Vive aqui porque são DUAS portas que gravam esse vínculo: marcar a banca
pelo cronograma (`marcar_banca_escopo`) e editá-la pela tela de Bancas
(`update_banca`, desde 2026-09-01). Escrita duas vezes, a regra ia divergir na
primeira correção que alguém fizesse só de um lado.
"""

from typing import List, Optional

from src.repositories.banca_escopo_repository import BancaEscopoRepository
from src.repositories.escopo_repository import EscopoRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.utils.exceptions import RegraDeNegocioError


def nome_do_escopo(escopo, catalogo_repository: EscopoRepository) -> str:
    if escopo.nome_customizado:
        return escopo.nome_customizado
    do_catalogo = (
        catalogo_repository.get_by_id(escopo.escopo_id) if escopo.escopo_id else None
    )
    return do_catalogo.nome if do_catalogo else f"escopo {escopo.id}"


def resolver_escopos(
    escopo_ids: List[int],
    *,
    projeto_id: int,
    banca_id: Optional[int],
    escopo_repository: ProjetoEscopoRepository,
    catalogo_repository: EscopoRepository,
    banca_escopo_repository: BancaEscopoRepository,
) -> List:
    """Os escopos pedidos, validados. Levanta na primeira recusa.

    `banca_id` é a banca que está pedindo — `None` quando ela ainda não
    existe. Serve para o escopo que JÁ é dela não ser lido como roubo.
    """
    escopos = []
    for pedido_id in sorted(set(escopo_ids)):
        alvo = escopo_repository.get_by_id(pedido_id)
        if not alvo:
            raise RegraDeNegocioError(f"Escopo {pedido_id} não encontrado")
        if alvo.projeto_id != projeto_id:
            raise RegraDeNegocioError("Uma banca só pode cobrir escopos do mesmo projeto")
        dono = banca_escopo_repository.get_banca_id(alvo.id)
        if dono is not None and (banca_id is None or dono != banca_id):
            raise RegraDeNegocioError(
                f"O escopo '{nome_do_escopo(alvo, catalogo_repository)}' já tem banca "
                "marcada — desmarque a dele antes de juntar os dois"
            )
        escopos.append(alvo)
    return escopos
