"""Edição manual do texto de um .docx já gerado (§ Contratos).

⭐ 2026-09-18 — porta de `contratos-backend/src/documentos/editar_docx.py`. O
Jurídico ajusta a redação de uma cláusula sem mexer nos dados estruturados
(que exigiriam reabrir o formulário e gerar tudo de novo).

Duas salvaguardas tornam isso seguro:

1. A tabela de parcelas fica em `doc.tables`, fora de `doc.paragraphs` — a
   edição indexada por parágrafo não a alcança. O bloco de assinaturas/
   testemunhas é composto por parágrafos alinhados por TAB; são reconhecidos
   pela presença de "\\t" e excluídos da lista editável.
2. Os parágrafos podem ter mais de um `run` (ex.: rótulo "Cláusula Nª" em
   negrito + corpo). Ao reescrever, o texto vai para o `run` de corpo e os
   demais são esvaziados, preservando a formatação do parágrafo.

⚠ NUNCA usar `paragrafo.text = novo`: esse setter do python-docx recria o
conteúdo num único `run` sem formatação, e um título perderia o negrito.
"""

from typing import Dict, List

from docx import Document
from docx.opc.exceptions import PackageNotFoundError


def _abrir(docx_path: str) -> Document:
    try:
        return Document(docx_path)
    except PackageNotFoundError:
        raise ValueError("O arquivo .docx deste rascunho não está mais disponível no servidor.")


def _editavel(paragrafo) -> bool:
    # Linhas de assinatura/testemunha são tabuladas ("Nome:\t\t\tCPF:") — não
    # fazem sentido como um campo de texto único, e reescrevê-las apagaria o
    # alinhamento por TAB.
    return bool(paragrafo.runs) and bool(paragrafo.text.strip()) and "\t" not in paragrafo.text


def extrair_paragrafos_editaveis(docx_path: str) -> List[dict]:
    """[{"ref": índice em doc.paragraphs, "texto": ...}].

    `ref` é a posição REAL na lista: parágrafos vazios/tabulados são
    omitidos do resultado, mas não reindexam os demais — é o que permite
    escrever de volta no parágrafo certo depois.
    """
    doc = _abrir(docx_path)
    return [
        {"ref": i, "texto": p.text}
        for i, p in enumerate(doc.paragraphs)
        if _editavel(p)
    ]


def aplicar_edicoes(docx_path: str, edicoes: Dict[int, str]) -> int:
    """Reescreve o texto dos parágrafos indicados no próprio arquivo.
    Devolve quantos foram efetivamente alterados."""
    doc = _abrir(docx_path)
    paragrafos = doc.paragraphs
    alterados = 0

    for ref, novo in edicoes.items():
        if ref < 0 or ref >= len(paragrafos):
            raise ValueError("O documento mudou desde que o editor foi aberto. Recarregue a página.")
        paragrafo = paragrafos[ref]
        if not paragrafo.runs or paragrafo.text == novo:
            continue
        paragrafo.runs[0].text = novo
        for extra in paragrafo.runs[1:]:
            extra.text = ""
        alterados += 1

    doc.save(docx_path)
    return alterados
