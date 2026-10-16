"""O que cada leitor enxerga das avaliações de uma banca (2026-10-16, a pedido).

A ficha (`GetBancaDetalhesUseCase`) sai com tudo: nome de quem avaliou, as
notas por critério, o comentário. Quem tem o Dashboard de Bancas recebe
assim. Pra todo mundo que vê o projeto, a aba Banca passa a mostrar os
RESULTADOS SEM AUTOR: o grupo precisa ler as notas e os comentários pra
ajustar o trabalho a tempo, mas não precisa saber quem escreveu cada um.
Quem só visita a aba (avaliador de fora) não vê resultado nenhum.

As duas funções recebem o dict da ficha e devolvem o mesmo dict mexido no
lugar. `leitor_id` é quem está lendo: o comentário que a própria pessoa
escreveu continua vindo pra ela em `avaliadores` (a aba mostra "Sua
avaliação" com ele), só o dos outros some.
"""

import hashlib


def _sem_comentario_dos_outros(avaliadores: list, leitor_id) -> list:
    # `avaliadores[].comentario_feedback` liga nome a texto: é por ele que a
    # ficha mostra "Sua avaliação" pro próprio avaliador. Pros demais ele é
    # o mesmo vazamento que a lista de avaliações com nome.
    return [
        a if a.get("usuario_id") == leitor_id else {**a, "comentario_feedback": None}
        for a in avaliadores or []
    ]


def ocultar_resultados(detalhes: dict, leitor_id=None) -> dict:
    """Nem nota nem comentário de ninguém: o que o visitante da aba recebe,
    e o que `GET /bancas/{id}/detalhes` sempre deu a quem não tem o dashboard."""
    detalhes["avaliacoes"] = []
    detalhes["nota_final"] = None
    detalhes["avaliacoes_anonimas"] = False
    detalhes["avaliadores"] = _sem_comentario_dos_outros(detalhes.get("avaliadores"), leitor_id)
    return detalhes


def anonimizar_resultados(detalhes: dict, leitor_id=None) -> dict:
    """Notas e comentários ficam; quem escreveu, não.

    Sai nome, id do avaliador e data de envio. A ordem também muda: a lista
    original vem na ordem em que as avaliações foram criadas, e quem soube
    "fulano enviou primeiro" leria o autor pela posição. A ordem aqui é por
    um hash do id da avaliação, estável entre dois carregamentos (a tela não
    embaralha a cada clique) e sem relação com quem enviou quando. O `id`
    devolvido é só a posição na lista, pra tela ter uma chave.
    """
    embaralhadas = sorted(
        detalhes.get("avaliacoes") or [],
        key=lambda a: (a.get("sessao") or 1, hashlib.sha1(f"{detalhes.get('id')}:{a.get('id')}".encode()).hexdigest()),
    )
    detalhes["avaliacoes"] = [
        {
            "id": posicao,
            "avaliador": None,
            "avaliador_id": None,
            "sessao": a.get("sessao") or 1,
            "comentario_feedback": a.get("comentario_feedback"),
            "submetida_em": None,
            "notas": a.get("notas") or [],
        }
        for posicao, a in enumerate(embaralhadas, start=1)
    ]
    detalhes["avaliacoes_anonimas"] = True
    detalhes["avaliadores"] = _sem_comentario_dos_outros(detalhes.get("avaliadores"), leitor_id)
    return detalhes
