"use strict";

const PRODUCTS = {
  content_manager: ["IBM Content Manager", 2],
  content_navigator: ["IBM Content Navigator", 3],
  daeja_viewone_virtual: ["IBM Daeja ViewONE Virtual", 3],
  db2: ["IBM Db2", 3],
  ibm_java: ["IBM SDK, Java Technology Edition", 2],
  iccsap: ["IBM Content Collector for SAP", 4],
  websphere: ["IBM WebSphere Application Server", 3]
};
const MAX_BYTES = 10 * 1024 * 1024;
const FRESH_HOURS = 72;
const own = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
const object = value => value !== null && typeof value === "object" && !Array.isArray(value);
const result = (code, label, reason) => ({code, label, reason});

function versionParts(value) {
  if (typeof value !== "string" || !/^\d+(?:\.\d+){1,5}$/.test(value.trim())) return null;
  const parts = value.trim().split(".").map(Number);
  return parts.every(Number.isSafeInteger) ? parts : null;
}

function compareVersions(a, b) {
  const x = versionParts(a), y = versionParts(b);
  if (!x || !y) return null;
  for (let n = 0; n < Math.max(x.length, y.length); n++) {
    const difference = (x[n] || 0) - (y[n] || 0);
    if (difference) return difference < 0 ? -1 : 1;
  }
  return 0;
}

function integer(value) {
  if (!((typeof value === "number" && Number.isSafeInteger(value)) || (typeof value === "string" && /^\d+$/.test(value)))) return null;
  const number = Number(value);
  return Number.isSafeInteger(number) && number >= 0 ? number : null;
}

function ifixLevel(p) {
  const explicit = integer(p.interim_fix);
  const match = String(p.build_level || "").match(/^icn(\d+)\.(\d+)\.\d+$/i);
  if (match) {
    const parts = versionParts(p.version);
    if (!parts || parts.slice(0, 3).join("") !== match[1]) return null;
    const inferred = integer(match[2]);
    if (p.interim_fix != null && explicit !== inferred) return null;
    return inferred;
  }
  return explicit;
}

function freshness(entry, catalog, now) {
  if (entry.refresh_error) return "Die Quelle konnte nicht aktualisiert werden; der bisherige Stand bleibt erhalten.";
  const evidence = entry.availability_evidence;
  const date = evidence && evidence.kind === "operator_confirmed"
    ? (evidence.checked_at ? evidence.checked_at + "T00:00:00Z" : null)
    : entry.refreshed_at || catalog.generated_at;
  if (typeof date !== "string" || !/^\d{4}-\d\d-\d\dT/.test(date)) return "Das Abrufdatum der IBM-Daten fehlt.";
  const timestamp = Date.parse(date);
  if (!Number.isFinite(timestamp) || timestamp > now + 300000) return "Das Katalogdatum fehlt, ist ungültig oder liegt in der Zukunft.";
  if (now - timestamp > FRESH_HOURS * 3600000) return "Die Daten sind älter als 72 Stunden. Prüfen Sie die IBM-Quelle oder öffnen Sie einen aktuellen Katalog.";
  return "";
}

// iFixes are independent records. Package prefixes never define applicability.
function fixAssociations(entry, installedVersion, targetVersion) {
  return (Array.isArray(entry && entry.interim_fixes) ? entry.interim_fixes : []).filter(object).map(fix => {
    const range = fix.applies_to || {};
    function inRange(version) {
      const low = compareVersions(version, range.min), high = compareVersions(version, range.max);
      return low === null || high === null ? null : low >= 0 && high <= 0;
    }
    return {fix, installed:inRange(installedVersion), target:inRange(targetVersion)};
  });
}

function downloadFor(id, entry, installed) {
  const base = ibmUrl(entry && entry.download_url);
  if (!base || id !== "websphere" || !installed || !/^9\.0\.5\.\d+$/.test(installed.version || "")) return base;
  const url = new URL(base);
  url.searchParams.set("release", installed.version);
  return url.href;
}

function compareProduct(id, installed, entry, catalog, now = Date.now()) {
  if (!installed) return result("empty", "Keine Inventardaten", "Öffnen Sie die Datei vom Server. Ein fehlender Eintrag beweist nicht, dass das Produkt nicht installiert ist.");
  if (!entry || !object(entry.available) || !own(PRODUCTS, id)) return result("review", "Kein Katalogeintrag", "Für diesen Eintrag wird eine eigene IBM-Quelle benötigt.");
  const stale = freshness(entry, catalog, now);
  if (stale) return result("stale", "Katalog prüfen", stale);
  if (installed._discoveryError) return result("error", "Fehler bei der Erfassung", installed._discoveryError);
  if (entry.support_status === "not_supported") return result("review", "Versionslinie nicht unterstützt", "Prüfen Sie den Supportstatus bei IBM.");
  const available = entry.available;
  const x = versionParts(installed.version), y = versionParts(available.version);
  if (!x || !y) return result("review", "Vergleich nicht möglich", "Für den Vergleich werden eindeutige numerische Produktversionen benötigt.");
  const streamLength = PRODUCTS[id][1];
  if (x.slice(0, streamLength).join(".") !== y.slice(0, streamLength).join(".")) {
    return result("different", "Andere Versionslinie", "Der Katalog bezieht sich auf " + y.slice(0, streamLength).join(".") + "; die Anwendbarkeit eines Wechsels ist nicht geklärt.");
  }
  const base = compareVersions(installed.version, available.version);
  if (base > 0) return result("different", "Neuer als Katalog", "Der erfasste Stand ist neuer als der Katalogstand. Ein Downgrade wird nicht vorgeschlagen.");
  if (base < 0) return result("update", "Neuerer Stand verfügbar", "Prüfen Sie vor der Installation die Plattform und die IBM-Voraussetzungen.");
  if (id === "content_manager") return result("review", "Fix Pack gleich · iFix prüfen", "Die Erfassung über cmlevel bestätigt keine einzelnen Interim Fixes.");
  if (id === "websphere") return result("level", "Fix Pack stimmt überein", "Die Basis stimmt überein. Nicht kumulative iFixes unten einzeln prüfen; daraus folgt kein vollständig aktueller Patchstand.");
  if (id === "db2") {
    if (typeof installed.special_build === "string" && installed.special_build === available.special_build) return result("match", "Update stimmt überein", "Der Stand stimmt mit dem veröffentlichten Update überein. Individuelle APARs wurden nicht separat geprüft.");
    return result("review", "Special Build prüfen", "Special-Build-Nummern werden nicht numerisch geordnet. Prüfen Sie den Inhalt anhand der IBM-Angaben.");
  }
  if (id === "iccsap") {
    const jre = compareVersions(installed.jre_version, available.jre_version);
    if (jre === null) return result("review", "Mitgelieferte JRE prüfen", "Das Inventar enthält keine gemessene JRE-Version. Datumsangaben in JRE_fix ersetzen keine Versionsnummer.");
    return jre < 0 ? result("update", "JRE-Update verfügbar", "Verwenden Sie das ICCSAP-Paket aus dem IBM-Bulletin.") : jre > 0 ? result("different", "JRE neuer als Katalog", "Der Inhalt des installierten Pakets muss geprüft werden.") : result("review", "JRE gleich · Binaries-iFixes prüfen", "IF21 und weitere Binaries-iFixes werden unabhängig von der JRE geprüft. Ein höherer IF ersetzt andere nicht automatisch.");
  }
  if (id === "content_navigator" || id === "daeja_viewone_virtual") {
    const ix = ifixLevel(installed), iy = integer(available.interim_fix);
    if (ix === null || iy === null) return result("review", "iFix-Stand prüfen", "Die iFix-Nummer fehlt oder widerspricht dem Build-Level.");
    if (id === "daeja_viewone_virtual" && installed.source === "ecmclient_version_txt") return result("review", "In ICN enthalten", "Prüfen Sie die Daeja-Version im ausgewählten ICN-Paket.");
    if (ix > iy) return result("different", "iFix neuer als Katalog", "Prüfen Sie eine aktuellere IBM-Quelle.");
    if (ix < iy) return result("update", "Neuerer iFix verfügbar", "Bekannt ist iFix " + iy + "; Anwendbarkeit und Abhängigkeiten stehen in der Readme.");
    if (id === "content_navigator" && installed.build_level && available.build_level && String(installed.build_level).toLowerCase() !== String(available.build_level).toLowerCase()) return result("review", "iFix gleich · anderer Build", "Der Build-Level weicht von der IBM-Readme ab; das Paket muss geprüft werden.");
    return result("match", "iFix stimmt überein", "Der angegebene iFix-Stand dieser Versionslinie stimmt überein.");
  }
  return result("match", "Version stimmt überein", "Verglichen wurde ausschließlich der angegebene SDK-Stand.");
}

function validateInventory(value) {
  if (!object(value) || value.schema_version !== 1 || !object(value.host) || !Array.isArray(value.products)) throw Error("Erwartet wird ein Inventar mit schema_version 1, einem host-Objekt und einer products-Liste.");
  if (value.products.length > 1000) throw Error("Die Datei enthält mehr als 1000 Produkte.");
  for (const p of value.products) {
    if (!object(p) || typeof p.id !== "string" || !p.id || p.id.length > 150) throw Error("Jeder products-Eintrag benötigt eine nicht leere id als Zeichenkette.");
    if (p.version != null && typeof p.version !== "string") throw Error("Die Produktversion muss eine Zeichenkette sein.");
    if (p.installed_fixes != null && (!Array.isArray(p.installed_fixes) || !p.installed_fixes.every(v => typeof v === "string"))) throw Error("installed_fixes muss eine Liste von Zeichenketten sein.");
  }
  return value;
}

function validateCatalog(value) {
  if (!object(value) || value.schema_version !== 2 || !object(value.products)) throw Error("Erwartet wird ein Katalog mit schema_version 2 und einem products-Objekt.");
  if (Object.keys(value.products).length > 1000) throw Error("Der Katalog ist zu groß.");
  for (const entry of Object.values(value.products)) {
    if (!object(entry) || (entry.available != null && !object(entry.available))) throw Error("Ungültiger Katalogeintrag.");
  }
  return value;
}

function ibmUrl(value) {
  if (typeof value !== "string") return null;
  try {
    const url = new URL(value);
    if (url.protocol !== "https:" || url.username || url.password || (url.port && url.port !== "443")) return null;
    if (url.hostname !== "ibm.com" && !url.hostname.endsWith(".ibm.com")) return null;
    return url.href;
  } catch (error) { return null; }
}

function matchingNote(id, entry, notes) {
  if (!entry || !object(entry.available) || !object(notes.products) || !own(notes.products, id)) return null;
  const note = notes.products[id];
  const same = Object.entries(note.for_available || {}).every(([key, value]) => key === "version" ? compareVersions(entry.available[key], value) === 0 : String(entry.available[key]) === String(value));
  return same ? note : null;
}

// Display ICCSAP fix identifiers only from its own package's Fixes section.
// Never infer a Java version from a date, another package, or rollback history.
function iccsapFixes(inventory) {
  const im = inventory.installation_manager;
  if (!object(im)) return [];
  if (Array.isArray(im.packages)) {
    const packages = im.packages.filter(p => object(p) && p.package_id === "com.ibm.im.iccsap.offering");
    return packages.length === 1 && Array.isArray(packages[0].fixes) ? packages[0].fixes.filter(v => typeof v === "string") : [];
  }
  if (!Array.isArray(im.packages_raw)) return [];
  let current = null, section = "", groups = [];
  for (const raw of im.packages_raw) {
    const line = String(raw).trim(), low = line.toLowerCase();
    if (["[package]", "[paket]", "[package group]", "[paketgruppe]"].includes(low)) {
      if (current) groups.push(current);
      current = ["[package]", "[paket]"].includes(low) ? {id:"", fixes:[]} : null;
      section = "";
    } else if (current && /^name\s*:/i.test(line)) {
      const match = line.match(/\(([^()]+)\)\s*$/);
      current.id = match ? match[1] : "";
    } else if (low === "fixes:") section = "fixes";
    else if (["rollback versions:", "rollbackversionen:", "features:", "komponenten:"].includes(low)) section = "other";
    else if (current && section === "fixes" && line && !line.includes(":") && !["none", "keine"].includes(low)) current.fixes.push(line);
  }
  if (current) groups.push(current);
  groups = groups.filter(p => p.id === "com.ibm.im.iccsap.offering");
  return groups.length === 1 ? groups[0].fixes : [];
}

function rowsFor(inventory, catalog) {
  const products = inventory ? inventory.products.map(p => ({...p})) : [];
  for (const p of products) {
    const discoveryId = p.id === "ibm_java" ? "websphere" : p.id === "daeja_viewone_virtual" ? "content_navigator" : p.id;
    const discovery = inventory.discovery && inventory.discovery[discoveryId];
    if (object(discovery) && discovery.status && !["ok", "skipped"].includes(discovery.status)) p._discoveryError = "Collector-Status: " + discovery.status + ". Die Daten dieses Eintrags können unvollständig sein.";
    if (p.id === "iccsap" && !p.installed_fixes && products.filter(x => x.id === "iccsap").length === 1) p.installed_fixes = iccsapFixes(inventory);
  }
  const rows = [];
  for (const id of Object.keys(PRODUCTS)) {
    const matches = products.filter(p => p.id === id);
    if (matches.length) for (const installed of matches) rows.push({id, installed, entry:catalog.products[id]});
    else rows.push({id, installed:null, entry:catalog.products[id]});
  }
  for (const installed of products.filter(p => !own(PRODUCTS, p.id))) rows.push({id:installed.id, installed, entry:catalog.products[installed.id]});
  return rows;
}

function startApp() {
  const $ = id => document.getElementById(id);
  let catalog = validateCatalog(JSON.parse($("catalog-data").textContent));
  const initial = JSON.parse($("inventory-data").textContent);
  let inventory = initial === null ? null : validateInventory(initial);
  const notes = JSON.parse($("notes-data").textContent);
  let inventoryName = "", catalogName = "eingebettet";
  const el = (tag, text, className) => { const node = document.createElement(tag); if (text !== undefined) node.textContent = String(text); if (className) node.className = className; return node; };
  const date = value => { const stamp = Date.parse(value); return Number.isFinite(stamp) ? new Date(stamp).toLocaleString("de-DE", {timeZone:"UTC", year:"numeric", month:"2-digit", day:"2-digit", hour:"2-digit", minute:"2-digit"}) + " UTC" : "kein Datum angegeben"; };
  function link(label, url, primary) {
    const safe = ibmUrl(url);
    if (!safe) return null;
    const a = el("a", label, primary ? "download" : "");
    a.href = safe; a.target = "_blank"; a.rel = "noopener noreferrer";
    return a;
  }
  function cell(row, label, content) { const td = el("td"); td.dataset.label = label; td.append(content); row.append(td); }
  function metadata(parent, text) { if (text) parent.append(el("span", text, "metadata")); }
  function render() {
    const now = Date.now();
    $("catalog-date").textContent = "Katalog: " + date(catalog.generated_at) + " · " + catalogName + " · IBM-Hinweise: " + notes.checked_at;
    $("clear-inventory").hidden = !inventory;
    $("inventory-title").textContent = inventory ? inventory.context_only ? "Versionsstand aus der bereitgestellten Beschreibung" : "Inventarstand: " + (inventory.host.hostname || "kein Servername angegeben") : "IBM-Katalog · 7 Hauptprodukte";
    $("inventory-meta").textContent = inventory ? inventory.context_only ? "Dies sind die zuvor angegebenen Versionen. Es wurde kein neuer Scan ausgeführt. Öffnen Sie eine aktuelle inventory.json für einen neuen Vergleich." : [inventoryName, "Erfasst: " + date(inventory.timestamp), inventory.host.machine, inventory.host.os_release && inventory.host.os_release.PRETTY_NAME].filter(Boolean).join(" · ") : "Öffnen Sie inventory.json für den Vergleich mit Ihrem Server. Der Katalog ist auch ohne Inventar nutzbar.";
    const warnings = [];
    const badEntries = Object.values(catalog.products).filter(e => freshness(e, catalog, now));
    if (badEntries.length) warnings.push("Für " + badEntries.length + " Einträge ist der Katalog veraltet, undatiert oder die Quelle nicht erreichbar. Die Stände dienen zur Orientierung.");
    if (now - Date.parse(notes.checked_at + "T00:00:00Z") > FRESH_HOURS * 3600000) warnings.push("Die IBM-Hinweise vom " + notes.checked_at + " müssen erneut geprüft werden, auch wenn catalog.json inzwischen aktualisiert wurde.");
    if (inventory && !inventory.context_only) {
      const stamp = Date.parse(inventory.timestamp);
      if (!Number.isFinite(stamp) || stamp > now + 300000 || now - stamp > FRESH_HOURS * 3600000) warnings.push("Das Inventar hat kein verlässliches aktuelles Erfassungsdatum. Verglichen werden die Werte aus der Datei; der aktuelle Serverzustand wurde nicht abgefragt.");
    }
    $("freshness").hidden = !warnings.length; $("freshness").textContent = warnings.join(" ");
    $("products").replaceChildren();
    const counts = {update:0, review:0, match:0};
    const rows = rowsFor(inventory, catalog);
    for (const row of rows) {
      const {id, installed:p, entry:e} = row, target = e && e.available || {};
      const note = matchingNote(id, e, notes);
      const status = compareProduct(id, p, e, catalog, now);
      if (status.code === "update") counts.update++;
      else if (["match", "level"].includes(status.code)) counts.match++;
      else if (p) counts.review++;
      const tr = el("tr");
      const product = el("div", undefined, "cell-content");
      product.append(el("strong", own(PRODUCTS, id) ? PRODUCTS[id][0] : p.name || id, "product-name"));
      const parts = versionParts(target.version);
      if (parts && own(PRODUCTS, id)) product.append(el("span", "Versionslinie " + parts.slice(0, PRODUCTS[id][1]).join("."), "stream"));
      if (p && p.installation_directory) metadata(product, p.installation_directory);
      cell(tr, "Produkt", product);
      const installedCell = el("div", undefined, "cell-content");
      installedCell.append(el("span", p ? p.version || "Version unbekannt" : "—", "version"));
      if (p) {
        const ix = ifixLevel(p);
        if (ix !== null) metadata(installedCell, "iFix " + ix);
        for (const text of [p.build_level, p.special_build, p.build && "Build " + p.build, p.jre_version && "JRE " + p.jre_version]) metadata(installedCell, text);
        const fixes = (p.installed_fixes || []).filter(v => /JRE_fix_\d{8}/i.test(v));
        if (fixes.length) metadata(installedCell, fixes.map(v => v.match(/JRE_fix_\d{8}/i)[0]).join(" · "));
      }
      cell(tr, "Installiert", installedCell);
      const availableCell = el("div", undefined, "cell-content");
      const targetText = [target.version, target.interim_fix != null ? "iFix " + target.interim_fix : "", target.jre_version ? "+ JRE " + target.jre_version : ""].filter(Boolean).join(" ") || "Keine Daten";
      availableCell.append(el("span", targetText, "version"));
      metadata(availableCell, target.special_build);
      if (note) metadata(availableCell, note.availability_note);
      if (e) {
        const evidence = e.availability_evidence;
        if (evidence && evidence.kind === "operator_confirmed") metadata(availableCell, "Paketverfügbarkeit vom Betreiber bestätigt: " + (evidence.checked_at || "Datum fehlt"));
        metadata(availableCell, (evidence && evidence.kind === "operator_confirmed" ? "Katalogabgleich: " : "Quelle abgerufen: ") + date(e.refreshed_at || catalog.generated_at));
      }
      if (note) {
        const details = el("details", undefined, "product-notes");
        details.append(el("summary", "Voraussetzungen und Hinweise"));
        for (const text of note.notes) details.append(el("p", text));
        details.append(el("p", "Hinweise geprüft am: " + (note.checked_at || notes.checked_at), "muted"));
        availableCell.append(details);
      }
      for (const association of fixAssociations(e, p && p.version, target.version)) {
        const f = association.fix;
        const block = el("div", undefined, "product-notes");
        block.append(el("strong", f.fix_id || "Unbekannter iFix"));
        metadata(block, "Nicht kumulativ · " + (f.filename || ""));
        if (association.target === false) metadata(block, "Kein Paket für die Zielbasis " + target.version + "; enthaltene APARs separat prüfen.");
        const range = f.applies_to || {};
        metadata(block, "Basisbereich: " + (range.min || "unbekannt") + " bis " + (range.max || "unbekannt"));
        if (p) metadata(block, "Installierte Basis: " + (association.installed === null ? "Zuordnung ungeprüft" : association.installed ? "im Versionsbereich" : "außerhalb des Versionsbereichs"));
        metadata(block, "Katalog-Zielbasis: " + (association.target === null ? "Zuordnung ungeprüft" : association.target ? "im Versionsbereich" : "außerhalb des Versionsbereichs"));
        metadata(block, "iFix im Inventar: " + (p && (p.installed_fixes || []).some(value => value === f.fix_id || value === f.apar) ? "Kennung vorhanden; Paketstand prüfen" : "nicht eindeutig nachgewiesen"));
        metadata(block, "iFix-Quelle geprüft: " + (f.checked_at || "unbekannt"));
        if (!f.checked_at || now - Date.parse(f.checked_at + "T00:00:00Z") > FRESH_HOURS * 3600000) metadata(block, "iFix-Quelle erneut prüfen; ein Basisabruf aktualisiert diese Prüfung nicht.");
        if (f.note) metadata(block, f.note);
        const source = link("IBM-Paket / Voraussetzungen", f.source_url);
        if (source) block.append(source);
        availableCell.append(block);
      }
      cell(tr, "Bei IBM bestätigt", availableCell);
      const statusCell = el("div", undefined, "cell-content");
      statusCell.append(el("span", status.label, "status " + status.code), el("p", status.reason, "reason"));
      cell(tr, "Vergleich", statusCell);
      const actions = el("div", undefined, "cell-content links");
      const links = note ? note.links.slice() : [];
      if (e && e.fix_pack_url) links.unshift({label:"Fix Pack " + target.version + " · Paket auswählen", url:e.fix_pack_url, download:true});
      if (e && e.source_url && !links.some(l => l.url === e.source_url)) links.push({label:"IBM-Quelle des Katalogs", url:e.source_url});
      const download = downloadFor(id, e, p);
      if (download && !links.some(l => l.url === download)) links.unshift({label:"Fix Central · installierte Basis und Updates", url:download, download:true});
      for (const item of links) { const a = link(item.label, item.url, item.download); if (a) actions.append(a); }
      if (!actions.childNodes.length) actions.append(el("span", "Keine Quelle angegeben", "metadata"));
      cell(tr, "Quellen und Downloads", actions);
      $("products").append(tr);
    }
    $("summary").textContent = inventory ? counts.update + " — neuerer Stand · " + counts.review + " — prüfen · " + counts.match + " — übereinstimmend" : "Bekannte Versionsstände und offizielle IBM-Seiten";
  }
  async function readFile(input, kind) {
    const file = input.files[0];
    if (!file) return;
    try {
      if (file.size > MAX_BYTES) throw Error("Die JSON-Datei darf höchstens 10 MiB groß sein.");
      const value = JSON.parse((await file.text()).replace(/^\uFEFF/, ""));
      if (kind === "inventory") { validateInventory(value); inventory = value; inventoryName = file.name; }
      else { validateCatalog(value); catalog = value; catalogName = file.name; }
      $("error").hidden = true; $("error").textContent = ""; render();
    } catch (error) {
      $("error").textContent = "Die Datei konnte nicht geladen werden: " + error.message + " Die bisherigen Daten bleiben erhalten.";
      $("error").hidden = false;
    } finally { input.value = ""; }
  }
  $("load-inventory").addEventListener("click", () => $("inventory-file").click());
  $("inventory-file").addEventListener("change", event => readFile(event.target, "inventory"));
  $("load-catalog").addEventListener("click", () => $("catalog-file").click());
  $("catalog-file").addEventListener("change", event => readFile(event.target, "catalog"));
  $("clear-inventory").addEventListener("click", () => { inventory = null; inventoryName = ""; render(); });
  render();
}

if (typeof module !== "undefined" && module.exports) module.exports = {versionParts, compareVersions, ifixLevel, freshness, compareProduct, validateInventory, validateCatalog, ibmUrl, matchingNote, iccsapFixes, rowsFor, fixAssociations, downloadFor};
if (typeof document !== "undefined") {
  try { startApp(); } catch (error) {
    const target = document.getElementById("error");
    target.textContent = "Die eingebetteten Daten konnten nicht geöffnet werden: " + error.message;
    target.hidden = false;
  }
}
