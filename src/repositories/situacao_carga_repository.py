from typing import Dict, List, Optional

from src.models.situacao_carga_model import SituacaoCargaModel
from src.repositories.base_repository import BaseRepository

#: Quantas faixas cada papel tem. Fixo, e não configurável, para o destaque da
#: aba de Alocação ser garantido por construção: a última faixa é sempre "a mais
#: carregada", sem depender de alguém lembrar de marcar algo.
FAIXAS_POR_PAPEL = 3

#: A escala inicial, criada na primeira leitura de cada papel. Sai da regra que
#: a diretoria descreveu: para consultor, 2 projetos é o ideal; para
#: coordenador, 4. É ponto de partida — nome, mínimo e cor são editáveis.
PADRAO: Dict[str, List[dict]] = {
    "consultor": [
        {"nome": "Disponível", "min_projetos": 0, "tom": "ok"},
        {"nome": "Quantidade ideal", "min_projetos": 2, "tom": "neutro"},
        {"nome": "Demanda alta", "min_projetos": 3, "tom": "alerta"},
    ],
    "coordenador": [
        {"nome": "Disponível", "min_projetos": 0, "tom": "ok"},
        {"nome": "Quantidade ideal", "min_projetos": 4, "tom": "neutro"},
        {"nome": "Demanda alta", "min_projetos": 5, "tom": "alerta"},
    ],
}


class SituacaoCargaRepository(BaseRepository[SituacaoCargaModel]):
    model = SituacaoCargaModel

    def listar_por_papel(self, papel: str) -> List[SituacaoCargaModel]:
        """Do menor mínimo para o maior — é a ordem em que a escala se lê."""
        return (
            self.db.query(self.model)
            .filter(self.model.papel == papel)
            .order_by(self.model.min_projetos.asc())
            .all()
        )

    def listar_todas(self) -> List[SituacaoCargaModel]:
        return (
            self.db.query(self.model)
            .order_by(self.model.papel.asc(), self.model.min_projetos.asc())
            .all()
        )

    def garantir_padrao(self, papel: str) -> List[SituacaoCargaModel]:
        """Cria a escala inicial se o papel ainda não tiver as três faixas.

        Sem isto, um banco recém-migrado deixaria todo mundo sem situação e a
        aba de Alocação abriria com a coluna vazia — o usuário não teria como
        adivinhar que precisa ir em Configurações primeiro.
        """
        existentes = self.listar_por_papel(papel)
        if len(existentes) == FAIXAS_POR_PAPEL:
            return existentes

        # Só acontece em banco novo ou se alguém mexeu na tabela por fora. Como
        # não há criar nem excluir pela API, reconstruir é seguro.
        for s in existentes:
            self.db.delete(s)
        for dados in PADRAO[papel]:
            self.db.add(self.model(papel=papel, **dados))
        self.db.commit()
        return self.listar_por_papel(papel)


def resolver(situacoes: List[SituacaoCargaModel], total: int) -> Optional[SituacaoCargaModel]:
    """Qual faixa vale para quem tem `total` projetos.

    A escala guarda só o mínimo de cada faixa, então a resposta é a última cujo
    mínimo cabe no total — o que torna buraco e sobreposição impossíveis, em vez
    de algo a validar.

    `None` quando o total fica abaixo do menor mínimo: a diretoria pode subir o
    mínimo da primeira faixa para deixar os menos carregados sem rótulo.
    """
    escolhida = None
    for s in sorted(situacoes, key=lambda x: x.min_projetos):
        if total >= s.min_projetos:
            escolhida = s
        else:
            break
    return escolhida


def faixa_mais_alta(situacoes: List[SituacaoCargaModel]) -> Optional[SituacaoCargaModel]:
    """A faixa de maior mínimo — quem cai nela é quem está com demanda alta.

    É por AQUI que o card de destaque decide, e não pelo nome nem pela cor: a
    posição na escala é estrutural, então o card funciona mesmo que a diretoria
    renomeie as faixas ou troque todas as cores.
    """
    return max(situacoes, key=lambda s: s.min_projetos, default=None)
