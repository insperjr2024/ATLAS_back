"""Leitura do calendário acadêmico do Insper em PDF.

O arquivo é uma página só, com 12 mini-calendários em duas faixas de seis
meses. As marcações aparecem de DUAS formas, e as duas precisam ser lidas:

- **Código em letra** logo abaixo do número do dia, na mesma coluna:
  F, FE, R, AI, AF, AS.
- **Cor de preenchimento** da célula, sem letra nenhuma: é assim que
  "Aulas Canceladas" aparece.

📐 A leitura é POSICIONAL, não textual. No texto puro os códigos saem numa
linha separada dos números e não há como saber a qual dia cada um pertence —
só as coordenadas amarram os dois.

O resultado NUNCA é gravado direto: a tela mostra o que foi lido para a
diretoria conferir, filtrar por categoria e corrigir antes de salvar, como o
§11 do case exige para a leitura da grade horária.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import BinaryIO, Dict, List, Optional

import pdfplumber


@dataclass(frozen=True)
class Categoria:
    """Uma linha da legenda do PDF, e o que ela vira no banco."""

    chave: str
    rotulo: str
    #: `tipo` da tabela `dia_nao_letivo`, que só aceita feriado/prova/recesso.
    tipo: str
    #: "global" vale para todas as frentes; "frente", só para a do PDF.
    escopo: str


#: Feriado é do país: global. Todo o resto sai do calendário de um CURSO —
#: avaliação, recesso e aulas canceladas de Administração não são os de
#: Engenharia —, então fica preso à frente cujo PDF foi carregado.
CATEGORIAS: Dict[str, Categoria] = {
    "F": Categoria("feriado", "Feriado", "feriado", "global"),
    "FE": Categoria("feriado_escolar", "Feriado escolar", "feriado", "global"),
    "AI": Categoria("avaliacao_intermediaria", "Avaliação intermediária", "prova", "frente"),
    "AF": Categoria("avaliacao_final", "Avaliação final", "prova", "frente"),
    "AS": Categoria("avaliacao_substitutiva", "Avaliação substitutiva", "prova", "frente"),
    "R": Categoria("recesso", "Recesso", "recesso", "frente"),
}

#: Aulas Canceladas não tem código em letra — só o preenchimento cinza da
#: célula. Vai gravada como `recesso` (o enum do banco tem três valores e não
#: valia uma migration por isso); o rótulo preserva a origem na descrição.
COR_AULAS_CANCELADAS = (0.85098, 0.85098, 0.85098)
CATEGORIA_AULAS_CANCELADAS = Categoria(
    "aulas_canceladas", "Aulas canceladas", "recesso", "frente"
)

#: Tolerância por canal de cor. O PDF grava float, e comparar por igualdade
#: exata quebraria com qualquer regravação do arquivo.
TOLERANCIA_COR = 0.02

MESES = [
    "JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO",
    "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO",
]

#: Distância horizontal máxima entre o centro do código e o do número. As
#: colunas têm ~14pt, então 5 separa colunas vizinhas sem perder o
#: desalinhamento normal de um código de duas letras.
TOLERANCIA_COLUNA = 5.0

#: O código fica logo abaixo do número (~6.6pt). 12 cobre a variação sem
#: alcançar a linha da semana seguinte, que está a ~13pt.
DISTANCIA_ABAIXO = 12.0

#: Uma linha de calendário tem números dos 6 meses lado a lado. Exigir
#: companhia separa dia de dígito solto no texto da legenda ("8 disciplinas").
MINIMO_NA_LINHA = 5


@dataclass
class DiaLido:
    data: date
    categoria: str
    rotulo: str
    tipo: str
    escopo: str


@dataclass
class LeituraCalendario:
    dias: List[DiaLido]
    #: Códigos que não casaram com nenhum dia. Diferente de zero é sinal de que
    #: o layout mudou — a tela avisa em vez de fingir que leu tudo.
    nao_casados: int


def _centro(palavra) -> float:
    return (palavra["x0"] + palavra["x1"]) / 2


def _mesma_cor(cor, alvo) -> bool:
    if not cor or len(cor) != len(alvo):
        return False
    return all(abs(a - b) <= TOLERANCIA_COR for a, b in zip(cor, alvo))


def ler_calendario(arquivo: BinaryIO, ano: int) -> LeituraCalendario:
    with pdfplumber.open(arquivo) as pdf:
        pagina = pdf.pages[0]
        palavras = pagina.extract_words()
        retangulos = list(pagina.rects)

    cabecalhos = [p for p in palavras if p["text"] in MESES]
    if not cabecalhos:
        raise ValueError(
            "Não encontrei os nomes dos meses no PDF. "
            "O arquivo é mesmo o calendário acadêmico do Insper?"
        )

    faixas = sorted({round(c["top"]) for c in cabecalhos})

    def faixa_de(elemento) -> int:
        """A faixa é o cabeçalho mais baixo que ainda fica ACIMA do elemento.

        O ponto médio entre cabeçalhos não serve: a grade de uma faixa desce
        bem além dele, e as últimas semanas cairiam na faixa de baixo.
        """
        topo = elemento["top"]
        acima = [f for f in faixas if f <= topo]
        return acima[-1] if acima else faixas[0]

    por_faixa = defaultdict(list)
    for c in cabecalhos:
        por_faixa[round(c["top"])].append(c)

    janelas = {}
    for topo, linha in por_faixa.items():
        linha.sort(key=_centro)
        for i, c in enumerate(linha):
            ini = 0.0 if i == 0 else (_centro(linha[i - 1]) + _centro(c)) / 2
            fim = 1e6 if i == len(linha) - 1 else (_centro(c) + _centro(linha[i + 1])) / 2
            janelas[c["text"]] = (topo, ini, fim)

    numeros = [p for p in palavras if p["text"].isdigit() and 1 <= int(p["text"]) <= 31]
    codigos = [p for p in palavras if p["text"] in CATEGORIAS]

    por_linha = defaultdict(list)
    for n in numeros:
        por_linha[round(n["top"])].append(n)
    numeros = [n for n in numeros if len(por_linha[round(n["top"])]) >= MINIMO_NA_LINHA]

    # A legenda repete os mesmos códigos no rodapé. Sem limitar à altura da
    # grade, eles entram como marcação e casam com qualquer número acima.
    fundo = {}
    for f in faixas:
        tops = [n["top"] for n in numeros if faixa_de(n) == f]
        fundo[f] = max(tops) + DISTANCIA_ABAIXO if tops else 0.0
    codigos = [c for c in codigos if c["top"] <= fundo[faixa_de(c)]]

    def mes_de(elemento) -> Optional[str]:
        for nome, (topo, ini, fim) in janelas.items():
            if topo == faixa_de(elemento) and ini <= _centro(elemento) < fim:
                return nome
        return None

    def data_de(numero) -> Optional[date]:
        nome = mes_de(numero)
        if not nome:
            return None
        try:
            return date(ano, MESES.index(nome) + 1, int(numero["text"]))
        except ValueError:
            # 31 num mês de 30 dias significa casamento errado, não calendário
            # errado.
            return None

    achados: Dict[date, Categoria] = {}
    nao_casados = 0

    # 1 · Códigos em letra.
    for c in codigos:
        candidatos = [
            n
            for n in numeros
            if abs(_centro(n) - _centro(c)) < TOLERANCIA_COLUNA
            and 0 < c["top"] - n["top"] < DISTANCIA_ABAIXO
            and mes_de(n) == mes_de(c)
        ]
        if not candidatos:
            nao_casados += 1
            continue
        quando = data_de(min(candidatos, key=lambda n: c["top"] - n["top"]))
        if not quando:
            nao_casados += 1
            continue
        achados[quando] = CATEGORIAS[c["text"]]

    # 2 · Aulas canceladas, pela cor do preenchimento.
    #
    # ⚠ Um retângulo cobre VÁRIOS dias: o bloco de 1 e 2 de abril é um só. Por
    # isso todos os números dentro dele contam, e não apenas o primeiro.
    for r in retangulos:
        if not _mesma_cor(r.get("non_stroking_color"), COR_AULAS_CANCELADAS):
            continue
        for n in numeros:
            centro_y = (n["top"] + n["bottom"]) / 2
            dentro = (
                r["x0"] - 1 <= _centro(n) <= r["x1"] + 1
                and r["top"] - 1 <= centro_y <= r["bottom"] + 1
            )
            if not dentro:
                continue
            quando = data_de(n)
            # O código em letra ganha da cor: um dia com F E fundo cinza é
            # feriado, que é a informação mais forte.
            if quando and quando not in achados:
                achados[quando] = CATEGORIA_AULAS_CANCELADAS

    dias = [
        DiaLido(
            data=quando,
            categoria=cat.chave,
            rotulo=cat.rotulo,
            tipo=cat.tipo,
            escopo=cat.escopo,
        )
        for quando, cat in sorted(achados.items())
    ]
    return LeituraCalendario(dias=dias, nao_casados=nao_casados)
