from sqlalchemy import Column, ForeignKey, Integer, Time, UniqueConstraint
from src.database.database import Base


class GradeHorariaModel(Base):
    """As faixas em que o membro TEM AULA, por semestre (§11).

    📐 Só existe linha para horário ocupado. Livre é ausência de linha — foi o
    que o núcleo pediu ("salvar só os horários que eles têm aula"), e evita
    gravar 30 linhas por pessoa por semestre para dizer o óbvio.

    📐 Guarda faixa (`hora_inicio`/`hora_fim`), não índice de slot. A tela
    oferece as 6 faixas fixas do Insper e hoje não deixa criar outra, mas
    gravar o horário de verdade significa que abrir para faixa fora do padrão
    depois é mudança de tela, não migration.

    O `semestre_id` é o que atende "atualização por semestre" do §11 — a grade
    da gestão anterior fica no histórico sozinha, sem ninguém apagar nada.
    """

    __tablename__ = "grade_horaria"
    __table_args__ = (
        UniqueConstraint(
            "usuario_id",
            "semestre_id",
            "dia_semana",
            "hora_inicio",
            name="uq_grade_horaria_usuario_semestre_dia_inicio",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuario.id"), nullable=False, index=True)
    semestre_id = Column(Integer, ForeignKey("semestre.id"), nullable=False, index=True)
    #: 0 = segunda … 4 = sexta. Sábado e domingo não entram: a grade do Insper
    #: é de seg a sex, e banca e reunião também.
    dia_semana = Column(Integer, nullable=False)
    hora_inicio = Column(Time, nullable=False)
    hora_fim = Column(Time, nullable=False)
