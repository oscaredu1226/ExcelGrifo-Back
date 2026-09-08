from fastapi import APIRouter


router = APIRouter(prefix="/api", tags=["Health"])


@router.get(
    "/health",
    summary="Health check",
    description="Verifica que la API este disponible.",
    responses={200: {"description": "API disponible"}},
)
def health_check() -> dict[str, str]:
    return {"status": "ok"}
