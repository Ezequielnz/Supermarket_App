from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as api_v1_router
from app.core.config import settings

app = FastAPI(title="FreshMart API")

# Dos origenes: la app del consumidor y el panel de supermercados. Metodos y
# cabeceras van enumerados en vez de "*" (docs/SEGURIDAD.md §8.2): con origenes
# explicitos el comodin no es explotable de por si, pero acotarlo reduce lo que
# un XSS en un origen permitido puede llegar a intentar.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/health")
def health_check():
    """Chequeo de salud para verificar que el servidor está arriba."""
    return {"status": "ok"}
