from sqlalchemy import JSON, Boolean, Column, Enum, ForeignKey, Integer, String, Text
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
    #: Referencia `posicao_permissao.posicao` — desde 2026-09-16 não é mais um
    #: ENUM fechado, é um catálogo (ver `PosicaoPermissaoModel`). A FK é o que
    #: impede apagar um cargo que ainda tem gente nele.
    posicao = Column(
        String(50),
        ForeignKey("posicao_permissao.posicao"),
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
    #: ⭐ 2026-09-16, a pedido — substitui os booleanos soltos `coordenador_
    #: vendas` e `bdr`. "Coordenador de vendas" virou posição de verdade
    #: (cargo "vendas", com `pode_coordenar_vendas`/`pode_responsavel_por_
    #: vendas` ligadas) — não precisa mais de campo nenhum aqui, é só a
    #: `posicao` normal da pessoa.
    #:
    #: O que sobra é o BDR: a ÚNICA situação da plataforma em que a pessoa
    #: tem DUAS posições ao mesmo tempo — a principal (`posicao`, sempre
    #: "consultor" na prática) e esta, opcional. As permissões efetivas são a
    #: UNIÃO das duas linhas de `PosicaoPermissaoModel` (ver
    #: `usuario_tem_permissao`). Vazio pra quase todo mundo.
    #:
    #: ⚠ Validado no use case, não em CHECK: hoje só aceita "bdr", e só
    #: quando `posicao == "consultor"` — a regra de negócio é estreita de
    #: propósito ("o único cargo que dá pra ter mais de um é consultor e
    #: bdr"), não um sistema de multi-cargo genérico. Generalizar isso é
    #: decisão futura, não abrir a porta agora pra qualquer combinação.
    cargo_extra = Column(String(50), ForeignKey("posicao_permissao.posicao"), nullable=True)
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