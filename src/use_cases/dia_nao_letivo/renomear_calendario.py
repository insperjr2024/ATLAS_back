"""Renomeia um calendário de curso dentro de uma frente.

O rótulo É a chave — `dia_nao_letivo.variante`, `frente.calendario_padrao` e
`projeto_escopo.calendario` guardam a mesma string. Foi a troca deliberada por
não ter tabela de domínio, e o preço é este arquivo: renomear não é um UPDATE,
são três, e deixar um para trás desliga o calendário dos escopos que apontavam
para o nome antigo sem erro nenhum aparecer na tela.
"""

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.models.frente_model import FrenteModel
from src.models.projeto_escopo_model import ProjetoEscopoModel
from src.repositories.dia_nao_letivo_repository import DiaNaoLetivoRepository
from src.repositories.frente_repository import FrenteRepository
from src.repositories.semestre_repository import SemestreRepository
from src.utils.exceptions import RegraDeNegocioError


class RenomearCalendarioRequest(BaseModel):
    frente_id: int
    nome: str = Field(min_length=1, max_length=30)


class RenomearCalendarioUseCase:
    def __init__(self, db: Session):
        self.db = db
        self.repository = DiaNaoLetivoRepository(db)
        self.frente_repository = FrenteRepository(db)
        self.semestre_repository = SemestreRepository(db)

    def execute(self, semestre_id: int, atual: str, request: RenomearCalendarioRequest):
        if not self.semestre_repository.get_by_id(semestre_id):
            raise RegraDeNegocioError("Semestre não encontrado")
        frente = self.frente_repository.get_by_id(request.frente_id)
        if not frente:
            raise RegraDeNegocioError("Frente não encontrada")

        novo = request.nome.strip()
        if not novo:
            raise RegraDeNegocioError("O calendário precisa de um nome")
        if novo == atual:
            return {"frente_id": frente.id, "nome": novo, "dias_renomeados": 0}

        existentes = self.repository.listar_variantes(semestre_id, request.frente_id)
        if atual not in existentes:
            raise RegraDeNegocioError(
                f"A frente {frente.nome} não tem um calendário chamado {atual}"
            )
        if novo in existentes:
            raise RegraDeNegocioError(
                f"A frente {frente.nome} já tem um calendário chamado {novo}. "
                "Dois calendários com o mesmo nome seriam o mesmo calendário."
            )

        dias = self.repository.renomear_variante(semestre_id, request.frente_id, atual, novo)

        # Os dois vínculos que apontam para o rótulo. Não são por semestre: a
        # base do escopo e o padrão da frente atravessam a virada de gestão,
        # então renomear num semestre renomeia o vínculo para todos. É o
        # comportamento certo enquanto o nome do calendário for o mesmo entre
        # semestres, que é o caso ("Engenharias" não muda em julho).
        #
        # ⚠ O escopo é filtrado também pela FRENTE: o rótulo só é único dentro
        # dela, e sem esse recorte renomear "Engenharias" na Tech renomearia um
        # calendário de mesmo nome de outra frente.
        self.db.query(FrenteModel).filter(
            FrenteModel.id == request.frente_id,
            FrenteModel.calendario_padrao == atual,
        ).update({FrenteModel.calendario_padrao: novo})
        escopos = (
            self.db.query(ProjetoEscopoModel)
            .filter(
                ProjetoEscopoModel.frente_id == request.frente_id,
                ProjetoEscopoModel.calendario == atual,
            )
            .update({ProjetoEscopoModel.calendario: novo})
        )

        self.db.commit()
        return {
            "frente_id": frente.id,
            "nome": novo,
            "dias_renomeados": dias,
            "escopos_renomeados": escopos,
        }
