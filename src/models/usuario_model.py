from sqlalchemy import JSON, Boolean, Column, Enum, Integer, String, Text
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from src.database.database import Base


class UsuarioModel(Base):
    """O membro da empresa.

    `posicao` é a única dimensão de permissão (desde 2026-08-07 — antes
    convivia com `cargo_id`, removido: as 13 caixas de permissão agora são
    editadas por posição, ver `PosicaoPermissaoModel`).

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
    posicao = Column(
        Enum(
            "diretor_projetos",
            "diretor_pessoas",
            "diretor",
            "gerente",
            "coordenador",
            "consultor",
            name="posicao_usuario",
        ),
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
    #: Data URI (`data:image/...;base64,...`), já redimensionada no cliente
    #: antes do upload. `MEDIUMTEXT` no MySQL (o `TEXT` puro estoura ~64KB,
    #: pouco até para uma foto pequena); `Text` comum nos outros dialetos,
    #: usados pelos testes em sqlite.
    foto = Column(Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=True)
    #: Tipos de `TIPO_NOTIFICACAO_ENUM` que esta pessoa desligou do e-mail —
    #: só os de `TIPOS_NOTIFICACAO_OPCIONAIS` (ver `notificacao_model.py`)
    #: podem entrar aqui, os fixos ignoram esta lista. Vazia (o padrão) =
    #: tudo ligado, de propósito: um tipo opcional novo já nasce ligado pra
    #: todo mundo, sem precisar de migração de dado.
    notificacoes_email_desativadas = Column(JSON, nullable=False, default=list, server_default="[]")