# Mødrehjælpens Lokalforeninger – Interaktivt Kort

Interaktiv kortvisualisering af alle Mødrehjælpens lokalforeninger i Danmark.

## Filer

| Fil | Beskrivelse |
|-----|-------------|
| `scrape.py` | Scraper – henter data fra moedrehjaelpen.dk og gemmer til `data.json` |
| `data.json` | Scraped og geocoded data (kan redigeres manuelt) |
| `index.html` | Kortvisualisering (ingen byggeprocess – åbn direkte) |

## Sådan serveres kortet lokalt

Kortet bruger `fetch()` til at hente `data.json`, så det kræver en webserver:

```bash
cd /sti/til/mappen
python -m http.server 8000
```

Åbn derefter [http://localhost:8000](http://localhost:8000) i browseren.

## Sådan opdateres data (kør scraperen igen)

Kræver Python 3.10+, `requests`, `beautifulsoup4` og `geopy`:

```bash
pip install requests beautifulsoup4 geopy
python scrape.py
```

Scraperen:
1. Henter listen over lokalforeninger fra `moedrehjaelpen.dk/lokalforeninger`
2. Besøger hver underside og udtrækker navn, adresse, telefon, email og aktiviteter
3. Geocoder hver lokalforening med Nominatim (OpenStreetMap) – 1 sekunds pause mellem kald
4. Gemmer resultatet til `data.json`

## Manuelle rettelser i data.json

`data.json` er et almindeligt JSON-array og kan redigeres direkte. Hvert element har:

```json
{
  "name": "Mødrehjælpen Odense lokalforening",
  "url": "https://moedrehjaelpen.dk/lokalforeninger/odense/",
  "address": "Gade 1, 1234 By",
  "city": "Odense",
  "phone": "12345678",
  "email": "odense@mhj-lokal.dk",
  "lat": 55.3997,
  "lng": 10.3852,
  "activities": ["Babycafé", "Den Rullende Kagemand - fødselsdagshjælp"]
}
```

Hvis du retter en adresse manuelt, skal `lat`/`lng` også opdateres (f.eks. via [nominatim.openstreetmap.org](https://nominatim.openstreetmap.org/)).

## Teknisk stack

- **Scraper**: Python · requests · BeautifulSoup4 · geopy/Nominatim
- **Kort**: Leaflet.js 1.9 (CDN) · CartoDB Positron tiles
- **Design**: Vanilla CSS · Inter (Google Fonts)
- **Ingen byggeprocess** – `index.html` er én selvstændig fil
