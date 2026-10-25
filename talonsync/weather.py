"""Weather for TalonCast, from Open-Meteo (free, no account, no key).

Everything is normalized into one plain dict (see Weather.to_dict) that the TalonCast pages in the
window and the TalonCast app on the PDA both use.
"""
from __future__ import annotations

import json
import math
import threading
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from typing import Callable, Dict, List, Optional

FORECAST = "https://api.open-meteo.com/v1/forecast"
GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
UA = {"User-Agent": "TalonSync/1.0 (TalonCast)"}

# ---------------------------------------------------------------- WMO weather codes
# code -> (long text, short text for the 4000-style panels, icon key, PDA icon number)
WMO = {
    0: ("Clear", "Clear", "sun", 0), 1: ("Mostly Clear", "M Clear", "sun", 0), 2: ("Partly Cloudy", "P Cloudy", "partly", 1),
    3: ("Cloudy", "Cloudy", "cloud", 2), 45: ("Fog", "Fog", "fog", 3), 48: ("Freezing Fog", "Frz Fog", "fog", 3),
    51: ("Light Drizzle", "Drizzle", "drizzle", 4), 53: ("Drizzle", "Drizzle", "drizzle", 4), 55: ("Heavy Drizzle", "Drizzle", "drizzle", 4),
    56: ("Freezing Drizzle", "Frz Drzl", "sleet", 7), 57: ("Freezing Drizzle", "Frz Drzl", "sleet", 7),
    61: ("Light Rain", "Lt Rain", "rain", 5), 63: ("Rain", "Rain", "rain", 5), 65: ("Heavy Rain", "Hvy Rain", "rain", 5),
    66: ("Freezing Rain", "Frz Rain", "sleet", 7), 67: ("Freezing Rain", "Frz Rain", "sleet", 7),
    71: ("Light Snow", "Lt Snow", "snow", 6), 73: ("Snow", "Snow", "snow", 6), 75: ("Heavy Snow", "Hvy Snow", "snow", 6),
    77: ("Snow Grains", "Snow", "snow", 6), 80: ("Rain Showers", "Showers", "showers", 5), 81: ("Rain Showers", "Showers", "showers", 5),
    82: ("Heavy Showers", "Showers", "showers", 5), 85: ("Snow Showers", "Snw Shwr", "snow", 6), 86: ("Snow Showers", "Snw Shwr", "snow", 6),
    95: ("Thunderstorms", "T-Storms", "storm", 8), 96: ("T-Storms, Hail", "T-Storms", "storm", 8), 99: ("T-Storms, Hail", "T-Storms", "storm", 8),
}


def wmo(code) -> tuple:
    return WMO.get(int(code or 0), ("Unknown", "--", "cloud", 2))


COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def compass(deg) -> str:
    if deg is None:
        return ""
    return COMPASS[int((float(deg) % 360) / 22.5 + 0.5) % 16]


# ---------------------------------------------------------------- nearby cities for the regional pages
CITIES = [
    ("New York", 40.71, -74.01), ("Los Angeles", 34.05, -118.24), ("Chicago", 41.88, -87.63), ("Houston", 29.76, -95.37),
    ("Phoenix", 33.45, -112.07), ("Philadelphia", 39.95, -75.17), ("San Antonio", 29.42, -98.49), ("San Diego", 32.72, -117.16),
    ("Dallas", 32.78, -96.80), ("Austin", 30.27, -97.74), ("Jacksonville", 30.33, -81.66), ("Columbus", 39.96, -83.00),
    ("Indianapolis", 39.77, -86.16), ("San Francisco", 37.77, -122.42), ("Seattle", 47.61, -122.33), ("Denver", 39.74, -104.99),
    ("Nashville", 36.16, -86.78), ("Oklahoma City", 35.47, -97.52), ("El Paso", 31.76, -106.49), ("Boston", 42.36, -71.06),
    ("Portland", 45.52, -122.68), ("Las Vegas", 36.17, -115.14), ("Detroit", 42.33, -83.05), ("Memphis", 35.15, -90.05),
    ("Louisville", 38.25, -85.76), ("Baltimore", 39.29, -76.61), ("Milwaukee", 43.04, -87.91), ("Albuquerque", 35.08, -106.65),
    ("Tucson", 32.22, -110.97), ("Fresno", 36.74, -119.79), ("Sacramento", 38.58, -121.49), ("Kansas City", 39.10, -94.58),
    ("Atlanta", 33.75, -84.39), ("Omaha", 41.26, -95.93), ("Raleigh", 35.78, -78.64), ("Miami", 25.76, -80.19),
    ("Minneapolis", 44.98, -93.27), ("Tulsa", 36.15, -95.99), ("Cleveland", 41.50, -81.69), ("Wichita", 37.69, -97.34),
    ("New Orleans", 29.95, -90.07), ("Tampa", 27.95, -82.46), ("Orlando", 28.54, -81.38), ("Pittsburgh", 40.44, -79.99),
    ("Cincinnati", 39.10, -84.51), ("St. Louis", 38.63, -90.20), ("Salt Lake City", 40.76, -111.89), ("Boise", 43.62, -116.20),
    ("Des Moines", 41.59, -93.62), ("Madison", 43.07, -89.40), ("Springfield", 39.80, -89.64), ("Peoria", 40.69, -89.59),
    ("Rockford", 42.27, -89.09), ("Fort Wayne", 41.08, -85.14), ("Grand Rapids", 42.96, -85.67), ("Little Rock", 34.75, -92.29),
    ("Birmingham", 33.52, -86.80), ("Jackson", 32.30, -90.18), ("Charlotte", 35.23, -80.84), ("Richmond", 37.54, -77.44),
    ("Washington", 38.91, -77.04), ("Buffalo", 42.89, -78.88), ("Albany", 42.65, -73.76), ("Hartford", 41.77, -72.67),
    ("Providence", 41.82, -71.41), ("Portland ME", 43.66, -70.26), ("Burlington", 44.48, -73.21), ("Charleston", 32.78, -79.93),
    ("Savannah", 32.08, -81.09), ("Tallahassee", 30.44, -84.28), ("Mobile", 30.69, -88.04), ("Shreveport", 32.53, -93.75),
    ("Amarillo", 35.22, -101.83), ("Lubbock", 33.58, -101.86), ("Corpus Christi", 27.80, -97.40), ("Billings", 45.78, -108.50),
    ("Fargo", 46.88, -96.79), ("Sioux Falls", 43.55, -96.73), ("Rapid City", 44.08, -103.23), ("Cheyenne", 41.14, -104.82),
    ("Spokane", 47.66, -117.43), ("Reno", 39.53, -119.81), ("Anchorage", 61.22, -149.90), ("Honolulu", 21.31, -157.86),
    ("Toronto", 43.65, -79.38), ("Montreal", 45.50, -73.57), ("Vancouver", 49.28, -123.12), ("Calgary", 51.05, -114.07),
    ("Winnipeg", 49.90, -97.14), ("Ottawa", 45.42, -75.70), ("Mexico City", 19.43, -99.13), ("Monterrey", 25.69, -100.32),
    ("London", 51.51, -0.13), ("Manchester", 53.48, -2.24), ("Edinburgh", 55.95, -3.19), ("Dublin", 53.35, -6.26),
    ("Paris", 48.86, 2.35), ("Lyon", 45.76, 4.84), ("Brussels", 50.85, 4.35), ("Amsterdam", 52.37, 4.90),
    ("Berlin", 52.52, 13.40), ("Hamburg", 53.55, 9.99), ("Munich", 48.14, 11.58), ("Frankfurt", 50.11, 8.68),
    ("Zurich", 47.38, 8.54), ("Vienna", 48.21, 16.37), ("Prague", 50.08, 14.44), ("Warsaw", 52.23, 21.01),
    ("Copenhagen", 55.68, 12.57), ("Oslo", 59.91, 10.75), ("Stockholm", 59.33, 18.07), ("Helsinki", 60.17, 24.94),
    ("Madrid", 40.42, -3.70), ("Barcelona", 41.39, 2.17), ("Lisbon", 38.72, -9.14), ("Rome", 41.90, 12.50),
    ("Milan", 45.46, 9.19), ("Athens", 37.98, 23.73), ("Istanbul", 41.01, 28.98), ("Kyiv", 50.45, 30.52),
    ("Tokyo", 35.68, 139.69), ("Osaka", 34.69, 135.50), ("Seoul", 37.57, 126.98), ("Beijing", 39.90, 116.40),
    ("Shanghai", 31.23, 121.47), ("Hong Kong", 22.32, 114.17), ("Taipei", 25.03, 121.57), ("Singapore", 1.35, 103.82),
    ("Bangkok", 13.76, 100.50), ("Manila", 14.60, 120.98), ("Jakarta", -6.21, 106.85), ("Delhi", 28.61, 77.21),
    ("Mumbai", 19.08, 72.88), ("Dubai", 25.20, 55.27), ("Cairo", 30.04, 31.24), ("Johannesburg", -26.20, 28.05),
    ("Sydney", -33.87, 151.21), ("Melbourne", -37.81, 144.96), ("Brisbane", -27.47, 153.03), ("Perth", -31.95, 115.86),
    ("Auckland", -36.85, 174.76), ("Sao Paulo", -23.55, -46.63), ("Rio de Janeiro", -22.91, -43.17), ("Buenos Aires", -34.60, -58.38),
    ("Santiago", -33.45, -70.67), ("Lima", -12.05, -77.04), ("Bogota", 4.71, -74.07),
]


def km(a_lat, a_lon, b_lat, b_lon) -> float:
    p = math.pi / 180
    d = 0.5 - math.cos((b_lat - a_lat) * p) / 2 + math.cos(a_lat * p) * math.cos(b_lat * p) * (1 - math.cos((b_lon - a_lon) * p)) / 2
    return 12742 * math.asin(math.sqrt(max(0.0, d)))


def nearby_cities(lat, lon, n=7, exclude: str = "") -> List[tuple]:
    rows = sorted((km(lat, lon, c[1], c[2]), c) for c in CITIES)
    out = []
    for d, c in rows:
        if d < 8 or c[0].lower() == exclude.lower():
            continue                       # that's us
        out.append((c[0], c[1], c[2], d))
        if len(out) >= n:
            break
    return out


# ---------------------------------------------------------------- moon
SYNODIC = 29.530588853
KNOWN_NEW = datetime(2000, 1, 6, 18, 14)


def moon_age(d: datetime) -> float:
    return ((d - KNOWN_NEW).total_seconds() / 86400.0) % SYNODIC


def moon_phases(start: datetime, count: int = 4) -> List[Dict]:
    """The next `count` principal phases (new, first quarter, full, last quarter) from start."""
    names = ["New", "First", "Full", "Last"]
    out = []
    age = moon_age(start)
    k = int(age // (SYNODIC / 4)) + 1
    base = start - timedelta(days=age)
    while len(out) < count:
        t = base + timedelta(days=k * SYNODIC / 4)
        out.append({"phase": names[k % 4], "date": t.date().isoformat()})
        k += 1
    return out


# ---------------------------------------------------------------- HTTP
def _get(url: str, params: Dict, timeout: float = 12.0) -> dict:
    q = urllib.parse.urlencode(params, safe=",")
    req = urllib.request.Request(f"{url}?{q}", headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def locate_by_ip() -> Optional[Dict]:
    """Roughly where this PC is (city level), from its internet address. No account needed."""
    for url in ("https://ipapi.co/json/", "https://ipwho.is/"):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=8) as r:
                d = json.loads(r.read().decode("utf-8"))
            lat, lon = d.get("latitude"), d.get("longitude")
            if lat is None or lon is None:
                continue
            return {"name": d.get("city") or "Here", "admin1": d.get("region") or "", "country": d.get("country_name") or d.get("country") or "",
                    "lat": float(lat), "lon": float(lon)}
        except Exception:
            continue
    return None


def geocode(name: str, count: int = 6) -> List[Dict]:
    d = _get(GEOCODE, {"name": name, "count": count, "language": "en", "format": "json"})
    out = []
    for r in d.get("results") or []:
        out.append({"name": r.get("name", ""), "admin1": r.get("admin1", ""), "country": r.get("country", ""),
                    "country_code": r.get("country_code", ""), "lat": r["latitude"], "lon": r["longitude"],
                    "timezone": r.get("timezone", "")})
    return out


CURRENT = "temperature_2m,relative_humidity_2m,apparent_temperature,is_day,weather_code,cloud_cover,pressure_msl,wind_speed_10m,wind_direction_10m,wind_gusts_10m,visibility,dew_point_2m,precipitation"
HOURLY = "temperature_2m,weather_code,precipitation_probability,pressure_msl,wind_speed_10m"
DAILY = "weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset,precipitation_probability_max,precipitation_sum,wind_speed_10m_max,wind_direction_10m_dominant,uv_index_max"


def fetch_raw(lat: float, lon: float, metric: bool) -> dict:
    return _get(FORECAST, {
        "latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}", "current": CURRENT, "hourly": HOURLY, "daily": DAILY,
        "temperature_unit": "celsius" if metric else "fahrenheit", "wind_speed_unit": "kmh" if metric else "mph",
        "precipitation_unit": "mm" if metric else "inch", "timezone": "auto", "forecast_days": 7, "past_days": 1,
    })


def fetch_many_current(points: List[tuple], metric: bool) -> List[dict]:
    if not points:
        return []
    d = _get(FORECAST, {
        "latitude": ",".join(f"{p[1]:.2f}" for p in points), "longitude": ",".join(f"{p[2]:.2f}" for p in points),
        "current": "temperature_2m,weather_code,wind_speed_10m,wind_direction_10m,is_day",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min", "forecast_days": 2,
        "temperature_unit": "celsius" if metric else "fahrenheit", "wind_speed_unit": "kmh" if metric else "mph", "timezone": "auto",
    })
    return d if isinstance(d, list) else [d]


# ---------------------------------------------------------------- normalize
def normalize(raw: dict, place: Dict, metric: bool, region: List[dict] = None, region_pts: List[tuple] = None) -> Dict:
    cur = raw.get("current") or {}
    hourly = raw.get("hourly") or {}
    daily = raw.get("daily") or {}
    now = datetime.fromisoformat(cur["time"]) if cur.get("time") else datetime.now()
    code = int(cur.get("weather_code") or 0)
    long, short, icon, pda_icon = wmo(code)
    # pressure trend: now vs 3 hours ago
    times = hourly.get("time") or []
    press = hourly.get("pressure_msl") or []
    idx = next((i for i, t in enumerate(times) if datetime.fromisoformat(t) >= now.replace(minute=0, second=0)), len(times) - 1)
    trend = ""
    if idx >= 3 and press and press[idx] is not None and press[idx - 3] is not None:
        dp = press[idx] - press[idx - 3]
        trend = "R" if dp > 0.6 else "F" if dp < -0.6 else "S"
    p_hpa = cur.get("pressure_msl")
    pressure = (round(p_hpa, 0) if metric else round(p_hpa * 0.02953, 2)) if p_hpa is not None else None
    vis_m = cur.get("visibility")
    visibility = (round(vis_m / 1000, 1) if metric else round(vis_m / 1609.34, 1)) if vis_m is not None else None
    hours = []
    for i in range(max(0, idx), min(len(times), idx + 25)):
        c = (hourly.get("weather_code") or [0])[i]
        hours.append({"time": times[i], "temp": _r((hourly.get("temperature_2m") or [None])[i]), "code": c,
                      "icon": wmo(c)[2], "pop": (hourly.get("precipitation_probability") or [None])[i],
                      "wind": _r((hourly.get("wind_speed_10m") or [None])[i])})
    days = []
    for i, t in enumerate(daily.get("time") or []):
        if date.fromisoformat(t) < now.date():
            continue
        c = (daily.get("weather_code") or [0])[i]
        L, S, I, P = wmo(c)
        days.append({"date": t, "dow": date.fromisoformat(t).strftime("%a"), "code": c, "text": L, "short": S, "icon": I, "pda_icon": P,
                     "hi": _r(daily["temperature_2m_max"][i]), "lo": _r(daily["temperature_2m_min"][i]),
                     "pop": (daily.get("precipitation_probability_max") or [None] * 99)[i],
                     "precip": (daily.get("precipitation_sum") or [None] * 99)[i],
                     "wind": _r((daily.get("wind_speed_10m_max") or [None] * 99)[i]),
                     "wind_dir": compass((daily.get("wind_direction_10m_dominant") or [None] * 99)[i]),
                     "uv": (daily.get("uv_index_max") or [None] * 99)[i],
                     "sunrise": (daily.get("sunrise") or [""] * 99)[i], "sunset": (daily.get("sunset") or [""] * 99)[i]})
    regional = []
    for pt, r in zip(region_pts or [], region or []):
        rc = r.get("current") or {}
        rd = r.get("daily") or {}
        c = int(rc.get("weather_code") or 0)
        regional.append({"name": pt[0], "lat": pt[1], "lon": pt[2], "dist_km": round(pt[3]), "temp": _r(rc.get("temperature_2m")),
                         "code": c, "short": wmo(c)[1], "icon": wmo(c)[2], "is_day": rc.get("is_day", 1),
                         "wind": _r(rc.get("wind_speed_10m")), "wind_dir": compass(rc.get("wind_direction_10m")),
                         "hi": _r((rd.get("temperature_2m_max") or [None, None])[-1]), "lo": _r((rd.get("temperature_2m_min") or [None, None])[-1]),
                         "tomorrow_icon": wmo((rd.get("weather_code") or [0, 0])[-1])[2]})
    w = {
        "ok": True, "fetched": datetime.now().isoformat(timespec="seconds"), "local_time": now.isoformat(),
        "place": place, "metric": metric, "units": {"temp": "C" if metric else "F", "wind": "km/h" if metric else "mph",
                                                   "pressure": "hPa" if metric else "in", "vis": "km" if metric else "mi",
                                                   "precip": "mm" if metric else "in"},
        "current": {"temp": _r(cur.get("temperature_2m")), "feels": _r(cur.get("apparent_temperature")),
                    "humidity": _r(cur.get("relative_humidity_2m")), "dew": _r(cur.get("dew_point_2m")),
                    "wind": _r(cur.get("wind_speed_10m")), "gust": _r(cur.get("wind_gusts_10m")),
                    "wind_dir": compass(cur.get("wind_direction_10m")), "wind_deg": cur.get("wind_direction_10m"),
                    "pressure": pressure, "trend": trend, "visibility": visibility, "clouds": _r(cur.get("cloud_cover")),
                    "code": code, "text": long, "short": short, "icon": icon, "pda_icon": pda_icon, "is_day": int(cur.get("is_day", 1))},
        "hourly": hours, "daily": days, "regional": regional,
        "moon": moon_phases(now), "moon_age": round(moon_age(now), 1),
    }
    w["narrative"] = narrative(w)
    return w


def _r(x):
    return None if x is None else int(round(float(x)))


def narrative(w: Dict) -> List[Dict]:
    """The scrolling 'Local Forecast' text, in the plain style of a 90s cable forecast."""
    u = w["units"]
    out = []
    days = w["daily"]
    if not days:
        return out
    hr = datetime.fromisoformat(w["local_time"]).hour

    def windtxt(d):
        if d.get("wind") is None:
            return ""
        if d["wind"] < 5:
            return " Winds light and variable."
        return f" {d['wind_dir'] or 'Variable'} wind around {d['wind']} {u['wind']}."

    def poptxt(d):
        p = d.get("pop")
        return f" Chance of precipitation {p} percent." if p and p >= 20 else ""

    d0 = days[0]
    if hr < 15:
        out.append({"title": "Today", "text": f"{d0['text']}. High near {d0['hi']}.{windtxt(d0)}{poptxt(d0)}"})
        out.append({"title": "Tonight", "text": f"{_night(d0['text'])}. Low around {d0['lo']}."})
    else:
        out.append({"title": "Tonight", "text": f"{_night(d0['text'])}. Low around {d0['lo']}.{windtxt(d0)}{poptxt(d0)}"})
    for d in days[1:4]:
        name = datetime.fromisoformat(d["date"]).strftime("%A")
        out.append({"title": name, "text": f"{d['text']}. High near {d['hi']}, low around {d['lo']}.{windtxt(d)}{poptxt(d)}"})
    return out


def _night(text: str) -> str:
    return {"Clear": "Clear skies", "Mostly Clear": "Mostly clear"}.get(text, text)


# ---------------------------------------------------------------- service
class WeatherService:
    def __init__(self, settings, log: Callable[[str], None] = None, on_update: Callable[[Dict], None] = None):
        self.s = settings
        self.log = log or (lambda m: None)
        self.on_update = on_update
        self.data: Dict = {"ok": False, "error": "Not loaded yet"}
        self._lock = threading.Lock()
        self._run = False
        self._kick = threading.Event()

    def start(self):
        if self._run:
            return
        self._run = True
        threading.Thread(target=self._loop, daemon=True, name="weather").start()

    def stop(self):
        self._run = False
        self._kick.set()

    def refresh_now(self):
        self._kick.set()

    def _loop(self):
        while self._run:
            if self.s.get("ts_enabled", True):
                self.update()
            mins = max(5, int(self.s.get("ts_refresh_minutes", 15)))
            self._kick.wait(mins * 60)
            self._kick.clear()

    def place(self) -> Optional[Dict]:
        p = self.s.get("ts_place") or {}
        return p if p.get("lat") is not None else None

    def update(self) -> Dict:
        place = self.place()
        metric = self.s.get("ts_units", "imperial") == "metric"
        if place is None:
            self.data = {"ok": False, "error": "Choose your city in TalonCast settings."}
            return self.data
        try:
            raw = fetch_raw(place["lat"], place["lon"], metric)
            pts = nearby_cities(place["lat"], place["lon"], int(self.s.get("ts_region_count", 7)), place.get("name", ""))
            extra = list(self.s.get("ts_extra_cities") or [])
            for c in extra:
                if c.get("lat") is not None:
                    pts.insert(0, (c["name"], c["lat"], c["lon"], km(place["lat"], place["lon"], c["lat"], c["lon"])))
            try:
                region = fetch_many_current(pts, metric)
            except Exception as e:
                self.log(f"TalonCast: regional weather failed ({e})")
                region, pts = [], []
            w = normalize(raw, place, metric, region, pts)
            with self._lock:
                self.data = w
            self.log(f"TalonCast: {place.get('name')} {w['current']['temp']}{w['units']['temp']} {w['current']['text']}")
        except Exception as e:
            msg = f"Couldn't get the weather ({e})."
            with self._lock:
                if self.data.get("ok"):
                    self.data["stale"] = True
                    self.data["error"] = msg
                else:
                    self.data = {"ok": False, "error": msg}
            self.log("TalonCast: " + msg)
        if self.on_update:
            try:
                self.on_update(self.data)
            except Exception as e:
                self.log(f"TalonCast: PDA update failed ({e})")
        return self.data


# ---------------------------------------------------------------- sample data (tests, and the "demo" weather)
def sample_raw(metric: bool = False, now: Optional[datetime] = None) -> dict:
    now = (now or datetime.now()).replace(second=0, microsecond=0)
    base = now.replace(minute=0) - timedelta(days=1)
    times = [(base + timedelta(hours=i)).isoformat(timespec="minutes") for i in range(24 * 8)]
    f = (lambda c: c) if metric else (lambda c: c * 9 / 5 + 32)
    temps = [round(f(9 + 6 * math.sin((i % 24 - 9) / 24 * 2 * math.pi) + (i // 24) * 0.7), 1) for i in range(len(times))]
    codes = [[0, 1, 2, 3, 61, 2, 0, 71][(i // 24) % 8] for i in range(len(times))]
    days = [(base.date() + timedelta(days=i)).isoformat() for i in range(8)]
    return {
        "current": {"time": now.isoformat(timespec="minutes"), "temperature_2m": f(12.4), "relative_humidity_2m": 64, "apparent_temperature": f(10.9),
                    "is_day": 1 if 7 <= now.hour < 18 else 0, "weather_code": 2, "cloud_cover": 45, "pressure_msl": 1016.2,
                    "wind_speed_10m": 9.0, "wind_direction_10m": 295, "wind_gusts_10m": 18.0, "visibility": 16000, "dew_point_2m": f(5.6), "precipitation": 0},
        "hourly": {"time": times, "temperature_2m": temps, "weather_code": codes,
                   "precipitation_probability": [(i * 7) % 60 for i in range(len(times))],
                   "pressure_msl": [1013 + 0.2 * (i % 24) for i in range(len(times))], "wind_speed_10m": [8 + (i % 5) for i in range(len(times))]},
        "daily": {"time": days, "weather_code": [0, 2, 3, 61, 80, 95, 71, 0],
                  "temperature_2m_max": [f(x) for x in (14, 15, 13, 10, 11, 16, 2, 8)], "temperature_2m_min": [f(x) for x in (5, 6, 4, 3, 2, 9, -3, -1)],
                  "sunrise": [d + "T07:12" for d in days], "sunset": [d + "T18:04" for d in days],
                  "precipitation_probability_max": [0, 10, 20, 70, 60, 80, 90, 5], "precipitation_sum": [0, 0, 0.1, 0.6, 0.3, 0.9, 1.2, 0],
                  "wind_speed_10m_max": [10, 12, 14, 18, 16, 22, 15, 9], "wind_direction_10m_dominant": [290, 270, 250, 200, 180, 220, 330, 300],
                  "uv_index_max": [3, 4, 2, 1, 2, 3, 1, 3]},
    }


def sample(place: Dict = None, metric: bool = False) -> Dict:
    place = place or {"name": "Chicago", "admin1": "Illinois", "country": "United States", "lat": 41.88, "lon": -87.63}
    pts = nearby_cities(place["lat"], place["lon"], 7, place["name"])
    region = []
    for i, p in enumerate(pts):
        region.append({"current": {"temperature_2m": (52 + (i * 7) % 15) if not metric else (11 + i % 6), "weather_code": [0, 2, 3, 61, 1, 45, 71][i % 7],
                                   "wind_speed_10m": 6 + i, "wind_direction_10m": 40 * i, "is_day": 1},
                       "daily": {"weather_code": [2, [0, 2, 3, 61][i % 4]], "temperature_2m_max": [60, 58 + i], "temperature_2m_min": [44, 40 + i]}})
    w = normalize(sample_raw(metric), place, metric, region, pts)
    w["sample"] = True
    return w
