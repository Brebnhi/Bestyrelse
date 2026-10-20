#!/usr/bin/env python3
"""Bestyrelsens robot – kører i GitHub Actions i repoet Brebnhi/bestyrelse.

Hvad den gør:
  * Laver de labels, siden bruger, så de altid findes: status (Next up, I gang, Venter, Færdig,
    Droppet), "Bestyrelsen" (opgaven kan alle i bestyrelsen tage) og "møder" (mødedatoerne).
  * Et issue med tabellen fra referatet (Opgave | Ansvarlig | Deadline) bliver til én
    opgave pr. række: deadline i titlen, fx "Book hal (3/10)" eller "Book hal (næste møde)",
    og en @Navn-label pr. ansvarlig. Deadlines som "ASAP", "om 14 dage", "uge 44", "fredag"
    og "inden jul" bliver til en rigtig dato. Robotten skriver en kvittering og lukker
    tabel-issuet.
  * Samler mødedatoerne i issuet "📅 Bestyrelsesmøder". Siden bruger dem til "næste møde"-
    deadlines og til opfølgningen før hvert møde.
  * Får en opgave en ny status-label, fjerner robotten den gamle. "Færdig" lukker
    opgaven, "Droppet" lukker den som droppet.
  * Ved "Run workflow" og når config.js eller robot.py bliver opdateret: rydder op (se ryd_op).

Workflowet (.github/workflows/robot.yml) sørger for, at kun repoets ejer (og
samarbejdspartnere) kan sætte robotten i gang. Mellemmanden (Google Apps Script) bruger
ejerens nøgle, så opgaver oprettet fra siden tæller som ejerens. Scriptet bruger kun
Pythons standardbibliotek.
"""
import calendar
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

API = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
REPO = os.environ.get("GITHUB_REPOSITORY", "Brebnhi/bestyrelse")
TOKEN = os.environ.get("GH_TOKEN", "")
SIDE = os.environ.get("SIDE", "https://brebnhi.github.io/bestyrelse/")
TZ = ZoneInfo("Europe/Copenhagen")
IDAG = datetime.now(TZ).date()

# Status-labels: navn -> (farve, beskrivelse)
STATUS = {
    "Next up": ("1D76DB", "Skal i gang som det næste"),
    "I gang": ("FBCA04", "Nogen arbejder på det"),
    "Venter": ("D4C5F9", "Venter på andre"),
    "Færdig": ("0E8A16", "Sæt den, så lukker robotten opgaven"),
    "Droppet": ("BFBFBF", "Sæt den, så lukker robotten opgaven som droppet"),
}
STATUS_ORD = {  # hvad der kan stå i en Status-kolonne
    "next up": "Next up", "next-up": "Next up", "nextup": "Next up", "næste": "Next up",
    "i gang": "I gang", "igang": "I gang", "i-gang": "I gang", "startet": "I gang",
    "in progress": "I gang", "venter": "Venter", "afventer": "Venter",
    "venter på andre": "Venter", "blokeret": "Venter", "færdig": "Færdig", "done": "Færdig",
    "afsluttet": "Færdig", "løst": "Færdig", "droppet": "Droppet", "annulleret": "Droppet",
}
IMPORT_LABEL = ("import", "EDEDED", "Tabel fra et møde – robotten har lavet opgaverne")
PULJE_LABEL = ("Bestyrelsen", "FBE7A1", "Kan alle i bestyrelsen tage – tryk 'Jeg tager den' på siden")
MOEDE_LABEL = ("møder", "C2E0C6", "Datoerne for bestyrelsesmøderne – siden og robotten læser dem herfra")
MOEDE_TITEL = "📅 Bestyrelsesmøder"
LOG_MAERKE = "**Opdateringer**"          # herefter står logbogen, som mellemmanden skriver
PERSONFARVE = "C5DEF5"
ALLE = {"alle", "bestyrelsen", "hele bestyrelsen", "fælles", "alle i bestyrelsen"}
EMNE_BESKRIVELSE = "Emne – sat af robotten ud fra teksten. Ret gerne."
ASAP_DAGE = 7                             # standard – kan rettes i config.js (asapDage)

# Bestyrelsen står i config.js (samme fil, som siden læser). Den her liste bruges kun, hvis
# config.js mangler eller ikke kan læses.
STANDARD_MEDLEMMER = [
    {"navn": "Søren", "rolle": "formand", "emner": ["Forening & bestyrelse"]},
    {"navn": "Heidi", "rolle": "sponsoransvarlig", "emner": ["Sponsorer & fonde"]},
    {"navn": "Anna", "rolle": "ungdomsansvarlig", "emner": ["Ungdom"]},
    {"navn": "Emma", "rolle": "tøj- og materialeansvarlig", "emner": ["Tøj & udstyr"]},
    {"navn": "Ida", "rolle": "festansvarlig", "emner": ["Arrangementer & frivillige"]},
    {"navn": "Sonja", "rolle": "", "emner": []},
    {"navn": "Mikkel", "rolle": "kasserer", "emner": ["Økonomi"]},
    {"navn": "Lars", "rolle": "kasserer", "emner": ["Økonomi"]},
    {"navn": "Marcel", "rolle": "kredsansvarlig", "emner": ["Hold & turneringer"]},
]
MDR = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "maj": 5, "jun": 6,
       "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12}
UGEDAG = ["man", "tir", "ons", "tor", "fre", "lør", "søn"]
HJAELP_MAERKE = "<!-- robot:hjaelp -->"

HJAELP = HJAELP_MAERKE + """
🤔 Jeg kunne ikke finde nogen opgaver i det her issue.

Kopiér tabellen fra referatet i Google Docs og sæt den ind med **Ctrl+V** (ikke Ctrl+Shift+V) –
så laver GitHub den om til en tabel. Den skal have kolonnerne *Opgave*, *Person* (eller
*Ansvarlig*) og *Deadline* (overskrifterne må gerne mangle, så læser jeg dem i den rækkefølge).
Du kan også skrive én opgave pr. linje:

```
Book hal til opstartsfest – Søren – 3/10
Ring til sponsorerne – Emma og Jonas – inden næste møde
```

Ret issuet (**Edit**), så prøver jeg igen."""


# ----------------------------------------------------------------------------- GitHub
def kald(metode, sti, data=None, forsoeg=3):
    """Kalder GitHubs API og returnerer (json, headers)."""
    url = sti if sti.startswith("http") else f"{API}/repos/{REPO}{sti}"
    krop = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=krop, method=metode, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "bestyrelsens-robot",
    })
    if krop is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raa = r.read()
            return (json.loads(raa) if raa else None), r.headers
    except urllib.error.HTTPError as e:
        tekst = e.read().decode(errors="replace")[:400]
        if e.code in (403, 429, 500, 502, 503) and forsoeg > 1:
            # GitHubs grænse for mange oprettelser i træk, eller en midlertidig fejl
            time.sleep(min(int(e.headers.get("Retry-After") or 10), 60))
            return kald(metode, sti, data, forsoeg - 1)
        raise ApiFejl(e.code, f"{metode} {sti} gav {e.code}: {tekst}") from None


class ApiFejl(Exception):
    def __init__(self, kode, besked):
        super().__init__(besked)
        self.kode = kode


def hent_alle(sti):
    ud = []
    while sti:
        data, h = kald("GET", sti)
        ud.extend(data or [])
        m = re.search(r'<([^>]+)>;\s*rel="next"', h.get("Link") or "")
        sti = m.group(1) if m else None
    return ud


def hent_labels():
    return {l["name"].lower(): l["name"] for l in hent_alle("/labels?per_page=100")}


def sikr_label(navn, farve, beskrivelse, kendte):
    """Returnerer labelens præcise navn og opretter den, hvis den mangler."""
    if navn.lower() in kendte:
        return kendte[navn.lower()]
    try:
        kald("POST", "/labels", {"name": navn, "color": farve, "description": beskrivelse})
        print(f"Label oprettet: {navn}")
    except ApiFejl as e:
        if e.kode != 422:  # 422 = findes allerede
            raise
    kendte[navn.lower()] = navn
    return navn


def kommenter(nr, tekst):
    kald("POST", f"/issues/{nr}/comments", {"body": tekst})


def fjern_label(nr, navn):
    try:
        kald("DELETE", f"/issues/{nr}/labels/{urllib.parse.quote(navn, safe='')}")
    except ApiFejl as e:
        if e.kode != 404:
            raise


def dato_fra_tid(stempel):
    """'2026-09-23T19:12:00Z' -> datoen i Danmark."""
    try:
        return datetime.fromisoformat(str(stempel).replace("Z", "+00:00")).astimezone(TZ).date()
    except (TypeError, ValueError):
        return IDAG


# ----------------------------------------------------------------------------- datoer
def lav_dato(d, m, aar, ref):
    """Dato uden årstal = nærmeste fremad (datoer mere end 60 dage tilbage er næste år)."""
    if not (1 <= m <= 12 and 1 <= d <= 31):
        return None
    if aar is not None and aar < 100:
        aar += 2000
    if aar is None:
        aar = ref.year
        try:
            if date(aar, m, d) < ref - timedelta(days=60):
                aar += 1
        except ValueError:
            return None
    try:
        return date(aar, m, d)
    except ValueError:
        return None


def find_dato(tekst, ref=None):
    """Finder en dato i teksten: 3/10 · 3/10-26 · 3.10.2026 · 2026-10-03 · 3. okt · fre d. 3/10."""
    ref = ref or IDAG
    s = tekst.lower()
    m = re.search(r"(?<!\d)(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)", s)
    if m:
        return lav_dato(int(m[3]), int(m[2]), int(m[1]), ref)
    m = re.search(r"(?<![\d/.])(\d{1,2})\s*[/.]\s*(\d{1,2})(?:\s*[/.\-]\s*(\d{4}|\d{2}))?(?!\d)", s)
    if m:
        return lav_dato(int(m[1]), int(m[2]), int(m[3]) if m[3] else None, ref)
    m = re.search(r"(?<!\d)(\d{1,2})\.?\s*(jan|feb|mar|apr|maj|jun|jul|aug|sep|okt|nov|dec)"
                  r"[a-zæøå]*\.?(?:\s+(\d{4}))?", s)
    if m:
        return lav_dato(int(m[1]), MDR[m[2]], int(m[3]) if m[3] else None, ref)
    return None


def kort_dato(d):
    return f"{UGEDAG[d.weekday()]} {d.day}/{d.month}" + ("" if d.year == IDAG.year else f"-{str(d.year)[2:]}")


def fuld_dato(d):
    return f"{d.day}/{d.month}-{d.year}"


# ------------------------------------------------- deadlines skrevet med ord ("ASAP", "uge 44" …)
NAESTE_MOEDE = re.compile(r"(næste|kommende|førstkommende)\s+(bestyrelses)?møde|^\s*n\.?\s?m\.?\s*$|"
                          r"næste\s+gang\s+vi\s+ses|til\s+mødet", re.I)
ASAP = re.compile(r"(?<![a-zæøå])(asap|a\.s\.a\.p\.?|hurtigst|snarest|straks|med\s+det\s+samme|"
                  r"omgående|akut|hurtigt\s+muligt|haster)(?![a-zæøå])", re.I)
INGEN = {"", "-", "—", "–", "?", "??", "x", "tbd", "ingen", "ingen deadline", "n/a", "na", "intet"}
FORAN = ("senest", "allersenest", "inden", "før", "foer", "til", "på", "pa", "d.", "den", "deadline",
         "frist", "ca.", "ca", "cirka", "omkring", "helst", "gerne", "allerhelst", "deadline:", "frist:")
TAL = {"en": 1, "én": 1, "et": 1, "ét": 1, "to": 2, "tre": 3, "fire": 4, "fem": 5, "seks": 6,
       "syv": 7, "otte": 8, "ni": 9, "ti": 10, "elleve": 11, "tolv": 12, "fjorten": 14,
       "et par": 2, "par": 2, "nogle": 3, "et": 1}
UGEDAGE = {"mandag": 0, "tirsdag": 1, "onsdag": 2, "torsdag": 3, "fredag": 4, "lørdag": 5, "søndag": 6}
UGEDAG_KORT = {"man": 0, "tir": 1, "tirs": 1, "ons": 2, "tor": 3, "tors": 3, "fre": 4, "lør": 5, "søn": 6}
MAANEDER = {"januar": 1, "jan": 1, "februar": 2, "feb": 2, "marts": 3, "mar": 3, "april": 4, "apr": 4,
            "maj": 5, "juni": 6, "jun": 6, "juli": 7, "august": 8, "aug": 8, "september": 9, "sep": 9,
            "sept": 9, "oktober": 10, "okt": 10, "november": 11, "nov": 11, "december": 12, "dec": 12}
# Ord, der ikke er en dato, men som gerne må stå som deadline i parentes, fx "Opdater hjemmesiden (løbende)"
FRIST_ORD = re.compile(r"^(løbende|efter behov|hele sæsonen|sæsonen|fast|kontinuerligt|altid|ved lejlighed|"
                       r"når muligt|når der er tid|ongoing|løbende opgave|hver uge|hver måned|ugentligt|"
                       r"månedligt|årligt|hvert år|næste sæson|inden sæsonstart|sæsonstart|efter jul|efter nytår|"
                       r"generalforsamlingen|inden generalforsamlingen)$", re.I)


class Frist:
    """En deadline læst fra referatet. slags: 'dato', 'moede' (næste møde), 'tekst' eller None."""
    __slots__ = ("slags", "dato", "tekst", "forklaring")

    def __init__(self, slags=None, dato=None, tekst=None, forklaring=None):
        self.slags, self.dato, self.tekst, self.forklaring = slags, dato, tekst, forklaring

    def __repr__(self):
        return f"Frist({self.slags!r}, {self.dato!r}, {self.tekst!r}, {self.forklaring!r})"


def soendag(d):
    return d + timedelta(days=6 - d.weekday())


def mandag(d):
    return d - timedelta(days=d.weekday())


def sidste_dag(aar, md):
    return date(aar, md, calendar.monthrange(aar, md)[1])


def fremad(lav, ref):
    """Kalder lav(år) og vælger det år, der giver en dato tidligst 60 dage før ref (som lav_dato)."""
    d = lav(ref.year)
    if d is not None and d < ref - timedelta(days=60):
        d = lav(ref.year + 1)
    return d


def paaske(aar):
    """Påskedag (gregoriansk, 'anonymous'-algoritmen)."""
    a, b, c = aar % 19, aar // 100, aar % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    md = (h + l - 7 * m + 114) // 31
    dag = ((h + l - 7 * m + 114) % 31) + 1
    return date(aar, md, dag)


def iso_soendag(aar, uge):
    try:
        return date.fromisocalendar(aar, uge, 7)
    except ValueError:
        return None


def antal(ord_):
    ord_ = ord_.strip()
    if ord_.isdigit():
        return int(ord_)
    return TAL.get(ord_)


def tolk_frist(celle, ref, asap_dage=ASAP_DAGE, idag=None):
    """Læser en deadline-celle. ref = datoen for mødet (relative ord regnes fra den).

    Returnerer en Frist. Eksempler (mødet var tirsdag 22/9-2026):
      "3/10" -> 3/10 · "næste møde" / "inden næste møde" / "NM" -> næste møde (følger mødedatoerne)
      "ASAP" / "hurtigst muligt" -> mødet + asap_dage (dog tidligst om 2 dage)
      "i morgen" -> 23/9 · "om 14 dage" -> 6/10 · "denne uge" -> søn 27/9 · "næste uge" -> søn 4/10
      "uge 44" -> søn 1/11 · "inden uge 44" -> søn 25/10 · "fredag" -> 25/9 · "inden fredag" -> 24/9
      "i oktober" / "ultimo oktober" -> 31/10 · "primo november" -> 7/11 · "medio november" -> 15/11
      "inden oktober" -> 30/9 · "inden jul" -> 23/12 · "løbende" -> tekst
    """
    idag = idag or IDAG
    raa = re.sub(r"\s+", " ", str(celle or "").replace("\xa0", " ")).strip()
    s = raa.lower().strip(" .,;:!")
    s = re.sub(r"(?<![a-zæøå])inden\s+for(?![a-zæøå])", "indenfor", s)   # "inden for 14 dage" ≠ "inden"
    if s in INGEN:
        return Frist()
    if NAESTE_MOEDE.search(s):
        return Frist("moede", forklaring=raa)
    d = find_dato(s, ref)
    if d:
        return Frist("dato", d)
    if ASAP.search(s) or s in ("nu", "hurtigt", "hurtig", "snart"):
        d = max(ref + timedelta(days=asap_dage), idag + timedelta(days=2))
        return Frist("dato", d, forklaring=raa)

    # Fjern fyldord foran ("senest", "inden", "til" …) og husk, om der stod "inden"/"før"
    k, foer = s, False
    while True:
        dele = k.split(" ", 1)
        if len(dele) == 2 and dele[0] in FORAN:
            foer = foer or dele[0] in ("inden", "før", "foer")
            k = dele[1].strip()
            continue
        break

    d = _relativ(k, foer, ref)
    if d:
        return Frist("dato", d, forklaring=raa)
    return Frist("tekst", tekst=raa[:40])         # fx "løbende" – står i parentes efter opgaven


def _relativ(k, foer, ref):
    """Hjælper til tolk_frist: k er teksten uden fyldord foran, foer = der stod "inden"/"før"."""
    # i dag / i morgen / i overmorgen
    if k in ("i dag", "idag", "i aften", "iaften", "i eftermiddag", "i formiddag", "dags dato", "today"):
        return ref
    if k in ("i morgen", "imorgen", "morgen", "tomorrow"):
        return ref + timedelta(days=1)
    if k in ("i overmorgen", "overmorgen"):
        return ref + timedelta(days=2)

    # om 14 dage / om en uge / inden for to uger / om et par dage / 3 uger
    m = re.match(r"^(?:om|inden\s+for|indenfor|i\s+løbet\s+af|within|in)?\s*(\d+|[a-zæøå]+(?:\s+par)?)\s+"
                 r"(dag|dage|døgn|uge|uger|måned|måneder|mdr\.?|md\.?)$", k)
    if m:
        n = antal(m[1])
        if n is not None and 0 < n <= 400:
            enhed = m[2]
            if enhed.startswith(("dag", "døgn")):
                dage = 3 if m[1] in ("et par", "par") else 4 if m[1] == "nogle" else n
                return ref + timedelta(days=dage)
            if enhed.startswith("uge"):
                return ref + timedelta(days=7 * n)
            md = ref.month - 1 + n
            aar, md = ref.year + md // 12, md % 12 + 1
            return date(aar, md, min(ref.day, calendar.monthrange(aar, md)[1]))

    # uger
    if k in ("denne uge", "i denne uge", "i ugen", "ugen ud", "i løbet af ugen", "this week", "ugen"):
        return soendag(ref)
    if k in ("weekenden", "weekend", "i weekenden", "i weekend", "weekenden over", "til weekenden"):
        if foer:  # "inden weekenden" = senest fredag
            return ref if ref.weekday() == 4 else ref + timedelta(days=(4 - ref.weekday()) % 7)
        return soendag(ref)
    if k in ("næste uge", "i næste uge", "next week", "slutningen af næste uge", "slut næste uge",
             "sidst i næste uge", "ultimo næste uge", "i løbet af næste uge"):
        return soendag(ref) if foer else soendag(ref) + timedelta(days=7)
    if re.match(r"^(start|starten|begyndelsen|primo|først|i starten|i begyndelsen)( af| i)? næste uge$", k):
        return mandag(ref) + timedelta(days=8)  # tirsdag i næste uge
    m = re.match(r"^(?:i\s+)?uge\s*(\d{1,2})(?:\s*[-/ ]\s*(\d{2}|\d{4}))?$", k)
    if m:
        uge = int(m[1])
        if foer:
            uge -= 1
        if m[2]:
            aar = int(m[2]) + (2000 if len(m[2]) == 2 else 0)
            return iso_soendag(aar, uge) if uge >= 1 else iso_soendag(aar - 1, 52)
        return fremad(lambda aar: iso_soendag(aar, uge) if uge >= 1 else iso_soendag(aar - 1, 52), ref)

    # ugedage: "fredag", "på fredag", "næste fredag", "fredag i næste uge", "fre"
    m = re.match(r"^(?:næste\s+|kommende\s+|på\s+)?(mandag|tirsdag|onsdag|torsdag|fredag|lørdag|søndag)"
                 r"(?:en)?(?:\s+i\s+(denne|næste)\s+uge)?$", k)
    dag = None
    if m:
        dag, uge = UGEDAGE[m[1]], m[2]
    elif k in UGEDAG_KORT:
        dag, uge = UGEDAG_KORT[k], None
    if dag is not None:
        if uge == "næste":
            d = mandag(ref) + timedelta(days=7 + dag)
        elif uge == "denne":
            d = mandag(ref) + timedelta(days=dag)
            if d <= ref:
                d += timedelta(days=7)
        else:
            d = ref + timedelta(days=(dag - ref.weekday()) % 7 or 7)
        return d - timedelta(days=1) if foer else d

    # måneder: "oktober", "i oktober", "ultimo oktober", "primo november", "medio nov", "inden oktober"
    m = re.match(r"^(?:(primo|start|starten af|først i|begyndelsen af|i begyndelsen af|i starten af)|"
                 r"(medio|midt i|midten af|i midten af|midt)|"
                 r"(ultimo|slut|slutningen af|i slutningen af|sidst i|udgangen af|i udgangen af|"
                 r"i løbet af|i))?\s*(januar|februar|marts|april|maj|juni|juli|august|september|oktober|"
                 r"november|december|jan|feb|mar|apr|jun|aug|sept|sep|okt|nov|dec)\.?(?:\s+(\d{4}))?$", k)
    if m:
        md = MAANEDER[m[4]]
        if foer and not (m[1] or m[2]):            # "inden oktober" = sidste dag i september
            lav = (lambda aar: sidste_dag(aar - 1, 12) if md == 1 else sidste_dag(aar, md - 1))
        elif m[1]:
            lav = (lambda aar: date(aar, md, 7))
        elif m[2]:
            lav = (lambda aar: date(aar, md, 15))
        else:
            lav = (lambda aar: sidste_dag(aar, md))
        return lav(int(m[5])) if m[5] else fremad(lav, ref)
    if k in ("denne måned", "i denne måned", "måneden ud", "i løbet af måneden"):
        return sidste_dag(ref.year, ref.month)
    if k in ("næste måned", "i næste måned", "i løbet af næste måned"):
        if foer:
            return sidste_dag(ref.year, ref.month)
        aar, md = (ref.year + 1, 1) if ref.month == 12 else (ref.year, ref.month + 1)
        return sidste_dag(aar, md)
    if re.match(r"^(start|starten|begyndelsen|primo|først)( af| i)? næste måned$", k):
        aar, md = (ref.year + 1, 1) if ref.month == 12 else (ref.year, ref.month + 1)
        return date(aar, md, 7)

    # højtider og ferier
    if k in ("jul", "julen", "juleferien", "jul og nytår", "juleaften", "december og jul", "i jul", "i julen",
             "i juleferien"):
        return fremad(lambda aar: date(aar, 12, 23), ref)
    if k in ("nytår", "nytåret", "årsskiftet", "udgangen af året", "slutningen af året", "året ud",
             "slut året", "årets udgang", "nytårsaften"):
        return fremad(lambda aar: date(aar, 12, 30 if foer else 31), ref)
    if k in ("sommerferien", "sommerferie", "sommer", "sommerpausen", "sommeren"):
        return fremad(lambda aar: date(aar, 6, 30), ref)
    if k in ("påske", "påsken", "påskeferien"):
        return fremad(lambda aar: paaske(aar) - timedelta(days=4), ref)
    if k in ("efterårsferien", "efterårsferie"):
        return fremad(lambda aar: iso_soendag(aar, 41 if foer else 42), ref)
    if k in ("vinterferien", "vinterferie"):
        return fremad(lambda aar: iso_soendag(aar, 6 if foer else 7), ref)
    return None


# ----------------------------------------------------------------------------- tabeller
SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")


def rens(celle, linjer=False):
    c = celle.replace("\\|", "|")
    c = re.sub(r"<br\s*/?>", "\n", c, flags=re.I)
    c = re.sub(r"<[^>]+>", "", c)
    c = re.sub(r"\[([^\]]*)\]\(([^)]*)\)", r"\1", c)          # [tekst](link) -> tekst
    c = re.sub(r"(\*\*|__|~~)", "", c)
    c = re.sub(r"(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])", r"\1", c)  # *kursiv*
    c = html.unescape(c).replace("\xa0", " ")
    if linjer:
        return "\n".join(re.sub(r"[ \t]+", " ", l).strip() for l in c.split("\n")).strip()
    return re.sub(r"\s+", " ", c).strip()


def md_celler(linje):
    s = linje.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    return re.split(r"(?<!\\)\|", s)


def find_tabeller(tekst):
    """Markdown-tabeller (som GitHub laver, når man indsætter en tabel) og tabulator-tabeller."""
    linjer = tekst.replace("\r", "").split("\n")
    tabeller, brugt, i = [], set(), 0
    while i < len(linjer) - 1:
        if "|" in linjer[i] and SEP.match(linjer[i + 1]):
            raekker = [md_celler(linjer[i])]
            brugt.update({i, i + 1})
            j = i + 2
            while j < len(linjer) and "|" in linjer[j] and linjer[j].strip():
                raekker.append(md_celler(linjer[j]))
                brugt.add(j)
                j += 1
            tabeller.append(raekker)
            i = j
        else:
            i += 1
    # Tabel uden skillelinje: flere linjer i træk, der starter med |
    blok = []
    for n, l in enumerate(linjer + [""]):
        if n not in brugt and l.strip().startswith("|") and l.count("|") >= 2:
            blok.append(md_celler(l))
        else:
            if len(blok) >= 2:
                tabeller.append(blok)
            blok = []
    # Tabulator-adskilt (fx indsat som ren tekst fra et regneark)
    blok = []
    for l in linjer + [""]:
        if "\t" in l and l.strip():
            blok.append(l.split("\t"))
        else:
            if len(blok) >= 1 and any(len(r) >= 2 for r in blok):
                tabeller.append(blok)
            blok = []
    return tabeller


ROLLER = [  # (rolle, mønster) – første match vinder for hver kolonne
    ("opgave", re.compile(r"^(opgave|opgaver|to ?-?do|handling|action)", re.I)),
    ("person", re.compile(r"(ansvarlig|hvem|person|navn|tovholder|ejer)", re.I)),
    ("deadline", re.compile(r"(deadline|frist|dato|hvornår|senest|tidspunkt)", re.I)),
    ("status", re.compile(r"^status", re.I)),
    ("noter", re.compile(r"(note|kommentar|bemærk|detalje)", re.I)),
    ("opgave2", re.compile(r"(punkt|hvad|beskrivelse|emne|aktivitet|opgave)", re.I)),
]


def kortlaeg(overskrift):
    """Finder ud af, hvilken kolonne der er hvad. Returnerer {rolle: indeks} eller None."""
    roller = {}
    for idx, celle in enumerate(overskrift):
        tekst = rens(celle)
        if not tekst or len(tekst) > 30:
            continue
        for rolle, moenster in ROLLER:
            if moenster.search(tekst) and rolle not in roller:
                roller[rolle] = idx
                break
    if "opgave" not in roller and "opgave2" in roller:
        roller["opgave"] = roller.pop("opgave2")
    roller.pop("opgave2", None)
    if "opgave" in roller and ("person" in roller or "deadline" in roller):
        return roller
    return None


def standard_roller(antal_):
    navne = ["opgave", "person", "deadline", "status"]
    return {navne[i]: i for i in range(min(antal_, 4))}


# ----------------------------------------------------------------------------- bestyrelsen
def js_til_json(s):
    """config.js er skrevet som et JavaScript-objekt. Gør det til JSON: fjerner kommentarer og
    kommaer til sidst og sætter anførselstegn om nøgler uden."""
    ud, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c in "\"'":
            j, buf = i + 1, []
            while j < n and s[j] != c:
                if s[j] == "\\" and j + 1 < n:
                    buf.append(s[j:j + 2])
                    j += 2
                    continue
                buf.append(s[j])
                j += 1
            tekst = "".join(buf)
            if c == "'":
                tekst = tekst.replace("\\'", "'").replace('"', '\\"')
            ud.append('"' + tekst + '"')
            i = j + 1
            continue
        if s.startswith("//", i):
            j = s.find("\n", i)
            i = n if j < 0 else j
            continue
        if s.startswith("/*", i):
            j = s.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        m = re.match(r"[A-Za-z_$][\w$]*", s[i:])
        if m and re.match(r"\s*:", s[i + m.end():]) and (not ud or not re.match(r"[\w$]", ud[-1][-1:])):
            ud.append('"' + m.group(0) + '"')
            i += m.end()
            continue
        ud.append(c)
        i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(ud))


def laes_konfig(sti=None):
    """{"medlemmer": [{navn, rolle, emner}], "asap_dage": 7} fra config.js."""
    sti = sti or os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.js")
    konfig = {"medlemmer": [dict(m) for m in STANDARD_MEDLEMMER], "asap_dage": ASAP_DAGE}
    try:
        tekst = open(sti, encoding="utf-8").read()
        start = tekst.index("{", re.search(r"window\.BESTYRELSE\s*=", tekst).end())
        data = json.loads(js_til_json(tekst[start:tekst.rindex("}") + 1]))
    except Exception as e:  # noqa: BLE001
        print(f"Kunne ikke læse config.js ({e}) – bruger standardlisten.")
        return konfig
    ud = []
    for m in data.get("medlemmer") or []:
        navn = str(m.get("navn") if isinstance(m, dict) else m or "").strip()
        if navn:
            ud.append({"navn": navn, "rolle": str((m.get("rolle") if isinstance(m, dict) else "") or "").strip(),
                       "emner": [str(e) for e in ((m.get("emner") if isinstance(m, dict) else None) or [])]})
    if ud:
        konfig["medlemmer"] = ud
    else:
        print("config.js har ingen medlemmer – bruger standardlisten.")
    try:
        a = int(data.get("asapDage"))
        if 1 <= a <= 60:
            konfig["asap_dage"] = a
    except (TypeError, ValueError):
        pass
    return konfig


def laes_bestyrelsen(sti=None):
    """[{navn, rolle, emner}] fra config.js – kun de her kan få opgaver."""
    return laes_konfig(sti)["medlemmer"]


def lav_navn(s):
    return re.sub(r"\s+", " ", re.sub(r"[^\wæøåÆØÅ ]+", " ", str(s).lower())).strip()


def find_medlem(navn, medlemmer):
    """(navne, via_rolle). 'Marcel D' -> Marcel, 'kasserer Lars' -> Lars, 'Kassererne' -> Mikkel og Lars."""
    n = lav_navn(navn)
    if not n:
        return [], False
    foerste = n.split()[0]
    for m in medlemmer:
        mn = lav_navn(m["navn"])
        if n == mn or foerste == mn.split()[0]:
            return [m["navn"]], False
    navngivne = [m["navn"] for m in medlemmer if navn_i(lav_navn(m["navn"]), n)]
    if navngivne:
        return navngivne, False
    ramt = []
    for m in medlemmer:
        stamme = (lav_navn(m.get("rolle") or "").split() or [""])[0]
        if len(stamme) >= 5 and n.startswith(stamme):
            ramt.append(m["navn"])
    return ramt, bool(ramt)


def klassificer(navne, medlemmer):
    """['Kassererne', 'Herre 1', 'Alle'] -> (['Mikkel', 'Lars'], ['Herre 1'], True)"""
    bestyrelse, andre, alle = [], [], False
    for n in navne:
        if n == "Alle" or n.lower() in ALLE:
            alle = True
            continue
        fundet, _ = find_medlem(n, medlemmer)
        if fundet:
            bestyrelse += [f for f in fundet if f not in bestyrelse]
        elif n.lower() not in [a.lower() for a in andre]:
            andre.append(n)
    return bestyrelse, andre, alle


def og_liste(navne):
    navne = list(navne)
    return navne[0] if len(navne) == 1 else ", ".join(navne[:-1]) + " og " + navne[-1]


def navn_i(navn, tekst):
    return re.search(r"(?<![\wæøå])" + re.escape(navn.lower()) + r"(?![\wæøå])", tekst.lower()) is not None


def er_pulje_label(navn):
    """'Bestyrelsen' (og de gamle '@Alle'/'@Bestyrelsen') = opgaven kan alle tage."""
    n = str(navn).strip().lower().lstrip("@").strip()
    return n in ALLE


# ----------------------------------------------------------------------------- emner
# Samme regler som på siden (index.html). Ord: tekst tæller 1 (højst 2 gange), "~ord" tæller ½,
# ("re", mønster[, vægt]) er et regulært udtryk. Det tidligste ord i teksten giver ekstra 0,3 point.
GRAENSE_FOER = r"(?:^|[^a-z0-9æøåéü])"
GRAENSE_EFTER = r"(?=[^a-z0-9æøåéü]|$)"


class Emne:
    def __init__(self, navn, farve, ord_, personer=()):
        self.navn, self.farve = navn, farve
        self.regler = []
        for o in ord_:
            if isinstance(o, tuple):
                kilde = o[1]
                if kilde.startswith(r"\b"):
                    kilde = GRAENSE_FOER + kilde[2:]
                if kilde.endswith(r"\b"):
                    kilde = kilde[:-2] + GRAENSE_EFTER
                self.regler.append((re.compile(kilde), o[2] if len(o) > 2 else 1.0))
            elif o.startswith("~"):
                self.regler.append((re.compile(re.escape(o[1:])), 0.5))
            else:
                self.regler.append((re.compile(re.escape(o)), 1.0))
        self.personer = [re.compile(p) for p in personer]


EMNER = [
    Emne("Økonomi", "F6E3A1", ["økonomi", "kontingent", "betal", "faktura", "regnskab", "budget", "refusion",
                               "mobilepay", "kasserer", "gæld", "penge", "takst", "udlæg", "indbetal", "opkræv",
                               "bankkonto", "beløb", "~pris", "~gebyr", "tilskud", "moms", "løn"],
         personer=[r"^kasserer(en|ne|e)?$"]),
    Emne("Sponsorer & fonde", "C9E7D3", ["sponsor", "fond", "ansøgning", "bambusa", "kampagne", "donation",
                                         "partner", "~støtte", "lodseddel", "lotteri"]),
    Emne("Hold & turneringer", "CFE0F7", ["jyllandsserie", "turnering", "licens", "kredskontakt", "melde fra",
                                          "kampprogram", "~serie", "division", "liga", "pokal", ("re", r"\bmix\b"),
                                          "holdtilmeld", "~tilmeld", "spillere", ("re", r"\bspiller\b", 0.5),
                                          "dobbelt klub", "klubskifte", ("re", r"\b(dame|herre)\s?\d\b", 0.5)]),
    Emne("Trænere & kurser", "E2D7F5", ["træner", "trænerhjælp", "kursus", "kurset", "kurser",
                                        ("re", r"\bdommer(e|ne|kursus|kurser|uddannelse)?\b"), "uddannelse", "dt-",
                                        "instruktør", "nødløsning"]),
    Emne("Ungdom", "FAD9C8", ["ungdom", ("re", r"\b[dhu]?u1\d\b"), "børn", "skoleforløb", "skole", "kickprojekt",
                              "forælder", "forældre", "boldlanger", "junior"]),
    Emne("Arrangementer & frivillige", "F7D0E1", ["fest", "julefrokost", "arrangement", "baren", ("re", r"\bbar\b"),
                                                  "indkøb", "speaker", "hjemmekamp", "tjans", "frivillig",
                                                  "stævneleder", "~stævne", "event", "afslutning", "reception",
                                                  "jubilæum"]),
    Emne("Tøj & udstyr", "D3EDF0", ["tøj", "trøje", "trøjen", "tryk", "merchandise", "udstyr", ("re", r"\bbolde?\b"),
                                    ("re", r"\bnet(tet)?\b"), "hæverkurv", "dommerstol", "flyttekasse", "materiel",
                                    "rekvisit"]),
    Emne("Kommunikation", "ECE6D3", ["hjemmeside", "facebook", "instagram", "nyhedsbrev", "presse", "interview",
                                     "dk4", ("re", r"\btv\b"), "volley-tv", "medie", "billede", "holdbeskrivelse",
                                     "plakat", "annonce", "~opslag", "~chat", "~gruppebesked", "~manus",
                                     ("re", r"\bsome\b"), "sociale medier"]),
    Emne("Haller & lokaler", "DCE3EA", [("re", r"\bhal(len|ler|lerne|tid|tider)?\b"), "haltid", "nøgle", "klubhus",
                                        "lokale", ("re", r"\brum(met)?\b"), "brik", "katedral", "computer", "~låne",
                                        "lån af", "omklædning", "depot", ("re", r"\bskab(e|et)?\b")]),
    Emne("Forening & bestyrelse", "E5E7EB", ["generalforsamling", "bestyrelse", "ordstyrer", "vedtægt", "referat",
                                             "kommune", "forening", "forbund", "medlem", "gældsbrev", "underskrift",
                                             "kontrakt", "~aftale", "strategi", "~næste sæson", "~dokument",
                                             "forsikring", "gdpr"]),
]
ANDET = Emne("Andet", "EEEEEE", [])


def gaet_emne(tekst, personer=()):
    t = " " + re.sub(r"\s+", " ", str(tekst or "").lower()) + " "
    point = [0.0] * len(EMNER)
    tidligst, tidligst_i = None, -1
    for i, e in enumerate(EMNER):
        for regel, vaegt in e.regler:
            n = 0
            for m in regel.finditer(t):
                n += 1
                if tidligst is None or m.start() < tidligst:
                    tidligst, tidligst_i = m.start(), i
                if n >= 2:
                    break
            point[i] += n * vaegt
        for navn in personer or []:
            nv = str(navn).lower().strip()
            if any(p.search(nv) for p in e.personer):
                point[i] += 1
    if tidligst_i >= 0:
        point[tidligst_i] += 0.3
    bedst, maks = -1, 0.0
    for i, p in enumerate(point):
        if p > maks + 1e-9:
            bedst, maks = i, p
    return EMNER[bedst] if bedst >= 0 else ANDET


def norm_emne(s):
    s = re.sub(r"^\s*(emne|kategori)\s*:\s*", "", str(s).lower())
    s = re.sub(r"\bog\b", "&", s)
    s = re.sub(r"[^\wæøå&]+", " ", s)
    return re.sub(r"\s*&\s*", " & ", s).strip()


def find_emne(navn):
    """Emnet for en label eller et navn i config.js ('Økonomi', 'Tøj', 'Sponsorer og fonde')."""
    n = norm_emne(navn)
    if not n:
        return None
    for e in EMNER + [ANDET]:
        en = norm_emne(e.navn)
        if n == en or n == en.split(" ")[0]:
            return e
    return None


def emne_ejere(emne, medlemmer):
    return [m["navn"] for m in medlemmer if any(find_emne(x) is emne for x in m.get("emner") or [])]


def fordel(personer_raa, tekst, medlemmer, emne=None, person_tekst=""):
    """Hvem i bestyrelsen opgaven skal ligge hos, og hvad den skal hedde. Navne uden for bestyrelsen
    bliver ikke labels: de skrives forrest i opgaven, og opgaven lægges hos den, der har emnet.
    Har ingen emnet, lægges opgaven hos Bestyrelsen, så alle kan tage den."""
    bestyrelse, andre, alle = klassificer(personer_raa, medlemmer)
    emne = emne or gaet_emne(tekst, personer_raa)
    via_emne = via_pulje = False
    if not bestyrelse and not alle:
        ejere = emne_ejere(emne, medlemmer)
        if ejere:
            bestyrelse, via_emne = ejere, True
        else:
            alle, via_pulje = True, True
    titel = tekst
    if andre and not all(navn_i(a, tekst) for a in andre):
        i_cellen = klassificer(personer(person_tekst), medlemmer) if person_tekst else ([], [], False)
        rene = person_tekst and not i_cellen[0] and not i_cellen[2]    # kun folk uden for bestyrelsen
        titel = f"{person_tekst if rene else og_liste(andre)}: {tekst}"
    return {"bestyrelse": bestyrelse, "alle": alle, "andre": andre, "emne": emne, "via_emne": via_emne,
            "via_pulje": via_pulje, "titel": titel}


def person_labels(f, kendte):
    labels = [sikr_label("@" + p, PERSONFARVE, "I bestyrelsen", kendte) for p in f["bestyrelse"]]
    if f["alle"]:
        labels.append(sikr_label(*PULJE_LABEL, kendte))
    return labels


def emne_label(emne, kendte):
    return None if emne is ANDET else sikr_label(emne.navn, emne.farve, EMNE_BESKRIVELSE, kendte)


def personer(celle):
    c = re.sub(r"\(.*?\)", " ", rens(celle))
    ud = []
    for d in re.split(r"\s*(?:,|/|&|\+|;|\n|\bog\b|\band\b)\s*", c, flags=re.I):
        d = d.strip(" .:-@\t")
        if not d or d in ("?", "—", "–"):
            continue
        if d.lower() in ALLE:
            d = "Alle"
        elif d == d.lower():
            d = d[:1].upper() + d[1:]
        if d.lower() not in [x.lower() for x in ud]:
            ud.append(d)
    return ud


def find_naeste_moede(tekst, ref=None):
    """'Næste møde: 29/10' – eller en linje, der starter med "Næste (bestyrelses)møde" og har en dato."""
    for linje in tekst.replace("\r", "").split("\n"):
        if linje.count("|") >= 2:          # en række i tabellen, ikke en linje om mødet
            continue
        m = re.match(r"^[\s>*_#-]*næste\s+(?:bestyrelses)?møde\b(.*)$", linje, re.I)
        if m:
            d = find_dato(m.group(1), ref)
            if d:
                return d
    return None


def fra_linjer(tekst):
    """Én opgave pr. linje: 'Opgave – Navn – 3/10' (bruges kun i 📥-issues uden tabel).
    Linjer uden bindestreg/semikolon (fx en hilsen) ignoreres."""
    raekker = []
    for l in tekst.replace("\r", "").split("\n"):
        s = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s+", "", l).strip()
        if not s or s.startswith("<!--") or s.startswith("#") or re.match(r"næste\s+(bestyrelses)?møde\b", s, re.I):
            continue
        dele = [d for d in re.split(r"\s+[–—-]\s+|\t|\s*;\s*|\s+\|\s+", s) if d.strip()]
        if len(dele) >= 2:
            raekker.append(dele)
    return raekker


def uden_html(tekst):
    """Når man kopierer en tabel fra Google Docs og sætter den ind i GitHub, bliver tabellen til
    Markdown, men Google Docs' HTML omkring den kommer med (<b id="docs-internal-guid-…"> …),
    og "Næste møde: 29/10" over tabellen ender inde i den HTML. Linjer med | (tabellen) røres ikke."""
    ud = []
    for linje in tekst.split("\n"):
        if "|" in linje or "<" not in linje:
            ud.append(linje)
            continue
        linje = re.sub(r"<(?:br|/p|/div|/li|/h[1-6]|/tr|/table)\b[^>]*>", "\n", linje, flags=re.I)
        ud.append(html.unescape(re.sub(r"<[^>]+>", "", linje)).replace("\xa0", " "))
    return "\n".join(ud)


# To afsnit i samme celle i Google Docs bliver klistret sammen ("Haraldslund:Klar kl. 17")
KLISTRET = re.compile(r"(?<=[a-zæøå0-9)][.:;!?])(?=[A-ZÆØÅ])")


def find_opgaver(body, tvungen=False, ref=None, asap_dage=ASAP_DAGE):
    """Returnerer (opgaver, næste_møde, problemer). ref = mødets dato (relative deadlines regnes herfra)."""
    ref = ref or IDAG
    tekst = uden_html(re.sub(r"<!--[\s\S]*?-->", "", body or ""))
    naeste = find_naeste_moede(tekst, ref)
    tabeller = find_tabeller(tekst)
    brugbare = []
    for t in tabeller:
        roller = kortlaeg(t[0])
        if roller:
            brugbare.append((t[1:], roller))
    if not brugbare and tvungen and len(tabeller) == 1:
        # Tabel uden genkendelige overskrifter: læses som Opgave | Ansvarlig | Deadline
        t = tabeller[0]
        brugbare.append((t, standard_roller(max(len(r) for r in t))))
    if not brugbare and not tabeller and tvungen:
        linjer = fra_linjer(tekst)
        if linjer:
            brugbare.append((linjer, standard_roller(max(len(r) for r in linjer))))

    opgaver, problemer, nr = [], [], 0
    for raekker, roller in brugbare:
        for celler in raekker:
            nr += 1
            hent = lambda rolle: celler[roller[rolle]] if rolle in roller and roller[rolle] < len(celler) else ""
            if not any(rens(c) for c in celler):
                continue
            if kortlaeg(celler):  # gentaget overskrift
                continue
            titel = KLISTRET.sub(" ", rens(hent("opgave")))
            if not titel:
                problemer.append(f"Række {nr} har ingen opgave: {' | '.join(rens(c) for c in celler if rens(c))}")
                continue
            frist = tolk_frist(rens(hent("deadline")), ref, asap_dage)
            status_tekst = rens(hent("status")).lower()
            opgaver.append({
                "titel": titel,
                "personer": personer(hent("person")),
                "person_tekst": re.sub(r"\s+", " ", rens(hent("person"))).strip(" ,;/"),
                "frist": frist,
                "status": STATUS_ORD.get(status_tekst),
                "noter": KLISTRET.sub(" ", rens(hent("noter"), linjer=True)),
            })
    return opgaver, naeste, problemer


# ----------------------------------------------------------------------------- mødedatoer
MOEDE_INTRO = ("Datoerne for bestyrelsens møder. Siden bruger dem til deadlines som \"næste møde\" og til "
               "opfølgningen før hvert møde.\nRet gerne her – én dato pr. linje, fx `- 29/10-2026 kl. 17`. "
               "Næste møde kan også sættes på [siden](" + SIDE + ").")


def er_moeder(i):
    titel = (i.get("title") or "").lstrip()
    return titel.startswith("📅") or any(
        (l["name"] if isinstance(l, dict) else l).lower() == MOEDE_LABEL[0] for l in i.get("labels", []))


def laes_moeder(body):
    """{dato: linjetekst} fra 📅-issuet. Linjer som '- 29/10-2026 kl. 17'."""
    ud = {}
    for linje in (body or "").replace("\r", "").split("\n"):
        m = re.match(r"^\s*[-*]\s+(.+)$", linje)
        if not m:
            continue
        d = find_dato(m.group(1), IDAG)
        if d:
            ud[d] = m.group(1).strip()
    return ud


def skriv_moeder(datoer):
    linjer = [f"- {datoer[d]}" for d in sorted(datoer)]
    return MOEDE_INTRO + "\n\n" + "\n".join(linjer) + "\n"


def opdater_moeder(holdt=None, naeste=None, issues=None, kun_tilfoej=False):
    """Skriver mødedatoerne i 📅-issuet (opretter det, hvis det mangler).
    holdt = et møde, der er holdt (fra tabel-issuets titel). naeste = næste møde ("Næste møde: 29/10").
    Et holdt møde fjerner datoer i dagene op til (mødet blev flyttet), og næste møde fjerner datoer
    mellem det holdte møde og det næste. Returnerer de sorterede datoer."""
    if issues is None:
        issues = hent_alle("/issues?state=open&per_page=100")
    issue = next((i for i in issues if not i.get("pull_request") and er_moeder(i)), None)
    datoer = laes_moeder(issue.get("body")) if issue else {}
    foer = dict(datoer)

    def tilfoej(d):
        if d not in datoer:
            datoer[d] = fuld_dato(d)

    if holdt:
        if not kun_tilfoej:
            for d in list(datoer):
                if holdt - timedelta(days=10) <= d < holdt:
                    del datoer[d]
        tilfoej(holdt)
    if naeste and (not holdt or naeste > holdt):
        if not kun_tilfoej:
            fra = holdt or IDAG
            for d in list(datoer):
                if fra < d < naeste:
                    del datoer[d]
        tilfoej(naeste)
    if datoer == foer and issue:
        return sorted(datoer)
    body = skriv_moeder(datoer)
    if issue:
        kald("PATCH", f"/issues/{issue['number']}", {"body": body})
        print(f"Mødedatoer opdateret i #{issue['number']}: {', '.join(fuld_dato(d) for d in sorted(datoer))}")
    else:
        kendte = hent_labels()
        label = sikr_label(*MOEDE_LABEL, kendte)
        ny, _ = kald("POST", "/issues", {"title": MOEDE_TITEL, "body": body, "labels": [label]})
        print(f"Oprettet #{ny['number']} {MOEDE_TITEL}")
        issues.append(ny)
    return sorted(datoer)


def moede_efter(datoer, d):
    """Første møde efter dato d (eller None)."""
    return next((x for x in sorted(datoer) if x > d), None)


def moede_dato(issue):
    """Datoen for mødet, et tabel-issue kommer fra: datoen i titlen, ellers dagen det blev oprettet."""
    oprettet = dato_fra_tid(issue.get("created_at"))
    titel = re.sub(r"^📥\s*", "", issue.get("title") or "")
    return find_dato(titel, oprettet) or oprettet


# ----------------------------------------------------------------------------- opgaver
SLUT_PARENTES = re.compile(r"\s*[(\[][^()\[\]]*[)\]]\s*$")


def norm_titel(t):
    t = SLUT_PARENTES.sub("", t or "")
    return re.sub(r"[^\w]+", " ", t.lower()).strip()


def er_frist_parentes(indhold):
    """Er '(…)' sidst i en titel en deadline? '3/10', 'næste møde', 'løbende' – men ikke '(Dame 1)'."""
    s = re.sub(r"^\s*(deadline|frist)\s*:?\s*", "", str(indhold or "").strip(" ()[]"), flags=re.I)
    return bool(find_dato(s) or NAESTE_MOEDE.search(s) or FRIST_ORD.match(s.strip()))


def byg_titel(o):
    titel = o["titel"]
    if len(titel) > 180:
        titel = titel[:177].rstrip() + "…"
    if SLUT_PARENTES.search(titel) and find_dato(SLUT_PARENTES.search(titel).group(0)):
        return titel  # der står allerede en deadline i opgaven
    f = o["frist"]
    if f.slags == "dato":
        d = f.dato
        uden_aar = lav_dato(d.day, d.month, None, IDAG)
        return f"{titel} ({d.day}/{d.month}{'' if uden_aar == d else '-' + str(d.year)})"
    if f.slags == "moede":
        return f"{titel} (næste møde)"
    if f.slags == "tekst" and f.tekst:
        return f"{titel} ({f.tekst})"
    return titel


def frist_tekst(f, moeder, ref):
    """Til kvitteringen: 'fre 2/10 (ASAP)', 'næste møde → ons 29/10', 'løbende', '–'."""
    if f.slags == "dato":
        return kort_dato(f.dato) + (f" ({f.forklaring})" if f.forklaring else "")
    if f.slags == "moede":
        d = moede_efter(moeder or [], ref)
        return f"næste møde → {kort_dato(d)}" if d else "næste møde ³"
    if f.slags == "tekst":
        return f.tekst
    return "–"


def behandl_import(issue, kendte, konfig):
    """Et 📥-issue (eller et issue med en tabel) bliver til én opgave pr. række. Returnerer True,
    hvis issuet var en tabel."""
    medlemmer = konfig["medlemmer"]
    nr = issue["number"]
    titel = (issue.get("title") or "").strip()
    if any(l["name"].lower() == IMPORT_LABEL[0] for l in issue.get("labels", [])):
        print(f"#{nr} er allerede behandlet.")
        return True
    if er_moeder(issue):
        return True
    tvungen = titel.startswith("📥")
    ref = moede_dato(issue)
    opgaver, naeste, problemer = find_opgaver(issue.get("body") or "", tvungen, ref, konfig["asap_dage"])
    if not opgaver:
        if tvungen and issue.get("state") == "open":
            tidligere = hent_alle(f"/issues/{nr}/comments?per_page=100")
            if not any(HJAELP_MAERKE in (k.get("body") or "") for k in tidligere):
                kommenter(nr, HJAELP)
        print(f"#{nr}: ingen opgaver fundet.")
        return tvungen

    alle_aabne = hent_alle("/issues?state=open&per_page=100")
    aabne = {}
    for i in alle_aabne:
        if not i.get("pull_request") and i["number"] != nr and not er_moeder(i):
            aabne.setdefault(norm_titel(i["title"]), i["number"])

    # Mødedatoerne: mødet i titlen er holdt, og "Næste møde:" er det næste
    moeder = []
    try:
        er_moede = tvungen and re.search(r"møde", titel, re.I)
        moeder = opdater_moeder(ref if er_moede else None, naeste, alle_aabne)
    except ApiFejl as e:
        print(f"Kunne ikke opdatere mødedatoerne: {e}")

    kilde = re.sub(r"^📥\s*", "", titel) or f"issue #{nr}"
    oprettet, sprunget, set_ = [], [], set()
    andre_navne = []
    for o in opgaver:
        if o["status"] in ("Færdig", "Droppet"):
            sprunget.append(f"{o['titel']} – står som {o['status'].lower()} i tabellen")
            continue
        # Kun bestyrelsen får labels. Andre navne skrives forrest i opgaven, og opgaven lægges hos
        # den i bestyrelsen, der har emnet (se config.js) – eller hos Bestyrelsen, så alle kan tage den.
        f = fordel(o["personer"], o["titel"], medlemmer, person_tekst=o.get("person_tekst", ""))
        o = dict(o, titel=f["titel"], fordeling=f)
        noegle = norm_titel(o["titel"])
        # Samme række to gange i samme issue (GitHub kan sætte en tabel med links ind to gange)
        fingeraftryk = (noegle, tuple(p.lower() for p in o["personer"]), o["frist"].slags, o["frist"].dato,
                        o["frist"].tekst)
        if fingeraftryk in set_:
            continue
        set_.add(fingeraftryk)
        if noegle in aabne:
            sprunget.append(f"{o['titel']} – findes allerede som #{aabne[noegle]}")
            continue
        labels = person_labels(f, kendte)
        el = emne_label(f["emne"], kendte)
        if el:
            labels.append(el)
        if o["status"]:
            labels.append(sikr_label(o["status"], *STATUS[o["status"]], kendte))
        krop = f"Oprettet af robotten fra #{nr} ({kilde})."
        if o["noter"]:
            krop += "\n\n" + o["noter"]
        if len(o["titel"]) > 180:
            krop += "\n\nHele opgaven: " + o["titel"]
        ny, _ = kald("POST", "/issues", {"title": byg_titel(o), "body": krop, "labels": labels})
        aabne[noegle] = ny["number"]
        oprettet.append((ny["number"], o))
        for a in f["andre"]:
            if a.lower() not in [x.lower() for x in andre_navne]:
                andre_navne.append(a)
        print(f"Oprettet #{ny['number']}: {byg_titel(o)}  {labels}")
        time.sleep(1)  # skån GitHubs grænse for mange oprettelser i træk

    dele = []
    if oprettet:
        dele.append(f"✅ **{len(oprettet)} {'opgave' if len(oprettet) == 1 else 'opgaver'} oprettet** – "
                    f"de ligger nu på [bestyrelsessiden]({SIDE}).\n")
        dele.append("| | Opgave | Ansvarlig | Emne | Deadline |\n|---|---|---|---|---|")
        for n, o in oprettet:
            f = o["fordeling"]
            navne = f["bestyrelse"] + (["Bestyrelsen 🙋"] if f["alle"] else [])
            hvem = ", ".join(navne) + (" ¹" if f["via_emne"] else " ²" if f["via_pulje"] else "")
            emne = f["emne"].navn if f["emne"] is not ANDET else "–"
            dele.append(f"| #{n} | {o['titel'].replace('|', '/')} | {hvem} | {emne} | "
                        f"{frist_tekst(o['frist'], moeder, ref).replace('|', '/')} |")
        if any(o["fordeling"]["via_emne"] for _, o in oprettet):
            dele.append("\n¹ Ingen fra bestyrelsen stod på opgaven, så den er lagt hos den, der har emnet "
                        "(se `config.js`).")
        if any(o["fordeling"]["via_pulje"] for _, o in oprettet):
            dele.append("\n² Ingen fra bestyrelsen stod på opgaven, og ingen har emnet – den ligger hos "
                        "*Bestyrelsen*, så alle kan tage den på siden.")
        if any(o["frist"].slags == "moede" and not moede_efter(moeder, ref) for _, o in oprettet):
            dele.append("\n³ Datoen for næste møde er ikke sat endnu. Sæt den på siden (📅 øverst), så får "
                        "opgaverne den som deadline med det samme.")
        if andre_navne:
            dele.append(f"\nℹ️ {og_liste(andre_navne)} er ikke i bestyrelsen og får ikke en label – navnene står "
                        "forrest i opgaven i stedet.")
    else:
        dele.append("Der var ingen nye opgaver at oprette.")
    if sprunget:
        dele.append("\n⏭️ **Sprunget over:**\n" + "\n".join(f"- {s}" for s in sprunget))
    if problemer:
        dele.append("\n⚠️ **Kunne ikke bruges:**\n" + "\n".join(f"- {p}" for p in problemer))
    dele.append("\nDette issue lukkes automatisk.")
    kommenter(nr, "\n".join(dele))
    kald("POST", f"/issues/{nr}/labels", {"labels": [sikr_label(*IMPORT_LABEL, kendte)]})
    kald("PATCH", f"/issues/{nr}", {"state": "closed", "state_reason": "completed"})
    return True


# ----------------------------------------------------------------------------- ret opgaver
def er_import(i):
    return (i.get("title") or "").lstrip().startswith("📥") or \
        any((l["name"] if isinstance(l, dict) else l).lower() == IMPORT_LABEL[0] for l in i.get("labels", []))


def er_opgave(i):
    if i.get("pull_request") or er_import(i) or er_moeder(i):
        return False
    if (i.get("user") or {}).get("login") == "github-actions[bot]":
        return True
    return (i.get("author_association") or "OWNER") in ("OWNER", "MEMBER", "COLLABORATOR")


def uden_log(body):
    """Beskrivelsen uden logbogen, som mellemmanden skriver nederst."""
    b = body or ""
    i = b.find(LOG_MAERKE)
    return b[:i].rstrip() if i >= 0 else b


def uden_deadline(titel):
    m = SLUT_PARENTES.search(titel or "")
    if m and er_frist_parentes(m.group(0)):
        return titel[:m.start()].rstrip(), titel[m.start():]
    return titel or "", ""


def ret_opgave(issue, medlemmer, kendte):
    """Sørger for, at en opgave kun har personer fra bestyrelsen (eller Bestyrelsen = alle kan tage
    den) og et emne. Returnerer True, hvis noget blev ændret. Gør ingenting, hvis opgaven er i orden."""
    nr = issue["number"]
    navne = [l["name"] if isinstance(l, dict) else l for l in issue.get("labels", [])]
    personer_raa = [n[1:].strip() for n in navne if n.startswith("@") and n[1:].strip()]
    if any(er_pulje_label(n) and not n.startswith("@") for n in navne):
        personer_raa.append("Alle")
    oevrige = [n for n in navne if not n.startswith("@") and not er_pulje_label(n)]
    emne = next((find_emne(n) for n in oevrige if find_emne(n)), None)
    tekst, deadline = uden_deadline(issue.get("title") or "")
    hel = re.search(r"(?:^|\n)Hele opgaven:[ \t]*([\s\S]+?)\s*$", uden_log(issue.get("body")))
    gaet_tekst = hel.group(1) if hel else tekst
    f = fordel(personer_raa, tekst, medlemmer, emne=emne or gaet_emne(gaet_tekst, personer_raa))
    nye = oevrige[:]
    for p in person_labels(f, kendte):
        if p not in nye:
            nye.append(p)
    if not emne:
        el = emne_label(f["emne"], kendte)
        if el and el not in nye:
            nye.append(el)
    ny_titel = f["titel"] + (" " + deadline.strip() if deadline else "")
    if len(ny_titel) > 250:
        ny_titel = issue.get("title") or ""
    gamle = sorted(navne)
    if sorted(nye) == gamle and ny_titel == (issue.get("title") or ""):
        return False
    aendring = {"labels": nye}
    if ny_titel != (issue.get("title") or ""):
        aendring["title"] = ny_titel
    kald("PATCH", f"/issues/{nr}", aendring)
    fjernet = [n for n in navne if n not in nye]
    tilfoejet = [n for n in nye if n not in navne]
    print(f"#{nr} rettet: {ny_titel!r}  +{tilfoejet}  -{fjernet}")
    return True


def ryd_op(medlemmer, kendte):
    """Kører ved "Run workflow" og når config.js/robot.py opdateres: flytter opgaver fra folk uden for
    bestyrelsen til den rigtige person, flytter de gamle @Alle-opgaver over på "Bestyrelsen", sætter emne
    på, sletter labels for personer, der ikke er i bestyrelsen, og samler mødedatoerne i 📅-issuet."""
    siden = (datetime.now(ZoneInfo("UTC")) - timedelta(days=45)).strftime("%Y-%m-%dT%H:%M:%SZ")
    aabne = hent_alle("/issues?state=open&per_page=100")
    issues = aabne + hent_alle(f"/issues?state=closed&per_page=100&since={siden}")
    rettet = 0
    for i in issues:
        if not er_opgave(i):
            continue
        if ret_opgave(i, medlemmer, kendte):
            rettet += 1
            time.sleep(1)
    slettet = []
    for l in hent_alle("/labels?per_page=100"):
        n = l["name"]
        if not n.startswith("@") or not n[1:].strip():
            continue
        navn = n[1:].strip()
        if navn.lower() not in ALLE and navn != "Alle":          # @Alle er afløst af "Bestyrelsen"
            fundet, via_rolle = find_medlem(navn, medlemmer)
            if fundet and not via_rolle and lav_navn(navn) == lav_navn(fundet[0]):
                continue                                   # et medlem af bestyrelsen
        try:
            kald("DELETE", f"/labels/{urllib.parse.quote(n, safe='')}")
            kendte.pop(n.lower(), None)
            slettet.append(n)
        except ApiFejl as e:
            if e.kode != 404:
                raise
    # Mødedatoer fra tidligere tabel-issues (titlen = mødet; "Næste møde:" i det nyeste)
    try:
        imports = [i for i in hent_alle("/issues?state=all&labels=import&per_page=100")
                   if not i.get("pull_request") and (i.get("title") or "").lstrip().startswith("📥")]
        imports.sort(key=lambda i: i.get("created_at") or "")
        for n_, i in enumerate(imports):
            holdt = moede_dato(i) if re.search(r"møde", i.get("title") or "", re.I) else None
            naeste = None
            if n_ == len(imports) - 1:
                naeste = find_naeste_moede(uden_html(i.get("body") or ""), dato_fra_tid(i.get("created_at")))
                if naeste and naeste < IDAG:
                    naeste = None
            if holdt or naeste:
                opdater_moeder(holdt, naeste, aabne, kun_tilfoej=True)
        if not any(er_moeder(i) for i in aabne):
            opdater_moeder(None, None, aabne)               # opret 📅-issuet, så det er klar
    except ApiFejl as e:
        print(f"Kunne ikke samle mødedatoerne: {e}")
    print(f"Oprydning: {rettet} opgaver rettet, {len(slettet)} labels slettet {slettet}")
    return rettet, slettet


def behandl_status(issue, ny_label):
    kanon = {k.lower(): k for k in STATUS}
    ny = ny_label.lower()
    if ny not in kanon:
        return
    nr = issue["number"]
    for l in issue.get("labels", []):
        if l["name"].lower() in kanon and l["name"].lower() != ny:
            fjern_label(nr, l["name"])
            print(f"#{nr}: fjernede {l['name']}")
    if kanon[ny] in ("Færdig", "Droppet"):
        fjern_label(nr, ny_label)  # et lukket issue er færdigt – labelen skal ikke hænge ved
        kald("PATCH", f"/issues/{nr}", {"state": "closed",
                                         "state_reason": "completed" if kanon[ny] == "Færdig" else "not_planned"})
        print(f"#{nr}: lukket ({kanon[ny]})")


# ----------------------------------------------------------------------------- start
def main():
    haendelse = os.environ.get("GITHUB_EVENT_NAME", "")
    sti = os.environ.get("GITHUB_EVENT_PATH")
    data = json.load(open(sti, encoding="utf-8")) if sti and os.path.exists(sti) else {}

    konfig = laes_konfig()
    medlemmer = konfig["medlemmer"]
    print("Bestyrelsen:", ", ".join(m["navn"] for m in medlemmer), f"· ASAP = {konfig['asap_dage']} dage")
    kendte = hent_labels()
    for navn, (farve, beskrivelse) in STATUS.items():
        sikr_label(navn, farve, beskrivelse, kendte)
    sikr_label(*IMPORT_LABEL, kendte)
    sikr_label(*PULJE_LABEL, kendte)
    sikr_label(*MOEDE_LABEL, kendte)
    if haendelse != "issues":
        print("Labels er på plads.")
        if haendelse in ("workflow_dispatch", "push"):
            ryd_op(medlemmer, kendte)
        return 0

    issue = data.get("issue") or {}
    if issue.get("pull_request"):
        return 0
    handling = data.get("action")
    if handling == "labeled":
        behandl_status(issue, (data.get("label") or {}).get("name", ""))
    elif handling in ("opened", "edited", "reopened"):
        var_tabel = behandl_import(issue, kendte, konfig)
        # En opgave oprettet direkte i GitHub eller fra siden: emne på, og ingen ansvarlig ->
        # den, der har emnet (eller Bestyrelsen)
        if not var_tabel and handling == "opened" and er_opgave(issue) and issue.get("state") == "open":
            ret_opgave(issue, medlemmer, kendte)
    return 0


if __name__ == "__main__":
    sys.exit(main())
