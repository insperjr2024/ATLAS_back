"""Marcar como lida — e o motivo de a rota aceitar `id` OU `chave`.

Um 📌 evento tem linha no banco, então tem `id`. Uma 🔄 condição **não tem** —
ela é recalculada a cada leitura e só ganha linha no instante em que alguém a
dispensa. Por isso o front devolve a `chave` que recebeu no `GET`, e é aqui
que a linha nasce.

Marcar uma condição como lida **não resolve o problema**: "Alfa sem kickoff"
continua aparecendo na lista até alguém marcar o kickoff. O que o `lida_em`
faz é tirá-la da contagem do sino. Confundir os dois transformaria o "marcar
todas como lidas" num apagador de pendências.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, model_validator
from sqlalchemy.orm import Session

from src.repositories.notificacao_repository import NotificacaoRepository
from src.use_cases.notificacao.listar_notificacoes import ListarNotificacoesUseCase
from src.utils.exceptions import RegraDeNegocioError


class MarcarLidaRequest(BaseModel):
    id: Optional[int] = None
    chave: Optional[str] = None

    @model_validator(mode="after")
    def exige_um_dos_dois(self):
        if self.id is None and not self.chave:
            raise ValueError("Informe `id` (evento) ou `chave` (condição).")
        return self


class MarcarLidaUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = NotificacaoRepository(db)

    def execute(self, current_user, request: MarcarLidaRequest, agora: datetime = None):
        agora = agora or datetime.now()

        if request.id is not None:
            linha = self.repository.marcar_lida(request.id, current_user.id, agora)
            if not linha:
                # Mesma resposta para "não existe" e "é de outra pessoa": dizer
                # qual dos dois é permitiria varrer ids alheios.
                raise RegraDeNegocioError("Notificação não encontrada.")
            return {"lida_em": linha.lida_em}

        return {"lida_em": self._dispensar_condicao(current_user, request.chave, agora)}

    def _dispensar_condicao(self, current_user, chave: str, agora: datetime):
        """A chave precisa corresponder a uma condição que a pessoa REALMENTE
        tem agora.

        Sem esta conferência, qualquer um gravaria linhas com chave inventada —
        e, pior, marcaria como lido o alerta de um projeto que nem enxerga. A
        própria listagem é a autorização: se a chave não está lá, não é dela.
        """
        listagem = ListarNotificacoesUseCase(self.db).execute(current_user)
        item = next(
            (i for i in listagem["itens"] if i["chave"] == chave and i["origem"] == "condicao"),
            None,
        )
        if not item:
            raise RegraDeNegocioError("Notificação não encontrada.")

        linha = self.repository.marcar_condicao_lida(
            usuario_id=current_user.id,
            chave_dedup=chave,
            tipo=item["tipo"],
            titulo=item["titulo"],
            projeto_id=item["projeto_id"],
            agora=agora,
        )
        return linha.lida_em


class MarcarTodasLidasUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = NotificacaoRepository(db)

    def execute(self, current_user, agora: datetime = None) -> dict:
        agora = agora or datetime.now()
        eventos = self.repository.marcar_eventos_lidos(current_user.id, agora)

        # As condições em aberto precisam virar linha uma a uma — é o único
        # jeito de guardar "eu já vi isto" para algo que não tem linha.
        listagem = ListarNotificacoesUseCase(self.db).execute(current_user)
        condicoes = 0
        for item in listagem["itens"]:
            if item["origem"] != "condicao" or item["lida"]:
                continue
            self.repository.marcar_condicao_lida(
                usuario_id=current_user.id,
                chave_dedup=item["chave"],
                tipo=item["tipo"],
                titulo=item["titulo"],
                projeto_id=item["projeto_id"],
                agora=agora,
            )
            condicoes += 1

        return {"marcadas": eventos + condicoes}
