from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from pydantic import BaseModel
from src.models.escopo_model import EscopoModel
from src.models.formulario_model import FormularioModel
from src.models.pergunta_model import PerguntaModel
from src.repositories.formulario_repository import FormularioRepository
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
        self.db = db
        self.repository = FormularioRepository(db)
        self.semestre_repository = SemestreRepository(db)

    def execute(self, request: CreateNovaVersaoFormularioRequest):
        # ⚠ ATÔMICO (2026-09-09). Antes cada `repository.create/update` dava
        # o seu próprio commit: desativava a versão boa, criava a nova
        # ATIVA e só então inseria as perguntas uma a uma. Qualquer falha no
        # meio (FK de escopo, timeout, conexão) deixava uma versão ativa
        # VAZIA e um 500 — e foi isso que encheu o banco de formulários
        # zerados. Agora é tudo numa transação: deu erro, nada muda e a
        # versão anterior continua no ar.
        perguntas = [p for p in request.perguntas if p.texto and p.texto.strip()]
        if not perguntas:
            raise RegraDeNegocioError("O formulário precisa de ao menos uma pergunta.")

        for p in perguntas:
            if len(p.texto.strip()) > 500:
                raise RegraDeNegocioError(
                    f"A pergunta \"{p.texto[:40]}…\" passa de 500 caracteres."
                )

        semestres = self.semestre_repository.get_all()
        semestre_atual = identificar_semestre(datetime.now(), semestres)
        if not semestre_atual:
            raise RegraDeNegocioError("Não existe semestre cadastrado para a data atual")

        escopo_ids = {p.escopo_id for p in perguntas if p.escopo_id is not None}
        if escopo_ids:
            existentes = {
                e.id
                for e in self.db.query(EscopoModel.id).filter(EscopoModel.id.in_(escopo_ids))
            }
            faltando = escopo_ids - existentes
            if faltando:
                raise RegraDeNegocioError(
                    f"Escopo(s) inexistente(s) no formulário: {sorted(faltando)}"
                )

        try:
            for f in self.repository.get_all():
                if f.ativo:
                    f.ativo = False

            novo_formulario = FormularioModel(semestre_id=semestre_atual.id, ativo=True)
            self.db.add(novo_formulario)
            self.db.flush()

            perguntas_criadas = []
            for p in perguntas:
                pergunta = PerguntaModel(
                    formulario_id=novo_formulario.id,
                    texto=p.texto.strip(),
                    ordem=p.ordem,
                    tipo_resposta=p.tipo_resposta,
                    escopo_id=p.escopo_id,
                )
                self.db.add(pergunta)
                perguntas_criadas.append(pergunta)

            self.db.flush()
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

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
            ],
        }
