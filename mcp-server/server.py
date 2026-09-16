#!/usr/bin/env python3
"""Trip-planner MCP server: two tools, no API keys.

    get_forecast(cities)  -> this weekend's forecast for each city (Open-Meteo, keyless).
                             Several real HTTP calls in sequence, so it takes a few seconds:
                             that delay is the point of the recipe, not a bug to hide.
    save_trip(...)        -> writes output/<trip_id>.json. Call it again with the same
                             trip_id to replace an earlier choice, so a correction leaves
                             exactly one file.

Run:  python server.py            (binds 0.0.0.0:8787, MCP endpoint at /mcp)
Env:  PORT        listen port (default 8787)
      OUTPUT_DIR  where save_trip writes (default ../output next to this file)
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

PORT = int(os.environ.get("PORT", "8787"))
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR") or Path(__file__).resolve().parent.parent / "output")

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather interpretation codes, as Open-Meteo returns them.
WMO = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "rime fog", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain", 71: "light snow", 73: "snow",
    75: "heavy snow", 80: "rain showers", 81: "heavy showers", 82: "violent showers",
    95: "thunderstorm", 96: "thunderstorm with hail", 99: "severe thunderstorm",
}

mcp = MCPServer("trip-planner")


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    print(f"{ts} {msg}", file=sys.stderr, flush=True)


def get_json(url: str, params: dict) -> dict:
    with urllib.request.urlopen(url + "?" + urllib.parse.urlencode(params), timeout=10) as r:
        return json.load(r)


def weekend(today: date | None = None) -> tuple[date, date]:
    """The coming Saturday and Sunday. On a Sunday, 'this weekend' is still today."""
    today = today or date.today()
    if today.weekday() == 6:
        return today - timedelta(days=1), today
    saturday = today + timedelta(days=(5 - today.weekday()) % 7)
    return saturday, saturday + timedelta(days=1)


def forecast_for(city: str, days: tuple[date, date]) -> dict:
    places = get_json(GEOCODE_URL, {"name": city, "count": 1, "language": "en", "format": "json"})
    if not places.get("results"):
        return {"city": city, "error": "city not found"}
    p = places["results"][0]
    fc = get_json(FORECAST_URL, {
        "latitude": p["latitude"], "longitude": p["longitude"], "timezone": "auto",
        "forecast_days": 10,
        "daily": "weather_code,temperature_2m_max,precipitation_probability_max,sunshine_duration",
    })
    d = fc["daily"]
    out = {"city": p["name"], "country": p.get("country", ""), "days": []}
    for day in days:
        iso = day.isoformat()
        if iso not in d["time"]:
            out["days"].append({"date": iso, "error": "beyond forecast range"})
            continue
        i = d["time"].index(iso)
        out["days"].append({
            "date": iso,
            "weekday": day.strftime("%A"),
            "sky": WMO.get(d["weather_code"][i], f"code {d['weather_code'][i]}"),
            "max_temp_c": d["temperature_2m_max"][i],
            "rain_chance_pct": d["precipitation_probability_max"][i],
            "sunshine_hours": round((d["sunshine_duration"][i] or 0) / 3600, 1),
        })
    return out


@mcp.tool()
def get_forecast(cities: list[str]) -> dict:
    """Weekend weather forecast for several candidate cities at once.

    Pass ALL candidate cities in one call (for example ["Lisbon", "Seville", "Malaga"]).
    Returns, for each city, Saturday's and Sunday's sky, maximum temperature in Celsius,
    chance of rain and hours of sunshine. This takes several seconds: it makes two live
    weather-service requests per city.
    """
    t0 = time.monotonic()
    log(f"get_forecast start cities={cities}")
    sat, sun = weekend()
    result = {"weekend": [sat.isoformat(), sun.isoformat()], "cities": []}
    for city in cities:
        try:
            result["cities"].append(forecast_for(city, (sat, sun)))
        except Exception as e:  # keep the other cities even if one lookup fails
            result["cities"].append({"city": city, "error": str(e)})
    log(f"get_forecast done in {time.monotonic() - t0:.1f}s")
    return result


@mcp.tool()
def save_trip(city: str, country: str = "", reason: str = "", trip_id: str = "") -> dict:
    """Record the caller's chosen destination for this weekend.

    Call this once the caller has picked a city. If the caller then changes their mind,
    call it AGAIN with the trip_id this tool returned, so the earlier choice is replaced
    rather than a second trip being added. Writes one JSON file per trip_id.
    """
    trip_id = trip_id.strip() or uuid.uuid4().hex[:8]
    sat, sun = weekend()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{trip_id}.json"
    replaced = path.exists()
    record = {
        "trip_id": trip_id,
        "city": city,
        "country": country,
        "reason": reason,
        "weekend": [sat.isoformat(), sun.isoformat()],
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    path.write_text(json.dumps(record, indent=2) + "\n")
    log(f"save_trip {'replaced' if replaced else 'wrote'} {path} city={city!r}")
    return {"saved": True, "replaced_previous": replaced, "trip_id": trip_id,
            "city": city, "file": str(path)}


if __name__ == "__main__":
    log(f"trip-planner MCP server on 0.0.0.0:{PORT}/mcp, output dir {OUTPUT_DIR}")
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=PORT,
        # The agent calls in from another host (a container, or a cloud agent through a
        # tunnel), so do not restrict the Host header to localhost.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
        # One JSON reply per call and no session state to lose on reconnect.
        json_response=True,
        stateless_http=True,
    )
