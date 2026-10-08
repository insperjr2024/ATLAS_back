from typing import Optional

from sqlalchemy.orm import Session

from src.repositories.desempenho_criterio_repository import DesempenhoCriterioRepository
from src.repositories.desempenho_formulario_repository import DesempenhoFormularioRepository
from src.repositories.desempenho_formulario_secao_repository import DesempenhoFormularioSecaoRepository
from src.repositories.desempenho_lote_formulario_repository import DesempenhoLoteFormularioRepository


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
        self.lote_formulario_repo = DesempenhoLoteFormularioRepository(db)

    def execute(self, tipo: str, papel: str, lote_id: Optional[int] = None) -> Optional[dict]:
        """A vigente de (tipo, papel); com `lote_id`, a versão que AQUELE lote
        usa (congelada, se o formulário foi editado "só pra futuros" com ele
        aberto)."""
        formulario = None
        if lote_id is not None:
            congelado_id = self.lote_formulario_repo.formulario_id_de(lote_id, papel)
            if congelado_id is not None:
                formulario = self.formulario_repo.get_by_id(congelado_id)
        if formulario is None:
            formulario = self.formulario_repo.vigente(tipo, papel)
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
            "vigente": formulario.vigente,
            "congelado_em": formulario.congelado_em,
            "secoes": secoes,
        }
