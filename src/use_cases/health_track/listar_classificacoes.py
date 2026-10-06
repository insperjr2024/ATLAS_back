from src.models.health_track_avaliacao_model import CLASSIFICACOES_HEALTH_TRACK


class ListarClassificacoesUseCase:
    """Verde, amarelo e vermelho com nome e descrição (§3), na ordem do mais
    saudável para o mais crítico — a tela de preenchimento lê daqui em vez de
    copiar o texto da spec."""

    def execute(self) -> list[dict]:
        return [dict(c) for c in CLASSIFICACOES_HEALTH_TRACK]
