"""O Repositório: todo documento jurídico final assinado, por gestão (§ Contratos).

⭐ 2026-09-18 — porta a tela `Repositorio.tsx`/`RepositorioProjeto.tsx` do
sistema antigo, adaptada ao arquivamento por `gestao_id` (não por pasta —
ver docstring de `marcar_assinado.py`).
"""

from typing import List, Optional

from sqlalchemy.orm import Session

from src.repositories.documento_contratual_repository import DocumentoContratualRepository
from src.repositories.documento_contratual_versao_repository import (
    DocumentoContratualVersaoRepository,
)
from src.repositories.semestre_repository import SemestreRepository
from src.utils.status_documento_contratual import ROTULO_TIPO


class ListarRepositorioContratualUseCase:
    def __init__(self, db: Session):
        self.documentos = DocumentoContratualRepository(db)
        self.versoes = DocumentoContratualVersaoRepository(db)
        self.semestres = SemestreRepository(db)

    def execute(self, gestao_id: Optional[int] = None, busca: Optional[str] = None) -> List[dict]:
        documentos = self.documentos.list_arquivados(gestao_id=gestao_id, busca=busca)
        semestres = {s.id: s for s in self.semestres.get_all()}

        itens = []
        for documento in documentos:
            versao_final = self.versoes.ultima_versao_obj(documento.id)
            gestao = semestres.get(documento.gestao_id)
            itens.append(
                {
                    "id": documento.id,
                    "projeto_id": documento.projeto_id,
                    "projeto_nome": documento.projeto.nome,
                    "cliente": documento.projeto.cliente,
                    "tipo": documento.tipo,
                    "tipo_rotulo": ROTULO_TIPO.get(documento.tipo, "Documento"),
                    "gestao_id": documento.gestao_id,
                    "gestao_nome": gestao.nome if gestao else None,
                    # O conteúdo mora no banco (ver docstring do model) — o
                    # front baixa por `documento.id` no endpoint dedicado,
                    # não por caminho. Só avisa se há o que baixar.
                    "tem_arquivo": bool(versao_final and versao_final.pdf_conteudo),
                    "arquivado_em": versao_final.arquivado_em if versao_final else None,
                }
            )
        return itens
