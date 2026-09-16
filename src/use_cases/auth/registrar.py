import secrets
from typing import Optional

from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from src.repositories.posicao_permissao_repository import PosicaoPermissaoRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.auth.senha_provisoria import emitir_senha_provisoria
from src.use_cases.usuario.get_usuario import serializar_usuario
from src.utils.email import EmailSender
from src.utils.senha import hash_senha
from src.utils.exceptions import RegraDeNegocioError


class RegistrarRequest(BaseModel):
    """Pré-cadastro feito pela diretoria (§10) — a rota já exige token.

    `posicao` entra aqui porque é o que define o que a pessoa enxerga E pode
    fazer assim que faz o primeiro login — desde 2026-08-07 não há mais
    `cargo` separado para escolher; as caixas de permissão vêm inteiras da
    posição (`GET /posicoes-permissoes`).

    ⚠ Desde 2026-09-16 não é mais um `Literal` fechado nos 6 cargos padrão —
    `posicao_permissao` é um catálogo que a diretoria pode estender (ver
    `create_posicao_permissao.py`), e o `Literal` recusaria qualquer cargo
    novo no boundary da API antes mesmo de chegar ao use case. Quem valida
    agora é `RegistrarUseCase`, contra as linhas que existem de verdade.

    ⭐ **Não há campo de senha**, e a ausência é a regra: quem cadastra não
    escolhe a senha de ninguém. O sistema sorteia uma provisória, manda por
    e-mail e obriga a pessoa a definir a dela no primeiro acesso.
    """

    nome: str
    email_insper: str
    posicao: str = "consultor"
    #: ⭐ 2026-09-16 — o cargo extra opcional. Só aceita "bdr", e só quando
    #: `posicao` é "consultor" (ver a mesma regra em `update_usuario.py`) —
    #: é a única situação em que a pessoa acumula duas posições.
    cargo_extra: Optional[str] = None
    semestre_graduacao: Optional[int] = Field(default=None, ge=1, le=8)


class RegistrarUseCase:
    def __init__(self, db: Session, email_sender=None):
        self.usuario_repository = UsuarioRepository(db)
        self.posicao_repository = PosicaoPermissaoRepository(db)
        # Injetável para o teste passar um dublê — mesma costura do
        # `SolicitarRecuperacaoUseCase`. Sem ela, rodar a suíte mandaria
        # e-mail de verdade.
        self.email_sender = email_sender or EmailSender()

    def execute(self, request: RegistrarRequest):
        existente = self.usuario_repository.get_by_email_insper(request.email_insper)
        if existente:
            raise RegraDeNegocioError("Já existe uma conta com este email")

        if not self.posicao_repository.get_by_posicao(request.posicao):
            raise RegraDeNegocioError("Posição inválida")

        if request.cargo_extra:
            if request.cargo_extra != "bdr":
                raise RegraDeNegocioError('O único cargo extra hoje é "bdr"')
            if request.posicao != "consultor":
                raise RegraDeNegocioError("BDR só pode ser adicionado a quem é consultor")

        # A senha real é sorteada logo abaixo, por `emitir_senha_provisoria`.
        # O placeholder existe porque `senha_hash` é NOT NULL e a emissão
        # precisa do usuário já criado (ela grava por id).
        usuario = self.usuario_repository.create(
            nome=request.nome,
            email_insper=request.email_insper,
            senha_hash=hash_senha(secrets.token_urlsafe(32)),
            posicao=request.posicao,
            cargo_extra=request.cargo_extra,
            status="ativo",
            ativo=True,
            semestre_graduacao=request.semestre_graduacao,
            senha_provisoria=True,
        )

        senha, email_enviado = emitir_senha_provisoria(
            self.usuario_repository, self.email_sender, usuario
        )

        # ⚠ A ÚNICA vez que a senha em claro aparece. Quem cadastrou é quem
        # consegue repassá-la se o e-mail não sair — depois desta resposta ela
        # não existe mais em lugar nenhum.
        return {
            **serializar_usuario(usuario),
            "senha_provisoria_gerada": senha,
            "email_enviado": email_enviado,
        }
