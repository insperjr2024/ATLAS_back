"""Leitura do calendário acadêmico do Insper em PDF.

O arquivo é uma página só, com 12 mini-calendários em duas faixas de seis
meses. Os dias não letivos aparecem como um código de UMA a DUAS letras logo
abaixo do número do dia, na mesma coluna.

📐 A leitura é POSICIONAL, não textual. No texto puro os códigos saem numa
linha separada dos números e não há como saber a qual dia cada um pertence —
só as coordenadas amarram os dois.

⚠ O que este módulo NÃO lê: "Férias" e "Aulas Canceladas" existem no PDF
apenas como cor de preenchimento, sem código em letra. A diretoria decidiu que
esses dois não contam como dia não útil (a Jr trabalha neles), então a leitura
por texto basta. Se um dia passarem a contar, será preciso ler as cores dos
retângulos, o que é bem mais frágil — depende de o Insper não mudar a paleta.

O resultado NUNCA é gravado direto: a tela mostra o que foi lido para a
diretoria conferir e corrigir antes de salvar, como o §11 do case exige para a
leitura da grade horária.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import BinaryIO, List

import pdfplumber

#: Código no PDF -> `tipo` de `dia_nao_letivo`.
#: `R` (recesso) fica de fora por decisão da diretoria: a Jr trabalha no recesso.
CODIGOS_NAO_UTEIS = {
    "F": "feriado",
    "FE": "feriado",
    "AI": "prova",
    "AF": "prova",
    "AS": "prova",
}

#: O que a legenda descreve, para a tela de conferência explicar o que leu.
DESCRICAO_CODIGO = {
    "F": "Feriado",
    "FE": "Feriado escolar",
    "AI": "Avaliação intermediária",
    "AF": "Avaliação final",
    "AS": "Avaliação substitutiva",
}

#: `R` é lido e descartado — mas precisa ser reconhecido, senão o código
#: sobraria como "não casado" e poluiria o diagnóstico da tela.
CODIGOS_IGNORADOS = {"R"}
TODOS_CODIGOS = set(CODIGOS_NAO_UTEIS) | CODIGOS_IGNORADOS

MESES = [
    "JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO",
    "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO",
]

#: Distância horizontal máxima entre o centro do código e o do número, em
#: pontos. As colunas do PDF têm ~14pt, então 5 separa colunas vizinhas sem
#: perder o desalinhamento normal de um código de duas letras.
TOLERANCIA_COLUNA = 5.0

#: O código fica logo abaixo do número (~6.6pt). 12 cobre a variação sem
#: alcançar a linha da semana seguinte, que está a ~13pt.
DISTANCIA_ABAIXO = 12.0

#: Uma linha de calendário tem números dos 6 meses lado a lado. Exigir
#: companhia separa dia de dígito solto no texto da legenda ("8 disciplinas").
MINIMO_NA_LINHA = 5


#: A quem o dia pertence.
#:
#: Feriado é do país: vale para todas as frentes, e subir o PDF de Business não
#: pode criar uma cópia dele em cada frente. Já as semanas de avaliação são do
#: CURSO — as datas de AI/AF/AS de Administração não são as de Engenharia —,
#: então essas ficam presas à frente cujo PDF foi carregado.
ESCOPO_POR_TIPO = {"feriado": "global", "prova": "frente"}


@dataclass
class DiaLido:
    data: date
    codigo: str
    tipo: str
    descricao: str

    @property
    def escopo(self) -> str:
        return ESCOPO_POR_TIPO[self.tipo]


@dataclass
class LeituraCalendario:
    dias: List[DiaLido]
    #: Códigos reconhecidos mas descartados (recesso).
    ignorados: List[date]
    #: Códigos que não casaram com nenhum dia. Diferente de zero é sinal de que
    #: o layout mudou — a tela avisa em vez de fingir que leu tudo.
    nao_casados: int


def _centro(palavra) -> float:
    return (palavra["x0"] + palavra["x1"]) / 2


def ler_calendario(arquivo: BinaryIO, ano: int) -> LeituraCalendario:
    with pdfplumber.open(arquivo) as pdf:
        palavras = pdf.pages[0].extract_words()

    cabecalhos = [p for p in palavras if p["text"] in MESES]
    if not cabecalhos:
        raise ValueError(
            "Não encontrei os nomes dos meses no PDF. "
            "O arquivo é mesmo o calendário acadêmico do Insper?"
        )

    faixas = sorted({round(c["top"]) for c in cabecalhos})

    def faixa_de(palavra) -> int:
        """A faixa é o cabeçalho mais baixo que ainda fica ACIMA do elemento.

        O ponto médio entre cabeçalhos não serve: a grade de uma faixa desce
        bem além dele, e as últimas semanas cairiam na faixa de baixo.
        """
        acima = [f for f in faixas if f <= palavra["top"]]
        return acima[-1] if acima else faixas[0]

    # Cada mês recebe uma janela horizontal, delimitada pelos vizinhos de faixa.
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
    codigos = [p for p in palavras if p["text"] in TODOS_CODIGOS]

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

    def mes_de(palavra):
        for nome, (topo, ini, fim) in janelas.items():
            if topo == faixa_de(palavra) and ini <= _centro(palavra) < fim:
                return nome
        return None

    dias: List[DiaLido] = []
    ignorados: List[date] = []
    nao_casados = 0

    for c in codigos:
        mes_codigo = mes_de(c)
        candidatos = [
            n
            for n in numeros
            if abs(_centro(n) - _centro(c)) < TOLERANCIA_COLUNA
            and 0 < c["top"] - n["top"] < DISTANCIA_ABAIXO
            and mes_de(n) == mes_codigo
        ]
        if not candidatos or not mes_codigo:
            nao_casados += 1
            continue

        numero = min(candidatos, key=lambda n: c["top"] - n["top"])
        try:
            quando = date(ano, MESES.index(mes_codigo) + 1, int(numero["text"]))
        except ValueError:
            # Data impossível (31 de mês com 30 dias) significa casamento
            # errado, não calendário errado. Conta como não casado.
            nao_casados += 1
            continue

        if c["text"] in CODIGOS_IGNORADOS:
            ignorados.append(quando)
            continue

        dias.append(
            DiaLido(
                data=quando,
                codigo=c["text"],
                tipo=CODIGOS_NAO_UTEIS[c["text"]],
                descricao=DESCRICAO_CODIGO[c["text"]],
            )
        )

    dias.sort(key=lambda d: d.data)
    ignorados.sort()
    return LeituraCalendario(dias=dias, ignorados=ignorados, nao_casados=nao_casados)
