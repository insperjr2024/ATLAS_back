"""Armazenamento local de arquivos enviados pelo usuário (§6.3: anexo da proposta)."""

from pathlib import Path

from src.config.config import get_settings


def pasta_propostas() -> Path:
    """Cria (se preciso) e devolve a pasta onde os PDFs de proposta ficam."""
    pasta = Path(get_settings().UPLOADS_DIR) / "propostas"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta
