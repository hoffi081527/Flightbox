
import json
import math
import urllib.request
from datetime import datetime, timezone

# Rohrbach bei Eppingen (ungefaehre Ortsmitte)
LAT = 49.14
LON = 8.93
RADIUS_NM = 30

url = f"https://api.adsb.lol/v2/point/{LAT}/{LON}/{RADIUS_NM}"

def entfernung_km(lat, lon):
    r = 6371
    a = math.sin(math.radians(lat - LAT) / 2) ** 2
    a += (
        math.cos(math.radians(LAT))
        * math.cos(math.radians(lat))
        * math.sin(math.radians(lon - LON) / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(a))

request = urllib.request.Request(
    url, headers={"User-Agent": "RohrbachFlightBox/1.0"}
)

with urllib.request.urlopen(request, timeout=20) as response:
    daten = json.load(response)

flugzeuge = []

for flugzeug in daten.get("ac", []):
    lat = flugzeug.get("lat")
    lon = flugzeug.get("lon")

    if lat is None or lon is None:
        continue

    hoehe = flugzeug.get("alt_baro")
    geschwindigkeit = flugzeug.get("gs")

    flugzeuge.append({
        "flug": (flugzeug.get("flight") or "").strip() or "Unbekannt",
        "typ": flugzeug.get("t") or "Unbekannt",
        "entfernung_km": round(entfernung_km(lat, lon), 1),
        "hoehe_m": round(hoehe * 0.3048) if isinstance(hoehe, (int, float)) else None,
        "geschwindigkeit_kmh": round(geschwindigkeit * 1.852) if isinstance(geschwindigkeit, (int, float)) else None,
        "status": "Am Boden" if hoehe == "ground" else "In der Luft"
    })

flugzeuge.sort(key=lambda x: x["entfernung_km"])

ausgabe = {
    "aktualisiert": datetime.now(timezone.utc).isoformat(),
    "flugzeuge": flugzeuge[:6]
}

with open("flights.json", "w", encoding="utf-8") as datei:
    json.dump(ausgabe, datei, ensure_ascii=False, indent=2)

print(f"{len(ausgabe['flugzeuge'])} Flugzeuge gespeichert.")
