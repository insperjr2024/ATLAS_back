"""Põe no Arquivo de Contratos os documentos já assinados e arquivados antes
do arquivo existir. Idempotente: quem já está lá só é atualizado.

Uso: PYTHONPATH=. uv run python scripts/arquivar_contratos_existentes.py
"""

from src.database.database import SessionLocal
from src.models.documento_contratual_model import DocumentoContratualModel
from src.use_cases.arquivo_contratos.arquivar import arquivar_documento_assinado


def main() -> None:
    db = SessionLocal()
    documentos = db.query(DocumentoContratualModel).filter_by(status="assinado_e_arquivado").all()
    feitos = 0
    for documento in documentos:
        if arquivar_documento_assinado(db, documento):
            feitos += 1
    print(f"{feitos} de {len(documentos)} documentos assinados estão no arquivo.")


if __name__ == "__main__":
    main()
