from typing import Optional

from sqlalchemy.orm import Session

from src.repositories.desempenho_criterio_repository import DesempenhoCriterioRepository
from src.repositories.desempenho_formulario_repository import DesempenhoFormularioRepository
from src.repositories.desempenho_formulario_secao_repository import DesempenhoFormularioSecaoRepository


def serializar_criterio(criterio) -> dict:
    return {
        "id": criterio.id,
        "label": criterio.label,
        "descricao": criterio.descricao,
        "tipo_resposta": criterio.tipo_resposta,
        "limite_caracteres": criterio.limite_caracteres,
        "ordem": criterio.ordem,
    }


class GetDesempenhoFormularioUseCase:
    def __init__(self, db: Session):
        self.formulario_repo = DesempenhoFormularioRepository(db)
        self.secao_repo = DesempenhoFormularioSecaoRepository(db)
        self.criterio_repo = DesempenhoCriterioRepository(db)

    def execute(self, tipo: str, papel: str) -> Optional[dict]:
        formulario = self.formulario_repo.first_by(tipo=tipo, papel=papel)
        if not formulario:
            return None

        secoes = []
        for secao in self.secao_repo.get_by_formulario(formulario.id):
            secoes.append(
                {
                    "id": secao.id,
                    "titulo": secao.titulo,
                    "descricao": secao.descricao,
                    "ordem": secao.ordem,
                    "criterios": [
                        serializar_criterio(c) for c in self.criterio_repo.get_by_secao(secao.id)
                    ],
                }
            )

        return {
            "id": formulario.id,
            "tipo": formulario.tipo,
            "papel": formulario.papel,
            "nota_geral_titulo": formulario.nota_geral_titulo,
            "nota_geral_descricao": formulario.nota_geral_descricao,
            "comentarios_titulo": formulario.comentarios_titulo,
            "comentarios_descricao": formulario.comentarios_descricao,
            "comentarios_aviso": formulario.comentarios_aviso,
            "secoes": secoes,
        }
