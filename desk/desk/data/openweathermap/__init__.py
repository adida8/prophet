"""OpenWeatherMap One Call 3.0 client.

v1 ships only the probe needed to verify the key. Forecast calls (B.2
weather) arrive in a later PR with venue-day batching per data-layer
spec §4.1.
"""

from desk.data.openweathermap.client import OpenWeatherClient, OpenWeatherError
from desk.data.openweathermap.status import OpenWeatherStatus, probe_status

__all__ = [
    "OpenWeatherClient",
    "OpenWeatherError",
    "OpenWeatherStatus",
    "probe_status",
]
