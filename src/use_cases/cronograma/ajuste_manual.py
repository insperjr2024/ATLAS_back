"""⭐ O ajuste manual da janela do escopo — a porta da diretoria de projetos.

O resto da tela trata a janela como parede. Pintar ou arrastar uma etapa para
fora dela é recusado (`update_cronograma._exigir_dentro_da_janela`), e o
caminho é pedir **dias de ajuste**, que tem prazo: o fim da ambientação no
primeiro escopo vendido, 3 dias úteis da reunião inicial nos demais (§8).
Passado esse prazo ninguém mais mexia — nem a diretoria de projetos, que é
justamente quem decide sobre prazo.

Este use case é a saída, e ele faz **uma coisa só**: muda o tamanho da janela.

📐 **As datas das etapas ficaram de fora** (2026-08-31, a pedido). Uma versão
anterior editava aqui também o intervalo de cada trecho, num formulário com uma
linha por etapa. Na tela isso virava uma parede de campos de data para uma
decisão que é de um número só — e o lugar de mover etapa continua sendo o
arrasto no calendário, que é onde a forma do cronograma se lê.

⚠ **Sem validação de janela, sem prazo, sem estado de projeto.** É o pedido
explícito: a diretoria mexe a qualquer momento. O que sobra é a integridade do
dado — janela de zero dia —, que não é regra de negócio: é o que faria a
contagem de dias úteis e o desenho do calendário passarem a mentir.
"""

from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.projeto_escopo_repository import ProjetoEscopoRepository
from src.utils.exceptions import RegraDeNegocioError


class AjusteManualRequest(BaseModel):
    #: O tamanho TOTAL da janela em dias úteis (vendidos + ajustados).
    dias_uteis_janela: int


class AjusteManualUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.escopo_repository = ProjetoEscopoRepository(db)

    def execute(self, escopo_id: int, request: AjusteManualRequest) -> dict:
        escopo = self.escopo_repository.get_by_id(escopo_id)
        if not escopo:
            raise RegraDeNegocioError("Escopo não encontrado")

        ajustados = self._ajustados_para(escopo, request.dias_uteis_janela)
        self.escopo_repository.update(escopo_id, dias_uteis_ajustados=ajustados)

        return {
            "id": escopo_id,
            "dias_uteis_vendidos": escopo.dias_uteis_vendidos,
            "dias_uteis_ajustados": ajustados,
        }

    def _ajustados_para(self, escopo, dias_uteis_janela: int) -> int:
        """A janela pedida, convertida no que de fato é gravado.

        ⭐ **`dias_uteis_vendidos` não é tocado.** Ele é o registro comercial e
        o modelo o chama de imutável: sobrescrevê-lo apagaria a diferença entre
        "vendemos 30" e "vendemos 20 e estouramos", que é de onde o
        monitoramento tira o atraso. A janela é `vendidos + ajustados`, então
        encolher ou esticar é mexer no segundo.

        ⚠ **`dias_uteis_ajustados` passa a poder ser NEGATIVO.** Até aqui ele
        só crescia (soma dos pedidos aprovados). Encolher a janela abaixo do
        que foi vendido é exatamente o que "sem restrição alguma" pede, e a
        alternativa — mexer nos vendidos — custaria o registro comercial.

        ⚠ O campo é o TOTAL, não um incremento: quem chega com 25+5 e pede 40
        fica com 15 ajustados, não 20.
        """
        if dias_uteis_janela < 1:
            raise RegraDeNegocioError("A janela precisa ter pelo menos 1 dia útil")
        return dias_uteis_janela - escopo.dias_uteis_vendidos
