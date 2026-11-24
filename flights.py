
import json
import math
import re
import urllib.request
from datetime import datetime, timezone

# Rohrbach bei Eppingen
LAT = 49.14
LON = 8.93
RADIUS_NM = 10.8

FLUG_URL = (
    f"https://api.adsb.lol/v2/point/{LAT}/{LON}/{RADIUS_NM}"
)
ROUTEN_URL = "https://api.adsb.lol/api/0/routeset"
FOTO_URL = "https://api.planespotters.net/pub/photos/hex/"


def entfernung_km(lat, lon):
    r = 6371
    a = math.sin(math.radians(lat - LAT) / 2) ** 2
    a += (
        math.cos(math.radians(LAT))
        * math.cos(math.radians(lat))
        * math.sin(math.radians(lon - LON) / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(a))


def foto_abfragen(hexcode):
    if not re.fullmatch(r"[0-9a-fA-F]{6}", hexcode or ""):
        return "", "", ""

    try:
        request = urllib.request.Request(
            FOTO_URL + hexcode,
            headers={
                "User-Agent": "RohrbachFlightBox/1.0",
                "Accept": "application/json"
            }
        )

        with urllib.request.urlopen(
            request, timeout=15
        ) as response:
            daten = json.load(response)

        fotos = daten.get("photos") or []

        for foto in fotos:
            bild = (
                (foto.get("thumbnail_large") or {}).get("src")
                or (foto.get("thumbnail") or {}).get("src")
                or ""
            )

            fotograf = foto.get("photographer") or ""
            link = foto.get("link") or ""

            if bild.startswith("https://") and link.startswith("https://") and fotograf:
                print("Flugzeugfoto gefunden:", hexcode)
                return bild, fotograf, link

    except Exception as fehler:
        print("Fotoabfrage fehlgeschlagen:", fehler)

    return "", "", ""


def route_abfragen(flugnummer, lat, lon):
    if not flugnummer or flugnummer == "Unbekannt":
        return "Unbekannt", "Unbekannt"

    payload = json.dumps({
        "planes": [{
            "callsign": flugnummer,
            "lat": lat,
            "lng": lon
        }]
    }).encode("utf-8")

    request = urllib.request.Request(
        ROUTEN_URL,
        data=payload,
        headers={
            "User-Agent": "RohrbachFlightBox/1.0",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(
            request, timeout=15
        ) as response:
            antwort = response.read().decode(
                "utf-8", errors="replace"
            )
            print("Routen-HTTP-Status:", response.status)
            print("Routen-Antwort:", repr(antwort[:300]))

            if not antwort.strip():
                return "Unbekannt", "Unbekannt"

            daten = json.loads(antwort)

        if not isinstance(daten, list) or not daten:
            return "Unbekannt", "Unbekannt"

        route = daten[0]

        if not isinstance(route, dict):
            return "Unbekannt", "Unbekannt"

        if route.get("plausible") is False:
            return "Unbekannt", "Unbekannt"

        airports = route.get("_airports") or []

        if len(airports) >= 2:
            start = (
                airports[0].get("location")
                or airports[0].get("iata")
                or "Unbekannt"
            )
            ziel = (
                airports[-1].get("location")
                or airports[-1].get("iata")
                or "Unbekannt"
            )
            return start, ziel

        codes = route.get("_airport_codes_iata") or ""
        teile = codes.split("-")

        if len(teile) >= 2:
            return teile[0], teile[-1]

    except Exception as fehler:
        print("Routenabfrage fehlgeschlagen:", fehler)

    return "Unbekannt", "Unbekannt"


request = urllib.request.Request(
    FLUG_URL,
    headers={"User-Agent": "RohrbachFlightBox/1.0"}
)

with urllib.request.urlopen(
    request, timeout=20
) as response:
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
        "flug": (
            (flugzeug.get("flight") or "").strip()
            or "Unbekannt"
        ),
        "typ": flugzeug.get("t") or "Unbekannt",
        "hex": flugzeug.get("hex") or "",
        "registrierung": flugzeug.get("r") or "",
        "entfernung_km": round(
            entfernung_km(lat, lon), 1
        ),
        "hoehe_m": (
            round(hoehe * 0.3048)
            if isinstance(hoehe, (int, float))
            else None
        ),
        "geschwindigkeit_kmh": (
            round(geschwindigkeit * 1.852)
            if isinstance(geschwindigkeit, (int, float))
            else None
        ),
        "status": (
            "Am Boden"
            if hoehe == "ground"
            else "In der Luft"
        ),
        "start": "Unbekannt",
        "ziel": "Unbekannt",
        "foto": "",
        "fotograf": "",
        "foto_link": "",
        "_lat": lat,
        "_lon": lon
    })

flugzeuge.sort(
    key=lambda x: x["entfernung_km"]
)

flugzeuge = flugzeuge[:6]

# Route und Foto des naechsten Flugzeugs
if flugzeuge:
    naechstes = flugzeuge[0]

    start, ziel = route_abfragen(
        naechstes["flug"],
        naechstes["_lat"],
        naechstes["_lon"]
    )

    naechstes["start"] = start
    naechstes["ziel"] = ziel

    foto, fotograf, foto_link = foto_abfragen(
        naechstes["hex"]
    )

    naechstes["foto"] = foto
    naechstes["fotograf"] = fotograf
    naechstes["foto_link"] = foto_link

# Interne Koordinaten entfernen
for flugzeug in flugzeuge:
    flugzeug.pop("_lat", None)
    flugzeug.pop("_lon", None)

ausgabe = {
    "aktualisiert": datetime.now(
        timezone.utc
    ).isoformat(),
    "flugzeuge": flugzeuge
}

with open(
    "flights.json", "w", encoding="utf-8"
) as datei:
    json.dump(
        ausgabe,
        datei,
        ensure_ascii=False,
        indent=2
    )

print(f"{len(flugzeuge)} Flugzeuge gespeichert.")

if flugzeuge:
    print("Start:", flugzeuge[0]["start"])
    print("Ziel:", flugzeuge[0]["ziel"])
    print("Registrierung:", flugzeuge[0]["registrierung"])
    print("Foto:", flugzeuge[0]["foto"] or "Kein Foto gefunden")

