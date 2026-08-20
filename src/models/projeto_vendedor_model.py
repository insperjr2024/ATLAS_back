from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint, func
from src.database.database import Base


class ProjetoVendedorModel(Base):
    """Quem VENDEU o projeto. Zero, um ou vários por projeto.

    ⭐ **Vendedor não é posição, é vínculo por projeto.** Não existe alguém que
    só vende: todo vendedor é um consultor (ou um coordenador comercial, que
    para a plataforma é a mesma coisa) que trouxe aquele projeto. Por isso não
    virou um valor de `posicao_usuario` — virou esta tabela.

    ⚠ **Por que não `projeto_membro.papel`.** Era o caminho óbvio: a tabela já
    existe e já tem `papel`. Mas 20 use cases leem aquele enum, e um terceiro
    valor mudaria todos em silêncio — o vendedor passaria a ocupar vaga de
    consultor na capacidade (`situacao_carga`), a entrar no ciclo de Avaliação
    de Desempenho e a aparecer no painel de equipe. Vender não é executar, e
    quem vendeu não faz parte do time que entrega.

    O que ele ganha é VISÃO, não trabalho: enxerga o projeto que vendeu
    (`aplicar_recorte_visao`), em modo somente leitura
    (`exigir_acesso_ao_projeto`). E perde uma coisa: não pode avaliar a banca
    de um projeto que vendeu, pela mesma razão do §8 que já barra a equipe.

    Sem `saiu_em`, ao contrário de `projeto_membro`: quem vendeu vendeu, é fato
    consumado. Desmarcar aqui é corrigir um registro errado, não registrar uma
    saída.
    """

    __tablename__ = "projeto_vendedor"
    __table_args__ = (
        # A mesma pessoa não vende o mesmo projeto duas vezes. Sem isto, dois
        # cliques no botão criariam duas linhas e a pessoa apareceria repetida
        # na ficha do projeto.
        UniqueConstraint("projeto_id", "usuario_id", name="uq_projeto_vendedor"),
    )

    id = Column(Integer, primary_key=True, index=True)
    projeto_id = Column(
        Integer, ForeignKey("projeto.id", ondelete="CASCADE"), nullable=False, index=True
    )
    usuario_id = Column(Integer, ForeignKey("usuario.id"), nullable=False, index=True)
    registrado_em = Column(DateTime, nullable=False, server_default=func.now())
    #: Quem marcou. Nulo quando a pessoa que registrou foi excluída de vez —
    #: mesma razão de `projeto.criado_por`: o registro da venda sobrevive a
    #: quem o digitou.
    registrado_por = Column(Integer, ForeignKey("usuario.id"), nullable=True)
