"""Conversão de .docx pra .pdf via LibreOffice headless (§ Contratos).

⭐ 2026-09-16 — porta de `contratos-backend/src/utils/pdf.py`, sem mudança:
não depende de nada específico da Contratos, é só um subprocess.
"""

import os
import subprocess

from src.config.config import get_settings


def converter_docx_para_pdf(docx_path: str) -> str:
    """Converte um .docx em .pdf usando o LibreOffice headless.

    Ponto sensível em produção: se o servidor não tiver LibreOffice
    disponível, trocar esta função por uma chamada a um serviço externo de
    conversão.

    Por padrão usa o comando "soffice" (precisa estar no PATH). Se isso for
    problemático, defina SOFFICE_PATH no .env com o caminho completo do
    executável, ex.: SOFFICE_PATH=/usr/bin/soffice.
    """
    out_dir = os.path.dirname(docx_path)
    env = {**os.environ, "SAL_USE_VCLPLUGIN": "svp"}
    soffice_bin = get_settings().SOFFICE_PATH

    try:
        subprocess.run(
            [soffice_bin, "--headless", "--convert-to", "pdf", "--outdir", out_dir, docx_path],
            check=True,
            env=env,
            capture_output=True,
        )
    except FileNotFoundError:
        raise RuntimeError(
            f'LibreOffice não foi encontrado em "{soffice_bin}". Instale o LibreOffice '
            "(https://www.libreoffice.org/download/) e, se o comando 'soffice' não estiver "
            "disponível no PATH, defina SOFFICE_PATH no .env com o caminho completo do "
            "executável."
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Falha ao converter o documento para PDF: {e.stderr.decode(errors='ignore')}")

    pdf_path = docx_path[:-5] + ".pdf" if docx_path.endswith(".docx") else docx_path + ".pdf"
    if not os.path.exists(pdf_path):
        raise RuntimeError(f"Conversão não gerou o PDF esperado em {pdf_path}.")
    return pdf_path
