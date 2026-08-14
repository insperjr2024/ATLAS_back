"""Mover a reunião inicial ZERA o cronograma do escopo (§5.4).

⭐ **Por que zerar, e não só recalcular.** A data da reunião inicial é a origem
da janela do escopo: todo o resto — etapas pintadas, data da banca, entrega
planejada — foi desenhado *a partir* dela. Mudar a origem e manter o desenho
produz um cronograma que ninguém combinou: etapas antes do começo, banca fora
da janela nova, entrega prometida para uma contagem que não existe mais.

O núcleo decidiu que a nova data define a janela e o resto recomeça. É mais
honesto que um remendo automático, e é a única versão que a pessoa consegue
prever antes de confirmar.

⚠ **Duas coisas não se zeram, e por isso barram a mudança inteira:**

- **banca já realizada** — apagá-la destruiria presença, votos e o resultado
  que liberou a entrega ao cliente (§5.5). Isso não se refaz;
- **escopo já entregue** — a janela está congelada (§5.4) e reabrir o início
  mexeria em dias já contados.

Nos dois casos a resposta é recusar a mudança, não zerar pela metade.
"""

from sqlalchemy.orm import Session

from src.repositories.banca_repository import BancaRepository
from src.repositories.cronograma_repository import CronogramaEtapaRepository
from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.utils.exceptions import RegraDeNegocioError


def exigir_reset_permitido(db: Session, projeto_escopo_id: int) -> None:
    """As travas que impedem zerar. Levanta `RegraDeNegocioError` explicando.

    Separada do reset de propósito: quem só quer saber "posso mexer nesta
    data?" — a tela, antes de oferecer a mudança — chama isto sem apagar nada.
    """
    escopo = ProjetoEscopoRepository(db).get_by_id(projeto_escopo_id)
    if not escopo:
        raise RegraDeNegocioError("Escopo não encontrado")

    if escopo.data_entrega_real:
        raise RegraDeNegocioError(
            "Este escopo já foi entregue ao cliente, e a janela dele está fechada. "
            "Mudar a reunião inicial mexeria em dias já contados — não dá para desfazer "
            "uma entrega mudando a data da largada."
        )

    banca = BancaRepository(db).get_by_projeto_escopo(projeto_escopo_id)
    if banca and banca.realizado_em:
        raise RegraDeNegocioError(
            "A banca deste escopo já aconteceu. Mudar a reunião inicial zera o "
            "cronograma, e isso apagaria a banca junto com a presença, os votos e o "
            "resultado dela — que é o que libera a entrega ao cliente. Se a data da "
            "reunião está errada, registre a correção no histórico do projeto."
        )


def resumir_o_que_sera_apagado(db: Session, projeto_escopo_id: int) -> dict:
    """O levantamento do estrago, sem apagar — para a confirmação na tela.

    📐 Perguntar "tem certeza?" sem dizer o tamanho do estrago não é
    confirmação, é formulário. A pessoa precisa ver que são 4 etapas e uma
    banca marcada antes de decidir.
    """
    etapas = CronogramaEtapaRepository(db).get_by_escopo(projeto_escopo_id)
    banca = BancaRepository(db).get_by_projeto_escopo(projeto_escopo_id)
    return {
        "etapas": len(etapas),
        "banca_marcada": banca.data_hora.isoformat() if banca and banca.data_hora else None,
    }


def zerar_cronograma_do_escopo(db: Session, projeto_escopo_id: int) -> dict:
    """Apaga o que foi desenhado a partir da largada antiga.

    Devolve o que saiu, para a tela dizer à pessoa o que ela perdeu — "3 etapas
    e a banca de 20/08" é diferente de "nada".

    ⚠ **A DATA da banca é apagada; a banca não.** Foi a leitura literal do que
    o núcleo pediu ("as datas de banca e entrega são apagadas"), e é também a
    única segura: onze tabelas referenciam `banca` — remarcações, candidaturas,
    avaliações, sessões, pedidos de exceção de choque —, e nenhuma delas tem
    cascata. Apagar a linha estourava a FK de `projeto_remarcacao_banca` no
    primeiro escopo real que tinha remarcação.

    Sem data, a banca volta ao estado "não marcada": ela continua sendo a banca
    daquele escopo, e o coordenador remarca dentro da janela nova.

    📐 **Quem estava alocado continua alocado.** Tirar as pessoas seria uma
    segunda decisão, que ninguém tomou — e refazer a escala custa mais que
    ajustar uma data. Se a data nova não servir para alguém, essa pessoa se
    desaloca, que é o gesto que já existe.
    """
    escopo_repository = ProjetoEscopoRepository(db)

    etapas = CronogramaEtapaRepository(db).get_by_escopo(projeto_escopo_id)
    for etapa in etapas:
        db.delete(etapa)

    banca_desmarcada = None
    banca = BancaRepository(db).get_by_projeto_escopo(projeto_escopo_id)
    if banca and banca.data_hora:
        banca_desmarcada = banca.data_hora.isoformat()
        banca.data_hora = None

    escopo = escopo_repository.get_by_id(projeto_escopo_id)
    if escopo:
        # A entrega planejada e o carimbo de oficialização descreviam o
        # cronograma que acabou de ser apagado.
        escopo.data_entrega_planejada = None
        escopo.cronograma_oficializado_em = None
        # ⚠ Os dias de ajuste TAMBÉM voltam a zero: foram concedidos para a
        # janela antiga. Mantê-los daria ao escopo um prazo esticado que a
        # diretoria nunca aprovou para esta largada.
        escopo.dias_uteis_ajustados = 0

    db.flush()
    return {
        "etapas_apagadas": len(etapas),
        "banca_desmarcada": banca_desmarcada,
    }
