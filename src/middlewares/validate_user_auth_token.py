"""Quem é o usuário da request — e se ele já pode usar a plataforma.

⭐ **A trava da senha provisória mora aqui, no caminho padrão**, e não numa
dependência extra que cada rota some. O sentido importa: assim rota nova nasce
travada, e só as três que precisam responder durante o primeiro acesso pedem
explicitamente a versão sem trava (`get_current_user_em_definicao_de_senha`).
O contrário — travar rota a rota — daria certo até alguém esquecer uma.
"""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from src.database.database import get_db
from src.repositories.usuario_repository import UsuarioRepository
from src.utils.token import decodificar_access_token

security = HTTPBearer()


def get_current_user_em_definicao_de_senha(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Autentica sem cobrar a definição de senha.

    Só para `/auth/me`, `/auth/renovar` e `/auth/definir-senha`: são as três
    que precisam responder DURANTE o primeiro acesso. Cobrar a senha nelas
    trancaria a própria saída do estado — a pessoa entraria e não teria como
    definir a senha nem descobrir quem ela é.
    """
    usuario_id = decodificar_access_token(credentials.credentials)
    if usuario_id is None:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")

    usuario = UsuarioRepository(db).get_by_id(usuario_id)
    if not usuario or not usuario.ativo:
        raise HTTPException(status_code=401, detail="Usuário não encontrado ou inativo")

    return usuario


def get_current_user(usuario=Depends(get_current_user_em_definicao_de_senha)):
    """O usuário da request, já obrigado a ter senha própria.

    403 e não 401: o token é válido e a pessoa É quem diz ser — o que falta é
    um passo dela. 401 faria o front deslogar e devolver ao login, que é
    exatamente o lugar de onde ela acabou de vir.
    """
    if usuario.senha_provisoria:
        raise HTTPException(
            status_code=403,
            detail="Defina a sua senha para usar a plataforma",
        )
    return usuario
