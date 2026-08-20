from typing import List, Optional

from sqlalchemy.orm import Session

from src.models.projeto_vendedor_model import ProjetoVendedorModel
from src.repositories.base_repository import BaseRepository


class ProjetoVendedorRepository(BaseRepository[ProjetoVendedorModel]):
    model = ProjetoVendedorModel

    def get_by_projeto(self, projeto_id: int) -> List[ProjetoVendedorModel]:
        return self.filter_by(projeto_id=projeto_id)

    def get_by_projetos(self, projeto_ids: List[int]) -> List[ProjetoVendedorModel]:
        """Em bloco, como o resto das listagens (§6.2) — a ficha de vários
        projetos não pode virar uma query por linha."""
        if not projeto_ids:
            return []
        return (
            self.db.query(self.model)
            .filter(self.model.projeto_id.in_(projeto_ids))
            .all()
        )

    def definir(
        self, projeto_id: int, usuario_ids: List[int], registrado_por: Optional[int] = None
    ) -> List[ProjetoVendedorModel]:
        """Deixa a lista de vendedores do projeto exatamente igual a
        `usuario_ids`.

        Só mexe na DIFERENÇA: apaga quem saiu, insere quem entrou e não toca em
        quem ficou. Apagar tudo e reinserir seria mais curto, mas perderia o
        `registrado_em` de quem já estava lá — e essa data é a única pista de
        quando a venda foi registrada.
        """
        atuais = {v.usuario_id: v for v in self.get_by_projeto(projeto_id)}
        desejados = set(usuario_ids)

        for usuario_id, linha in atuais.items():
            if usuario_id not in desejados:
                self.db.delete(linha)

        for usuario_id in desejados - set(atuais):
            self.db.add(
                self.model(
                    projeto_id=projeto_id,
                    usuario_id=usuario_id,
                    registrado_por=registrado_por,
                )
            )

        self.db.commit()
        return self.get_by_projeto(projeto_id)

    def projeto_ids_do_vendedor(self, usuario_id: int) -> List[int]:
        return [
            linha.projeto_id
            for linha in self.filter_by(usuario_id=usuario_id)
        ]
