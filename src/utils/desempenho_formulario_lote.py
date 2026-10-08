"""Qual formulário vale pra um lote e um papel: a versão congelada do lote,
se houver (`desempenho_lote_formulario`), senão a vigente."""


def formulario_do_lote(formulario_repo, lote_formulario_repo, lote, papel: str):
    congelado_id = lote_formulario_repo.formulario_id_de(lote.id, papel)
    if congelado_id is not None:
        formulario = formulario_repo.get_by_id(congelado_id)
        if formulario:
            return formulario
    return formulario_repo.vigente(lote.tipo, papel)
