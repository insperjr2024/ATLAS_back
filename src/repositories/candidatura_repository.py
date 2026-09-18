from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from src.models.banca_model import BancaModel
from src.models.candidatura_model import CandidaturaModel
from src.utils.exceptions import RegraDeNegocioError, ResourceInUseError
from typing import Dict, List, Optional
from datetime import datetime


class CandidaturaRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, banca_id: int, usuario_id: int,
               criado_em: datetime, confirmado: bool = False) -> CandidaturaModel:
        candidatura = CandidaturaModel(
            banca_id=banca_id,
            usuario_id=usuario_id,
            criado_em=criado_em,
            confirmado=confirmado
        )
        self.db.add(candidatura)
        try:
            self.db.commit()
        except IntegrityError:
            # Rede de segurança da constraint `uq_candidatura_banca_usuario`
            # (2026-09-16): o use case já barra a duplicata em condições
            # normais, mas dois cliques em "Alocar-se" quase simultâneos
            # podem passar pela checagem antes de qualquer um commitar — foi
            # assim que uma consultora entrou 4x na mesma banca.
            self.db.rollback()
            raise RegraDeNegocioError("Esta pessoa já é candidata desta banca.")
        self.db.refresh(candidatura)
        return candidatura

    def get_by_id(self, candidatura_id: int) -> Optional[CandidaturaModel]:
        return self.db.query(CandidaturaModel).filter(CandidaturaModel.id == candidatura_id).first()

    def get_all(self) -> List[CandidaturaModel]:
        return self.db.query(CandidaturaModel).all()

    def get_by_banca(self, banca_id: int) -> List[CandidaturaModel]:
        return self.db.query(CandidaturaModel).filter(CandidaturaModel.banca_id == banca_id).all()

    def get_by_bancas(self, banca_ids: List[int]) -> List[CandidaturaModel]:
        """As candidaturas de VÁRIAS bancas, numa consulta só.

        Existe para a fila de Aprovações: ela precisa do eleitorado de cada
        banca sem resultado para dizer "1 de 2 votaram", e chamar
        `get_by_banca` num laço é uma consulta por banca.
        """
        if not banca_ids:
            return []
        return (
            self.db.query(CandidaturaModel)
            .filter(CandidaturaModel.banca_id.in_(banca_ids))
            .all()
        )

    def contagem_bancas_por_usuario(self, realizado: Optional[bool] = None) -> Dict[int, int]:
        """Quantas bancas cada pessoa carrega — ranking do push (2026-09-15).

        ⚠ Substitui `ultima_alocacao_por_usuario` como critério do rodízio: o
        rodízio antigo olhava só "há quanto tempo foi a última alocação", não
        quantas bancas a pessoa já carrega — alguém com várias inscrições
        manuais e nenhuma escalação automática recente entrava primeiro na
        fila mesmo já carregado.

        ⚠ Por padrão (`realizado=None`) conta o HISTÓRICO inteiro, não só o
        que ainda vai acontecer (2026-09-15, a pedido — versão anterior
        filtrava só bancas futuras). Quem já realizou banca este semestre já
        carregou a parte dele: contar só a agenda futura fazia essa pessoa
        parecer "livre" de novo assim que a última banca dela acontecia, e o
        rodízio empilhava mais em cima. Só cancelada não conta — ela não
        aconteceu de propósito. **O push sempre chama sem argumento** — a
        régua do rodízio é essa, ponto; o parâmetro existe só pra
        `GetCargaBancasUseCase` oferecer o recorte (já atendidas / futuras /
        todas) que a diretoria pediu pra CONFERIR carga, não pra decidir quem
        escalar (2026-09-17).
        """
        query = (
            self.db.query(
                CandidaturaModel.usuario_id,
                func.count(CandidaturaModel.id),
            )
            .join(BancaModel, BancaModel.id == CandidaturaModel.banca_id)
            .filter(BancaModel.cancelada_em.is_(None))
        )
        if realizado is True:
            query = query.filter(BancaModel.realizado_em.is_not(None))
        elif realizado is False:
            query = query.filter(BancaModel.realizado_em.is_(None))
        linhas = query.group_by(CandidaturaModel.usuario_id).all()
        return {usuario_id: qtd for usuario_id, qtd in linhas}

    def get_by_usuario(self, usuario_id: int) -> List[CandidaturaModel]:
        return self.db.query(CandidaturaModel).filter(CandidaturaModel.usuario_id == usuario_id).all()

    def update(self, candidatura_id: int, **kwargs) -> Optional[CandidaturaModel]:
        candidatura = self.get_by_id(candidatura_id)
        if not candidatura:
            return None
        for key, value in kwargs.items():
            setattr(candidatura, key, value)
        self.db.commit()
        self.db.refresh(candidatura)
        return candidatura

    def delete(self, candidatura_id: int) -> bool:
        candidatura = self.get_by_id(candidatura_id)
        if not candidatura:
            return False
        try:
            self.db.delete(candidatura)
            self.db.commit()
            return True
        except IntegrityError:
            self.db.rollback()
            raise ResourceInUseError()