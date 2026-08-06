from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.repositories.formulario_repository import FormularioRepository
from src.repositories.pergunta_repository import PerguntaRepository
from src.repositories.semestre_repository import SemestreRepository
from src.utils.identificar_semestre import identificar_semestre
from src.utils.exceptions import RegraDeNegocioError


class PerguntaNovaVersao(BaseModel):
    texto: str
    ordem: int
    tipo_resposta: str = "nota"
    escopo_id: Optional[int] = None


class CreateNovaVersaoFormularioRequest(BaseModel):
    perguntas: List[PerguntaNovaVersao]


class CreateNovaVersaoFormularioUseCase:
    def __init__(self, db: Session):
        self.repository = FormularioRepository(db)
        self.pergunta_repository = PerguntaRepository(db)
        self.semestre_repository = SemestreRepository(db)

    def execute(self, request: CreateNovaVersaoFormularioRequest):
        semestres = self.semestre_repository.get_all()
        semestre_atual = identificar_semestre(datetime.now(), semestres)
        if not semestre_atual:
            raise RegraDeNegocioError("Não existe semestre cadastrado para a data atual")

        formularios_existentes = self.repository.get_all()
        for f in formularios_existentes:
            if f.ativo:
                self.repository.update(f.id, ativo=False)

        novo_formulario = self.repository.create(
            semestre_id=semestre_atual.id,
            ativo=True
        )

        perguntas_criadas = [
            self.pergunta_repository.create(
                formulario_id=novo_formulario.id,
                texto=p.texto,
                ordem=p.ordem,
                tipo_resposta=p.tipo_resposta,
                escopo_id=p.escopo_id,
            )
            for p in request.perguntas
        ]

        return {
            "id": novo_formulario.id,
            "semestre_id": novo_formulario.semestre_id,
            "perguntas": [
                {
                    "id": p.id,
                    "texto": p.texto,
                    "ordem": p.ordem,
                    "tipo_resposta": p.tipo_resposta,
                    "escopo_id": p.escopo_id,
                }
                for p in perguntas_criadas
            ]
        }