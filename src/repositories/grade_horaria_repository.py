from datetime import time
from typing import List, Tuple

from sqlalchemy.orm import Session

from src.models.grade_horaria_model import GradeHorariaModel


class GradeHorariaRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_usuario(self, usuario_id: int, semestre_id: int) -> List[GradeHorariaModel]:
        return (
            self.db.query(GradeHorariaModel)
            .filter(
                GradeHorariaModel.usuario_id == usuario_id,
                GradeHorariaModel.semestre_id == semestre_id,
            )
            .order_by(GradeHorariaModel.dia_semana, GradeHorariaModel.hora_inicio)
            .all()
        )

    def get_por_semestre(self, semestre_id: int) -> List[GradeHorariaModel]:
        """Todas as grades do semestre — para quem precisa cruzar horários."""
        return (
            self.db.query(GradeHorariaModel)
            .filter(GradeHorariaModel.semestre_id == semestre_id)
            .all()
        )

    def usuario_ids_com_grade(self, semestre_id: int) -> List[int]:
        """Quem tem AO MENOS uma faixa gravada no semestre.

        Uma consulta agregada, não uma por pessoa: a tela de Membros pergunta
        isso para a lista inteira de uma vez. Grade vazia ("não tenho aula")
        não deixa linha, então não se distingue de "nunca enviou". Não há dado
        que separe os dois, e a compatibilidade já trata os dois igual.
        """
        linhas = (
            self.db.query(GradeHorariaModel.usuario_id)
            .filter(GradeHorariaModel.semestre_id == semestre_id)
            .distinct()
            .all()
        )
        return [uid for (uid,) in linhas]

    def substituir(
        self,
        usuario_id: int,
        semestre_id: int,
        faixas: List[Tuple[int, time, time]],
    ) -> List[GradeHorariaModel]:
        """Troca a grade inteira da pessoa naquele semestre.

        📐 Apaga e regrava em vez de calcular diferença: a tela manda o estado
        final do quadro, não uma lista de mudanças. Fazer diff aqui só criaria
        chance de sobrar faixa que a pessoa desmarcou.

        Um commit só — se a gravação falhar no meio, a pessoa não fica sem
        grade nenhuma.
        """
        self.db.query(GradeHorariaModel).filter(
            GradeHorariaModel.usuario_id == usuario_id,
            GradeHorariaModel.semestre_id == semestre_id,
        ).delete(synchronize_session=False)

        novas = [
            GradeHorariaModel(
                usuario_id=usuario_id,
                semestre_id=semestre_id,
                dia_semana=dia,
                hora_inicio=inicio,
                hora_fim=fim,
            )
            for dia, inicio, fim in faixas
        ]
        self.db.add_all(novas)
        self.db.commit()
        return novas
