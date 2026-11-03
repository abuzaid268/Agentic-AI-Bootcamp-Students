"""GET /api/destinations?q=…: worldwide city search for the destination box. Read-only, no sign-in needed."""
from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from .service import DEFAULT_LIMIT, MAX_LIMIT, DestinationError, DestinationSearch

router = APIRouter(prefix="/api/destinations", tags=["destinations"])


def _service(request: Request) -> DestinationSearch:
    service = getattr(request.app.state, "destination_search", None)
    if service is None:
        service = request.app.state.destination_search = DestinationSearch()
    return service


@router.get("/status")
def destination_search_status(request: Request):
    """Whether city search can run on this server (licence decision), before searching."""
    return JSONResponse(_service(request).status(), headers={"Cache-Control": "no-store"})


@router.get("")
def search_destinations(
    request: Request,
    q: str = Query("", max_length=200, description="The beginning of a city name, at least 2 letters"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    lang: str = Query("en", min_length=2, max_length=2, description="Language of the names (ISO 639-1)"),
):
    try:
        answer = _service(request).search(q, limit=limit, language=lang)
    except DestinationError as error:
        headers = {"Retry-After": str(error.retry_after)} if error.retry_after is not None else None
        return JSONResponse(error.as_dict(), status_code=error.status, headers=headers)
    return JSONResponse(answer, headers={"Cache-Control": "private, max-age=300"})
