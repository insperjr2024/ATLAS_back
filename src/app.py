from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routers import auth, avaliacoes, bancas, catalogo, projetos, usuarios

app = FastAPI(title="API ATLAS")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


app.include_router(auth.router_publico)
app.include_router(auth.router)
app.include_router(catalogo.router)
app.include_router(usuarios.router)
app.include_router(projetos.router)
app.include_router(bancas.router)
app.include_router(avaliacoes.router)
