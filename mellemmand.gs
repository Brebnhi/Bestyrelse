/**
 * Bestyrelsens mellemmand – Aalborg Volley · version 2
 *
 * Lader alle i bestyrelsen arbejde med opgaverne på https://brebnhi.github.io/bestyrelse/ uden en
 * GitHub-konto. Siden sender en lille besked hertil, og scriptet gør det i GitHub med din nøgle
 * (en fine-grained token, der kun kan røre issues i repoet Brebnhi/bestyrelse).
 *
 * Kan:      oprette en opgave (hvad, hvem, hvornår) · rette den · "Jeg tager den" · lægge den tilbage
 *           til bestyrelsen · skifte status (med resultat, når den er færdig) · skrive en opdatering ·
 *           sætte datoen for næste møde · hente opgaverne, hvis GitHub siger stop til siden.
 * Kan ikke: slette noget, ændre andet end issues i repoet eller læse andre repoer.
 *
 * NØGLEN står ikke her i koden, men under Projektindstillinger (tandhjulet ⚙️ til venstre) →
 * Scriptegenskaber, som egenskaben NOEGLE. Så kan koden skiftes ud uden at røre nøglen.
 *
 * SÅDAN OPDATERES MELLEMMANDEN
 *   1. Åbn mellemmand.gs i repoet Brebnhi/bestyrelse og klik på kopi-ikonet øverst til højre over koden.
 *   2. Her i editoren: klik i koden, tryk Cmd+A og Cmd+V (Ctrl på Windows), og tryk Gem (💾).
 *   3. Implementer → Administrer implementeringer → blyanten ✏️ → Version: "Ny version" → Implementer.
 *      Adressen (…/exec) er den samme som før, så config.js skal ikke rettes.
 * Første gang (fra version 1) skal nøglen flyttes fra den gamle kode over i Scriptegenskaber – se README.
 */
const NOEGLE = "SÆT-DIN-NØGLE-IND-HER";   // lad linjen stå – nøglen ligger under Scriptegenskaber (se øverst)

const REPO = "Brebnhi/bestyrelse";
const SIDE = "https://brebnhi.github.io/bestyrelse/";
const VERSION = 2;
const TZ = "Europe/Copenhagen";
const MAKS_PR_TIME = 150;          // ændringer i timen – bremser misbrug af den åbne adresse
const FARVER = {                   // labels, mellemmanden selv kan oprette
  person: ["C5DEF5", "I bestyrelsen"],
  "bestyrelsen": ["FBE7A1", "Kan alle i bestyrelsen tage – tryk 'Jeg tager den' på siden"],
  "next up": ["1D76DB", "Skal i gang som det næste"],
  "i gang": ["FBCA04", "Nogen arbejder på det"],
  "venter": ["D4C5F9", "Venter på andre"],
  "møder": ["C2E0C6", "Datoerne for bestyrelsesmøderne – siden og robotten læser dem herfra"]
};

// ================================================================== indgange
function doPost(e) {
  let svar;
  try {
    const d = JSON.parse((e && e.postData && e.postData.contents) || "{}");
    svar = behandl(d);
  } catch (err) {
    svar = { ok: false, fejl: fejlTekst(err) };
  }
  return svarJson(svar);
}

function doGet(e) {
  const p = (e && e.parameter) || {};
  try {
    if (p.handling === "liste") return svarJson({ ok: true, issues: hentListe() });
    return svarJson({ ok: true, navn: "Bestyrelsens mellemmand", repo: REPO });
  } catch (err) {
    return svarJson({ ok: false, fejl: fejlTekst(err) });
  }
}

function svarJson(o) {
  o.version = VERSION;
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}

// Kør den her én gang fra editoren (vælg "test" og tryk Kør), hvis du vil se, at nøglen virker.
function test() {
  const k = konfig();
  Logger.log("Bestyrelsen: " + k.medlemmer.join(", "));
  const r = gh("get", "");
  Logger.log("Forbindelse til " + r.full_name + " ✓ (" + r.open_issues_count + " åbne issues)");
}

// ================================================================== handlinger
function behandl(d) {
  if (!d.handling && d.nr && d.status) d.handling = "status";          // siden fra version 1
  const cache = CacheService.getScriptCache();
  const idNoegle = d.id ? "id:" + String(d.id).slice(0, 80) : null;
  if (idNoegle) {
    const tidligere = cache.get(idNoegle);
    if (tidligere) return JSON.parse(tidligere);                      // samme besked sendt to gange
  }
  const laas = LockService.getScriptLock();
  if (!laas.tryLock(25000)) throw "Der er travlt lige nu – prøv igen om lidt.";
  try {
    if (idNoegle && cache.get(idNoegle)) return JSON.parse(cache.get(idNoegle));
    taelOp(cache);
    const svar = udfoer(d);
    if (idNoegle) cache.put(idNoegle, JSON.stringify(svar).slice(0, 90000), 21600);
    return svar;
  } finally {
    laas.releaseLock();
  }
}

function taelOp(cache) {
  const noegle = "n:" + Utilities.formatDate(new Date(), TZ, "yyyyMMddHH");
  const n = +(cache.get(noegle) || 0);
  if (n >= MAKS_PR_TIME) throw "Der er lavet rigtig mange ændringer den sidste time – prøv igen lidt senere.";
  cache.put(noegle, String(n + 1), 3700);
}

function udfoer(d) {
  const k = konfig();
  const v1 = d.handling === "status" && !d.af && d.version !== 2;     // siden fra version 1 sendte intet navn
  const af = v1 ? "Nogen" : findMedlem(d.af, k.medlemmer);
  if (!af) throw "Vælg dit navn på siden, før du retter noget.";
  const data = Object.assign({}, d, { af: af });
  if (d.handling === "opret") return opret(data, k);
  if (d.handling === "moede") return moede(data);
  if (["status", "opdatering", "tag", "slip", "ret"].indexOf(d.handling) >= 0) return paaOpgave(data, k);
  throw "Ukendt handling: " + d.handling;
}

function opret(d, k) {
  if (!renTitel(d.hvad)) throw "Skriv, hvad opgaven går ud på.";
  const ny = bygNy({
    hvad: d.hvad, hvem: validerHvem(d.hvem, k.medlemmer), deadline: validerFrist(d.deadline), af: d.af, id: d.id
  }, { dato: fuldDato(idag()), ref: idag() });
  const issue = gh("post", "/issues", { title: ny.title, body: ny.body, labels: ny.labels.map(sikrLabel) });
  return { ok: true, nr: issue.number, issue: tilSiden(issue) };
}

function paaOpgave(d, k) {
  const nr = parseInt(d.nr, 10);
  if (!(nr > 0)) throw "Mangler opgavens nummer.";
  const issue = gh("get", "/issues/" + nr);
  if (issue.pull_request || erMoedeIssue(issue) || /^\s*📥/u.test(issue.title || "")) throw "Det er ikke en opgave.";
  if (d.handling === "ret") {
    if (d.hvem != null) d.hvem = validerHvem(d.hvem, k.medlemmer);
    if (d.deadline != null) d.deadline = validerFrist(d.deadline);
  }
  const foer = {
    title: issue.title, body: String(issue.body || ""), labels: issue.labels.map(function (l) { return l.name; }),
    state: issue.state, state_reason: issue.state_reason
  };
  const efter = anvend(foer, d, { dato: fuldDato(idag()), ref: datoFraTid(issue.created_at) });
  const aendring = {};
  if (efter.title !== foer.title) aendring.title = efter.title;
  if (efter.body !== foer.body) aendring.body = efter.body;
  const sammeLabels = efter.labels.length === foer.labels.length &&
    efter.labels.every(function (l) { return foer.labels.some(function (f) { return lav(f) === lav(l); }); });
  if (!sammeLabels) aendring.labels = efter.labels.map(sikrLabel);
  if (efter.state !== foer.state) {
    aendring.state = efter.state;
    aendring.state_reason = efter.state === "closed" ? efter.state_reason : "reopened";
  } else if (efter.state === "closed" && efter.state_reason !== foer.state_reason) {
    aendring.state_reason = efter.state_reason;
  }
  const opdateret = Object.keys(aendring).length ? gh("patch", "/issues/" + nr, aendring) : issue;
  return { ok: true, nr: nr, issue: tilSiden(opdateret) };
}

function moede(d) {
  const dato = d.dato ? isoTilDato(d.dato) : null;
  const erstat = d.erstat ? isoTilDato(d.erstat) : null;
  if (d.dato && !dato) throw "Datoen kunne ikke læses.";
  if (!dato && !erstat) throw "Vælg en dato.";
  let issue = findMoedeIssue();
  const foer = issue ? laesMoeder(issue.body, idag()) : {};
  const body = skrivMoeder(opdaterMoeder(foer, dato, erstat, d.tid, idag()));
  if (issue) {
    if (body !== String(issue.body || "").replace(/\r/g, "")) issue = gh("patch", "/issues/" + issue.number, { body: body });
  } else {
    issue = gh("post", "/issues", { title: MOEDE_TITEL, body: body, labels: [sikrLabel(MOEDE_LABEL)] });
  }
  return { ok: true, nr: issue.number, issue: tilSiden(issue) };
}

function findMoedeIssue() {
  const aabne = hentAlle("/issues?state=open&per_page=100");
  return aabne.filter(function (i) { return !i.pull_request && erMoedeIssue(i); })[0] || null;
}

function hentListe() {
  const cache = CacheService.getScriptCache();
  const gemt = cache.get("liste");
  if (gemt) return JSON.parse(gemt);
  const siden = new Date();
  siden.setUTCHours(0, 0, 0, 0);
  siden.setUTCDate(siden.getUTCDate() - 150);
  const alle = hentAlle("/issues?state=open&per_page=100").concat(hentAlle("/issues?state=closed&per_page=100" +
    "&sort=updated&direction=desc&since=" + siden.toISOString().replace(/\.\d{3}Z$/, "Z")));
  const ud = alle.filter(function (i) { return !i.pull_request; }).map(tilSiden);
  const tekst = JSON.stringify(ud);
  if (tekst.length < 95000) cache.put("liste", tekst, 30);
  return ud;
}

// ================================================================== tjek af det, siden sender
function konfig() {
  const cache = CacheService.getScriptCache();
  const gemt = cache.get("konfig");
  if (gemt) return JSON.parse(gemt);
  const k = { medlemmer: [], asapDage: 7 };
  try {
    const r = UrlFetchApp.fetch(SIDE + "config.js?t=" + Date.now(), { muteHttpExceptions: true });
    if (r.getResponseCode() === 200) {
      const t = r.getContentText("UTF-8");
      const re = /["']?navn["']?\s*:\s*["']([^"']+)["']/g;
      let m;
      while ((m = re.exec(t))) if (m[1].trim()) k.medlemmer.push(m[1].trim());
      const a = /["']?asapDage["']?\s*:\s*(\d+)/.exec(t);
      if (a) k.asapDage = +a[1];
    }
  } catch (e) { /* bruger reserven herunder */ }
  if (!k.medlemmer.length) {
    k.medlemmer = hentLabelNavne().filter(function (n) { return erPersonLabel(n) && !erPuljeLabel(n); }).map(personNavn);
  }
  cache.put("konfig", JSON.stringify(k), 600);
  return k;
}

function findMedlem(navn, medlemmer) {
  const n = lav(String(navn || "").trim());
  if (!n) return null;
  return medlemmer.filter(function (m) { return lav(m) === n; })[0] || null;
}

function validerHvem(hvem, medlemmer) {
  const ud = [];
  for (const n of Array.isArray(hvem) ? hvem : [hvem]) {
    const navn = personNavn(String(n || "").trim()) || String(n || "").trim();
    if (!navn) continue;
    if (erPuljeLabel(navn)) { ud.push(PULJE); continue; }
    const m = findMedlem(navn, medlemmer);
    if (!m) throw navn + " er ikke med i bestyrelsen (config.js).";
    ud.push(m);
  }
  return ud;
}

function validerFrist(f) {
  if (f == null || f === "") return "";
  if (f === "moede") return "moede";
  if (isoTilDato(f)) return f;
  throw "Deadline kunne ikke læses.";
}

// ================================================================== GitHub
function noegle() {
  if (NOEGLE && NOEGLE.indexOf("SÆT-DIN-NØGLE") < 0) return NOEGLE.trim();
  const egenskaber = PropertiesService.getScriptProperties().getProperties() || {};
  if (String(egenskaber.NOEGLE || "").trim()) return String(egenskaber.NOEGLE).trim();
  for (const k in egenskaber) {        // stavet anderledes (fx NØGLE)? Så tag den, der ligner en GitHub-nøgle
    const v = String(egenskaber[k] || "").trim();
    if (/^(github_pat_|ghp_)\w+$/.test(v)) return v;
  }
  throw "Mellemmanden mangler nøglen til GitHub. Den skal ligge under Projektindstillinger → Scriptegenskaber " +
    "som NOEGLE (se README).";
}

function gh(metode, sti, data) {
  const url = /^https:/.test(sti) ? sti : "https://api.github.com/repos/" + REPO + sti;
  const valg = {
    method: metode, muteHttpExceptions: true,
    headers: { Authorization: "Bearer " + noegle(), Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28" }
  };
  if (data !== undefined) { valg.contentType = "application/json"; valg.payload = JSON.stringify(data); }
  const r = UrlFetchApp.fetch(url, valg);
  const kode = r.getResponseCode();
  const tekst = r.getContentText("UTF-8");
  if (kode >= 200 && kode < 300) return tekst ? JSON.parse(tekst) : null;
  let besked = "";
  try { besked = JSON.parse(tekst).message || ""; } catch (e) { besked = tekst.slice(0, 200); }
  if (kode === 401) throw "Nøglen til GitHub virker ikke længere (udløbet eller slettet). Formanden skal lave en ny – se README.";
  if (kode === 403 && /rate limit/i.test(besked)) throw "GitHub har travlt lige nu – prøv igen om lidt.";
  if (kode === 403) throw "Nøglen har ikke lov til det her. Den skal have Issues: Read and write på repoet bestyrelse.";
  if (kode === 404) throw "Fandt ikke opgaven i GitHub.";
  if (kode === 410) throw "Opgaven er slettet i GitHub.";
  if (kode === 422) throw "GitHub afviste ændringen: " + besked;
  throw "GitHub svarede " + kode + (besked ? " (" + besked + ")" : "") + ".";
}

function hentAlle(sti) {
  let ud = [], url = "https://api.github.com/repos/" + REPO + sti;
  for (let side = 0; url && side < 5; side++) {
    const r = UrlFetchApp.fetch(url, {
      muteHttpExceptions: true,
      headers: { Authorization: "Bearer " + noegle(), Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28" }
    });
    if (r.getResponseCode() !== 200) return gh("get", sti);        // giver en forståelig fejl
    ud = ud.concat(JSON.parse(r.getContentText("UTF-8")));
    const h = r.getHeaders();
    const m = /<([^>]+)>;\s*rel="next"/.exec(h.Link || h.link || "");
    url = m ? m[1] : null;
  }
  return ud;
}

function hentLabelNavne(frisk) {
  const cache = CacheService.getScriptCache();
  const gemt = !frisk && cache.get("labels");
  if (gemt) return JSON.parse(gemt);
  const navne = hentAlle("/labels?per_page=100").map(function (l) { return l.name; });
  cache.put("labels", JSON.stringify(navne), 600);
  return navne;
}

// Returnerer labelens præcise navn i GitHub og opretter den (med farve), hvis den mangler
function sikrLabel(navn) {
  const findes = hentLabelNavne().filter(function (n) { return lav(n) === lav(navn); })[0];
  if (findes) return findes;
  const f = erPersonLabel(navn) ? FARVER.person : FARVER[lav(navn)];
  if (f) {
    try {
      gh("post", "/labels", { name: navn, color: f[0], description: f[1] });
    } catch (e) {
      if (!/already_exists|already exists/i.test(String(e))) throw e;
    }
    CacheService.getScriptCache().remove("labels");
  }
  return navn;
}

function tilSiden(i) {
  return {
    number: i.number, title: i.title, body: String(i.body || "").slice(0, 12000), state: i.state,
    state_reason: i.state_reason || null, created_at: i.created_at, closed_at: i.closed_at || null,
    updated_at: i.updated_at, html_url: i.html_url,
    labels: (i.labels || []).map(function (l) { return typeof l === "string" ? l : l.name; }),
    author_association: i.author_association || "OWNER", user: { login: (i.user && i.user.login) || "" }
  };
}

// ================================================================== datoer i Danmark
function idag() { return isoTilDato(Utilities.formatDate(new Date(), TZ, "yyyy-MM-dd")); }
function datoFraTid(stempel) {
  const d = new Date(stempel);
  return isNaN(d) ? idag() : isoTilDato(Utilities.formatDate(d, TZ, "yyyy-MM-dd"));
}
function fejlTekst(err) {
  if (typeof err === "string") return err;
  return "Noget gik galt i mellemmanden: " + (err && err.message ? err.message : String(err));
}

// ================================================================ FÆLLES (start)
// Samme kode står i index.html og i mellemmand.gs – ret begge steder. Reglerne for, hvordan en
// opgave (et issue) ser ud: titel "Book hal (3/10)" eller "Book hal (næste møde)", labels @Navn /
// Bestyrelsen / status, og en logbog nederst i beskrivelsen under **Opdateringer**.
const DAG = 864e5;
const MDR = { jan: 1, feb: 2, mar: 3, apr: 4, maj: 5, jun: 6, jul: 7, aug: 8, sep: 9, okt: 10, nov: 11, dec: 12 };
const PULJE = "Bestyrelsen";                       // label: opgaven kan alle i bestyrelsen tage
const ALLE_NAVNE = ["alle", "bestyrelsen", "hele bestyrelsen", "fælles", "alle i bestyrelsen"];
const LOG_MAERKE = "**Opdateringer**";
const MOEDE_TITEL = "📅 Bestyrelsesmøder";
const MOEDE_LABEL = "møder";
const MOEDE_INTRO = "Datoerne for bestyrelsens møder. Siden bruger dem til deadlines som \"næste møde\" og til " +
  "opfølgningen før hvert møde.\nRet gerne her – én dato pr. linje, fx `- 29/10-2026 kl. 17`. Næste møde kan " +
  "også sættes på [siden](https://brebnhi.github.io/bestyrelse/).";
const STATUSSER = {
  ny:      { navn: "Ikke startet", label: null },
  next:    { navn: "Next up", label: "Next up" },
  igang:   { navn: "I gang", label: "I gang" },
  venter:  { navn: "Venter", label: "Venter" },
  faerdig: { navn: "Færdig", label: null, lukket: true, grund: "completed" },
  droppet: { navn: "Droppet", label: null, lukket: true, grund: "not_planned" }
};
const STATUS_ALIAS = {
  next: ["next up", "next-up", "nextup", "næste", "næste op"],
  igang: ["i gang", "igang", "i-gang", "in progress", "igangværende", "startet"],
  venter: ["venter", "venter på andre", "afventer", "blokeret", "waiting", "blocked"],
  faerdig: ["færdig", "done", "afsluttet", "løst"],
  droppet: ["droppet", "annulleret"]
};
const NAESTE_MOEDE = /(næste|kommende|førstkommende)\s+(bestyrelses)?møde|^\s*n\.?\s?m\.?\s*$|til\s+mødet/i;
const FRIST_ORD = /^(løbende|efter behov|hele sæsonen|sæsonen|fast|kontinuerligt|altid|ved lejlighed|når muligt|når der er tid|ongoing|løbende opgave|hver uge|hver måned|ugentligt|månedligt|årligt|hvert år|næste sæson|inden sæsonstart|sæsonstart|efter jul|efter nytår|generalforsamlingen|inden generalforsamlingen)$/i;
const FRIST_PARENTES = /\s*[(\[]\s*(?:deadline|frist)?\s*:?\s*([^()\[\]]+?)\s*[)\]]\s*$/i;

function lav(s) { return String(s == null ? "" : s).toLocaleLowerCase("da"); }
function midnat(d) { return new Date(d.getFullYear(), d.getMonth(), d.getDate()); }
function plusDage(d, n) { return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n); }
function iso(d) { return d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2); }
function isoTilDato(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(s || ""));
  if (!m) return null;
  const d = new Date(+m[1], +m[2] - 1, +m[3]);
  return d.getMonth() === +m[2] - 1 && d.getDate() === +m[3] ? d : null;
}
function fuldDato(d) { return d.getDate() + "/" + (d.getMonth() + 1) + "-" + d.getFullYear(); }

// Dato uden årstal: samme år som ref – medmindre datoen så ligger mere end 60 dage før, så næste år
function lavDato(d, m, aar, ref) {
  if (!(m >= 1 && m <= 12 && d >= 1 && d <= 31)) return null;
  if (aar != null && aar < 100) aar += 2000;
  if (aar == null) {
    const r = midnat(ref || new Date());
    aar = r.getFullYear();
    if (new Date(aar, m - 1, d) < plusDage(r, -60)) aar += 1;
  }
  const dt = new Date(aar, m - 1, d);
  return dt.getMonth() === m - 1 && dt.getDate() === d ? dt : null;
}
// En dato i starten af teksten: 3/10 · 3/10-26 · 3.10.2026 · 2026-10-03 · 3. okt · 3 oktober 2026
function tolkDato(tekst, ref) {
  const s = lav(String(tekst || "").trim());
  let m = /^(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)/.exec(s);
  if (m) return lavDato(+m[3], +m[2], +m[1], ref);
  m = /^(\d{1,2})\s*[\/.]\s*(\d{1,2})(?:\s*[\/.\-]\s*(\d{4}|\d{2}))?(?!\d)/.exec(s);
  if (m) return lavDato(+m[1], +m[2], m[3] ? +m[3] : null, ref);
  m = /^(\d{1,2})\.?\s*(jan|feb|mar|apr|maj|jun|jul|aug|sep|okt|nov|dec)[a-zæøå]*\.?(?:\s+(\d{4}))?/.exec(s);
  if (m) return lavDato(+m[1], MDR[m[2]], m[3] ? +m[3] : null, ref);
  return null;
}
// En dato et vilkårligt sted i teksten (som robottens find_dato)
function findDato(tekst, ref) {
  const s = lav(tekst);
  let m = /(?:^|[^\d])(\d{4})-(\d{1,2})-(\d{1,2})(?!\d)/.exec(s);
  if (m) return lavDato(+m[3], +m[2], +m[1], ref);
  m = /(?:^|[^\d\/.])(\d{1,2})\s*[\/.]\s*(\d{1,2})(?:\s*[\/.\-]\s*(\d{4}|\d{2}))?(?!\d)/.exec(s);
  if (m) return lavDato(+m[1], +m[2], m[3] ? +m[3] : null, ref);
  m = /(?:^|[^\d])(\d{1,2})\.?\s*(jan|feb|mar|apr|maj|jun|jul|aug|sep|okt|nov|dec)[a-zæøå]*\.?(?:\s+(\d{4}))?/.exec(s);
  if (m) return lavDato(+m[1], MDR[m[2]], m[3] ? +m[3] : null, ref);
  return null;
}

// ---------------------------------------------------------------- labels
function statusFraLabel(navn) {
  const n = lav(navn).replace(/^[^\p{L}\p{N}]+/u, "").replace(/\s+/g, " ").trim();
  for (const id in STATUS_ALIAS) if (STATUS_ALIAS[id].indexOf(n) >= 0) return id;
  return null;
}
function erStatusLabel(navn) { return statusFraLabel(navn) !== null; }
function erPersonLabel(navn) { return /^(?:@|👤)\s*\S/u.test(String(navn || "")); }
function personNavn(label) { return String(label || "").replace(/^(?:@|👤)\s*/u, "").trim(); }
function erPuljeLabel(navn) { return ALLE_NAVNE.indexOf(lav(String(navn || "").trim().replace(/^@\s*/, "").trim())) >= 0; }
function erMoedeIssue(i) {
  const labels = (i.labels || []).map(function (l) { return lav(typeof l === "string" ? l : l.name); });
  return /^\s*📅/u.test(i.title || "") || labels.indexOf(MOEDE_LABEL) >= 0;
}
// ["Ida", "Søren"] -> ["@Ida", "@Søren"] · ["Bestyrelsen"] / [] -> ["Bestyrelsen"]
function personLabels(hvem) {
  const ud = [];
  for (const n of hvem || []) {
    const navn = personNavn(String(n || "").trim()) || String(n || "").trim();
    if (!navn) continue;
    const l = erPuljeLabel(navn) ? PULJE : "@" + navn;
    if (!ud.some(function (x) { return lav(x) === lav(l); })) ud.push(l);
  }
  const navne = ud.filter(function (l) { return l !== PULJE; });
  return navne.length ? navne : [PULJE];
}
function ogListe(navne) {
  return navne.length <= 1 ? navne.join("") : navne.slice(0, -1).join(", ") + " og " + navne[navne.length - 1];
}

// ---------------------------------------------------------------- titler og deadlines
// "Book hal (3/10)" -> { tekst: "Book hal", suffix: " (3/10)", slags: "dato", dato }
// "Book hal (næste møde)" -> slags "moede" · "Opdater siden (løbende)" -> slags "tekst"
function delTitel(titel, ref) {
  const t = String(titel || "").trim();
  const m = FRIST_PARENTES.exec(t);
  if (m && m.index > 0) {
    const indhold = m[1].trim();
    const tekst = t.slice(0, m.index).trim();
    if (NAESTE_MOEDE.test(indhold)) return { tekst: tekst, suffix: " (" + indhold + ")", slags: "moede" };
    const d = tolkDato(indhold, ref);
    if (d) return { tekst: tekst, suffix: " (" + indhold + ")", slags: "dato", dato: d };
    if (FRIST_ORD.test(indhold)) return { tekst: tekst, suffix: " (" + indhold + ")", slags: "tekst", fristTekst: indhold };
  }
  return { tekst: t, suffix: "", slags: null };
}
// deadline: "" (ingen) · "moede" (næste møde) · "2026-10-29"
function fristSuffix(deadline, ref) {
  if (!deadline) return "";
  if (deadline === "moede") return " (næste møde)";
  const d = isoTilDato(deadline);
  if (!d) return "";
  const udenAar = lavDato(d.getDate(), d.getMonth() + 1, null, ref || new Date());
  const sammeAar = udenAar && udenAar.getTime() === d.getTime();
  return " (" + d.getDate() + "/" + (d.getMonth() + 1) + (sammeAar ? "" : "-" + d.getFullYear()) + ")";
}
function fristVist(deadline) {
  if (deadline === "moede") return "næste møde";
  const d = isoTilDato(deadline);
  return d ? d.getDate() + "/" + (d.getMonth() + 1) : "ingen";
}
function renTekst(s, maks) {
  return String(s == null ? "" : s).replace(/<!--|-->/g, "").replace(/[\r\n\t]+/g, " ").replace(/\s+/g, " ")
    .trim().slice(0, maks || 500);
}
function renTitel(s) { return renTekst(s, 200); }

// ---------------------------------------------------------------- logbogen
// "- 19/10-2026 · Ida · Færdig: Hallen er booket" (type uden kolon, tekst efter ": ")
function logLinje(dato, af, type, tekst) {
  return "- " + dato + " · " + renTekst(af, 40).replace(/·/g, "-") + " · " + type + (tekst ? ": " + renTekst(tekst) : "");
}
function medLog(body, linjer) {
  let b = String(body || "").replace(/\s+$/, "");
  if (b.indexOf(LOG_MAERKE) < 0) b = (b ? b + "\n\n" : "") + LOG_MAERKE;
  return b + "\n" + linjer.join("\n");
}
// -> { foer: tekst over logbogen, log: [{ dato, datoTekst, af, type, tekst }] }
function delLog(body) {
  const b = String(body || "").replace(/\r/g, "");
  const i = b.indexOf(LOG_MAERKE);
  if (i < 0) return { foer: b, log: [] };
  const log = [];
  for (const linje of b.slice(i + LOG_MAERKE.length).split("\n")) {
    const m = /^\s*[-*]\s+(\d{1,2})\/(\d{1,2})-(\d{4})\s+·\s+([^·]+?)\s+·\s+([^:]+?)(?::\s*(.*))?\s*$/.exec(linje);
    if (!m) continue;
    const d = new Date(+m[3], +m[2] - 1, +m[1]);
    log.push({ dato: d, datoTekst: m[1] + "/" + m[2], af: m[4].trim(), type: m[5].trim(), tekst: (m[6] || "").trim() });
  }
  return { foer: b.slice(0, i).replace(/\s+$/, ""), log: log };
}

// ---------------------------------------------------------------- én handling på en opgave
// issue: { title, body, labels: [navne], state, state_reason } · d: { handling, … , af }
// nu: { dato: "19/10-2026", ref: datoen opgaven blev oprettet (til "3/10" uden årstal) }
// Returnerer opgaven, som den ser ud bagefter. Kaster en fejltekst, hvis handlingen ikke giver mening.
function anvend(issue, d, nu) {
  let labels = (issue.labels || []).map(function (l) { return typeof l === "string" ? l : l.name; });
  let title = issue.title || "", state = issue.state || "open", grund = issue.state_reason || null;
  const log = [], af = d.af || "Nogen";
  const udenPersoner = function () { return labels.filter(function (l) { return !erPersonLabel(l) && !erPuljeLabel(l); }); };
  const personer = function () {
    return labels.filter(function (l) { return erPersonLabel(l) && !erPuljeLabel(l); }).map(personNavn);
  };
  if (d.handling === "status") {
    const st = STATUSSER[d.status];
    if (!st) throw "Ukendt status: " + d.status;
    labels = labels.filter(function (l) { return !erStatusLabel(l); });
    if (st.label) labels.push(st.label);
    if (st.lukket) { state = "closed"; grund = st.grund; } else { state = "open"; grund = null; }
    log.push(logLinje(nu.dato, af, st.navn, d.tekst));
  } else if (d.handling === "opdatering") {
    if (!renTekst(d.tekst)) throw "Skriv en opdatering.";
    log.push(logLinje(nu.dato, af, "Opdatering", d.tekst));
  } else if (d.handling === "tag") {
    const har = personer();
    if (har.length && !har.some(function (p) { return lav(p) === lav(af); })) throw ogListe(har) + " har allerede taget den 🙂";
    if (!har.length || labels.some(erPuljeLabel)) {
      labels = udenPersoner().concat(["@" + af]);
      log.push(logLinje(nu.dato, af, "Tog opgaven"));
    }
  } else if (d.handling === "slip") {
    if (!personer().some(function (p) { return lav(p) === lav(af); })) throw "Opgaven ligger ikke hos dig.";
    const tilbage = personer().filter(function (p) { return lav(p) !== lav(af); });
    labels = udenPersoner().concat(tilbage.length ? tilbage.map(function (p) { return "@" + p; }) : [PULJE]);
    log.push(logLinje(nu.dato, af, tilbage.length ? "Sprang fra opgaven" : "Lagt tilbage til bestyrelsen"));
  } else if (d.handling === "ret") {
    const dele = delTitel(title, nu.ref);
    const nyTekst = d.hvad != null ? renTitel(d.hvad) || dele.tekst : dele.tekst;
    const nySuffix = d.deadline != null ? fristSuffix(d.deadline, nu.ref) : dele.suffix;
    const aendr = [];
    if (nyTekst !== dele.tekst) aendr.push("tekst");
    if (nySuffix.trim() !== dele.suffix.trim()) aendr.push("deadline → " + (d.deadline ? fristVist(d.deadline) : "ingen"));
    title = nyTekst + nySuffix;
    if (d.hvem) {
      const nye = personLabels(d.hvem);
      const gamle = labels.filter(function (l) { return erPersonLabel(l) || erPuljeLabel(l); });
      const samme = nye.length === gamle.length && nye.every(function (l) {
        return gamle.some(function (g) { return lav(g) === lav(l) || (erPuljeLabel(g) && erPuljeLabel(l)); });
      });
      if (!samme) {
        labels = udenPersoner().concat(nye);
        aendr.push("ansvarlig → " + nye.map(function (l) { return l === PULJE ? PULJE : personNavn(l); }).join(", "));
      }
    }
    if (aendr.length) log.push(logLinje(nu.dato, af, "Rettet", aendr.join(", ")));
  } else {
    throw "Ukendt handling: " + d.handling;
  }
  const unikke = [];
  for (const l of labels) if (!unikke.some(function (x) { return lav(x) === lav(l); })) unikke.push(l);
  return {
    title: title,
    body: log.length ? medLog(issue.body, log) : String(issue.body || ""),
    labels: unikke,
    state: state,
    state_reason: grund
  };
}
// En ny opgave fra siden: { hvad, hvem: [navne], deadline, af, id }
function bygNy(d, nu) {
  return {
    title: renTitel(d.hvad) + fristSuffix(d.deadline, nu.ref),
    body: (d.id ? "<!-- id:" + String(d.id).replace(/[^\w-]/g, "") + " -->\n" : "") + LOG_MAERKE + "\n" +
      logLinje(nu.dato, d.af || "Nogen", "Tilføjet"),
    labels: personLabels(d.hvem),
    state: "open",
    state_reason: null
  };
}

// ---------------------------------------------------------------- mødedatoerne (📅-issuet)
// -> { "2026-10-29": "29/10-2026 kl. 17", … }
function laesMoeder(body, ref) {
  const ud = {};
  for (const linje of String(body || "").replace(/\r/g, "").split("\n")) {
    const m = /^\s*[-*]\s+(.+)$/.exec(linje);
    if (!m) continue;
    const d = findDato(m[1], ref || new Date());
    if (d) ud[iso(d)] = m[1].trim();
  }
  return ud;
}
function skrivMoeder(datoer) {
  return MOEDE_INTRO + "\n\n" + Object.keys(datoer).sort().map(function (k) { return "- " + datoer[k]; }).join("\n") + "\n";
}
// Næste møde sat til dato (fjerner møder fra i dag og frem til den dato, og det møde der flyttes)
function opdaterMoeder(datoer, dato, erstat, tid, idag) {
  const ud = {};
  for (const k in datoer) ud[k] = datoer[k];
  if (erstat) delete ud[iso(erstat)];
  if (dato) {
    for (const k of Object.keys(ud)) {
      const d = isoTilDato(k);
      if (d && d >= midnat(idag) && d < dato) delete ud[k];
    }
    const t = /^(\d{1,2}):(\d{2})$/.exec(String(tid || ""));
    ud[iso(dato)] = fuldDato(dato) + (t ? " kl. " + (+t[1]) + (t[2] === "00" ? "" : "." + t[2]) : "");
  }
  return ud;
}
// ================================================================ FÆLLES (slut)
