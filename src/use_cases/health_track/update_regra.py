from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.repositories.health_track_regra_repository import HealthTrackRegraRepository
from src.use_cases.health_track.get_regra import autores, serializar_regra
from src.utils.exceptions import RegraDeNegocioError
from src.utils.fuso import agora_utc

CAMPOS = ("verde_max_amarelos", "verde_max_vermelhos", "vermelho_min_amarelos", "vermelho_min_vermelhos")


class UpdateRegraRequest(BaseModel):
    verde_max_amarelos: int = Field(ge=0)
    verde_max_vermelhos: int = Field(ge=0)
    vermelho_min_amarelos: int = Field(ge=1)
    vermelho_min_vermelhos: int = Field(ge=1)


class UpdateRegraUseCase:
    """Edita a regra do status geral (§5) criando uma versão nova, que vale a
    partir de agora. A anterior fica intacta: é por ela que os ciclos de
    antes continuam mostrando o status "na época".

    Os mínimos do vermelho começam em 1 (no `Field`): com 0, todo projeto
    seria vermelho. E cada mínimo do vermelho precisa passar o máximo
    correspondente do verde — se não passasse, a tela mostraria uma faixa
    de verde que nunca acontece, porque vermelho é checado antes.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repository = HealthTrackRegraRepository(db)

    def execute(self, request: UpdateRegraRequest, current_user) -> dict:
        if request.vermelho_min_amarelos <= request.verde_max_amarelos:
            raise RegraDeNegocioError(
                "O mínimo de amarelos do vermelho precisa ser maior que o máximo de amarelos do verde"
            )
        if request.vermelho_min_vermelhos <= request.verde_max_vermelhos:
            raise RegraDeNegocioError(
                "O mínimo de vermelhos do vermelho precisa ser maior que o máximo de vermelhos do verde"
            )

        versoes = self.repository.get_versoes()
        atual = versoes[-1] if versoes else None
        valores = request.model_dump()
        # Salvar sem mudar nada não cria versão: seria uma "mudança de regra"
        # no histórico que não mudou status nenhum.
        if atual and all(getattr(atual, c) == valores[c] for c in CAMPOS):
            return serializar_regra(atual, autores(self.db, [atual]))

        nova = self.repository.create(**valores, vigente_desde=agora_utc(), criado_por=current_user.id)
        return serializar_regra(nova, autores(self.db, [nova]))
