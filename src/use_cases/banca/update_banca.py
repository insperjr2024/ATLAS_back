from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.banca_escopo_repository import BancaEscopoRepository
from src.repositories.banca_repository import BancaRepository
from src.use_cases.banca.excecao_choque import checar_choque
from src.utils.banca_status import calcular_status_banca
from src.utils.exceptions import RegraDeNegocioError
from src.utils.fuso import normalizar_utc
from src.utils.notificar import notificar


class UpdateBancaRequest(BaseModel):
    nome_projeto: Optional[str] = None
    escopo_id: Optional[int] = None
    coordenador_id: Optional[int] = None
    data_hora: Optional[datetime] = None
    #: Só a diretoria altera — ver `require_diretor` no use case.
    piso_minimo_override: Optional[int] = None


class UpdateBancaUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = BancaRepository(db)
        self.banca_escopo_repository = BancaEscopoRepository(db)

    def execute(self, banca_id: int, request: UpdateBancaRequest, eh_diretor: bool = False):
        data = request.dict(exclude_unset=True)

        if "piso_minimo_override" in data and not eh_diretor:
            raise RegraDeNegocioError("Só a diretoria pode alterar o piso mínimo de uma banca")

        existente = self.repository.get_by_id(banca_id)
        if not existente:
            return None

        escopo_ids = self.banca_escopo_repository.get_escopo_ids(banca_id)

        # ⚠ ANTES de qualquer comparação: o front manda `toISOString()`, que
        # chega como datetime COM fuso, e a coluna devolve SEM. Comparados
        # crus, os dois nunca são iguais — as duas guardas abaixo disparavam em
        # toda edição, mesmo quando a data não tinha sido tocada, e o botão
        # Editar da tela de Bancas não salvava nada, de campo nenhum.
        if "data_hora" in data:
            data["data_hora"] = normalizar_utc(data["data_hora"])
        data_mudou = "data_hora" in data and data["data_hora"] != existente.data_hora

        # 🔒 §5.6: remarcar a banca de um escopo nunca é silenciosa — exige
        # diretoria e justificativa. Esta rota é a genérica do módulo legado
        # e não tem como cumprir isso, então ela para aqui e manda usar o
        # cronograma, que impõe a regra.
        if escopo_ids and data_mudou:
            raise RegraDeNegocioError(
                "Para mudar a data desta banca, use o cronograma do projeto: "
                "remarcar exige justificativa e autorização da diretoria. "
                "Os outros campos podem ser editados por aqui."
            )

        # 🔒 §8 também aqui: a banca LEGADA (sem escopo) escapa do bloco acima e
        # tinha caminho livre para ser movida para cima de outra banca. A regra
        # do choque vale para toda porta que grava `data_hora`.
        if data_mudou:
            checar_choque(
                self.db,
                data["data_hora"],
                banca_repository=self.repository,
                ignorar_banca_id=banca_id,
                projeto_escopo_id=escopo_ids[0] if escopo_ids else None,
            )

        banca = self.repository.update(banca_id, **data)
        if not banca:
            return None

        # ⭐ Quem foi escalado tem de saber que a banca mudou — a agenda dele
        # mexeu sem que ele pedisse. Antes, editar era silencioso: a pessoa
        # aparecia no dia e no horário antigos.
        notificar_alocados(
            self.db,
            banca,
            f"A banca de {banca.nome_projeto} foi editada. Confira os dados em Bancas.",
        )
        return {
            "id": banca.id,
            "nome_projeto": banca.nome_projeto,
            "escopo_id": banca.escopo_id,
            "coordenador_id": banca.coordenador_id,
            "data_hora": banca.data_hora,
            "projeto_escopo_ids": escopo_ids,
            "realizado_em": banca.realizado_em,
            "resultado": banca.resultado,
            "status": calcular_status_banca(banca.data_hora, banca.realizado_em),
            "piso_minimo_override": banca.piso_minimo_override,
        }


class DeleteBancaUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = BancaRepository(db)

    def execute(self, banca_id: int) -> bool:
        # ⚠ Avisar ANTES de apagar: depois do delete não há mais como saber
        # quem estava escalado — a candidatura vai junto.
        banca = self.repository.get_by_id(banca_id)
        if banca:
            notificar_alocados(
                self.db,
                banca,
                f"A banca de {banca.nome_projeto} foi cancelada e não acontecerá mais.",
            )
        return self.repository.delete(banca_id)


def notificar_alocados(db: Session, banca, mensagem: str) -> None:
    """Avisa quem está escalado nesta banca.

    ⭐ Editar e excluir mexem na agenda de quem foi escalado sem que ele tenha
    pedido — o §8 trata escalação como compromisso, e compromisso que muda em
    silêncio é falta anunciada. A remarcação pelo cronograma já avisava
    (`notificar_banca_remarcada`); estas duas portas não avisavam ninguém.
    """
    from src.repositories.candidatura_repository import CandidaturaRepository

    for candidatura in CandidaturaRepository(db).get_by_banca(banca.id):
        notificar(
            db,
            candidatura.usuario_id,
            mensagem,
            banca_id=banca.id,
            tipo="banca_aviso",
        )