from typing import List, Literal, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.desempenho_criterio_repository import DesempenhoCriterioRepository
from src.repositories.desempenho_formulario_repository import DesempenhoFormularioRepository
from src.repositories.desempenho_formulario_secao_repository import DesempenhoFormularioSecaoRepository
from src.use_cases.desempenho_formulario.get_formulario import GetDesempenhoFormularioUseCase


class CriterioInput(BaseModel):
    id: Optional[int] = None
    label: str
    descricao: Optional[str] = None
    tipo_resposta: Literal["nota", "texto"] = "nota"
    limite_caracteres: Optional[int] = None


class SecaoInput(BaseModel):
    id: Optional[int] = None
    titulo: str
    descricao: Optional[str] = None
    criterios: List[CriterioInput]


class UpdateDesempenhoFormularioRequest(BaseModel):
    nota_geral_titulo: Optional[str] = None
    nota_geral_descricao: Optional[str] = None
    comentarios_titulo: Optional[str] = None
    comentarios_descricao: Optional[str] = None
    comentarios_aviso: Optional[str] = None
    secoes: Optional[List[SecaoInput]] = None


class UpdateDesempenhoFormularioUseCase:
    """Edita textos e, se `secoes` vier no request, substitui a árvore
    inteira de seções/critérios daquele formulário — upsert por `id`
    (presente = atualiza, ausente = cria) e remove o que não veio na lista."""

    def __init__(self, db: Session):
        self.db = db
        self.formulario_repo = DesempenhoFormularioRepository(db)
        self.secao_repo = DesempenhoFormularioSecaoRepository(db)
        self.criterio_repo = DesempenhoCriterioRepository(db)

    def execute(self, tipo: str, papel: str, request: UpdateDesempenhoFormularioRequest) -> Optional[dict]:
        formulario = self.formulario_repo.first_by(tipo=tipo, papel=papel)
        if not formulario:
            return None

        textos = request.dict(exclude_unset=True, exclude={"secoes"})
        if textos:
            self.formulario_repo.update(formulario.id, **textos)

        if request.secoes is not None:
            secoes_atuais = {s.id: s for s in self.secao_repo.get_by_formulario(formulario.id)}
            ids_mantidos = set()

            for ordem, secao_in in enumerate(request.secoes):
                if secao_in.id and secao_in.id in secoes_atuais:
                    secao = self.secao_repo.update(
                        secao_in.id, titulo=secao_in.titulo, descricao=secao_in.descricao, ordem=ordem
                    )
                else:
                    secao = self.secao_repo.create(
                        formulario_id=formulario.id,
                        titulo=secao_in.titulo,
                        descricao=secao_in.descricao,
                        ordem=ordem,
                    )
                ids_mantidos.add(secao.id)

                criterios_atuais = {c.id: c for c in self.criterio_repo.get_by_secao(secao.id)}
                criterio_ids_mantidos = set()
                for ordem_c, criterio_in in enumerate(secao_in.criterios):
                    if criterio_in.id and criterio_in.id in criterios_atuais:
                        criterio = self.criterio_repo.update(
                            criterio_in.id,
                            label=criterio_in.label,
                            descricao=criterio_in.descricao,
                            tipo_resposta=criterio_in.tipo_resposta,
                            limite_caracteres=criterio_in.limite_caracteres,
                            ordem=ordem_c,
                        )
                    else:
                        criterio = self.criterio_repo.create(
                            secao_id=secao.id,
                            label=criterio_in.label,
                            descricao=criterio_in.descricao,
                            tipo_resposta=criterio_in.tipo_resposta,
                            limite_caracteres=criterio_in.limite_caracteres,
                            ordem=ordem_c,
                        )
                    criterio_ids_mantidos.add(criterio.id)

                for criterio_id in set(criterios_atuais) - criterio_ids_mantidos:
                    self.criterio_repo.delete(criterio_id)

            for secao_id in set(secoes_atuais) - ids_mantidos:
                self.secao_repo.delete(secao_id)

        return GetDesempenhoFormularioUseCase(self.db).execute(tipo, papel)
