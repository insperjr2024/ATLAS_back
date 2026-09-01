from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.projeto_repository import ProjetoRepository
from src.repositories.projeto_status_historico_repository import ProjetoStatusHistoricoRepository
from src.use_cases.projeto.encerrar_ambientacao import EncerrarAmbientacaoUseCase
from src.utils.exceptions import RegraDeNegocioError
from src.utils.status_projeto import (
    destinos_validos,
    pausar,
    retomar,
    rotulo,
    transicao_manual_valida,
)


def _erro_de_transicao(anterior: str, novo: str, tem_kickoff: bool) -> str:
    """A mensagem que a pessoa lê quando o arrasto (ou o seletor) é recusado.

    ⭐ Fala em ETAPAS, com o nome que está na tela — nunca com a chave da
    coluna. A versão antiga devolvia `'validacao_bancas' não é um destino
    válido a partir de 'validacao_bancas'`: uma tautologia, escrita num
    vocabulário que não existe na interface, e que não dizia o que fazer.

    Cada recusa tem uma causa diferente, e cada causa tem uma saída diferente
    — por isso são mensagens separadas, e não uma só com a lista de destinos
    grudada no fim.
    """
    de, para = rotulo(anterior), rotulo(novo)

    # O caso mais comum, e o que a mensagem antiga tratava pior. Quem lê
    # acabou de arrastar o card e está vendo a etapa antiga na tela: o que ela
    # precisa saber é que a página está atrasada, não que "X não vai para X".
    if anterior == novo:
        return (
            f"Este projeto já está em {de}. Se o card aparecia em outra coluna, "
            "recarregue a página: a etapa mudou depois que a tela carregou."
        )

    if anterior == "pausado":
        return (
            f"Este projeto está {de}. Use Retomar para devolvê-lo à etapa em que "
            "parou — de Pausado não dá para ir direto para outra etapa."
        )

    if anterior == "vendido" and not tem_kickoff:
        return (
            f"{de} só avança para {rotulo('ambientacao')}, e só depois do kickoff "
            "marcado: é ele que dá a data de início da ambientação. Marque o "
            "kickoff na página do projeto e tente de novo."
        )

    destinos = destinos_validos(anterior, tem_kickoff)
    if not destinos:
        return f"Um projeto em {de} não pode mudar de etapa."

    return (
        f"Não dá para ir de {de} para {para}. "
        f"A partir de {de}, as etapas possíveis são: "
        f"{', '.join(rotulo(d) for d in destinos)}."
    )


class UpdateStatusRequest(BaseModel):
    #: Qualquer etapa ativa, ou "pausado" / "retomar".
    status_novo: str


class UpdateStatusUseCase:
    """✋ As transições manuais do §4 — Coord (Dir/Ger herdam); Cons não.

    Livre entre as etapas ativas, nos dois sentidos (inclusive reabrir um
    projeto finalizado). Vendido só sai pra Ambientação, e só com kickoff já
    marcado. Toda transição, em qualquer sentido, grava no histórico.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repository = ProjetoRepository(db)
        self.historico_repository = ProjetoStatusHistoricoRepository(db)

    def execute(self, projeto_id: int, request: UpdateStatusRequest, alterado_por: Optional[int] = None):
        projeto = self.repository.get_by_id(projeto_id)
        if not projeto:
            return None

        anterior = projeto.status
        tem_kickoff = projeto.data_kickoff is not None

        if request.status_novo == "pausado":
            novo_status, status_a_guardar = pausar(anterior)
            self.repository.update(projeto_id, status=novo_status, status_antes_pausa=status_a_guardar)

        elif request.status_novo == "retomar":
            novo_status = retomar(projeto.status_antes_pausa)
            self.repository.update(projeto_id, status=novo_status, status_antes_pausa=None)

        elif transicao_manual_valida(anterior, request.status_novo, tem_kickoff):
            novo_status = request.status_novo
            self.repository.update(projeto_id, status=novo_status)

        else:
            raise RegraDeNegocioError(
                _erro_de_transicao(anterior, request.status_novo, tem_kickoff)
            )

        self.historico_repository.create(
            projeto_id=projeto_id,
            status_anterior=anterior,
            status_novo=novo_status,
            alterado_por=alterado_por,
        )

        # 🤖 Entrou em Ambientação com a janela já vencida (kickoff antigo, ou
        # o projeto ficou parado em Vendido): a virada é imediata, e não na
        # passada da madrugada — a alternativa seria a tela mostrar
        # "Ambientação" por um dia sabendo que ela acabou. As duas linhas
        # ficam no histórico, que é o registro fiel do que aconteceu.
        if novo_status == "ambientacao" and EncerrarAmbientacaoUseCase(self.db).executar_para(
            projeto_id
        ):
            return {"id": projeto_id, "status_anterior": anterior, "status": "em_andamento"}

        return {"id": projeto_id, "status_anterior": anterior, "status": novo_status}
