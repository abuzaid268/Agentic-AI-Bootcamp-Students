import os
from typing import Any

import httpx


class TripStoreError(RuntimeError):
    """Raised when saving a trip fails."""


def save_trip_to_store(
    itinerary: dict[str, Any],
    traveller_id: str,
    action_id: str,
) -> dict[str, Any]:
    """
    Save an approved itinerary through the Travel API.

    The action_id is used as an idempotency key to prevent
    duplicate trip creation.
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

    api_url = os.getenv(
        "TRAVEL_API_URL",
        "http://127.0.0.1:8001",
    ).rstrip("/")

    api_key = os.getenv("TRAVEL_API_KEY")

    if not api_key:
        raise TripStoreError("Travel API key is not configured.")

    destination = itinerary["destination"]
    days_count = len(itinerary["days"])

    payload = {
        "traveller_id": traveller_id,
        "title": f"{destination}, {days_count} days",
        "itinerary": itinerary,
    }

    headers = {
        "X-API-Key": api_key,
        "Idempotency-Key": action_id,
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                f"{api_url}/api/trips",
                json=payload,
                headers=headers,
            )

            response.raise_for_status()
            result = response.json()

    except httpx.HTTPError as exc:
        raise TripStoreError(
            "Travel API request failed."
        ) from exc

    except ValueError as exc:
        raise TripStoreError(
            "Travel API returned an invalid response."
        ) from exc

    if not isinstance(result, dict) or not result.get("trip_id"):
        raise TripStoreError(
            "Travel API did not return a valid trip ID."
        )

    return result

def _store_client() -> tuple[str, dict[str, str]]:
    api_url = os.getenv("TRAVEL_API_URL", "http://127.0.0.1:8001").rstrip("/")
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
