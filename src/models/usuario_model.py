from sqlalchemy import Boolean, Column, Enum, ForeignKey, Integer, String
from src.database.database import Base


class UsuarioModel(Base):
    """O membro da empresa.

    Duas dimensões diferentes, de propósito:
    - `cargo_id` → as 3 flags de permissão DO MÓDULO DE BANCAS (P2/P3);
    - `posicao`  → o perfil do §3, que manda no resto da plataforma.

    `status` distingue os dois casos de saída do §10 — o booleano `ativo`
    sozinho não conseguia. `ativo` vira espelho (`status == "ativo"`) para não
    quebrar o login nem o front que já lê esse campo.
    """

    __tablename__ = "usuario"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(150), nullable=False)
    email_insper = Column(String(150), unique=True, nullable=False)
    senha_hash = Column(String(255), nullable=False)
    #: ⭐ A senha atual é a PROVISÓRIA que foi por e-mail no cadastro, e a
    #: pessoa ainda não escolheu a dela. Enquanto isto for verdade, o login
    #: funciona mas a plataforma fica travada (`get_current_user`): a única
    #: coisa que responde é a tela de definir senha.
    #:
    #: Nasce `False` para todo mundo que já estava cadastrado — quem já tem
    #: senha própria não é empurrado para tela nenhuma.
    senha_provisoria = Column(Boolean, nullable=False, default=False, server_default="0")
    cargo_id = Column(Integer, ForeignKey("cargo.id"), nullable=False)
    posicao = Column(
        Enum("diretor", "gerente", "coordenador", "consultor", name="posicao_usuario"),
        nullable=False,
        default="consultor",
        server_default="consultor",
    )
    status = Column(
        Enum("ativo", "ex_membro", "desligado", name="status_usuario"),
        nullable=False,
        default="ativo",
        server_default="ativo",
    )
    ativo = Column(Boolean, default=True, nullable=False)
    # 1º a 8º semestre da graduação — nullable porque diretoria/gerência não
    # necessariamente são alunos de graduação em curso.
    semestre_graduacao = Column(Integer, nullable=True)