from sqlalchemy.orm import Session
from src.repositories.avaliacao_nota_repository import AvaliacaoNotaRepository
from src.repositories.pergunta_repository import PerguntaRepository
from src.utils.banca_nota import calcular_notas_por_pergunta


class GetNotasPorPerguntaUseCase:
    def __init__(self, db: Session):
        self.avaliacao_nota_repository = AvaliacaoNotaRepository(db)
        self.pergunta_repository = PerguntaRepository(db)

    def execute(self, banca_id: int):
        notas = self.avaliacao_nota_repository.get_by_banca(banca_id)
        medias = calcular_notas_por_pergunta(notas)
        resultado = []
        for pergunta_id, media in medias.items():
            pergunta = self.pergunta_repository.get_by_id(pergunta_id)
            resultado.append({
                "pergunta_id": pergunta_id,
                "texto": pergunta.texto if pergunta else None,
                "media": media
            })
        return resultado