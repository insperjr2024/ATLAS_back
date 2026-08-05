"""Lê o PDF do calendário acadêmico e devolve o que encontrou — sem gravar.

📐 Nunca grava direto, de propósito. A leitura é posicional e pode errar se o
Insper mudar o layout, então a diretoria confere e corrige na tela antes de
salvar. É o mesmo contrato que o §11 do case exige para a grade horária:
"a plataforma nunca salva direto... pede que confira e corrija antes".
"""

from typing import BinaryIO, Optional

from sqlalchemy.orm import Session

from src.repositories.semestre_repository import SemestreRepository
from src.utils.calendario_pdf import ler_calendario
from src.utils.exceptions import RegraDeNegocioError


class LerCalendarioPdfUseCase:
    def __init__(self, db: Session):
        self.semestre_repository = SemestreRepository(db)

    def execute(self, semestre_id: int, arquivo: BinaryIO, frente_id: Optional[int] = None):
        semestre = self.semestre_repository.get_by_id(semestre_id)
        if not semestre:
            raise RegraDeNegocioError("Semestre não encontrado")

        # O PDF é anual e a tabela é por semestre. O ano sai do próprio
        # semestre, e não do nome do arquivo, que ninguém controla.
        try:
            leitura = ler_calendario(arquivo, semestre.inicio.year)
        except ValueError as e:
            raise RegraDeNegocioError(str(e))

        # Fora da janela do semestre não interessa: o PDF cobre janeiro a
        # dezembro e o semestre é metade disso.
        dentro = [d for d in leitura.dias if semestre.inicio <= d.data <= semestre.fim]
        fora = len(leitura.dias) - len(dentro)

        return {
            "semestre_id": semestre_id,
            "frente_id": frente_id,
            "dias": [
                {
                    "data": d.data,
                    "tipo": d.tipo,
                    "codigo": d.codigo,
                    "descricao": d.descricao,
                    # "global" (feriado, vale para todas) ou "frente" (semana de
                    # avaliação, que é do curso). Quem grava usa isso para
                    # separar os dois lotes.
                    "escopo": d.escopo,
                }
                for d in dentro
            ],
            "resumo": {
                "lidos": len(leitura.dias),
                "no_semestre": len(dentro),
                "fora_do_semestre": fora,
                "globais": len([d for d in dentro if d.escopo == "global"]),
                "da_frente": len([d for d in dentro if d.escopo == "frente"]),
                "recessos_ignorados": len(leitura.ignorados),
                # Diferente de zero significa que algum código não achou o dia
                # dele — sinal de layout mudado. A tela avisa em vez de fingir
                # que leu tudo.
                "nao_reconhecidos": leitura.nao_casados,
            },
        }
