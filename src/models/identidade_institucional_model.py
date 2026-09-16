from sqlalchemy import Column, Integer, String
from src.database.database import Base


class IdentidadeInstitucionalModel(Base):
    """Linha única (id=1) com a identidade institucional usada na geração de
    documentos jurídicos: quem é o presidente e quem são as testemunhas fixas
    da Insper Jr na gestão vigente. Muda a cada troca de gestão.

    ⭐ 2026-09-16 — vinha de `ConfiguracaoModel` na plataforma Contratos, que
    também guardava a gestão atual (um número calculado à parte). Aqui isso
    não é necessário: gestão já é `SemestreRepository(db).get_ativo()`, a
    mesma entidade que o resto do ATLAS usa (§12) — sem reinventar.
    """

    __tablename__ = "identidade_institucional"

    id = Column(Integer, primary_key=True, default=1)

    presidente_nome = Column(String(255), nullable=False, server_default="JOSÉ ROBERTO SARAIVA COSTA JÚNIOR")
    presidente_cpf = Column(String(20), nullable=False, server_default="042.777.813-14")
    presidente_rg = Column(String(30), nullable=False, server_default="688539531")
    presidente_orgao_emissor = Column(String(20), nullable=False, server_default="SSP/SP")
    presidente_endereco = Column(
        String(500), nullable=False,
        server_default="Rua Casa do Ator, nº 829, Vila Olímpia, CEP: 4546003, São Paulo/SP",
    )
    presidente_estado_civil = Column(String(30), nullable=False, server_default="solteiro")
    presidente_nacionalidade = Column(String(30), nullable=False, server_default="brasileiro")
    presidente_profissao = Column(String(100), nullable=False, server_default="estudante")
    #: Contato de apoio do presidente. Nullable: nenhum fluxo automático usa
    #: hoje, só aparece na tela de administração.
    presidente_email = Column(String(255), nullable=True)
    presidente_telefone = Column(String(30), nullable=True)

    #: Testemunha 1 = testemunha da Insper Jr, impressa (lado esquerdo) em
    #: todos os documentos. Testemunha 2 = padrão do CONTRATANTE quando o
    #: cliente não informa testemunha própria, e também 2ª testemunha da
    #: Insper quando o cliente informa duas. Ambas são só nomes impressos no
    #: documento.
    testemunha1_nome = Column(String(255), nullable=False, server_default="Pedro de Paula Eduardo")
    testemunha1_cpf = Column(String(20), nullable=False, server_default="495.388.168-03")
    testemunha1_email = Column(String(255), nullable=True)
    testemunha1_telefone = Column(String(30), nullable=True)
    testemunha2_nome = Column(String(255), nullable=False, server_default="Matias Bordalo Amaro Krueder")
    testemunha2_cpf = Column(String(20), nullable=False, server_default="477.886.678-97")
    testemunha2_email = Column(String(255), nullable=True)
    testemunha2_telefone = Column(String(30), nullable=True)
