"""GET /api/flights: flight offers and prices for a route and dates. Informational, read-only, no sign-in needed.
There is deliberately no route that books, orders or pays."""
from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from .service import DEFAULT_LIMIT, MAX_LIMIT, FlightError, FlightSearch

router = APIRouter(prefix="/api/flights", tags=["flights"])


def _service(request: Request) -> FlightSearch:
    service = getattr(request.app.state, "flight_search", None)
    if service is None:
        service = request.app.state.flight_search = FlightSearch()
    return service


@router.get("/status")
def flight_search_status(request: Request):
    """Whether flight prices can be shown here, and as which data mode (LIVE, TEST, DEMO), before searching."""
    return JSONResponse(_service(request).status(), headers={"Cache-Control": "no-store"})


@router.get("")
def search_flights(
    request: Request,
    origin: str = Query("", max_length=10, description="Departure airport IATA code, e.g. TLV"),
    destination: str = Query("", max_length=10, description="Arrival airport IATA code, e.g. LHR"),
    departure_date: str = Query("", max_length=10, description="YYYY-MM-DD"),
    return_date: str = Query("", max_length=10, description="YYYY-MM-DD; empty for a one-way trip"),
    adults: str = Query("1", max_length=3, description="1-9 adult passengers"),
    cabin_class: str = Query("economy", max_length=20, description="economy, premium_economy, business, first"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
):
    try:
        answer = _service(request).search(origin=origin, destination=destination, departure_date=departure_date,
                                          return_date=return_date, adults=adults, cabin_class=cabin_class,
                                          limit=limit)
    except FlightError as error:
        headers = {"Retry-After": str(error.retry_after)} if error.retry_after is not None else None
        return JSONResponse(error.as_dict(), status_code=error.status, headers=headers)
    # Prices change and offers expire: never let a browser or proxy reuse an answer.
    return JSONResponse(answer, headers={"Cache-Control": "no-store"})
