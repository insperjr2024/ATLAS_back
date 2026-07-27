from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from src.database.database import get_db
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
def create_formulario(
    request: CreateFormularioRequest,
    db: Session = Depends(get_db)
):
    use_case = CreateFormularioUseCase(db)
    return use_case.execute(request)

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
def create_candidatura(
    request: CreateCandidaturaRequest,
    db: Session = Depends(get_db)
):
    use_case = CreateCandidaturaUseCase(db)
    return use_case.execute(request)


@app.post("/avaliacoes")
def create_avaliacao(
    request: CreateAvaliacaoRequest,
    db: Session = Depends(get_db)
):
    use_case = CreateAvaliacaoUseCase(db)
    return use_case.execute(request)


@app.post("/avaliacoes-notas")
def create_avaliacao_nota(
    request: CreateAvaliacaoNotaRequest,
    db: Session = Depends(get_db)
):
    use_case = CreateAvaliacaoNotaUseCase(db)
    return use_case.execute(request)

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