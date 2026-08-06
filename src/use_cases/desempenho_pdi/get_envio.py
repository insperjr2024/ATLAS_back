from sqlalchemy.orm import Session

from src.repositories.desempenho_pdi_envio_repository import DesempenhoPdiEnvioRepository
from src.repositories.desempenho_pdi_item_repository import DesempenhoPdiItemRepository
from src.repositories.desempenho_pdi_pasta_repository import DesempenhoPdiPastaRepository
from src.repositories.semestre_repository import SemestreRepository
from src.repositories.usuario_repository import UsuarioRepository


class ListEnviosDoUsuarioUseCase:
    """Uma linha por PASTA, com a checklist de itens dentro — cada item com
    ou sem envio. É a lista que a tela de relatório de PDI desenha."""

    def __init__(self, db: Session):
        self.pasta_repository = DesempenhoPdiPastaRepository(db)
        self.item_repository = DesempenhoPdiItemRepository(db)
        self.envio_repository = DesempenhoPdiEnvioRepository(db)
        self.usuario_repository = UsuarioRepository(db)
        self.semestre_repository = SemestreRepository(db)

    def execute(self, mentorado_id: int) -> list[dict]:
        envios_por_item = {e.item_id: e for e in self.envio_repository.get_por_mentorado(mentorado_id)}
        resultado = []
        for pasta in self.pasta_repository.get_ordenadas():
            # Semestre é derivado do prazo (não é campo da pasta) — mesmo
            # cálculo de `serializar_pasta` em create_pasta.py.
            semestre = self.semestre_repository.get_por_data(pasta.prazo)
            itens = []
            for item in self.item_repository.get_da_pasta(pasta.id):
                envio = envios_por_item.get(item.id)
                enviado_por = self.usuario_repository.get_by_id(envio.enviado_por) if envio else None
                itens.append(
                    {
                        "item_id": item.id,
                        "item_nome": item.nome,
                        "tipo_arquivo": item.tipo_arquivo,
                        "envio": (
                            {
                                "arquivo_nome": envio.arquivo_nome,
                                "enviado_por": envio.enviado_por,
                                "enviado_por_nome": enviado_por.nome if enviado_por else None,
                                "enviado_em": envio.enviado_em,
                            }
                            if envio
                            else None
                        ),
                    }
                )
            resultado.append(
                {
                    "pasta_id": pasta.id,
                    "pasta_nome": pasta.nome,
                    "pasta_tipo": pasta.tipo,
                    "pasta_semestre": semestre.nome if semestre else None,
                    "prazo": pasta.prazo,
                    "itens": itens,
                }
            )
        return resultado
