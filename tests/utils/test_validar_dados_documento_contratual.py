"""Campos obrigatórios de um documento jurídico (§ Contratos, 2026-09-20/21)."""

from src.utils.dados_documento_contratual import dados_iniciais_contrato
from src.utils.validar_dados_documento_contratual import campos_faltando, erro_campos_faltando


def rotulos(faltando):
    return [rotulo for _, rotulo in faltando]


def caminhos(faltando):
    return [caminho for caminho, _ in faltando]


def _contratante_completo():
    return {
        "razao_social": "Empresa X",
        "cnpj": "11.222.333/0001-81",
        "endereco": "Rua X, 100",
        "representante": {
            "nome": "Fulano",
            "nacionalidade": "Brasileira",
            "estado_civil": "Solteiro",
            "profissao": "Empresário",
            "cargo": "Diretor",
            "rg": "12.345.678-9 SSP/SP",
            "cpf": "111.444.777-35",
            "endereco": "Rua Y, 200",
        },
        "email_cobranca": "",
    }


def _testemunhas_completas():
    return [{"nome": "Testemunha 1", "cpf": "111.444.777-35"}, {"nome": "", "cpf": ""}]


def _assinatura_completa():
    return {"dia": 18, "mes": 9, "ano": 2026}


class TestComumATodosOsTipos:
    def test_contrato_em_branco_lista_tudo(self):
        faltando = rotulos(campos_faltando("contrato", dados_iniciais_contrato()))

        assert "Razão social do contratante" in faltando
        assert "CNPJ do contratante" in faltando
        assert "Nome do representante" in faltando
        assert "Nome da testemunha 1" in faltando
        assert "Dia da assinatura" in faltando

    def test_cada_item_carrega_o_caminho_do_campo(self):
        faltando = campos_faltando("contrato", dados_iniciais_contrato())

        assert ("contratante.razao_social", "Razão social do contratante") in faltando
        assert ("assinatura.dia", "Dia da assinatura") in faltando

    def test_testemunha_2_e_sempre_opcional(self):
        dados = {
            "contratante": _contratante_completo(),
            "testemunhas": _testemunhas_completas(),
            "assinatura": _assinatura_completa(),
        }
        faltando = campos_faltando("nda", dados)

        assert faltando == []

    def test_email_e_telefone_do_representante_sao_opcionais(self):
        contratante = _contratante_completo()
        contratante["representante"]["email"] = ""
        contratante["representante"]["telefone"] = ""
        dados = {
            "contratante": contratante,
            "testemunhas": _testemunhas_completas(),
            "assinatura": _assinatura_completa(),
        }

        assert campos_faltando("nda", dados) == []

    def test_outro_nunca_exige_nada(self):
        assert campos_faltando("outro", {}) == []
        assert campos_faltando("outro", None) == []


class TestContrato:
    def _dados_base(self):
        return {
            "contratante": _contratante_completo(),
            "testemunhas": _testemunhas_completas(),
            "assinatura": _assinatura_completa(),
            "projeto": {
                "servico": "Consultoria",
                "escopos": [{"nome": "Ambientação", "prazo_dias_uteis": 5}],
                "num_consultores": 3,
                "num_coordenadores": 1,
            },
            "financeiro": {
                "valor_total": 22000,
                "forma_pagamento": "PIX",
                "parcelado": False,
            },
        }

    def test_completo_nao_falta_nada(self):
        assert campos_faltando("contrato", self._dados_base()) == []

    def test_exige_escopos(self):
        dados = self._dados_base()
        dados["projeto"]["escopos"] = []

        assert "Escopos do projeto" in rotulos(campos_faltando("contrato", dados))

    def test_exige_numero_de_consultores(self):
        dados = self._dados_base()
        dados["projeto"]["num_consultores"] = 0

        assert "Número de consultores" in rotulos(campos_faltando("contrato", dados))

    def test_parcelado_exige_dados_da_parcela(self):
        dados = self._dados_base()
        dados["financeiro"]["parcelado"] = True

        faltando = rotulos(campos_faltando("contrato", dados))

        assert "Número de parcelas" in faltando
        assert "Data do primeiro vencimento" in faltando
        assert "Dia do vencimento mensal" in faltando

    def test_parcela_unica_nao_exige_dados_de_parcelamento(self):
        dados = self._dados_base()
        # parcelado=False (padrão) — não deveria cobrar número de parcelas.
        assert "Número de parcelas" not in rotulos(campos_faltando("contrato", dados))


class TestTep:
    def test_exige_escopos_entregues_e_execucao(self):
        dados = {
            "contratante": _contratante_completo(),
            "testemunhas": _testemunhas_completas(),
            "assinatura": _assinatura_completa(),
            "projeto": {"nome": "", "escopos_entregues": []},
            "execucao": {"data_inicio": "", "data_fim": ""},
        }

        faltando = rotulos(campos_faltando("tep", dados))

        assert "Nome do projeto" in faltando
        assert "Escopos entregues" in faltando
        assert "Data de início da execução" in faltando
        assert "Data de término da execução" in faltando


class TestUsoImagem:
    def test_exige_contexto(self):
        dados = {
            "contratante": _contratante_completo(),
            "testemunhas": _testemunhas_completas(),
            "assinatura": _assinatura_completa(),
            "contexto": "",
        }

        assert "Contexto de captação da imagem" in rotulos(campos_faltando("uso_imagem", dados))


class TestAditivo:
    def _dados_base(self):
        return {
            "contratante": _contratante_completo(),
            "testemunhas": _testemunhas_completas(),
            "assinatura": _assinatura_completa(),
            "secoes": {"objeto": False, "alteracao": False, "preco": False, "prazo": False},
        }

    def test_exige_pelo_menos_uma_secao(self):
        faltando = rotulos(campos_faltando("aditivo", self._dados_base()))

        assert any("Pelo menos uma seção" in f for f in faltando)

    def test_secao_objeto_exige_descricao_e_itens(self):
        dados = self._dados_base()
        dados["secoes"]["objeto"] = True
        dados["objeto"] = {"descricao": "", "itens": []}

        faltando = rotulos(campos_faltando("aditivo", dados))

        assert "Descrição do objeto do aditivo" in faltando
        assert "Itens do objeto do aditivo" in faltando

    def test_secao_preco_parcelado_exige_parcelas(self):
        dados = self._dados_base()
        dados["secoes"]["preco"] = True
        dados["preco"] = {"valor_novo": 30000, "parcelado": True}

        faltando = rotulos(campos_faltando("aditivo", dados))

        assert "Número de parcelas do aditivo" in faltando

    def test_secao_marcada_e_preenchida_nao_falta_nada(self):
        dados = self._dados_base()
        dados["secoes"]["prazo"] = True
        dados["prazo"] = {"dias_uteis": 30}

        assert campos_faltando("aditivo", dados) == []


class TestErroCamposFaltando:
    def test_mensagem_lista_os_rotulos(self):
        faltando = [("assinatura.dia", "Dia da assinatura"), ("assinatura.mes", "Mês da assinatura")]

        erro = erro_campos_faltando(faltando)

        assert str(erro) == "Faltam campos obrigatórios: Dia da assinatura, Mês da assinatura."

    def test_carrega_os_caminhos_pro_front_destacar_o_campo(self):
        faltando = [("assinatura.dia", "Dia da assinatura"), ("assinatura.mes", "Mês da assinatura")]

        erro = erro_campos_faltando(faltando)

        assert erro.campos == ["assinatura.dia", "assinatura.mes"]

    def test_erro_de_regra_leva_os_campos_no_detail(self):
        from src.utils.erro_http import erro_de_regra

        faltando = [("assinatura.dia", "Dia da assinatura")]
        http_erro = erro_de_regra(erro_campos_faltando(faltando))

        assert http_erro.status_code == 422
        assert http_erro.detail["campos"] == ["assinatura.dia"]
        assert "Dia da assinatura" in http_erro.detail["msg"]
