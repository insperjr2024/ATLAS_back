from src.documentos_contratuais.extrair_coleta import PendenciaColeta
from src.utils.adaptar_coleta_para_tipo import adaptar_coleta_para_tipo
from src.utils.dados_documento_contratual import dados_iniciais_contrato


def dados_contrato_exemplo():
    dados = dados_iniciais_contrato()
    dados["contratante"]["razao_social"] = "EMPRESA X"
    dados["testemunhas"] = [{"nome": "Fulano", "cpf": "111.444.777-35"}, {"nome": "", "cpf": ""}]
    dados["financeiro"]["valor_total"] = 10000.0
    return dados


def test_tipo_contrato_devolve_os_dados_sem_adaptar():
    dados = dados_contrato_exemplo()
    pendencias = [PendenciaColeta("contratante.cnpj", "CNPJ não encontrado no documento.")]

    resultado, mensagens = adaptar_coleta_para_tipo("contrato", dados, pendencias, "Projeto Alfa")

    assert resultado is dados
    assert mensagens == ["CNPJ não encontrado no documento."]


def test_nda_so_herda_contratante_e_testemunhas():
    dados = dados_contrato_exemplo()
    pendencias = [
        PendenciaColeta("contratante.cnpj", "CNPJ não encontrado no documento."),
        PendenciaColeta("financeiro.valor_total", "Valor do projeto não reconhecido."),
    ]

    resultado, mensagens = adaptar_coleta_para_tipo("nda", dados, pendencias, "Projeto Alfa")

    assert resultado["contratante"]["razao_social"] == "EMPRESA X"
    assert "financeiro" not in resultado
    # Pendência de financeiro não interessa ao NDA, some da lista.
    assert mensagens == ["CNPJ não encontrado no documento."]


def test_aditivo_tambem_herda_valor_total():
    dados = dados_contrato_exemplo()
    pendencias = [PendenciaColeta("financeiro.valor_total", "Valor do projeto não reconhecido.")]

    _resultado, mensagens = adaptar_coleta_para_tipo("aditivo", dados, pendencias, "Projeto Alfa")

    assert mensagens == ["Valor do projeto não reconhecido."]


def test_pendencia_de_documento_sempre_aparece():
    dados = dados_contrato_exemplo()
    pendencias = [PendenciaColeta("documento", "Tabela fora do padrão.")]

    _resultado, mensagens = adaptar_coleta_para_tipo("nda", dados, pendencias, "Projeto Alfa")

    assert mensagens == ["Tabela fora do padrão."]
