from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.repositories.dia_nao_letivo_repository import DiaNaoLetivoRepository
from src.repositories.semestre_repository import SemestreRepository
from src.utils.exceptions import RegraDeNegocioError

TipoDiaNaoLetivo = Literal["feriado", "prova", "recesso"]


class DiaNaoLetivoItem(BaseModel):
    data: date
    tipo: TipoDiaNaoLetivo = "feriado"
    descricao: Optional[str] = None


class CreateDiasNaoLetivosRequest(BaseModel):
    """Carga em lote: a diretoria sobe o calendário do semestre de uma vez.

    `frente_id` nulo grava o calendário GLOBAL, que vale para todas as frentes
    — é onde mora o feriado nacional. Com frente, grava o calendário base
    daquela frente, que vem do PDF do curso dela.

    `variante` grava dentro de UM calendário da frente ("Ciência da
    Computação"), quando ela tem mais de um. Nula, grava o que vale para a
    frente inteira — que é o caso de toda frente com um curso só.
    """

    dias: List[DiaNaoLetivoItem]
    substituir: bool = False
    frente_id: Optional[int] = None
    variante: Optional[str] = None


class CreateDiasNaoLetivosUseCase:
    def __init__(self, db: Session):
        self.repository = DiaNaoLetivoRepository(db)
        self.semestre_repository = SemestreRepository(db)

    def execute(self, semestre_id: int, request: CreateDiasNaoLetivosRequest):
        semestre = self.semestre_repository.get_by_id(semestre_id)
        if not semestre:
            raise RegraDeNegocioError("Semestre não encontrado")

        # Um calendário de curso mora DENTRO de uma frente. Sem frente ele
        # seria um feriado nacional que só vale para alguns cursos, que é uma
        # contradição — e, pior, ficaria invisível: a resolução por projeto só
        # procura variante dentro da frente.
        variante = (request.variante or "").strip() or None
        if variante and request.frente_id is None:
            raise RegraDeNegocioError(
                "Um calendário de curso precisa de uma frente: quem vale para todas "
                "é o calendário global, que não tem curso."
            )

        # Substituir apaga só o calendário DESTA frente, e dentro dela só ESTA
        # variante: recarregar o PDF de Business não pode derrubar o que já foi
        # conferido em Tech, nem o de Ciência da Computação apagar o das
        # engenharias, que está na mesma frente.
        if request.substituir:
            self.repository.delete_da_frente(semestre_id, request.frente_id, variante)

        existentes = {
            d.data
            for d in self.repository.get_by_semestre(semestre_id)
            if d.frente_id == request.frente_id and d.variante == variante
        }

        criados, ignorados = [], []
        for item in request.dias:
            # 📐 Semana de prova é do CURSO, não do país: as datas de avaliação
            # de Administração não são as de Engenharia. Um `prova` global
            # aplicaria a prova de uma frente ao cronograma de todas.
            #
            # Feriado é o contrário — global por natureza — mas nada impede que
            # uma frente tenha um feriado só dela (feriado escolar do curso),
            # então esse lado não é travado.
            if item.tipo == "prova" and request.frente_id is None:
                raise RegraDeNegocioError(
                    "Semana de avaliação precisa de uma frente: cada curso tem as suas datas. "
                    "Feriados é que valem para todas."
                )
            if not (semestre.inicio <= item.data <= semestre.fim):
                raise RegraDeNegocioError(
                    f"{item.data:%d/%m/%Y} está fora do semestre "
                    f"{semestre.nome} ({semestre.inicio:%d/%m/%Y} a {semestre.fim:%d/%m/%Y})"
                )
            # Recarregar o calendário não pode explodir no unique: o dia que já
            # está lá é só ignorado.
            if item.data in existentes:
                ignorados.append(item.data)
                continue
            registro = self.repository.create(
                semestre_id=semestre_id,
                frente_id=request.frente_id,
                variante=variante,
                data=item.data,
                tipo=item.tipo,
                descricao=item.descricao,
            )
            existentes.add(item.data)
            criados.append(registro)

        return {
            "semestre_id": semestre_id,
            "frente_id": request.frente_id,
            "variante": variante,
            "criados": len(criados),
            "ignorados": len(ignorados),
            "dias": [
                {
                    "id": d.id,
                    "data": d.data,
                    "tipo": d.tipo,
                    "descricao": d.descricao,
                }
                for d in criados
            ],
        }
