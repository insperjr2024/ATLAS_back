"""Quem tem uma caixa de permissão — pra notificar, não pra checar login.

⭐ 2026-09-18 — o modelo de permissão é por POSIÇÃO (`posicao_permissao`), sem
um jeito pronto de perguntar "quais PESSOAS têm a caixa X" (só "esta pessoa
tem?", via `usuario_tem_permissao`). Contratos precisa disso pra notificar
"todo o Jurídico" sem saber de antemão quem está na posição — junta
`PosicaoPermissaoRepository.get_posicoes_com_permissao` (já existe, usado
hoje pelo push automático) com `UsuarioRepository.
get_ativos_por_posicoes_ou_cargo_extra` (o mesmo OU de posição-base/
cargo_extra que `usuario_tem_permissao` usa por pessoa).
"""

from typing import List

from sqlalchemy.orm import Session

from src.models.usuario_model import UsuarioModel
from src.repositories.posicao_permissao_repository import PosicaoPermissaoRepository
from src.repositories.usuario_repository import UsuarioRepository


def usuarios_com_permissao(db: Session, campo: str) -> List[UsuarioModel]:
    posicoes = PosicaoPermissaoRepository(db).get_posicoes_com_permissao(campo)
    return UsuarioRepository(db).get_ativos_por_posicoes_ou_cargo_extra(posicoes)
