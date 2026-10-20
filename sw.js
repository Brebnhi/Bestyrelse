// Bestyrelsens opgaver – service worker. Gør, at siden kan ligge på hjemmeskærmen som en app og åbne
// uden net. Siden hentes altid frisk, når der er net (så en ny version ses med det samme); uden net – eller
// hvis nettet er meget langsomt – bruges den gemte. Opslag hos GitHub og mellemmanden røres ikke.
const CACHE = "bestyrelsen-v2";
const FILER = ["./", "index.html", "config.js", "manifest.webmanifest", "ikoner/ikon.svg",
  "ikoner/ikon-192.png", "ikoner/apple-touch-icon.png"];

self.addEventListener("install", function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(FILER); }).catch(function () {}));
  self.skipWaiting();
});

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (navne) {
    return Promise.all(navne.filter(function (n) { return n !== CACHE; }).map(function (n) { return caches.delete(n); }));
  }).then(function () { return self.clients.claim(); }));
});

function fraLager(req) {
  return caches.match(req, { ignoreSearch: true }).then(function (m) { return m || caches.match("./"); });
}

self.addEventListener("fetch", function (e) {
  const req = e.request;
  if (req.method !== "GET" || new URL(req.url).origin !== self.location.origin) return;
  const net = fetch(req, { cache: "no-cache" }).then(function (svar) {
    if (svar && svar.ok) {
      const kopi = svar.clone();
      caches.open(CACHE).then(function (c) { c.put(req, kopi); });
    }
    return svar;
  });
  if (req.mode === "navigate") {
    // Siden selv: frisk fra nettet, men højst 4 sekunders ventetid, hvis der ligger en gemt udgave
    e.respondWith(new Promise(function (ok) {
      let svaret = false;
      const tid = setTimeout(function () {
        fraLager(req).then(function (m) { if (m && !svaret) { svaret = true; ok(m); } });
      }, 4000);
      net.then(function (svar) { clearTimeout(tid); if (!svaret) { svaret = true; ok(svar); } })
        .catch(function () { clearTimeout(tid); fraLager(req).then(function (m) { if (!svaret) { svaret = true; ok(m || Response.error()); } }); });
    }));
    return;
  }
  e.respondWith(net.catch(function () { return fraLager(req); }));
});
