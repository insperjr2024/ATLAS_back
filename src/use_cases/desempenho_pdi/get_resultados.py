"""Resultados de uma pasta de PDI: todo mundo que mandou alguma coisa nela,
com os arquivos por item (2026-10-06, a pedido)."""

from sqlalchemy.orm import Session

from src.repositories.desempenho_mentoria_repository import DesempenhoMentoriaRepository
from src.repositories.desempenho_pdi_envio_repository import DesempenhoPdiEnvioRepository
from src.repositories.desempenho_pdi_item_repository import DesempenhoPdiItemRepository
from src.repositories.desempenho_pdi_pasta_repository import DesempenhoPdiPastaRepository
from src.repositories.usuario_repository import UsuarioRepository
from src.use_cases.desempenho_pdi.get_pendencias import entregue_com_atraso
from src.utils.exceptions import RegraDeNegocioError


class ListResultadosPastaPdiUseCase:
    def __init__(self, db: Session):
        self.pasta_repository = DesempenhoPdiPastaRepository(db)
        self.item_repository = DesempenhoPdiItemRepository(db)
        self.envio_repository = DesempenhoPdiEnvioRepository(db)
        self.mentoria_repository = DesempenhoMentoriaRepository(db)
        self.usuario_repository = UsuarioRepository(db)

    def execute(self, pasta_id: int) -> dict:
        pasta = self.pasta_repository.get_by_id(pasta_id)
        if not pasta:
            raise RegraDeNegocioError("Pasta de PDI não encontrada")
        itens = self.item_repository.get_da_pasta(pasta_id)
        nomes = {u.id: u.nome for u in self.usuario_repository.get_all()}
        mentor_de = {m.mentorado_id: m.mentor_id for m in self.mentoria_repository.get_all()}

        por_mentorado: dict[int, dict] = {}
        for item in itens:
            for envio in self.envio_repository.get_por_item(item.id):
                linha = por_mentorado.setdefault(
                    envio.mentorado_id,
                    {
                        "mentorado_id": envio.mentorado_id,
                        "mentorado_nome": nomes.get(envio.mentorado_id),
                        "mentor_id": mentor_de.get(envio.mentorado_id),
                        "mentor_nome": nomes.get(mentor_de.get(envio.mentorado_id)),
                        "envios": [],
                    },
                )
                linha["envios"].append(
                    {
                        "item_id": item.id,
                        "item_nome": item.nome,
                        "tipo_arquivo": item.tipo_arquivo,
                        "arquivo_nome": envio.arquivo_nome,
                        "enviado_por": envio.enviado_por,
                        "enviado_por_nome": nomes.get(envio.enviado_por),
                        "enviado_em": envio.enviado_em,
                        "atrasado": entregue_com_atraso(envio.enviado_em, pasta.prazo),
                    }
                )

        pessoas = sorted(por_mentorado.values(), key=lambda p: (p["mentorado_nome"] or "").casefold())
        return {
            "pasta_id": pasta.id,
            "pasta_nome": pasta.nome,
            "prazo": pasta.prazo,
            "total_itens": len(itens),
            "pessoas": pessoas,
        }
