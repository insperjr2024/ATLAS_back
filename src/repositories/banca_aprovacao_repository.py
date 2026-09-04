from typing import List, Optional

from sqlalchemy.orm import Session

from src.models.banca_aprovacao_model import BancaAprovacaoModel


class BancaAprovacaoRepository:
    """As assinaturas de aprovação de uma banca (§5.5, §8), por tentativa (§9)."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_banca(self, banca_id: int, sessao: Optional[int] = None) -> List[BancaAprovacaoModel]:
        query = self.db.query(BancaAprovacaoModel).filter(BancaAprovacaoModel.banca_id == banca_id)
        if sessao is not None:
            query = query.filter(BancaAprovacaoModel.sessao == sessao)
        return query.all()

    def get_um(
        self, banca_id: int, papel: str, frente_id: Optional[int], sessao: int
    ) -> Optional[BancaAprovacaoModel]:
        return (
            self.db.query(BancaAprovacaoModel)
            .filter(
                BancaAprovacaoModel.banca_id == banca_id,
                BancaAprovacaoModel.papel == papel,
                BancaAprovacaoModel.frente_id == frente_id,
                BancaAprovacaoModel.sessao == sessao,
            )
            .first()
        )

    def registrar(
        self,
        banca_id: int,
        papel: str,
        frente_id: Optional[int],
        sessao: int,
        usuario_id: int,
        aprovado: bool,
        nota: Optional[str],
    ) -> BancaAprovacaoModel:
        """Grava a decisão — atualiza a linha existente DESTA sessão em vez de
        duplicar.

        ⚠ Responder de novo (trocar de ideia antes do resultado fechar) não
        pode empilhar uma segunda linha para o mesmo (banca, papel, frente,
        sessão): a leitura em `montar_situacao_aprovacao` pegaria só uma das
        duas e a outra ficaria orfã — não há UNIQUE aqui, mesmo padrão de
        `BancaExcecaoChoqueModel`.
        """
        existente = self.get_um(banca_id, papel, frente_id, sessao)
        if existente:
            existente.usuario_id = usuario_id
            existente.aprovado = aprovado
            existente.nota = nota
            self.db.commit()
            self.db.refresh(existente)
            return existente
        linha = BancaAprovacaoModel(
            banca_id=banca_id,
            papel=papel,
            frente_id=frente_id,
            sessao=sessao,
            usuario_id=usuario_id,
            aprovado=aprovado,
            nota=nota,
        )
        self.db.add(linha)
        self.db.commit()
        self.db.refresh(linha)
        return linha
