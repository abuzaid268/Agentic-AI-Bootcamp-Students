"""Rebuild app/destinations/data/popular_destinations.json, the short-query list. Run by hand to refresh:

    python -m app.destinations.build_popular

The list below names destinations only (city name and ISO country code). Every record is GeoNames data as the
Open-Meteo Geocoding API serves it (CC BY 4.0, free API, no key): the script asks the provider for the name in
that country and keeps the populated place with exactly that name and the largest population. Nothing is typed
in by hand, and a name the provider does not confirm is reported and left out, never guessed: so is a match of
fewer than MIN_POPULATION people (a village sharing the name, as "Oaxaca" is in Guanajuato). The names follow
GeoNames' English spelling ("St Petersburg", "Washington D.C.", "Oaxaca City"); review the output after a refresh.

It makes one provider call per name (about 230, spaced out): run it in development, not on a production server
(app/open_meteo.py). Output is sorted by GeoNames id, so a refresh diffs cleanly.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import time

import httpx

from .service import POPULAR_PATH, PROVIDER_URL, SOURCE, _fold, normalize_result

# (name as GeoNames spells it in English, ISO 3166-1 alpha-2 country): places travellers commonly plan trips to.
POPULAR: list[tuple[str, str]] = [
    # Europe
    ("Paris", "FR"), ("Nice", "FR"), ("Lyon", "FR"), ("Marseille", "FR"), ("Bordeaux", "FR"),
    ("London", "GB"), ("Edinburgh", "GB"), ("Manchester", "GB"), ("Liverpool", "GB"), ("Dublin", "IE"),
    ("Amsterdam", "NL"), ("Rotterdam", "NL"), ("Brussels", "BE"), ("Bruges", "BE"), ("Berlin", "DE"),
    ("Munich", "DE"), ("Hamburg", "DE"), ("Frankfurt am Main", "DE"), ("Cologne", "DE"), ("Vienna", "AT"),
    ("Salzburg", "AT"), ("Zurich", "CH"), ("Geneva", "CH"), ("Lucerne", "CH"), ("Rome", "IT"), ("Milan", "IT"),
    ("Venice", "IT"), ("Florence", "IT"), ("Naples", "IT"), ("Bologna", "IT"), ("Palermo", "IT"),
    ("Madrid", "ES"), ("Barcelona", "ES"), ("Seville", "ES"), ("Valencia", "ES"), ("Granada", "ES"),
    ("Málaga", "ES"), ("Palma", "ES"), ("Lisbon", "PT"), ("Porto", "PT"), ("Athens", "GR"),
    ("Thessaloniki", "GR"), ("Prague", "CZ"), ("Budapest", "HU"), ("Warsaw", "PL"), ("Kraków", "PL"),
    ("Copenhagen", "DK"), ("Stockholm", "SE"), ("Oslo", "NO"), ("Bergen", "NO"), ("Helsinki", "FI"),
    ("Reykjavík", "IS"), ("Tallinn", "EE"), ("Riga", "LV"), ("Vilnius", "LT"), ("Dubrovnik", "HR"),
    ("Split", "HR"), ("Zagreb", "HR"), ("Ljubljana", "SI"), ("Belgrade", "RS"), ("Bucharest", "RO"),
    ("Sofia", "BG"), ("Valletta", "MT"), ("Monaco", "MC"), ("Luxembourg", "LU"), ("Moscow", "RU"),
    ("St Petersburg", "RU"), ("Kyiv", "UA"), ("Tbilisi", "GE"), ("Yerevan", "AM"), ("Baku", "AZ"),
    # Middle East and Africa
    ("Istanbul", "TR"), ("Antalya", "TR"), ("Ankara", "TR"), ("İzmir", "TR"), ("Amman", "JO"), ("Aqaba", "JO"),
    ("Irbid", "JO"), ("Madaba", "JO"), ("Jerusalem", "IL"), ("Tel Aviv", "IL"), ("Haifa", "IL"), ("Eilat", "IL"),
    ("Beirut", "LB"), ("Cairo", "EG"), ("Alexandria", "EG"), ("Luxor", "EG"), ("Sharm el Sheikh", "EG"),
    ("Hurghada", "EG"), ("Aswan", "EG"), ("Dubai", "AE"), ("Abu Dhabi", "AE"), ("Sharjah city", "AE"),
    ("Doha", "QA"), ("Manama", "BH"), ("Kuwait City", "KW"), ("Muscat", "OM"), ("Riyadh", "SA"),
    ("Jeddah", "SA"), ("Mecca", "SA"), ("Medina", "SA"), ("Damascus", "SY"), ("Baghdad", "IQ"), ("Erbil", "IQ"),
    ("Tehran", "IR"), ("Isfahan", "IR"), ("Marrakesh", "MA"), ("Casablanca", "MA"), ("Fes", "MA"),
    ("Tangier", "MA"), ("Rabat", "MA"), ("Tunis", "TN"), ("Algiers", "DZ"), ("Nairobi", "KE"),
    ("Mombasa", "KE"), ("Zanzibar", "TZ"), ("Dar es Salaam", "TZ"), ("Addis Ababa", "ET"), ("Cape Town", "ZA"),
    ("Johannesburg", "ZA"), ("Durban", "ZA"), ("Lagos", "NG"), ("Accra", "GH"), ("Dakar", "SN"),
    ("Kigali", "RW"), ("Port Louis", "MU"),
    # Asia
    ("Tokyo", "JP"), ("Kyoto", "JP"), ("Osaka", "JP"), ("Hiroshima", "JP"), ("Sapporo", "JP"), ("Seoul", "KR"),
    ("Busan", "KR"), ("Beijing", "CN"), ("Shanghai", "CN"), ("Hong Kong", "HK"), ("Macao", "MO"),
    ("Taipei", "TW"), ("Bangkok", "TH"), ("Chiang Mai", "TH"), ("Phuket", "TH"), ("Pattaya", "TH"),
    ("Singapore", "SG"), ("Kuala Lumpur", "MY"), ("George Town", "MY"), ("Jakarta", "ID"), ("Denpasar", "ID"),
    ("Ubud", "ID"), ("Yogyakarta", "ID"), ("Manila", "PH"), ("Cebu City", "PH"), ("Hanoi", "VN"),
    ("Ho Chi Minh City", "VN"), ("Da Nang", "VN"), ("Hoi An", "VN"), ("Siem Reap", "KH"), ("Phnom Penh", "KH"),
    ("Luang Prabang", "LA"), ("Kathmandu", "NP"), ("New Delhi", "IN"), ("Mumbai", "IN"), ("Jaipur", "IN"),
    ("Agra", "IN"), ("Panjim", "IN"), ("Bengaluru", "IN"), ("Kolkata", "IN"), ("Varanasi", "IN"),
    ("Colombo", "LK"), ("Kandy", "LK"), ("Malé", "MV"), ("Dhaka", "BD"), ("Karachi", "PK"), ("Lahore", "PK"),
    ("Islamabad", "PK"), ("Tashkent", "UZ"), ("Samarkand", "UZ"), ("Almaty", "KZ"),
    # Americas
    ("New York", "US"), ("Los Angeles", "US"), ("San Francisco", "US"), ("Chicago", "US"),
    ("Las Vegas", "US"), ("Miami", "US"), ("Orlando", "US"), ("Washington D.C.", "US"), ("Boston", "US"),
    ("Seattle", "US"), ("New Orleans", "US"), ("Honolulu", "US"), ("San Diego", "US"), ("Toronto", "CA"),
    ("Vancouver", "CA"), ("Montreal", "CA"), ("Quebec", "CA"), ("Mexico City", "MX"), ("Cancún", "MX"),
    ("Oaxaca City", "MX"), ("Havana", "CU"), ("San Juan", "PR"), ("Panama City", "PA"), ("San José", "CR"),
    ("Cartagena", "CO"), ("Bogotá", "CO"), ("Medellín", "CO"), ("Lima", "PE"), ("Cusco", "PE"), ("Quito", "EC"),
    ("Rio de Janeiro", "BR"), ("São Paulo", "BR"), ("Salvador", "BR"), ("Buenos Aires", "AR"),
    ("Mendoza", "AR"), ("Santiago", "CL"), ("Montevideo", "UY"), ("La Paz", "BO"),
    # Oceania
    ("Sydney", "AU"), ("Melbourne", "AU"), ("Brisbane", "AU"), ("Perth", "AU"), ("Cairns", "AU"),
    ("Auckland", "NZ"), ("Queenstown", "NZ"), ("Wellington", "NZ"), ("Nadi", "FJ"),
]

MIN_POPULATION = 5000

KEPT_FIELDS = ("id", "name", "latitude", "longitude", "feature_code", "country_code", "country", "admin1",
               "population", "timezone")


def resolve(client: httpx.Client, name: str, country: str) -> dict | None:
    """The provider's populated place called exactly `name` in `country` with the largest population, or None."""
    response = client.get(PROVIDER_URL, params={"name": name, "countryCode": country, "count": 20,
                                                "language": "en", "format": "json"})
    response.raise_for_status()
    matches = [item for item in response.json().get("results") or []
               if normalize_result(item) and _fold(item.get("name") or "") == _fold(name)
               and (item.get("country_code") or "").upper() == country
               and (item.get("population") or 0) >= MIN_POPULATION]
    if not matches:
        return None
    best = max(matches, key=lambda item: item.get("population") or 0)
    return {field: best[field] for field in KEPT_FIELDS if best.get(field) is not None}


def main() -> int:
    places, missing = {}, []
    with httpx.Client(timeout=10, headers={"User-Agent": "Rihla-trip-planner (dataset build)"}) as client:
        for name, country in POPULAR:
            place = resolve(client, name, country)
            if place is None:
                missing.append(f"{name} ({country})")
            else:
                places[place["id"]] = place
            time.sleep(0.3)  # well under the free API's limits
    POPULAR_PATH.parent.mkdir(parents=True, exist_ok=True)
    POPULAR_PATH.write_text(json.dumps({
        "source": dict(SOURCE),
        "built": dt.date.today().isoformat(),
        "builder": "python -m app.destinations.build_popular",
        "places": sorted(places.values(), key=lambda place: place["id"]),
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(places)} places written to {POPULAR_PATH}")
    if missing:
        print("Not confirmed by the provider, left out: " + ", ".join(missing), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
