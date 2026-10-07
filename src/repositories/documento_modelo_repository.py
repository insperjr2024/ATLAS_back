from typing import Optional

from src.models.documento_modelo_model import DocumentoModeloModel
from src.repositories.base_repository import BaseRepository


class DocumentoModeloRepository(BaseRepository[DocumentoModeloModel]):
    model = DocumentoModeloModel

    def get_por_tipo(self, tipo: str) -> Optional[DocumentoModeloModel]:
        return self.first_by(tipo=tipo)

    def substituir(self, tipo: str, arquivo_nome: str, conteudo: bytes, enviado_por: Optional[int]):
        atual = self.get_por_tipo(tipo)
        if atual:
            atual.arquivo_nome = arquivo_nome
            atual.arquivo_conteudo = conteudo
            atual.enviado_por = enviado_por
            from src.utils.fuso import agora_utc

            atual.enviado_em = agora_utc()
            self.db.commit()
            self.db.refresh(atual)
            return atual
        return self.create(tipo=tipo, arquivo_nome=arquivo_nome, arquivo_conteudo=conteudo, enviado_por=enviado_por)
