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

// Hide packages outside the target range; retain unknown ranges for review.
function visibleFixAssociations(entry, installedVersion, targetVersion) {
  return fixAssociations(entry, installedVersion, targetVersion).filter(a => a.target !== false);
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
  if (installed._discoveryError) return result("error", "Erfassung fehlgeschlagen", installed._discoveryError);
  if (id === "daeja_viewone_virtual" && installed.source === "ecmclient_version_txt") return result("review", "In ICN enthalten", "Diese Komponente wird mit ICN geliefert. Den Stand im ICN-Paket prüfen.");
  if (!entry || !object(entry.available) || !own(PRODUCTS, id)) return result("review", "Kein Katalogeintrag", "Für diesen Eintrag wird eine eigene IBM-Quelle benötigt.");
  const stale = freshness(entry, catalog, now);
  if (stale) return result("stale", "Katalog prüfen", stale);
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
    if (ix > iy) return result("different", "iFix neuer als Katalog", "Prüfen Sie eine aktuellere IBM-Quelle.");
    if (ix < iy) return result("update", "Neuerer iFix verfügbar", "Bekannt ist iFix " + iy + "; Anwendbarkeit und Abhängigkeiten stehen in der Readme.");
    if (id === "content_navigator" && installed.build_level && available.build_level && String(installed.build_level).toLowerCase() !== String(available.build_level).toLowerCase()) return result("review", "iFix gleich · anderer Build", "Der Build-Level weicht von der IBM-Readme ab; das Paket muss geprüft werden.");
    return result("match", "iFix stimmt überein", "Der angegebene iFix-Stand dieser Versionslinie stimmt überein.");
  }
  return result("match", "Version stimmt überein", "Verglichen wurde ausschließlich der angegebene SDK-Stand.");
}

function validateInventory(value) {
  if (!object(value) || value.schema_version !== 1 || !object(value.host) || !Array.isArray(value.products)) throw Error("Erwartet wird ein Inventar mit schema_version 1, einem host-Objekt und einer products-Liste.");
  for (const field of ["discovery", "installation_manager"]) {
    if (value[field] != null && !object(value[field])) throw Error(field + " muss ein Objekt sein.");
  }
  if (value.host.os_release != null && !object(value.host.os_release)) throw Error("host.os_release muss ein Objekt sein.");
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
    if (entry.available && entry.available.version != null && typeof entry.available.version !== "string") throw Error("Die Katalogversion muss eine Zeichenkette sein.");
    if (entry.available) {
      for (const field of ["build_level", "special_build", "jre_version"]) if (entry.available[field] != null && typeof entry.available[field] !== "string") throw Error("Katalogfeld " + field + " muss eine Zeichenkette sein.");
      for (const field of ["interim_fix", "fix_pack"]) if (entry.available[field] != null && integer(entry.available[field]) === null) throw Error("Katalogfeld " + field + " muss eine nicht negative Ganzzahl sein.");
    }
    if (entry.availability_evidence != null && !object(entry.availability_evidence)) throw Error("Ungültiger Herkunftsnachweis im Katalog.");
    if (entry.interim_fixes != null) {
      if (!Array.isArray(entry.interim_fixes) || entry.interim_fixes.length > 1000) throw Error("interim_fixes muss eine Liste mit höchstens 1000 Einträgen sein.");
      for (const fix of entry.interim_fixes) {
        if (!object(fix) || (fix.applies_to != null && !object(fix.applies_to))) throw Error("Ungültiger iFix-Eintrag oder Versionsbereich.");
        for (const field of ["fix_id", "apar", "filename", "source_url", "checked_at", "note"]) {
          if (fix[field] != null && typeof fix[field] !== "string") throw Error("iFix-Feld " + field + " muss eine Zeichenkette sein.");
        }
      }
    }
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
  const grouped = new Map();
  for (const original of inventory ? inventory.products : []) {
    const p = {...original};
    const list = grouped.get(p.id) || [];
    list.push(p); grouped.set(p.id, list);
  }
  const rows = [];
  for (const id of [...Object.keys(PRODUCTS), ...[...grouped.keys()].filter(id => !own(PRODUCTS, id))]) {
    const discoveryId = id === "ibm_java" ? "websphere" : id === "daeja_viewone_virtual" ? "content_navigator" : id;
    const discovery = inventory && inventory.discovery && inventory.discovery[discoveryId];
    const matches = grouped.get(id) || [];
    if (id === "iccsap" && matches.length === 1 && !matches[0].installed_fixes) matches[0].installed_fixes = iccsapFixes(inventory);
    for (const p of matches.length ? matches : [null]) {
      if (p && object(discovery) && discovery.status && !["ok", "skipped"].includes(discovery.status)) p._discoveryError = "Collector-Status: " + discovery.status + ". Die Erfassung ist unvollständig.";
      rows.push({id, installed:p, entry:own(catalog.products, id) ? catalog.products[id] : null, discovery});
    }
  }
  return rows;
}

function rowStatus(row, inventory, catalog, now = Date.now()) {
  if (inventory && !row.installed) {
    const discovery = row.discovery;
    if (object(discovery) && discovery.status && !["ok", "skipped", "not_found"].includes(discovery.status)) {
      return result("error", "Erfassung fehlgeschlagen", "Collector-Status: " + discovery.status + (discovery.path ? " · " + discovery.path : "") + ". Erfassung auf dem Server prüfen.");
    }
    return result("empty", "Nicht erkannt", "Das Inventar enthält keinen Produkteintrag." + (discovery && discovery.path ? " Geprüfter Pfad: " + discovery.path + "." : "") + " Dies bestätigt keine Deinstallation.");
  }
  return compareProduct(row.id, row.installed, row.entry, catalog, now);
}

const REVIEW_CODES = new Set(["review", "stale", "error", "different"]);
function filteredRows(rows, query = "", filter = "all") {
  const needle = query.trim().toLocaleLowerCase("de-DE");
  return rows.filter(row => {
    const p = row.installed || {};
    const text = [row.id, own(PRODUCTS, row.id) ? PRODUCTS[row.id][0] : p.name, p.version, p.installation_directory, row.entry && row.entry.available && row.entry.available.version].join(" ").toLocaleLowerCase("de-DE");
    const code = row.status.code;
    return (!needle || text.includes(needle)) && (filter === "all" || filter === "attention" && (code === "update" || REVIEW_CODES.has(code)) || filter === "update" && code === "update" || filter === "review" && REVIEW_CODES.has(code) || filter === "match" && ["match", "level"].includes(code) || filter === "missing" && code === "empty");
  });
}

function linksFor(id, entry, installed, note) {
  const links = [];
  if (entry && entry.fix_pack_url) links.push({label:"Fix Pack " + (entry.available && entry.available.version || "") + " · IBM-Download", url:entry.fix_pack_url, download:true});
  if (note && Array.isArray(note.links)) links.push(...note.links);
  const download = downloadFor(id, entry, installed);
  if (download) links.push({label:id === "websphere" ? "Weitere Fixes zur installierten Basis" : "Pakete in Fix Central", url:download, download:!links.some(l => l.download)});
  if (entry && entry.source_url) links.push({label:"IBM-Quelle des Katalogs", url:entry.source_url});
  const seen = new Set();
  return links.filter(item => {
    const safe = ibmUrl(item.url);
    if (!safe) return false;
    const key = new URL(safe); key.searchParams.sort();
    if (seen.has(key.href)) return false;
    seen.add(key.href); return true;
  });
}

function importPayloads(payloads, state) {
  const next = {...state}, kinds = new Set();
  for (const payload of payloads) {
    const value = payload.value;
    const kind = value && value.schema_version === 1 ? "inventory" : value && value.schema_version === 2 ? "catalog" : null;
    if (!kind) throw Error("Bitte inventory.json (Schema 1) oder catalog.json (Schema 2) auswählen.");
    if (kinds.has(kind)) throw Error("Bitte nur eine Inventardatei und einen Katalog gleichzeitig auswählen.");
    kinds.add(kind);
    next[kind] = kind === "inventory" ? validateInventory(value) : validateCatalog(value);
    next[kind + "Name"] = payload.name;
  }
  return next;
}

function startApp() {
  const $ = id => document.getElementById(id);
  let state = {
    catalog:validateCatalog(JSON.parse($("catalog-data").textContent)),
    inventory:JSON.parse($("inventory-data").textContent),
    catalogName:"eingebettet", inventoryName:""
  };
  if (state.inventory !== null) validateInventory(state.inventory);
  const notes = JSON.parse($("notes-data").textContent);
  let importSequence = 0;
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
    const {catalog, inventory, catalogName, inventoryName} = state;
    const now = Date.now();
    const rows = rowsFor(inventory, catalog).map(row => ({...row, status:rowStatus(row, inventory, catalog, now)}));
    const shown = filteredRows(rows, $("search").value, $("status-filter").value);
    if (inventory) {
      const priority = {update:0,error:1,review:2,stale:2,different:3,match:4,level:4,empty:5};
      shown.sort((a, b) => (priority[a.status.code] ?? 5) - (priority[b.status.code] ?? 5));
    }
    const fragment = document.createDocumentFragment();
    for (const row of shown) {
      const {id, installed:p, entry:e, status} = row, target = e && e.available || {};
      const note = matchingNote(id, e, notes);
      const tr = el("tr"); tr.dataset.status = status.code;
      const product = el("div", undefined, "cell-content");
      product.append(el("strong", own(PRODUCTS, id) ? PRODUCTS[id][0] : p.name || id, "product-name"));
      const parts = versionParts(target.version);
      if (parts && own(PRODUCTS, id)) metadata(product, "Versionslinie " + parts.slice(0, PRODUCTS[id][1]).join("."));
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
      availableCell.append(el("span", [target.version, target.interim_fix != null ? "iFix " + target.interim_fix : "", target.jre_version ? "+ JRE " + target.jre_version : ""].filter(Boolean).join(" ") || "Keine Daten", "version"));
      metadata(availableCell, target.special_build);
      if (target.fix_pack != null) metadata(availableCell, "Fix Pack " + target.fix_pack);
      if (e && e.fix_pack_cumulative) metadata(availableCell, "Kumulativer Fix Pack", "metadata");
      if (e) {
        const evidence = e.availability_evidence;
        metadata(availableCell, evidence && evidence.kind === "operator_confirmed" ? "Paket bestätigt: " + (evidence.checked_at || "Datum fehlt") : "Abgerufen: " + date(e.refreshed_at || catalog.generated_at));
      }
      if (note) {
        const details = el("details", undefined, "product-notes");
        details.append(el("summary", "Voraussetzungen und Hinweise"));
        if (note.availability_note) details.append(el("p", note.availability_note));
        for (const text of note.notes) details.append(el("p", text));
        details.append(el("p", "Hinweise geprüft: " + (note.checked_at || notes.checked_at), "muted"));
        availableCell.append(details);
      }
      const associations = visibleFixAssociations(e, p && p.version, target.version);
      if (associations.length) {
        const group = el("details", undefined, "product-notes ifix-group");
        group.append(el("summary", "iFixes zur Zielbasis (" + associations.length + ")"));
        for (const association of associations) {
          const f = association.fix, range = f.applies_to || {};
          const block = el("div", undefined, "ifix-item");
          block.append(el("strong", f.fix_id || "Unbekannter iFix"));
          metadata(block, "Nicht kumulativ · " + (f.filename || ""));
          metadata(block, "Basisbereich: " + (range.min || "unbekannt") + " bis " + (range.max || "unbekannt"));
          metadata(block, association.target === null ? "Anwendbarkeit ungeprüft" : "Zielbasis im Versionsbereich");
          metadata(block, "Kennung im Inventar: " + (p && (p.installed_fixes || []).some(value => value === f.fix_id || value === f.apar) ? "vorhanden; Paketstand prüfen" : "nicht nachgewiesen"));
          metadata(block, "Quelle geprüft: " + (f.checked_at || "unbekannt"));
          if (!f.checked_at || now - Date.parse(f.checked_at + "T00:00:00Z") > FRESH_HOURS * 3600000) metadata(block, "iFix-Quelle erneut prüfen.");
          if (f.note) metadata(block, f.note);
          const source = link("IBM-Paket und Voraussetzungen", f.source_url);
          if (source) block.append(source);
          group.append(block);
        }
        availableCell.append(group);
      }
      cell(tr, "Bekannter Zielstand", availableCell);
      const statusCell = el("div", undefined, "cell-content");
      statusCell.append(el("span", status.label, "status " + status.code));
      if (inventory) statusCell.append(el("p", status.reason, "reason"));
      cell(tr, "Vergleich", statusCell);
      const actions = el("div", undefined, "cell-content links");
      for (const item of linksFor(id, e, p, note)) { const a = link(item.label, item.url, item.download); if (a) actions.append(a); }
      if (!actions.childNodes.length) actions.append(el("span", "Keine Quelle angegeben", "metadata"));
      cell(tr, "Downloads und Quellen", actions);
      fragment.append(tr);
    }
    $("products").replaceChildren(fragment);
    $("empty-results").hidden = shown.length > 0;
    $("summary").textContent = shown.length + " von " + rows.length + " Produktzeilen";
    const counts = {update:0, review:0, match:0};
    for (const row of rows) {
      if (row.status.code === "update") counts.update++;
      else if (REVIEW_CODES.has(row.status.code)) counts.review++;
      else if (["match", "level"].includes(row.status.code)) counts.match++;
    }
    for (const name of Object.keys(counts)) $("count-" + name).textContent = inventory ? counts[name] : "—";
    for (const card of document.querySelectorAll("[data-filter]")) {
      card.disabled = !inventory;
      card.setAttribute("aria-pressed", String($("status-filter").value === card.dataset.filter));
    }
    $("clear-inventory").hidden = !inventory;
    $("onboarding").hidden = !!inventory;
    $("inventory-title").textContent = inventory ? inventory.context_only ? "Versionen aus einer bereitgestellten Beschreibung" : "Server: " + (inventory.host.hostname || "Name fehlt") : "Inventar laden und Updates vergleichen";
    $("inventory-meta").textContent = inventory ? inventory.context_only ? "Kein neuer Serverscan. Eine aktuelle inventory.json liefert den gemessenen Stand." : [inventoryName, "Erfasst: " + date(inventory.timestamp), inventory.host.machine, inventory.host.os_release && inventory.host.os_release.PRETTY_NAME].filter(Boolean).join(" · ") : "inventory.json auswählen oder hier ablegen. Die Datei bleibt in diesem Browser.";
    $("catalog-date").textContent = "Katalog: " + date(catalog.generated_at) + " · " + catalogName;
    const warnings = [];
    const badEntries = Object.values(catalog.products).filter(e => freshness(e, catalog, now));
    if (badEntries.length) warnings.push(badEntries.length + " Katalogeinträge benötigen eine Quellenprüfung. Ältere Stände bleiben zur Orientierung sichtbar.");
    if (now - Date.parse(notes.checked_at + "T00:00:00Z") > FRESH_HOURS * 3600000) warnings.push("Die ergänzenden IBM-Hinweise vom " + notes.checked_at + " sind älter als 72 Stunden. Für neuere Hinweise die aktuelle HTML-Datei öffnen.");
    if (inventory && !inventory.context_only) {
      const stamp = Date.parse(inventory.timestamp);
      if (!Number.isFinite(stamp) || stamp > now + 300000 || now - stamp > FRESH_HOURS * 3600000) warnings.push("Das Inventar ist undatiert, älter als 72 Stunden oder hat ein Datum in der Zukunft. Angezeigt wird der Stand aus der Datei; für einen aktuellen Vergleich das Inventar auf dem Server neu erstellen.");
    }
    $("refresh-catalog").hidden = badEntries.length === 0;
    $("freshness").hidden = !warnings.length;
    $("freshness-message").textContent = warnings.join(" ");
  }
  async function importFiles(files) {
    if (!files.length) return;
    const sequence = ++importSequence;
    $("load-message").textContent = "Dateien werden geprüft …";
    try {
      if (files.length > 2) throw Error("Bitte höchstens inventory.json und catalog.json gemeinsam ablegen.");
      const payloads = await Promise.all(files.map(async file => {
        if (file.size > MAX_BYTES) throw Error("Jede JSON-Datei darf höchstens 10 MiB groß sein.");
        return {name:file.name, value:JSON.parse((await file.text()).replace(/^\uFEFF/, ""))};
      }));
      if (sequence !== importSequence) return;
      const next = importPayloads(payloads, state), previous = state;
      state = next;
      try { render(); } catch (error) { state = previous; render(); throw error; }
      $("error").hidden = true;
      $("error").textContent = "";
      $("load-message").textContent = payloads.map(p => p.name).join(" und ") + " geladen.";
    } catch (error) {
      if (sequence !== importSequence) return;
      $("error").textContent = "Datei nicht übernommen: " + error.message + " Die bisherigen Daten bleiben erhalten.";
      $("error").hidden = false;
      $("load-message").textContent = "";
    }
  }
  for (const kind of ["inventory", "catalog"]) {
    $("load-" + kind).addEventListener("click", () => $(kind + "-file").click());
    $(kind + "-file").addEventListener("change", event => { importFiles([...event.target.files]); event.target.value = ""; });
  }
  $("clear-inventory").addEventListener("click", () => {
    importSequence++; state = {...state, inventory:null, inventoryName:""};
    $("search").value = ""; $("status-filter").value = "all";
    $("error").hidden = true; $("load-message").textContent = "Inventar entfernt."; render();
  });
  $("search").addEventListener("input", render);
  $("status-filter").addEventListener("change", render);
  $("reset-filter").addEventListener("click", () => { $("search").value = ""; $("status-filter").value = "all"; render(); $("search").focus(); });
  for (const card of document.querySelectorAll("[data-filter]")) card.addEventListener("click", () => { $("status-filter").value = card.dataset.filter; render(); });
  $("print").addEventListener("click", () => window.print());
  $("refresh-catalog").addEventListener("click", () => $("catalog-file").click());
  const zone = $("drop-zone");
  document.addEventListener("dragover", event => { event.preventDefault(); zone.classList.add("drag-active"); });
  document.addEventListener("dragleave", event => { if (!event.relatedTarget) zone.classList.remove("drag-active"); });
  document.addEventListener("drop", event => { event.preventDefault(); zone.classList.remove("drag-active"); importFiles([...event.dataTransfer.files]); });
  render();
}

if (typeof module !== "undefined" && module.exports) module.exports = {versionParts, compareVersions, ifixLevel, freshness, compareProduct, validateInventory, validateCatalog, ibmUrl, matchingNote, iccsapFixes, rowsFor, fixAssociations, visibleFixAssociations, downloadFor, rowStatus, filteredRows, linksFor, importPayloads};
if (typeof document !== "undefined") {
  try { startApp(); } catch (error) {
    const target = document.getElementById("error");
    target.textContent = "Die eingebetteten Daten konnten nicht geöffnet werden: " + error.message;
    target.hidden = false;
  }
}
