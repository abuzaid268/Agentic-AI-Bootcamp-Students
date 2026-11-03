"""GET /api/airports?q=…: airport search for the departure and arrival boxes. Read-only, no sign-in needed."""
from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from .service import DEFAULT_LIMIT, MAX_LIMIT, AirportError, AirportSearch

router = APIRouter(prefix="/api/airports", tags=["airports"])


def _service(request: Request) -> AirportSearch:
    service = getattr(request.app.state, "airport_search", None)
    if service is None:
        service = request.app.state.airport_search = AirportSearch()
    return service


@router.get("/countries")
def airport_countries(request: Request):
    """The countries in the airport data, by name, for the departure country picker."""
    try:
        answer = _service(request).countries()
    except AirportError as error:
        return JSONResponse(error.as_dict(), status_code=error.status)
    return JSONResponse(answer, headers={"Cache-Control": "public, max-age=86400"})


@router.get("")
def search_airports(
    request: Request,
    q: str = Query("", max_length=200, description="Airport name, city, country, IATA or ICAO code; 2+ letters"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    scheduled_only: bool = Query(False, description="Only airports OurAirports marks as having scheduled service"),
    country: str = Query("", max_length=2, description="Only airports in this country (ISO 3166-1 alpha-2, e.g. JO)"),
):
    try:
        answer = _service(request).search(q, limit=limit, scheduled_only=scheduled_only, country=country)
    except AirportError as error:
        return JSONResponse(error.as_dict(), status_code=error.status)
    return JSONResponse(answer, headers={"Cache-Control": "public, max-age=3600"})
