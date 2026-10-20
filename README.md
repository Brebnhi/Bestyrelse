# Bestyrelsens opgaver – Aalborg Volley

**https://brebnhi.github.io/bestyrelse/**

Bestyrelsens opgaver på én side. Alle i bestyrelsen kan tilføje en opgave, tage en, skrive en
opdatering og melde den færdig – uden login og uden at røre GitHub. Bag siden ligger opgaverne som
**issues** her i repoet, og *mellemmanden* (et lille Google-script, se nederst) gemmer det, folk gør.

## Til alle i bestyrelsen

**Læg siden på telefonen** – så åbner den som en app, og det går lige så hurtigt som en notesblok:

- **iPhone:** åbn siden i Safari → Del-knappen (firkanten med pilen op) → **Føj til hjemmeskærm**.
- **Android:** åbn siden i Chrome → **⋮** → **Installer app** (eller *Føj til startskærm*).
  Hold fingeren på ikonet for en genvej direkte til *Tilføj opgave*.

Første gang vælger du dit navn. Så viser siden dine opgaver først, og de andre kan se, hvem der har
skrevet hvad. Hver person kan også få sit eget link: `https://brebnhi.github.io/bestyrelse/?person=Ida`.

**Tilføj en opgave:** tryk **＋** (nederst til højre på telefonen) og udfyld

| | |
|---|---|
| **Hvad** | Hvad skal gøres. |
| **Hvem** | Dig selv (valgt på forhånd), en eller flere andre – eller **🙋 Bestyrelsen**, hvis alle kan tage den. |
| **Hvornår** | *Ingen*, *ASAP* (om en uge), *Næste møde* (følger datoen for næste møde) eller en dato. |

Opgaven ligger klar til alle med det samme. Er der ikke net, bliver den gemt, så snart der er net igen.

**Kan alle tage:** opgaver hos *Bestyrelsen* ligger under **🙋 Kan alle tage** hos alle. Tryk
**Tag den**, så bliver den din. Kan du alligevel ikke nå en opgave, så åbn den og vælg
**Læg den tilbage til bestyrelsen**.

**Tryk på en opgave** for at se det hele og

- **skifte status** – *Ikke startet*, *Next up*, *I gang*, *Venter* eller *Færdig ✓*,
- **skrive en opdatering til de andre**, fx "Har skrevet til kommunen – venter svar",
- **rette** hvad, hvem og hvornår (✏️ *Ret opgaven*).

Når en opgave meldes **færdig**, spørger siden: *Hvad blev det til?* Svaret – fx "Hallen er booket
12/12" – står i opfølgningen til næste møde, så alle ved, hvad det endte med. Det samme, når en opgave
droppes: *Hvorfor?* Alt, der sker med en opgave, står i dens **historik**.

## Til mødet – godkendelse af sidste referat

Fanen **Til mødet** samler det, bestyrelsen skal igennem under *godkendelse af sidste referat*:

- **✅ Klaret siden sidste møde** – hvem, og hvad det blev til (eller ⚠️ *intet resultat skrevet*).
- **⏳ Åbne opgaver** pr. person – status, deadline og seneste nyt (eller ⚠️ *ingen status siden mødet*).
- Øverst: hvem der har givet status på alle sine opgaver ✓, og hvem der mangler.

**📋 Kopiér til referatet** lægger det hele som to tabeller i udklipsholderen – klar til at sætte ind i
referatet i Google Docs.

**Sikringen:** en uge før mødet får hver person et lille banner på siden, hvis nogle af deres opgaver
ikke har fået en status siden sidste møde. **Giv status** går dem igennem én ad gangen (*Ikke nået
endnu*, *I gang*, *Venter på andre* eller *Færdig ✓* og en kort tekst) – det tager et minut.

## Efter et bestyrelsesmøde – indsæt hele tabellen (formanden)

Den hurtige vej, når mødet har givet mange opgaver:

1. Tryk **📥 Indsæt tabel fra mødet** under **📥 Efter et møde** nederst på siden (eller opret selv et
   issue, hvis titel starter med 📥). Mødets dato står allerede i titlen.
2. Skriv datoen for næste møde i linjen `Næste møde:`, hvis I kender den (ellers sæt den på siden senere).
3. Markér tabellen i referatet i Google Docs, kopiér den og sæt den ind med **Ctrl+V** (ikke
   Ctrl+Shift+V) – så laver GitHub den om til en tabel. Kolonnerne er *Opgave*, *Person* (eller
   *Ansvarlig*) og *Deadline* – overskrifterne må gerne mangle, og tomme rækker springes over.
4. Tryk **Create**. Efter ca. et minut har robotten lavet én opgave pr. række, skrevet en kvittering og
   lukket tabel-issuet.

Robotten forstår:

| I tabellen | Bliver til |
|---|---|
| `Søren`, `Emma og Ida`, `Søren/Emma` | Én `@Navn`-label pr. person – kun for bestyrelsen (se herunder) |
| `Kassererne`, `Formanden` | Personerne med den rolle i `config.js` (fx Mikkel og Lars) |
| `Bestyrelsen` eller `Alle` | Labelen **Bestyrelsen** – kan alle tage |
| Navne uden for bestyrelsen, fx `Herre 1` | Ingen label – navnet skrives forrest i opgaven (`Herre 1: Står for julefrokosten`), og opgaven lægges hos den, der har emnet |
| Tom *Person* | Hos den, der har emnet – ellers hos *Bestyrelsen* |
| `3/10`, `3.10`, `3. okt`, `1/2-2027` | Deadline sidst i titlen, fx `Book hal (3/10)` |
| `næste møde`, `inden næste møde`, `til mødet`, `NM` | `(næste møde)` – deadline følger datoen for det næste møde, også hvis den først bliver sat senere |
| `ASAP`, `hurtigst muligt`, `snarest`, `straks` | En uge efter mødet (antal dage: `asapDage` i `config.js`) |
| `i morgen`, `om 14 dage`, `om en uge`, `inden for to uger` | Regnet fra mødets dato |
| `fredag`, `på fredag`, `fredag i næste uge`, `inden fredag` | Den førstkommende fredag (*inden* = dagen før) |
| `denne uge`, `næste uge`, `i weekenden`, `uge 44`, `inden uge 44` | Søndagen i ugen (*inden uge 44* = søndag i uge 43) |
| `oktober`, `ultimo oktober`, `primo november`, `medio november`, `inden oktober` | Sidste dag i måneden · den 7. · den 15. · sidste dag i måneden før |
| `inden jul`, `inden nytår`, `inden sommerferien`, `inden påske`, `efterårsferien` | 23/12 · 30/12 · 30/6 · onsdag før påske · søndag i uge 42 |
| Anden tekst, fx `løbende` | Står i parentes efter opgaven |
| Ekstra kolonne *Status* eller *Noter* | Status-label eller noter på opgaven |

Kvitteringen viser, hvad robotten har læst, fx *fre 2/10 (ASAP)* og *næste møde → tor 29/10*. Findes en
opgave allerede (samme titel), springer robotten den over. Ingen tabel ved hånden? Skriv én opgave pr.
linje: `Book hal til opstartsfest – Søren – inden næste møde`.

## Næste møde og mødedatoerne

Mødedatoerne står i issuet **📅 Bestyrelsesmøder**. Robotten skriver mødet ind, når en tabel fra mødet
bliver sat ind (og datoen fra linjen `Næste møde:`), og alle kan sætte eller flytte næste møde på siden
(📅 øverst → *ret* / *sæt dato*). Opgaver med deadline *næste møde* følger datoen, og *Til mødet* regner
"siden sidste møde" herfra. Du kan også rette datoerne direkte i issuet – én dato pr. linje,
fx `- 29/10-2026 kl. 17`.

## Bestyrelsen, emner og hvem der får opgaven

Kun dem, der står under `medlemmer` i [`config.js`](https://github.com/Brebnhi/bestyrelse/edit/main/config.js),
kan få opgaver. Det er også dem, man kan vælge på siden.

Hver opgave får et **emne** (Økonomi, Sponsorer & fonde, Hold & turneringer, Trænere & kurser, Ungdom,
Arrangementer & frivillige, Tøj & udstyr, Kommunikation, Haller & lokaler, Forening & bestyrelse – eller
Andet), som gættes ud fra ordene i opgaven. Står der ikke nogen fra bestyrelsen på en opgave fra
tabellen, lægger robotten den hos den, der har emnet under `emner` i `config.js`:

| Emne | Hos |
|---|---|
| Økonomi | Mikkel og Lars |
| Sponsorer & fonde | Heidi |
| Ungdom | Anna |
| Tøj & udstyr | Emma |
| Arrangementer & frivillige | Ida |
| Hold & turneringer | Marcel |
| Forening & bestyrelse | Søren |

Har ingen emnet, ligger opgaven hos **Bestyrelsen**, så alle kan tage den. Gætter robotten forkert på
emnet, så giv opgaven en label i GitHub med det rigtige emne, fx `Økonomi` eller bare `Tøj`.

**Ny i bestyrelsen?** Tilføj en linje under `medlemmer` i `config.js` (fx
`{ "navn": "Jonas", "rolle": "", "emner": [] },`) og tryk **Commit changes**. Går nogen ud, så slet
linjen. Robotten rydder selv op bagefter: den flytter opgaver fra folk, der ikke er i bestyrelsen, til
den rigtige person og sletter de forkerte labels.

## Status i GitHub

Alt kan stadig gøres i GitHub: vælg en status-label (*Next up*, *I gang*, *Venter*, *Færdig*, *Droppet*)
under **Labels** – robotten fjerner selv den gamle, og *Færdig*/*Droppet* lukker opgaven. Ret deadline i
titlen og personen med `@Navn`-labelen. Logbogen nederst i beskrivelsen (**Opdateringer**) skrives af
mellemmanden – lad den stå.

## Mellemmanden – så alle kan bruge siden uden GitHub-konto

GitHub kræver login for at ændre noget. Derfor går alt, man gør på siden, gennem *Bestyrelsens
mellemmand*: et lille Google Apps Script i din Google-konto med en GitHub-nøgle, der kun har adgang til
issues i det her repo. Koden står i [`mellemmand.gs`](mellemmand.gs) (uden nøgle). Adressen på
mellemmanden står i `config.js`; er den tom, kan siden kun vise opgaverne.

Mellemmanden kan oprette og rette opgaver, tage/lægge tilbage, skifte status, skrive i logbogen og sætte
næste møde – ikke slette noget. Den tjekker, at navnene står i `config.js`, og bremser, hvis nogen laver
over 150 ændringer i timen. Rammer et netværk GitHubs grænse for opslag uden login, henter siden
opgaverne gennem mellemmanden i stedet.

Nøglen ligger i scriptets indstillinger (⚙️ **Projektindstillinger → Scriptegenskaber**, som `NOEGLE`) –
ikke i koden. Så kan koden skiftes ud uden at røre nøglen.

**Opdatering fra version 1** (én gang):

1. Upload filerne til repoet, så [`mellemmand.gs`](mellemmand.gs) ligger her.
2. Gå til [script.google.com](https://script.google.com) → **Bestyrelsens mellemmand**.
3. **Flyt nøglen ud af koden:** dobbeltklik på nøglen i den gamle kode (den lange tekst, der starter med
   `github_pat_`) og kopiér den. Klik på tandhjulet ⚙️ **Projektindstillinger** → **Scriptegenskaber** →
   **Tilføj scriptegenskab**. Egenskab: `NOEGLE` · Værdi: nøglen → **Gem scriptegenskaber**.
4. **Skift koden:** åbn [`mellemmand.gs`](mellemmand.gs) her i repoet og klik på kopi-ikonet øverst til højre
   over koden. I Apps Script: klik på **<>** (Editor), klik i koden, tryk **Cmd+A** og **Cmd+V** (Ctrl på
   Windows) og **Gem** 💾. Linjen med `SÆT-DIN-NØGLE-IND-HER` skal blive stående.
5. **Tjek:** vælg `test` i rullemenuen øverst og tryk **Kør**. I loggen nederst skal der stå
   *Forbindelse til Brebnhi/bestyrelse ✓*.
6. **Udgiv:** **Implementer → Administrer implementeringer** → blyanten ✏️ → *Version:* **Ny version** →
   **Implementer**. Vælg ikke *Ny implementering* – så får mellemmanden en ny adresse.

**Senere opdateringer:** kun trin 4 og 6 – nøglen bliver liggende under Scriptegenskaber.

**Første opsætning** (kun hvis mellemmanden ikke findes):

1. **Lav nøglen:** [ny fine-grained token](https://github.com/settings/personal-access-tokens/new?name=Bestyrelsens%20mellemmand&description=Lader%20bestyrelsessiden%20gemme%20%C3%A6ndringer%20i%20opgaverne&target_name=Brebnhi&expires_in=none&issues=write).
   Vælg *Only select repositories* → `bestyrelse`, tryk **Generate token** og kopiér nøglen.
2. **Lav scriptet:** [script.google.com](https://script.google.com) → **Nyt projekt**. Kald det
   *Bestyrelsens mellemmand*, slet det, der står, sæt indholdet af `mellemmand.gs` ind og gem. Læg nøglen
   under ⚙️ **Projektindstillinger → Scriptegenskaber** som `NOEGLE`.
3. **Udgiv det:** **Implementer → Ny implementering** → tandhjulet → **Webapp**. *Udfør som:* Mig ·
   *Hvem har adgang:* Alle → **Implementer** → godkend adgangen (*Avanceret → Gå til Bestyrelsens
   mellemmand*). Kopiér webappens adresse (slutter på `/exec`).
4. **Sæt adressen ind** i [`config.js`](https://github.com/Brebnhi/bestyrelse/edit/main/config.js)
   og tryk **Commit changes**.

Nøglen ligger kun i dit Google-script – aldrig her i det offentlige repo. Vil du lukke for det, så slet
nøglen på GitHub under *Settings → Developer settings → Fine-grained tokens*. Finder du ikke nøglen i den
gamle kode, så lav bare en ny (trin 1 under *Første opsætning*) og læg den under Scriptegenskaber.

## Godt at vide

- **Alt er offentligt.** Repoet og siden kan ses af alle, der har linket. Skriv ikke følsomme ting i
  opgaverne, fx personsager, beløb eller telefonnumre.
- **Alle med linket kan tilføje og rette** – men ikke slette. Alt står i historikken og i GitHub, så det
  kan rettes, hvis noget går galt.
- **Mange mails fra GitHub?** Sæt **Watch** øverst i repoet til *Participating and @mentions*.
- **Gør ikke repoet privat** – så kan siden ikke længere læse opgaverne.
- **Se et eksempel:** https://brebnhi.github.io/bestyrelse/?eksempel – her kan man prøve alt uden at
  gemme noget.

## Filer

| Fil | Hvad |
|---|---|
| `index.html` | Siden. Slås til under **Settings → Pages → Deploy from a branch → main / (root)**. |
| `config.js` | Bestyrelsen, ASAP-dage og adressen på mellemmanden (læses af siden, robotten og mellemmanden). |
| `robot.py` | Robotten: tabel → opgaver, deadlines med ord, emner, status-labels, mødedatoer og oprydning. |
| `.github/workflows/robot.yml` | Starter robotten ved nye/rettede issues, og når `config.js` eller `robot.py` opdateres. |
| `mellemmand.gs` | Koden til mellemmanden i Google Apps Script (uden nøgle). |
| `manifest.webmanifest`, `sw.js`, `ikoner/` | Gør, at siden kan lægges på hjemmeskærmen som en app og åbne uden net. |

Robotten kører under **Actions → Bestyrelsens robot**. Omdøber du repoet, så ret `REPO` øverst i
scriptet i `index.html`, i `mellemmand.gs` og i kortet på startsiden (`tjans/docs/index.html` i
`Brebnhi.github.io`).
