"""As situações de carga (§7.3), editáveis pela diretoria.

Cada papel tem TRÊS faixas, sempre — não há criar nem excluir, só editar. É o
que garante que o card de demanda alta da aba de Alocação nunca fique vazio por
configuração: a última faixa existe por construção, então sempre há uma resposta
para "quem está com demanda alta", sem depender de alguém lembrar de marcar algo.

Nome, mínimo e cor de cada faixa são livres. Guardando só o mínimo, buraco e
sobreposição ficam impossíveis de configurar — o que sobra de validação é pouco
e está aqui.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.repositories.situacao_carga_repository import SituacaoCargaRepository
from src.utils.exceptions import RegraDeNegocioError

PAPEIS = ("coordenador", "consultor")
TOM = Literal["ok", "atencao", "alerta", "neutro"]


def serializar(s):
    return {
        "id": s.id,
        "papel": s.papel,
        "nome": s.nome,
        "min_projetos": s.min_projetos,
        "tom": s.tom,
    }


class AtualizarSituacaoRequest(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=1, max_length=60)
    min_projetos: Optional[int] = Field(default=None, ge=0)
    tom: Optional[TOM] = None


class SituacaoCargaUseCase:
    def __init__(self, db: Session):
        self.repository = SituacaoCargaRepository(db)

    def listar(self):
        # Garante a escala inicial na primeira visita, senão a tela de
        # configuração abre vazia e não há como adivinhar o formato esperado.
        for papel in PAPEIS:
            self.repository.garantir_padrao(papel)
        return [serializar(s) for s in self.repository.listar_todas()]

    def atualizar(self, situacao_id: int, request: AtualizarSituacaoRequest):
        situacao = self.repository.get_by_id(situacao_id)
        if not situacao:
            return None

        dados = request.model_dump(exclude_unset=True)
        novo_minimo = dados.get("min_projetos")
        if novo_minimo is not None and novo_minimo != situacao.min_projetos:
            self._recusar_troca_de_ordem(situacao, novo_minimo)

        return serializar(self.repository.update(situacao_id, **dados))

    # ---------------------------------------------------------------- regras

    def _recusar_troca_de_ordem(self, situacao, novo_minimo: int) -> None:
        """O mínimo pode mudar, mas a faixa não pode ULTRAPASSAR as vizinhas.

        As três faixas se leem pela ordem dos mínimos, e é dessa ordem que sai
        quem entra no card de demanda alta — a última. Sem esta regra, baixar o
        mínimo da faixa alta abaixo do da faixa do meio troca as duas de lugar:
        a tela reordena as linhas, e quem tem mais projetos passa a ser rotulado
        com o nome do meio. O card e a pílula da tabela contariam histórias
        diferentes sobre a mesma pessoa, sem nada apontando o erro.

        Aconteceu de verdade: 'Carga alta' de coordenador foi para 3 e ficou
        abaixo de 'Quantidade ideal' (4).

        Só recusamos a ULTRAPASSAGEM. Mover a faixa dentro do espaço entre as
        vizinhas continua livre, que é o ajuste que a diretoria de fato faz.
        """
        vizinhas = [
            s
            for s in self.repository.listar_por_papel(situacao.papel)
            if s.id != situacao.id
        ]
        abaixo = [s.min_projetos for s in vizinhas if s.min_projetos < situacao.min_projetos]
        acima = [s.min_projetos for s in vizinhas if s.min_projetos > situacao.min_projetos]

        piso = max(abaixo) if abaixo else None
        teto = min(acima) if acima else None

        if (piso is not None and novo_minimo <= piso) or (
            teto is not None and novo_minimo >= teto
        ):
            raise RegraDeNegocioError(
                f'"{situacao.nome}" precisa continuar {self._limites_em_texto(piso, teto)}, '
                "senão troca de lugar com a faixa vizinha"
            )

    @staticmethod
    def _limites_em_texto(piso: Optional[int], teto: Optional[int]) -> str:
        if piso is not None and teto is not None:
            return f"acima de {piso} e abaixo de {teto}"
        if piso is not None:
            return f"acima de {piso}"
        return f"abaixo de {teto}"
