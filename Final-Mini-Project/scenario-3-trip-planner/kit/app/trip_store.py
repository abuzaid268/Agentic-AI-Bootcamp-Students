import os
import re
from typing import Any

import httpx

from app.mcp_app_client import call_app_tool


class TripStoreError(RuntimeError):
    """Raised when saving a trip fails. `code` is the Trip Store's error code when it gave one."""

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.code = code


TRIP_ID = re.compile(r"TRIP-\d+")


def trip_title(itinerary: dict[str, Any]) -> str:
    """The title a saved trip gets: "<destination>, <n> days"."""
    days = len(itinerary.get("days") or [])
    return f"{itinerary.get('destination')}, {days} {'day' if days == 1 else 'days'}"


def save_trip_to_store(
    itinerary: dict[str, Any],
    traveller_id: str,
    action_id: str,
    title: str | None = None,
) -> dict[str, Any]:
    """
    Save an approved itinerary through the MCP server's save_trip tool.

    The action_id is the idempotency key: the Trip Store answers a repeated save of the
    same body with the same trip and saves nothing new. There is no REST fallback: if
    the MCP call fails, nothing is reported as saved.
    """

    if not traveller_id or not traveller_id.strip():
        raise TripStoreError("Traveller ID is required.")

    if not isinstance(itinerary, dict):
        raise TripStoreError("Itinerary must be a dictionary.")

    required_fields = {
        "destination",
        "currency",
        "budget_total",
        "days",
    }

    missing_fields = [
        field
        for field in required_fields
        if field not in itinerary
    ]

    if missing_fields:
        raise TripStoreError(
            "Itinerary is missing required fields: "
            + ", ".join(sorted(missing_fields))
        )

    if not itinerary["days"]:
        raise TripStoreError("Itinerary must contain at least one day.")

    try:
        result = call_app_tool("save_trip", {
            "traveller_id": traveller_id.strip(),
            "title": title or trip_title(itinerary),
            "itinerary": itinerary,
            "idempotency_key": action_id,
        })
    except Exception as exc:
        raise TripStoreError("The MCP server could not be reached to save the trip.", "mcp_unavailable") from exc

    if not isinstance(result, dict):
        raise TripStoreError("The MCP save_trip tool returned an invalid response.", "bad_result")

    if result.get("ok") is not True:
        error = result.get("error") if isinstance(result.get("error"), dict) else {}
        raise TripStoreError(
            str(error.get("message") or "The Trip Store did not save the trip."),
            str(error.get("code") or "save_failed"),
        )

    trip_id = result.get("trip_id")
    if not isinstance(trip_id, str) or not TRIP_ID.fullmatch(trip_id):
        raise TripStoreError("The Trip Store did not return a valid trip ID.", "bad_result")

    return {k: v for k, v in result.items() if k != "ok"}


# Reads for My Trips (application code, not an agent tool): the Travel API's REST endpoints. Writes go only
# through the MCP save_trip tool above, after an explicit approval.
def _store_client() -> tuple[str, dict[str, str]]:
    api_url = os.getenv("TRAVEL_API_URL", "http://127.0.0.1:8103").rstrip("/")
    api_key = os.getenv("TRAVEL_API_KEY")
    if not api_key:
        raise TripStoreError("Travel API key is not configured.")
    return api_url, {"X-API-Key": api_key}


def list_trips_from_store(traveller_id: str) -> list[dict[str, Any]]:
    """The traveller's saved trips (summaries) from the Trip Store, newest first."""
    api_url, headers = _store_client()
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(f"{api_url}/api/travellers/{traveller_id}/trips", headers=headers)
            response.raise_for_status()
            result = response.json()
    except httpx.HTTPError as exc:
        raise TripStoreError("Travel API request failed.") from exc
    except ValueError as exc:
        raise TripStoreError("Travel API returned an invalid response.") from exc
    trips = result.get("trips") if isinstance(result, dict) else None
    if not isinstance(trips, list):
        raise TripStoreError("Travel API returned an invalid trip list.")
    return sorted(trips, key=lambda t: str(t.get("created_at") or ""), reverse=True)


def get_trip_from_store(trip_id: str) -> dict[str, Any] | None:
    """One saved trip with its itinerary, or None when the Trip Store has no such trip."""
    api_url, headers = _store_client()
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(f"{api_url}/api/trips/{trip_id}", headers=headers)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            result = response.json()
    except httpx.HTTPError as exc:
        raise TripStoreError("Travel API request failed.") from exc
    except ValueError as exc:
        raise TripStoreError("Travel API returned an invalid response.") from exc
    if not isinstance(result, dict) or not isinstance(result.get("itinerary"), dict):
        raise TripStoreError("Travel API returned an invalid trip.")
    return result
