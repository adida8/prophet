"""Minimal probe for OpenWeatherMap.

OpenWeatherMap has no first-class /status endpoint, so we do the
cheapest call that proves the key works: a One Call 3.0 request for a
fixed location (London, 51.5074, −0.1278) with `exclude=minutely,hourly,
daily,alerts` so only the current-weather block is returned. If we get
a 200 with a payload that contains `current.temp`, the key + endpoint
are usable. Success is enough for the guardrail-4 smoke check.
"""

from __future__ import annotations

from dataclasses import dataclass

from desk.data.openweathermap.client import OpenWeatherClient


@dataclass(frozen=True)
class OpenWeatherStatus:
    ok: bool
    sample_temperature_c: float | None  # what we read back at the probe location
    sample_location:      str

    def headline(self) -> str:
        loc = self.sample_location
        if not self.ok:
            return f"openweathermap · KEY FAILED at {loc}"
        return (
            f"openweathermap · ok · sample temperature at {loc}: "
            f"{self.sample_temperature_c:.1f}°C"
        )


async def probe_status(client: OpenWeatherClient) -> OpenWeatherStatus:
    # London is just a stable lat/lon — only used to prove the key works.
    sample_loc = "London, UK"
    resp = await client.get(
        "/onecall",
        params={
            "lat": "51.5074",
            "lon": "-0.1278",
            "units": "metric",
            "exclude": "minutely,hourly,daily,alerts",
        },
    )
    current = (resp.payload or {}).get("current") or {}
    temp = current.get("temp")
    if temp is None:
        return OpenWeatherStatus(
            ok=False, sample_temperature_c=None, sample_location=sample_loc,
        )
    return OpenWeatherStatus(
        ok=True,
        sample_temperature_c=float(temp),
        sample_location=sample_loc,
    )
