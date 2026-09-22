"""`_contexto_base` — o ponto em que os campos de `dados` viram o contexto
Jinja2 que os templates .docx leem (§ Contratos, 2026-09-22).

Existe só por causa de um incidente real: o formulário guardava RG e órgão
emissor em `rg`, um campo só, mas em algum momento os dois viraram
`rg_numero`/`rg_orgao_emissor` sem que o motor de geração acompanhasse — os
cinco templates .docx sempre esperaram `rep.rg_numero`/`rep.rg_orgao_emissor`
como dois merge fields separados. Nenhum teste chamava `_contexto_base` (nem
`renderizar`) de verdade, e "gerar rascunho" só quebrava em produção. Este
teste trava exatamente essa junção.
"""

from src.documentos_contratuais.render_template import _contexto_base


class TestContextoBaseRg:
    def test_separa_rg_num_campo_so_em_numero_e_orgao(self):
        dados = {
            "contratante": {
                "representante": {"nome": "Fulano", "rg": "12345678 SSP/SP"},
            },
        }

        contexto = _contexto_base("contrato", dados, identidade={})

        assert contexto["rep"]["rg_numero"] == "12.345.678"
        assert contexto["rep"]["rg_orgao_emissor"] == "SSP/SP"

    def test_rg_vazio_nao_estoura(self):
        dados = {"contratante": {"representante": {"nome": "Fulano", "rg": ""}}}

        contexto = _contexto_base("contrato", dados, identidade={})

        assert contexto["rep"]["rg_numero"] == ""
        assert contexto["rep"]["rg_orgao_emissor"] == ""

    def test_sem_representante_nenhum_nao_estoura(self):
        contexto = _contexto_base("contrato", dados={}, identidade={})

        assert contexto["rep"]["rg_numero"] == ""
        assert contexto["rep"]["rg_orgao_emissor"] == ""
