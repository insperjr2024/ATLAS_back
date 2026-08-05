from sqlalchemy import Column, Integer, String, Boolean
from src.database.database import Base


class CargoModel(Base):
    """As permissões de plataforma, uma caixa por capacidade.

    `pode_gerenciar_cargos` é a única que não basta sozinha: editar cargo é
    editar quem pode o quê, então a rota também exige `posicao == "diretor"`.
    Sem isso, quem tivesse a caixa marcada podia se auto-conceder o resto.
    """

    __tablename__ = "cargo"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    pode_definir_formulario = Column(Boolean, default=False, nullable=False)
    pode_agendar_banca = Column(Boolean, default=False, nullable=False)
    pode_gerenciar_cargos = Column(Boolean, default=False, nullable=False)
    pode_gerenciar_membros = Column(Boolean, default=False, nullable=False)
    pode_gerenciar_nucleo = Column(Boolean, default=False, nullable=False)
    # Avaliação de Desempenho (P4) — antes eram travadas por `posicao`
    # (gestão/diretoria) direto na rota. Viraram caixa de cargo para a
    # diretoria poder delegar sem promover ninguém de posição.
    pode_gerenciar_desempenho = Column(Boolean, default=False, nullable=False)
    pode_definir_formulario_desempenho = Column(Boolean, default=False, nullable=False)