"""Só "Primeiro nome + inicial do sobrenome" dos membros ativos — pra
decoração da tela de login (o globo), que é pública e não pode vazar e-mail,
cargo nem nada além do nome de quem já está na empresa. Mesmo formato dos
fixos do globo (`MembersGlobe.tsx` — "Henrique M.", "Enzo P." etc).
"""

import re
import unicodedata
from typing import List

from sqlalchemy.orm import Session

from src.repositories.usuario_repository import UsuarioRepository

# Já têm ponto fixo no globo (`MembersGlobe.tsx` — 5 na linha do equador +
# José S. no polo norte). Se a conta real deles existir no banco (é o caso
# depois que a plataforma foi ao ar), não pode aparecer de novo como ponto
# dinâmico.
NOMES_FIXOS_DO_GLOBO = {
    "heloisa nogueira",
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


def _nome_exibido(nome_completo: str) -> str:
    partes = nome_completo.strip().split(" ")
    if len(partes) < 2:
        return partes[0]
    return f"{partes[0]} {partes[-1][0].upper()}."


class ListarPrimeirosNomesUseCase:
    def __init__(self, db: Session):
        self.repository = UsuarioRepository(db)

    def execute(self) -> List[str]:
        ativos = self.repository.get_ativos()
        # `dict.fromkeys` tira duplicata mantendo a ordem — dois "João N."
        # na empresa não precisam de dois pontos iguais no globo (mas um
        # "João N." e um "João B." são nomes diferentes, ficam os dois).
        nomes_exibidos = (
            _nome_exibido(usuario.nome)
            for usuario in ativos
            if not _eh_fundador(usuario.nome)
        )
        return list(dict.fromkeys(nome for nome in nomes_exibidos if nome))
