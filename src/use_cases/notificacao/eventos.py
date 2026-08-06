"""Um helper por 📌 evento — o texto e os destinatários num lugar só.

Os use cases que disparam (criar projeto, editar equipe, registrar entrega,
confirmar candidatura) ficam com **uma linha** cada. Sem isto, a redação do
aviso e a regra de quem recebe se espalhariam por quatro arquivos que ninguém
lê junto, e o e-mail da fase 2 acabaria com outra redação.

Todos herdam a garantia de `registrar_notificacao`: falha ao notificar **não**
derruba a ação que gerou o evento.
"""

from sqlalchemy.orm import Session

from src.use_cases.notificacao.destinatarios import lideranca_do_projeto
from src.use_cases.notificacao.registrar_notificacao import registrar, registrar_varios


def notificar_alocacao(db: Session, projeto, usuario_id: int) -> None:
    """"Você entrou no Projeto Alfa" — só para quem entrou.

    Gerente e diretor não recebem: foram eles que alocaram, e avisar alguém do
    que a própria pessoa acabou de fazer é o tipo de ruído que faz o sino ser
    ignorado.
    """
    registrar(
        db,
        usuario_id=usuario_id,
        tipo="alocado_em_projeto",
        titulo=f"Você entrou no projeto {projeto.nome}",
        corpo=f"Cliente: {projeto.cliente}",
        projeto_id=projeto.id,
        rota=f"/projetos/{projeto.id}",
        # Por PROJETO e por pessoa: quem sai e volta na mesma equipe não é
        # avisado duas vezes — o histórico de `projeto_membro` guarda a ida e
        # volta, o sino não precisa repeti-la.
        chave_dedup=f"alocado_em_projeto:projeto={projeto.id}:usuario={usuario_id}",
    )


def notificar_entrega(db: Session, projeto, escopo_id: int, nome_escopo: str) -> None:
    """A entrega sobe para a liderança, não desce para a equipe.

    Quem entregou já sabe que entregou. Quem precisa saber é quem acompanha o
    portfólio — a diretora e o gerente da frente (§7.1: o contraponto positivo
    do monitoramento).
    """
    registrar_varios(
        db,
        lideranca_do_projeto(db, projeto.id),
        tipo="entrega_registrada",
        titulo=f"{projeto.nome} — {nome_escopo} entregue",
        projeto_id=projeto.id,
        rota=f"/projetos/{projeto.id}",
        payload={"projeto_escopo_id": escopo_id},
        chave_dedup=f"entrega_registrada:escopo={escopo_id}",
    )


def notificar_escalacao_banca(
    db: Session, banca_id: int, usuario_id: int, nome_projeto: str, data_hora
) -> None:
    """Hoje cobre a **confirmação de inscrição**; o push automático do §8
    (rodízio respeitando grade horária) ainda não existe no código.

    Quando existir, é este mesmo helper que ele chama — o texto e a chave já
    servem para os dois casos, porque do ponto de vista de quem recebe a
    notícia é a mesma: "você tem banca em tal dia".
    """
    quando = data_hora.strftime("%d/%m às %H:%M") if data_hora else "data a definir"
    registrar(
        db,
        usuario_id=usuario_id,
        tipo="escalacao_banca",
        titulo=f"Você está na banca de {nome_projeto} — {quando}",
        # Sem `projeto_id`: quem participa da banca normalmente NÃO é da equipe
        # do projeto (§8 proíbe), então preencher a FK daria a ele um link para
        # um projeto que o recorte de visão não deixa abrir.
        rota=f"/bancas/{banca_id}",
        payload={"banca_id": banca_id},
        chave_dedup=f"escalacao_banca:banca={banca_id}:usuario={usuario_id}",
    )
