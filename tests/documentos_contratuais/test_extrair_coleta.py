"""Extração da Coleta de Dados (§ Contratos, 2026-09-18).

As funções puras (CPF/CNPJ/RG/moeda/data) são as mesmas do sistema antigo,
testadas aqui direto. O pipeline inteiro é exercitado contra um .docx
sintético — mesma estrutura (tabela principal por seção + tabelas de
testemunha) que o time recebe de verdade.
"""

from docx import Document

from src.documentos_contratuais.extrair_coleta import (
    extrair_dados_coleta,
    extrair_etapas,
    formatar_cnpj,
    formatar_cpf,
    formatar_rg,
    formatar_telefone,
    normalizar_rotulo,
    parse_data_iso,
    parse_moeda,
    validar_cnpj,
    validar_cpf,
)


class TestFuncoesPuras:
    def test_normaliza_rotulo_com_espaco_e_pontuacao(self):
        assert normalizar_rotulo("  Será parcelado ?  ") == "sera parcelado"
        assert normalizar_rotulo("CNPJ:") == "cnpj"

    def test_valida_cpf_correto(self):
        assert validar_cpf("11144477735") is True

    def test_recusa_cpf_com_digitos_iguais(self):
        assert validar_cpf("11111111111") is False

    def test_valida_cnpj_correto(self):
        assert validar_cnpj("11222333000181") is True

    def test_formata_cpf(self):
        assert formatar_cpf("11144477735") == "111.444.777-35"

    def test_formata_cnpj(self):
        assert formatar_cnpj("11222333000181") == "11.222.333/0001-81"

    def test_formata_rg_padrao_sp(self):
        assert formatar_rg("2027163 SSP/SC") == "2027163 SSP/SC"

    def test_formata_telefone_celular(self):
        assert formatar_telefone("11999998888") == "(11) 99999-8888"

    def test_parse_moeda(self):
        assert parse_moeda("R$ 22.000,00") == 22000.0

    def test_parse_data_iso_formato_br(self):
        assert parse_data_iso("30/07/2026") == "2026-07-30"

    def test_parse_data_iso_recusa_texto_livre(self):
        assert parse_data_iso("30/07 e todos os dias 30") is None

    def test_extrai_etapas(self):
        escopos, pendencias = extrair_etapas("Ambientação (5 dias úteis) + Análise Mercadológica (30 dias úteis)")
        assert escopos == [
            {"nome": "Ambientação", "prazo_dias_uteis": 5},
            {"nome": "Análise Mercadológica", "prazo_dias_uteis": 30},
        ]
        assert pendencias == []

    def test_etapa_fora_do_formato_vira_pendencia(self):
        escopos, pendencias = extrair_etapas("Algo sem prazo definido")
        assert escopos == []
        assert len(pendencias) == 1


def _tabela_secao(doc, titulo, linhas):
    tabela = doc.add_table(rows=0, cols=2)
    header = tabela.add_row()
    header.cells[0].text = titulo
    header.cells[1].text = titulo
    for rotulo, valor in linhas:
        row = tabela.add_row()
        row.cells[0].text = rotulo
        row.cells[1].text = valor
    return tabela


def _docx_coleta_completa():
    import io

    doc = Document()
    _tabela_secao(
        doc,
        "INFORMAÇÕES DA CLIENTE",
        [
            ("Razão Social", "empresa exemplo ltda"),
            ("CNPJ", "11.222.333/0001-81"),
            ("Endereço completo [logradouro, CEP, bairro, cidade, estado]", "Rua X, 100\nBairro Y\nSão Paulo/SP"),
        ],
    )
    _tabela_secao(
        doc,
        "REPRESENTANTE LEGAL",
        [
            ("Nome do representante legal", "joão da silva"),
            ("Email", "joao@exemplo.com"),
            ("Telefone", "11999998888"),
            ("Cargo do representante legal", "Diretor"),
            ("Nacionalidade", "Brasileira"),
            ("Estado civil", "Casado"),
            ("Profissão", "Empresário"),
            ("CPF do representante legal", "111.444.777-35"),
            ("RG do representante (com órgão emissor)", "2027163 SSP/SC"),
            ("Endereço completo [logradouro, CEP, bairro, cidade, estado]", "Rua Y, 200"),
        ],
    )
    _tabela_secao(
        doc,
        "INFORMAÇÕES SOBRE O SERVIÇO",
        [
            ("Qual serviço será prestado", "Consultoria de mercado"),
            ("Quais as etapas do serviço (com o prazo estipulado para cada etapa)",
             "Ambientação (5 dias úteis) + Análise Mercadológica (30 dias úteis)"),
            ("Quantos consultores serão disponibilizados", "3"),
            ("Quantos coordenadores serão disponibilizados", "1"),
            ("Data de início do serviço", "01/03/2026"),
            ("Data de término do serviço", "30/06/2026"),
        ],
    )
    _tabela_secao(
        doc,
        "CUSTO DO PROJETO",
        [
            ("Qual o valor do projeto", "R$ 22.000,00"),
            ("Será parcelado", "Sim"),
            ("Quantas parcelas serão", "2"),
            ("Quando irá começar o pagamento", "15/03/2026"),
            ("Em que dia do mês o pagamento será realizado", "15"),
            ("Qual será a forma de pagamento (Pix, boleto)", "Pix"),
        ],
    )
    _tabela_secao(doc, "TESTEMUNHA 1", [("Nome", "Maria Testemunha"), ("CPF", "111.444.777-35")])
    # Testemunha 2 propositalmente incompleta (só o nome) — deve virar pendência.
    _tabela_secao(doc, "TESTEMUNHA 2", [("Nome", "Zé Testemunha")])

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


class TestExtrairDadosColeta:
    def test_extrai_todos_os_campos_reconheciveis(self):
        dados, pendencias = extrair_dados_coleta(_docx_coleta_completa())

        assert dados["contratante"]["razao_social"] == "EMPRESA EXEMPLO LTDA"
        assert dados["contratante"]["cnpj"] == "11.222.333/0001-81"
        assert dados["contratante"]["representante"]["nome"] == "João da Silva"
        assert dados["contratante"]["representante"]["cpf"] == "111.444.777-35"
        assert dados["contratante"]["representante"]["rg"] == "2027163 SSP/SC"
        assert dados["contratante"]["email_cobranca"] == "joao@exemplo.com"
        assert dados["projeto"]["num_consultores"] == 3
        assert dados["projeto"]["escopos"] == [
            {"nome": "Ambientação", "prazo_dias_uteis": 5},
            {"nome": "Análise Mercadológica", "prazo_dias_uteis": 30},
        ]
        assert dados["financeiro"]["valor_total"] == 22000.0
        assert dados["financeiro"]["parcelado"] is True
        assert dados["financeiro"]["numero_parcelas"] == 2
        # Derivado, nunca lido do documento.
        assert dados["financeiro"]["valor_parcela"] == 11000.0
        assert dados["testemunhas"][0]["nome"] == "Maria Testemunha"

    def test_testemunha_incompleta_vira_pendencia(self):
        _dados, pendencias = extrair_dados_coleta(_docx_coleta_completa())

        assert any("Testemunha 2" in p and "CPF" in p for p in pendencias)

    def test_recusa_arquivo_que_nao_e_docx(self):
        import pytest

        with pytest.raises(ValueError, match="não é um .docx válido"):
            extrair_dados_coleta(b"isto nao e um docx")

    def test_recusa_docx_sem_nenhuma_tabela(self):
        import io

        import pytest

        doc = Document()
        doc.add_paragraph("Sem tabelas aqui.")
        buffer = io.BytesIO()
        doc.save(buffer)

        with pytest.raises(ValueError, match="nenhuma tabela"):
            extrair_dados_coleta(buffer.getvalue())

    def test_campo_ausente_vira_pendencia_sem_derrubar_extracao(self):
        import io

        doc = Document()
        _tabela_secao(doc, "INFORMAÇÕES DA CLIENTE", [("Razão Social", "empresa exemplo")])
        buffer = io.BytesIO()
        doc.save(buffer)

        dados, pendencias = extrair_dados_coleta(buffer.getvalue())

        assert dados["contratante"]["razao_social"] == "EMPRESA EXEMPLO"
        assert any("CNPJ do contratante" in p for p in pendencias)
