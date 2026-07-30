from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from src.database.database import get_db
from src.utils.exceptions import ResourceInUseError
from fastapi import FastAPI, Depends, HTTPException
from typing import Optional
from src.use_cases.cargo.create_cargo import CreateCargoUseCase, CreateCargoRequest
from src.use_cases.escopo.create_escopo import CreateEscopoUseCase, CreateEscopoRequest
from src.use_cases.semestre.create_semestre import CreateSemestreUseCase, CreateSemestreRequest
from src.use_cases.usuario.create_usuario import CreateUsuarioUseCase, CreateUsuarioRequest
from src.use_cases.formulario.create_formulario import CreateFormularioUseCase, CreateFormularioRequest
from src.use_cases.banca.create_banca import CreateBancaUseCase, CreateBancaRequest
from src.use_cases.pergunta.create_pergunta import CreatePerguntaUseCase, CreatePerguntaRequest
from src.use_cases.candidatura.create_candidatura import CreateCandidaturaUseCase, CreateCandidaturaRequest
from src.use_cases.avaliacao.create_avaliacao import CreateAvaliacaoUseCase, CreateAvaliacaoRequest
from src.use_cases.avaliacao_nota.create_avaliacao_nota import CreateAvaliacaoNotaUseCase, CreateAvaliacaoNotaRequest
from src.use_cases.frente.create_frente import CreateFrenteUseCase, CreateFrenteRequest
from src.use_cases.equipe_projeto.create_equipe_projeto import CreateEquipeProjetoUseCase, CreateEquipeProjetoRequest
from src.use_cases.usuario_frente.create_usuario_frente import CreateUsuarioFrenteUseCase, CreateUsuarioFrenteRequest
from src.use_cases.banca_frente.create_banca_frente import CreateBancaFrenteUseCase, CreateBancaFrenteRequest
from src.use_cases.cargo.update_cargo import UpdateCargoUseCase, UpdateCargoRequest, DeleteCargoUseCase
from src.use_cases.escopo.update_escopo import UpdateEscopoUseCase, UpdateEscopoRequest, DeleteEscopoUseCase
from src.use_cases.semestre.update_semestre import UpdateSemestreUseCase, UpdateSemestreRequest, DeleteSemestreUseCase
from src.use_cases.usuario.update_usuario import UpdateUsuarioUseCase, UpdateUsuarioRequest, DeleteUsuarioUseCase
from src.use_cases.formulario.update_formulario import UpdateFormularioUseCase, UpdateFormularioRequest, DeleteFormularioUseCase
from src.use_cases.banca.update_banca import UpdateBancaUseCase, UpdateBancaRequest, DeleteBancaUseCase
from src.use_cases.pergunta.update_pergunta import UpdatePerguntaUseCase, UpdatePerguntaRequest, DeletePerguntaUseCase
from src.use_cases.candidatura.update_candidatura import UpdateCandidaturaUseCase, UpdateCandidaturaRequest, DeleteCandidaturaUseCase
from src.use_cases.avaliacao.update_avaliacao import UpdateAvaliacaoUseCase, UpdateAvaliacaoRequest, DeleteAvaliacaoUseCase
from src.use_cases.avaliacao_nota.update_avaliacao_nota import UpdateAvaliacaoNotaUseCase, UpdateAvaliacaoNotaRequest, DeleteAvaliacaoNotaUseCase
from src.use_cases.frente.update_frente import UpdateFrenteUseCase, UpdateFrenteRequest, DeleteFrenteUseCase
from src.use_cases.equipe_projeto.update_equipe_projeto import UpdateEquipeProjetoUseCase, UpdateEquipeProjetoRequest, DeleteEquipeProjetoUseCase
from src.use_cases.usuario_frente.update_usuario_frente import UpdateUsuarioFrenteUseCase, UpdateUsuarioFrenteRequest, DeleteUsuarioFrenteUseCase
from src.use_cases.banca_frente.update_banca_frente import UpdateBancaFrenteUseCase, UpdateBancaFrenteRequest, DeleteBancaFrenteUseCase
from src.use_cases.cargo.get_cargo import GetCargoUseCase, ListCargosUseCase
from src.use_cases.escopo.get_escopo import GetEscopoUseCase, ListEscoposUseCase
from src.use_cases.semestre.get_semestre import GetSemestreUseCase, ListSemestresUseCase
from src.use_cases.usuario.get_usuario import GetUsuarioUseCase, ListUsuariosUseCase
from src.use_cases.formulario.get_formulario import GetFormularioUseCase, ListFormulariosUseCase
from src.use_cases.banca.get_banca import GetBancaUseCase, ListBancasUseCase
from src.use_cases.banca.get_notas_por_pergunta import GetNotasPorPerguntaUseCase
from src.use_cases.pergunta.get_pergunta import GetPerguntaUseCase, ListPerguntasUseCase
from src.use_cases.candidatura.get_candidatura import GetCandidaturaUseCase, ListCandidaturasUseCase
from src.use_cases.avaliacao.get_avaliacao import GetAvaliacaoUseCase, ListAvaliacoesUseCase
from src.use_cases.avaliacao_nota.get_avaliacao_nota import GetAvaliacaoNotaUseCase, ListAvaliacoesNotasUseCase
from src.use_cases.frente.get_frente import GetFrenteUseCase, ListFrentesUseCase
from src.use_cases.equipe_projeto.get_equipe_projeto import GetEquipeProjetoUseCase, ListEquipesProjetoUseCase
from src.use_cases.usuario_frente.get_usuario_frente import GetUsuarioFrenteUseCase, ListUsuariosFrentesUseCase
from src.use_cases.banca_frente.get_banca_frente import GetBancaFrenteUseCase, ListBancasFrentesUseCase
from src.use_cases.configuracao.get_configuracao import GetConfiguracaoUseCase
from src.use_cases.configuracao.update_configuracao import UpdateConfiguracaoUseCase, UpdateConfiguracaoRequest
from src.use_cases.banca.get_bancas_para_avaliar import GetBancasParaAvaliarUseCase
from src.use_cases.avaliacao.get_avaliacoes_pendentes import GetAvaliacoesPendentesUseCase
from src.use_cases.usuario.get_desempenho import GetDesempenhoUseCase
from src.use_cases.banca.get_historico_bancas import GetHistoricoBancasUseCase
from src.use_cases.formulario.get_formulario_ativo import GetFormularioAtivoUseCase
from src.use_cases.formulario.create_nova_versao_formulario import CreateNovaVersaoFormularioUseCase, CreateNovaVersaoFormularioRequest
from src.utils.exceptions import ResourceInUseError, RegraDeNegocioError


app = FastAPI(title="API BANCAS I")


@app.post("/cargos")
def create_cargo(
    request: CreateCargoRequest,
    db: Session = Depends(get_db)
):
    use_case = CreateCargoUseCase(db)
    return use_case.execute(request)


@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/escopos")
def create_escopo(
    request: CreateEscopoRequest,
    db: Session = Depends(get_db)
):
    use_case = CreateEscopoUseCase(db)
    return use_case.execute(request)

@app.post("/semestres")
def create_semestre(
    request: CreateSemestreRequest,
    db: Session = Depends(get_db)
):
    use_case = CreateSemestreUseCase(db)
    return use_case.execute(request)

@app.post("/usuarios")
def create_usuario(
    request: CreateUsuarioRequest,
    db: Session = Depends(get_db)
):
    use_case = CreateUsuarioUseCase(db)
    return use_case.execute(request)

@app.post("/formularios")
def create_formulario(request: CreateFormularioRequest, db: Session = Depends(get_db)):
    use_case = CreateFormularioUseCase(db)
    return use_case.execute(request)


@app.get("/formularios/ativo")
def get_formulario_ativo(db: Session = Depends(get_db)):
    result = GetFormularioAtivoUseCase(db).execute()
    if not result:
        raise HTTPException(status_code=404, detail="Nenhum formulário ativo encontrado")
    return result


@app.post("/formularios/nova-versao")
def create_nova_versao_formulario(request: CreateNovaVersaoFormularioRequest, db: Session = Depends(get_db)):
    try:
        return CreateNovaVersaoFormularioUseCase(db).execute(request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.get("/formularios")
def list_formularios(db: Session = Depends(get_db)):
    return ListFormulariosUseCase(db).execute()

@app.get("/formularios/{formulario_id}")
def get_formulario(formulario_id: int, db: Session = Depends(get_db)):
    result = GetFormularioUseCase(db).execute(formulario_id)
    if not result:
        raise HTTPException(status_code=404, detail="Formulário não encontrado")
    return result 

@app.post("/bancas")
def create_banca(
    request: CreateBancaRequest,
    db: Session = Depends(get_db)
):
    use_case = CreateBancaUseCase(db)
    return use_case.execute(request)


@app.post("/perguntas")
def create_pergunta(
    request: CreatePerguntaRequest,
    db: Session = Depends(get_db)
):
    use_case = CreatePerguntaUseCase(db)
    return use_case.execute(request)


@app.post("/candidaturas")
def create_candidatura(request: CreateCandidaturaRequest, db: Session = Depends(get_db)):
    try:
        return CreateCandidaturaUseCase(db).execute(request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/avaliacoes")
def create_avaliacao(
    request: CreateAvaliacaoRequest,
    db: Session = Depends(get_db)
):
    use_case = CreateAvaliacaoUseCase(db)
    return use_case.execute(request)


@app.post("/avaliacoes-notas")
def create_avaliacao_nota(request: CreateAvaliacaoNotaRequest, db: Session = Depends(get_db)):
    try:
        return CreateAvaliacaoNotaUseCase(db).execute(request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))

@app.post("/frentes")
def create_frente(
    request: CreateFrenteRequest,
    db: Session = Depends(get_db)
):
    use_case = CreateFrenteUseCase(db)
    return use_case.execute(request)


@app.post("/equipes-projeto")
def create_equipe_projeto(
    request: CreateEquipeProjetoRequest,
    db: Session = Depends(get_db)
):
    use_case = CreateEquipeProjetoUseCase(db)
    return use_case.execute(request)


@app.post("/usuarios-frentes")
def create_usuario_frente(
    request: CreateUsuarioFrenteRequest,
    db: Session = Depends(get_db)
):
    use_case = CreateUsuarioFrenteUseCase(db)
    return use_case.execute(request)


@app.post("/bancas-frentes")
def create_banca_frente(
    request: CreateBancaFrenteRequest,
    db: Session = Depends(get_db)
):
    use_case = CreateBancaFrenteUseCase(db)
    return use_case.execute(request)

@app.patch("/cargos/{cargo_id}")
def update_cargo(cargo_id: int, request: UpdateCargoRequest, db: Session = Depends(get_db)):
    result = UpdateCargoUseCase(db).execute(cargo_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Cargo não encontrado")
    return result

@app.delete("/cargos/{cargo_id}", status_code=204)
def delete_cargo(cargo_id: int, db: Session = Depends(get_db)):
    try:
        deleted = DeleteCargoUseCase(db).execute(cargo_id)
    except ResourceInUseError:
        raise HTTPException(status_code=409, detail="Não é possível excluir: existem registros vinculados a este cargo")
    if not deleted:
        raise HTTPException(status_code=404, detail="Cargo não encontrado")
    return None


@app.patch("/escopos/{escopo_id}")
def update_escopo(escopo_id: int, request: UpdateEscopoRequest, db: Session = Depends(get_db)):
    result = UpdateEscopoUseCase(db).execute(escopo_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Escopo não encontrado")
    return result

@app.delete("/escopos/{escopo_id}", status_code=204)
def delete_escopo(escopo_id: int, db: Session = Depends(get_db)):
    try:
        deleted = DeleteEscopoUseCase(db).execute(escopo_id)
    except ResourceInUseError:
        raise HTTPException(status_code=409, detail="Não é possível excluir: existem registros vinculados a este escopo")
    if not deleted:
        raise HTTPException(status_code=404, detail="Escopo não encontrado")
    return None


@app.patch("/semestres/{semestre_id}")
def update_semestre(semestre_id: int, request: UpdateSemestreRequest, db: Session = Depends(get_db)):
    result = UpdateSemestreUseCase(db).execute(semestre_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Semestre não encontrado")
    return result

@app.delete("/semestres/{semestre_id}", status_code=204)
def delete_semestre(semestre_id: int, db: Session = Depends(get_db)):
    try:
        deleted = DeleteSemestreUseCase(db).execute(semestre_id)
    except ResourceInUseError:
        raise HTTPException(status_code=409, detail="Não é possível excluir: existem registros vinculados a este semestre")
    if not deleted:
        raise HTTPException(status_code=404, detail="Semestre não encontrado")
    return None


@app.patch("/usuarios/{usuario_id}")
def update_usuario(usuario_id: int, request: UpdateUsuarioRequest, db: Session = Depends(get_db)):
    result = UpdateUsuarioUseCase(db).execute(usuario_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return result

@app.delete("/usuarios/{usuario_id}", status_code=204)
def delete_usuario(usuario_id: int, db: Session = Depends(get_db)):
    try:
        deleted = DeleteUsuarioUseCase(db).execute(usuario_id)
    except ResourceInUseError:
        raise HTTPException(status_code=409, detail="Não é possível excluir: existem registros vinculados a este usuário")
    if not deleted:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return None


@app.patch("/formularios/{formulario_id}")
def update_formulario(formulario_id: int, request: UpdateFormularioRequest, db: Session = Depends(get_db)):
    result = UpdateFormularioUseCase(db).execute(formulario_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Formulário não encontrado")
    return result

@app.delete("/formularios/{formulario_id}", status_code=204)
def delete_formulario(formulario_id: int, db: Session = Depends(get_db)):
    try:
        deleted = DeleteFormularioUseCase(db).execute(formulario_id)
    except ResourceInUseError:
        raise HTTPException(status_code=409, detail="Não é possível excluir: existem registros vinculados a este formulário")
    if not deleted:
        raise HTTPException(status_code=404, detail="Formulário não encontrado")
    return None


@app.patch("/bancas/{banca_id}")
def update_banca(banca_id: int, request: UpdateBancaRequest, db: Session = Depends(get_db)):
    result = UpdateBancaUseCase(db).execute(banca_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Banca não encontrada")
    return result

@app.delete("/bancas/{banca_id}", status_code=204)
def delete_banca(banca_id: int, db: Session = Depends(get_db)):
    try:
        deleted = DeleteBancaUseCase(db).execute(banca_id)
    except ResourceInUseError:
        raise HTTPException(status_code=409, detail="Não é possível excluir: existem registros vinculados a esta banca")
    if not deleted:
        raise HTTPException(status_code=404, detail="Banca não encontrada")
    return None


@app.patch("/perguntas/{pergunta_id}")
def update_pergunta(pergunta_id: int, request: UpdatePerguntaRequest, db: Session = Depends(get_db)):
    result = UpdatePerguntaUseCase(db).execute(pergunta_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Pergunta não encontrada")
    return result

@app.delete("/perguntas/{pergunta_id}", status_code=204)
def delete_pergunta(pergunta_id: int, db: Session = Depends(get_db)):
    try:
        deleted = DeletePerguntaUseCase(db).execute(pergunta_id)
    except ResourceInUseError:
        raise HTTPException(status_code=409, detail="Não é possível excluir: existem registros vinculados a esta pergunta")
    if not deleted:
        raise HTTPException(status_code=404, detail="Pergunta não encontrada")
    return None


@app.patch("/candidaturas/{candidatura_id}")
def update_candidatura(candidatura_id: int, request: UpdateCandidaturaRequest, db: Session = Depends(get_db)):
    result = UpdateCandidaturaUseCase(db).execute(candidatura_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Candidatura não encontrada")
    return result

@app.delete("/candidaturas/{candidatura_id}", status_code=204)
def delete_candidatura(candidatura_id: int, db: Session = Depends(get_db)):
    try:
        deleted = DeleteCandidaturaUseCase(db).execute(candidatura_id)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail="Candidatura não encontrada")
    return None


@app.patch("/avaliacoes/{avaliacao_id}")
def update_avaliacao(avaliacao_id: int, request: UpdateAvaliacaoRequest, db: Session = Depends(get_db)):
    result = UpdateAvaliacaoUseCase(db).execute(avaliacao_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")
    return result

@app.delete("/avaliacoes/{avaliacao_id}", status_code=204)
def delete_avaliacao(avaliacao_id: int, db: Session = Depends(get_db)):
    try:
        deleted = DeleteAvaliacaoUseCase(db).execute(avaliacao_id)
    except ResourceInUseError:
        raise HTTPException(status_code=409, detail="Não é possível excluir: existem registros vinculados a esta avaliação")
    if not deleted:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")
    return None


@app.patch("/avaliacoes-notas/{avaliacao_nota_id}")
def update_avaliacao_nota(avaliacao_nota_id: int, request: UpdateAvaliacaoNotaRequest, db: Session = Depends(get_db)):
    try:
        result = UpdateAvaliacaoNotaUseCase(db).execute(avaliacao_nota_id, request)
    except RegraDeNegocioError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Nota de avaliação não encontrada")
    return result

@app.delete("/avaliacoes-notas/{avaliacao_nota_id}", status_code=204)
def delete_avaliacao_nota(avaliacao_nota_id: int, db: Session = Depends(get_db)):
    try:
        deleted = DeleteAvaliacaoNotaUseCase(db).execute(avaliacao_nota_id)
    except ResourceInUseError:
        raise HTTPException(status_code=409, detail="Não é possível excluir: existem registros vinculados a esta nota")
    if not deleted:
        raise HTTPException(status_code=404, detail="Nota de avaliação não encontrada")
    return None


@app.patch("/frentes/{frente_id}")
def update_frente(frente_id: int, request: UpdateFrenteRequest, db: Session = Depends(get_db)):
    result = UpdateFrenteUseCase(db).execute(frente_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Frente não encontrada")
    return result

@app.delete("/frentes/{frente_id}", status_code=204)
def delete_frente(frente_id: int, db: Session = Depends(get_db)):
    try:
        deleted = DeleteFrenteUseCase(db).execute(frente_id)
    except ResourceInUseError:
        raise HTTPException(status_code=409, detail="Não é possível excluir: existem registros vinculados a esta frente")
    if not deleted:
        raise HTTPException(status_code=404, detail="Frente não encontrada")
    return None


@app.patch("/equipes-projeto/{equipe_id}")
def update_equipe_projeto(equipe_id: int, request: UpdateEquipeProjetoRequest, db: Session = Depends(get_db)):
    result = UpdateEquipeProjetoUseCase(db).execute(equipe_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Registro de equipe não encontrado")
    return result

@app.delete("/equipes-projeto/{equipe_id}", status_code=204)
def delete_equipe_projeto(equipe_id: int, db: Session = Depends(get_db)):
    try:
        deleted = DeleteEquipeProjetoUseCase(db).execute(equipe_id)
    except ResourceInUseError:
        raise HTTPException(status_code=409, detail="Não é possível excluir: registro vinculado a outros dados")
    if not deleted:
        raise HTTPException(status_code=404, detail="Registro de equipe não encontrado")
    return None


@app.patch("/usuarios-frentes/{usuario_frente_id}")
def update_usuario_frente(usuario_frente_id: int, request: UpdateUsuarioFrenteRequest, db: Session = Depends(get_db)):
    result = UpdateUsuarioFrenteUseCase(db).execute(usuario_frente_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    return result

@app.delete("/usuarios-frentes/{usuario_frente_id}", status_code=204)
def delete_usuario_frente(usuario_frente_id: int, db: Session = Depends(get_db)):
    try:
        deleted = DeleteUsuarioFrenteUseCase(db).execute(usuario_frente_id)
    except ResourceInUseError:
        raise HTTPException(status_code=409, detail="Não é possível excluir: registro vinculado a outros dados")
    if not deleted:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    return None


@app.patch("/bancas-frentes/{banca_frente_id}")
def update_banca_frente(banca_frente_id: int, request: UpdateBancaFrenteRequest, db: Session = Depends(get_db)):
    result = UpdateBancaFrenteUseCase(db).execute(banca_frente_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    return result

@app.delete("/bancas-frentes/{banca_frente_id}", status_code=204)
def delete_banca_frente(banca_frente_id: int, db: Session = Depends(get_db)):
    try:
        deleted = DeleteBancaFrenteUseCase(db).execute(banca_frente_id)
    except ResourceInUseError:
        raise HTTPException(status_code=409, detail="Não é possível excluir: registro vinculado a outros dados")
    if not deleted:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    return None

@app.get("/cargos")
def list_cargos(db: Session = Depends(get_db)):
    return ListCargosUseCase(db).execute()

@app.get("/cargos/{cargo_id}")
def get_cargo(cargo_id: int, db: Session = Depends(get_db)):
    result = GetCargoUseCase(db).execute(cargo_id)
    if not result:
        raise HTTPException(status_code=404, detail="Cargo não encontrado")
    return result


@app.get("/escopos")
def list_escopos(db: Session = Depends(get_db)):
    return ListEscoposUseCase(db).execute()

@app.get("/escopos/{escopo_id}")
def get_escopo(escopo_id: int, db: Session = Depends(get_db)):
    result = GetEscopoUseCase(db).execute(escopo_id)
    if not result:
        raise HTTPException(status_code=404, detail="Escopo não encontrado")
    return result


@app.get("/semestres")
def list_semestres(db: Session = Depends(get_db)):
    return ListSemestresUseCase(db).execute()

@app.get("/semestres/{semestre_id}")
def get_semestre(semestre_id: int, db: Session = Depends(get_db)):
    result = GetSemestreUseCase(db).execute(semestre_id)
    if not result:
        raise HTTPException(status_code=404, detail="Semestre não encontrado")
    return result


@app.get("/usuarios")
def list_usuarios(db: Session = Depends(get_db)):
    return ListUsuariosUseCase(db).execute()

@app.get("/usuarios/{usuario_id}")
def get_usuario(usuario_id: int, db: Session = Depends(get_db)):
    result = GetUsuarioUseCase(db).execute(usuario_id)
    if not result:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return result
    

@app.get("/bancas")
def list_bancas(db: Session = Depends(get_db)):
    return ListBancasUseCase(db).execute()

@app.get("/bancas/{banca_id}")
def get_banca(banca_id: int, db: Session = Depends(get_db)):
    result = GetBancaUseCase(db).execute(banca_id)
    if not result:
        raise HTTPException(status_code=404, detail="Banca não encontrada")
    return result


@app.get("/perguntas")
def list_perguntas(db: Session = Depends(get_db)):
    return ListPerguntasUseCase(db).execute()

@app.get("/perguntas/{pergunta_id}")
def get_pergunta(pergunta_id: int, db: Session = Depends(get_db)):
    result = GetPerguntaUseCase(db).execute(pergunta_id)
    if not result:
        raise HTTPException(status_code=404, detail="Pergunta não encontrada")
    return result


@app.get("/candidaturas")
def list_candidaturas(db: Session = Depends(get_db)):
    return ListCandidaturasUseCase(db).execute()

@app.get("/candidaturas/{candidatura_id}")
def get_candidatura(candidatura_id: int, db: Session = Depends(get_db)):
    result = GetCandidaturaUseCase(db).execute(candidatura_id)
    if not result:
        raise HTTPException(status_code=404, detail="Candidatura não encontrada")
    return result


@app.get("/avaliacoes")
def list_avaliacoes(db: Session = Depends(get_db)):
    return ListAvaliacoesUseCase(db).execute()

@app.get("/avaliacoes/{avaliacao_id}")
def get_avaliacao(avaliacao_id: int, db: Session = Depends(get_db)):
    result = GetAvaliacaoUseCase(db).execute(avaliacao_id)
    if not result:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")
    return result


@app.get("/avaliacoes-notas")
def list_avaliacoes_notas(db: Session = Depends(get_db)):
    return ListAvaliacoesNotasUseCase(db).execute()

@app.get("/avaliacoes-notas/{avaliacao_nota_id}")
def get_avaliacao_nota(avaliacao_nota_id: int, db: Session = Depends(get_db)):
    result = GetAvaliacaoNotaUseCase(db).execute(avaliacao_nota_id)
    if not result:
        raise HTTPException(status_code=404, detail="Nota de avaliação não encontrada")
    return result


@app.get("/frentes")
def list_frentes(db: Session = Depends(get_db)):
    return ListFrentesUseCase(db).execute()

@app.get("/frentes/{frente_id}")
def get_frente(frente_id: int, db: Session = Depends(get_db)):
    result = GetFrenteUseCase(db).execute(frente_id)
    if not result:
        raise HTTPException(status_code=404, detail="Frente não encontrada")
    return result


@app.get("/equipes-projeto")
def list_equipes_projeto(db: Session = Depends(get_db)):
    return ListEquipesProjetoUseCase(db).execute()

@app.get("/equipes-projeto/{equipe_id}")
def get_equipe_projeto(equipe_id: int, db: Session = Depends(get_db)):
    result = GetEquipeProjetoUseCase(db).execute(equipe_id)
    if not result:
        raise HTTPException(status_code=404, detail="Registro de equipe não encontrado")
    return result


@app.get("/usuarios-frentes")
def list_usuarios_frentes(db: Session = Depends(get_db)):
    return ListUsuariosFrentesUseCase(db).execute()

@app.get("/usuarios-frentes/{usuario_frente_id}")
def get_usuario_frente(usuario_frente_id: int, db: Session = Depends(get_db)):
    result = GetUsuarioFrenteUseCase(db).execute(usuario_frente_id)
    if not result:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    return result


@app.get("/bancas-frentes")
def list_bancas_frentes(db: Session = Depends(get_db)):
    return ListBancasFrentesUseCase(db).execute()

@app.get("/bancas-frentes/{banca_frente_id}")
def get_banca_frente(banca_frente_id: int, db: Session = Depends(get_db)):
    result = GetBancaFrenteUseCase(db).execute(banca_frente_id)
    if not result:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    return result

@app.get("/bancas/{banca_id}/notas-por-pergunta")
def get_notas_por_pergunta(banca_id: int, db: Session = Depends(get_db)):
    return GetNotasPorPerguntaUseCase(db).execute(banca_id)

@app.get("/configuracao")
def get_configuracao(db: Session = Depends(get_db)):
    return GetConfiguracaoUseCase(db).execute()


@app.patch("/configuracao")
def update_configuracao(request: UpdateConfiguracaoRequest, db: Session = Depends(get_db)):
    return UpdateConfiguracaoUseCase(db).execute(request)

@app.get("/usuarios/{usuario_id}/bancas-para-avaliar")
def get_bancas_para_avaliar(usuario_id: int, db: Session = Depends(get_db)):
    return GetBancasParaAvaliarUseCase(db).execute(usuario_id)


@app.get("/avaliacoes-pendentes")
def get_avaliacoes_pendentes(db: Session = Depends(get_db)):
    return GetAvaliacoesPendentesUseCase(db).execute()

@app.get("/usuarios/{usuario_id}/desempenho")
def get_desempenho(usuario_id: int, semestre_id: Optional[int] = None, db: Session = Depends(get_db)):
    result = GetDesempenhoUseCase(db).execute(usuario_id, semestre_id)
    if not result:
        raise HTTPException(status_code=404, detail="Semestre não encontrado")
    return result

@app.get("/historico-bancas")
def get_historico_bancas(
    consultor_id: Optional[int] = None,
    coordenador_id: Optional[int] = None,
    escopo_id: Optional[int] = None,
    semestre_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    return GetHistoricoBancasUseCase(db).execute(consultor_id, coordenador_id, escopo_id, semestre_id)