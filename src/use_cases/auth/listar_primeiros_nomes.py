"""Só os primeiros nomes dos membros ativos — pra decoração da tela de
login (o globo), que é pública e não pode vazar e-mail, cargo nem nada
além do nome de quem já está na empresa.
"""

import re
import unicodedata
from typing import List

from sqlalchemy.orm import Session

from src.repositories.usuario_repository import UsuarioRepository

# Já têm ponto fixo no globo (`MembersGlobe.tsx` — 4 na linha do equador +
# José S. no polo norte; Heloísa não tem mais ponto fixo, ela aparece pela
# conta real dela mesma, como todo mundo). Se a conta real deles existir no
# banco (é o caso depois que a plataforma foi ao ar), não pode aparecer de
# novo como ponto dinâmico.
NOMES_FIXOS_DO_GLOBO = {
    "henrique montoro",
    "joao baptista",
    "enzo perego",
    "mateus loureiro",
    "jose saraiva",
}


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sem_acento).strip().lower()


def _eh_fundador(nome_completo: str) -> bool:
    partes = set(_normalizar(nome_completo).split(" "))
    return any(
        set(excluido.split(" ")).issubset(partes) for excluido in NOMES_FIXOS_DO_GLOBO
    )


class ListarPrimeirosNomesUseCase:
    def __init__(self, db: Session):
        self.repository = UsuarioRepository(db)

    def execute(self) -> List[str]:
        ativos = self.repository.get_ativos()
        # `dict.fromkeys` tira duplicata mantendo a ordem — dois "João" na
        # empresa não precisam de dois pontos iguais no globo.
        primeiros_nomes = (
            usuario.nome.strip().split(" ")[0]
            for usuario in ativos
            if not _eh_fundador(usuario.nome)
        )
        return list(dict.fromkeys(nome for nome in primeiros_nomes if nome))
