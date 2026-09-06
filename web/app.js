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
  if (entry.refresh_error) return "Не удалось обновить источник; сохранён предыдущий уровень.";
  const date = entry.refreshed_at || catalog.generated_at;
  if (typeof date !== "string" || !/^\d{4}-\d\d-\d\dT/.test(date)) return "Не указана дата получения данных IBM.";
  const timestamp = Date.parse(date);
  if (!Number.isFinite(timestamp) || timestamp > now + 300000) return "Дата каталога отсутствует, некорректна или находится в будущем.";
  if (now - timestamp > FRESH_HOURS * 3600000) return "Данные старше 72 часов. Проверьте IBM или откройте свежий каталог.";
  return "";
}

function compareProduct(id, installed, entry, catalog, now = Date.now()) {
  if (!installed) return result("empty", "Нет данных inventory", "Загрузите файл с сервера; отсутствие записи не доказывает отсутствие продукта.");
  if (!entry || !object(entry.available) || !own(PRODUCTS, id)) return result("review", "Нет данных каталога", "Для этой записи нужен отдельный источник IBM.");
  const stale = freshness(entry, catalog, now);
  if (stale) return result("stale", "Проверить каталог", stale);
  if (installed._discoveryError) return result("error", "Ошибка обнаружения", installed._discoveryError);
  if (entry.support_status === "not_supported") return result("review", "Ветка не поддерживается", "Проверьте статус поддержки у IBM.");
  const available = entry.available;
  const x = versionParts(installed.version), y = versionParts(available.version);
  if (!x || !y) return result("review", "Не удалось сравнить", "Нужны точные числовые версии продукта.");
  const streamLength = PRODUCTS[id][1];
  if (x.slice(0, streamLength).join(".") !== y.slice(0, streamLength).join(".")) {
    return result("different", "Другая ветка", "Каталог относится к " + y.slice(0, streamLength).join(".") + "; применимость перехода не определена.");
  }
  const base = compareVersions(installed.version, available.version);
  if (base > 0) return result("different", "Выше каталога", "Найденный уровень новее указанного в каталоге; понижение не предлагается.");
  if (base < 0) return result("update", "Есть более новый уровень", "Перед установкой проверьте платформу и требования IBM.");
  if (id === "content_manager") return result("review", "FP совпадает · проверить iFix", "Collector cmlevel не подтверждает наличие отдельных interim fixes.");
  if (id === "websphere") return result("level", "Fix Pack совпадает", "Отдельные iFix/security fixes не проверены.");
  if (id === "db2") {
    if (typeof installed.special_build === "string" && installed.special_build === available.special_build) return result("match", "Update совпадает", "Совпадение с опубликованным Update; индивидуальные APAR отдельно не проверены.");
    return result("review", "Сверить special build", "Номера special build не сравниваются по величине. Нужна проверка состава по IBM.");
  }
  if (id === "iccsap") {
    const jre = compareVersions(installed.jre_version, available.jre_version);
    if (jre === null) return result("review", "Проверить встроенную JRE", "В inventory нет измеренной версии JRE. Даты JRE_fix не заменяют номер версии.");
    return jre < 0 ? result("update", "Есть обновление JRE", "Используйте пакет ICCSAP из бюллетеня IBM.") : jre > 0 ? result("different", "JRE выше каталога", "Состав установленного пакета требует сверки.") : result("match", "JRE совпадает", "Проверен только уровень встроенной JRE.");
  }
  if (id === "content_navigator" || id === "daeja_viewone_virtual") {
    const ix = ifixLevel(installed), iy = integer(available.interim_fix);
    if (ix === null || iy === null) return result("review", "Проверить уровень iFix", "Номер iFix отсутствует или противоречит build level.");
    if (id === "daeja_viewone_virtual" && installed.source === "ecmclient_version_txt") return result("review", "Встроен в ICN", "Проверяйте поставку Daeja в выбранном пакете ICN.");
    if (ix > iy) return result("different", "iFix выше каталога", "Проверьте более свежую страницу IBM.");
    if (ix < iy) return result("update", "Есть более новый iFix", "Известен iFix " + iy + "; применимость и зависимости — в Readme.");
    if (id === "content_navigator" && installed.build_level && available.build_level && String(installed.build_level).toLowerCase() !== String(available.build_level).toLowerCase()) return result("review", "iFix совпадает · другой build", "Build level отличается от Readme IBM; требуется сверка пакета.");
    return result("match", "iFix совпадает", "Совпадает указанный уровень iFix в этой ветке.");
  }
  return result("match", "Версия совпадает", "Проверен указанный уровень SDK, не всё окружение.");
}

function validateInventory(value) {
  if (!object(value) || value.schema_version !== 1 || !object(value.host) || !Array.isArray(value.products)) throw Error("Ожидается inventory schema_version 1 с host и списком products.");
  if (value.products.length > 1000) throw Error("В файле больше 1000 продуктов.");
  for (const p of value.products) {
    if (!object(p) || typeof p.id !== "string" || !p.id || p.id.length > 150) throw Error("У каждой записи products должен быть текстовый id.");
    if (p.version != null && typeof p.version !== "string") throw Error("Версия продукта должна быть строкой.");
    if (p.installed_fixes != null && (!Array.isArray(p.installed_fixes) || !p.installed_fixes.every(v => typeof v === "string"))) throw Error("installed_fixes должен быть списком строк.");
  }
  return value;
}

function validateCatalog(value) {
  if (!object(value) || value.schema_version !== 2 || !object(value.products)) throw Error("Ожидается catalog schema_version 2 с объектом products.");
  if (Object.keys(value.products).length > 1000) throw Error("Каталог слишком большой.");
  for (const entry of Object.values(value.products)) {
    if (!object(entry) || (entry.available != null && !object(entry.available))) throw Error("Некорректная запись каталога.");
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
    if (object(discovery) && discovery.status && !["ok", "skipped"].includes(discovery.status)) p._discoveryError = "Статус collector: " + discovery.status + ". Данные этой записи могут быть неполными.";
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
  let inventoryName = "", catalogName = "встроенный";
  const el = (tag, text, className) => { const node = document.createElement(tag); if (text !== undefined) node.textContent = String(text); if (className) node.className = className; return node; };
  const date = value => { const stamp = Date.parse(value); return Number.isFinite(stamp) ? new Date(stamp).toLocaleString("ru-RU", {timeZone:"UTC", year:"numeric", month:"2-digit", day:"2-digit", hour:"2-digit", minute:"2-digit"}) + " UTC" : "дата не указана"; };
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
    $("catalog-date").textContent = "Каталог: " + date(catalog.generated_at) + " · " + catalogName + " · Примечания IBM: " + notes.checked_at;
    $("clear-inventory").hidden = !inventory;
    $("inventory-title").textContent = inventory ? inventory.context_only ? "Версии из приложенного описания" : "Снимок: " + (inventory.host.hostname || "имя сервера не указано") : "Каталог IBM · 7 основных продуктов";
    $("inventory-meta").textContent = inventory ? inventory.context_only ? "Это ранее указанные версии. Новый скан не выполнялся; загрузите inventory.json для обновления." : [inventoryName, "Сбор: " + date(inventory.timestamp), inventory.host.machine, inventory.host.os_release && inventory.host.os_release.PRETTY_NAME].filter(Boolean).join(" · ") : "Откройте inventory.json для сравнения с вашим сервером. Каталог доступен и без него.";
    const warnings = [];
    const badEntries = Object.values(catalog.products).filter(e => freshness(e, catalog, now));
    if (badEntries.length) warnings.push("Для " + badEntries.length + " записей каталог устарел, не датирован или источник недоступен. Уровни показаны для справки.");
    if (now - Date.parse(notes.checked_at + "T00:00:00Z") > FRESH_HOURS * 3600000) warnings.push("Примечания IBM от " + notes.checked_at + " требуют повторной проверки, даже если catalog.json обновился.");
    if (inventory && !inventory.context_only) {
      const stamp = Date.parse(inventory.timestamp);
      if (!Number.isFinite(stamp) || stamp > now + 300000 || now - stamp > FRESH_HOURS * 3600000) warnings.push("Inventory не имеет достоверной свежей даты. Сравниваются значения из файла, а не текущее состояние сервера.");
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
      if (parts && own(PRODUCTS, id)) product.append(el("span", "Ветка " + parts.slice(0, PRODUCTS[id][1]).join("."), "stream"));
      if (p && p.installation_directory) metadata(product, p.installation_directory);
      cell(tr, "Продукт", product);
      const installedCell = el("div", undefined, "cell-content");
      installedCell.append(el("span", p ? p.version || "Версия неизвестна" : "—", "version"));
      if (p) {
        const ix = ifixLevel(p);
        if (ix !== null) metadata(installedCell, "iFix " + ix);
        for (const text of [p.build_level, p.special_build, p.build && "Build " + p.build, p.jre_version && "JRE " + p.jre_version]) metadata(installedCell, text);
        const fixes = (p.installed_fixes || []).filter(v => /JRE_fix_\d{8}/i.test(v));
        if (fixes.length) metadata(installedCell, fixes.map(v => v.match(/JRE_fix_\d{8}/i)[0]).join(" · "));
      }
      cell(tr, "Установлено", installedCell);
      const availableCell = el("div", undefined, "cell-content");
      const targetText = [target.version, target.interim_fix != null ? "iFix " + target.interim_fix : "", target.jre_version ? "+ JRE " + target.jre_version : ""].filter(Boolean).join(" ") || "Нет данных";
      availableCell.append(el("span", targetText, "version"));
      metadata(availableCell, target.special_build);
      if (note) metadata(availableCell, note.availability_note);
      if (e) metadata(availableCell, "Источник получен: " + date(e.refreshed_at || catalog.generated_at));
      if (note) {
        const details = el("details", undefined, "product-notes");
        details.append(el("summary", "Условия и примечания"));
        for (const text of note.notes) details.append(el("p", text));
        details.append(el("p", "Проверка примечаний: " + notes.checked_at, "muted"));
        availableCell.append(details);
      }
      cell(tr, "Подтверждено IBM", availableCell);
      const statusCell = el("div", undefined, "cell-content");
      statusCell.append(el("span", status.label, "status " + status.code), el("p", status.reason, "reason"));
      cell(tr, "Сравнение", statusCell);
      const actions = el("div", undefined, "cell-content links");
      const links = note ? note.links.slice() : [];
      if (e && e.source_url && !links.some(l => l.url === e.source_url)) links.push({label:"Источник каталога IBM", url:e.source_url});
      if (e && e.download_url && !links.some(l => l.url === e.download_url)) links.unshift({label:"IBM: страница скачивания", url:e.download_url, download:true});
      for (const item of links) { const a = link(item.label, item.url, item.download); if (a) actions.append(a); }
      if (!actions.childNodes.length) actions.append(el("span", "Источник не указан", "metadata"));
      cell(tr, "Ссылки", actions);
      $("products").append(tr);
    }
    $("summary").textContent = inventory ? counts.update + " — более новый уровень · " + counts.review + " — проверить · " + counts.match + " — совпадает" : "Известные уровни и официальные страницы IBM";
  }
  async function readFile(input, kind) {
    const file = input.files[0];
    if (!file) return;
    try {
      if (file.size > MAX_BYTES) throw Error("Максимальный размер JSON — 10 МБ.");
      const value = JSON.parse((await file.text()).replace(/^\uFEFF/, ""));
      if (kind === "inventory") { validateInventory(value); inventory = value; inventoryName = file.name; }
      else { validateCatalog(value); catalog = value; catalogName = file.name; }
      $("error").hidden = true; $("error").textContent = ""; render();
    } catch (error) {
      $("error").textContent = "Файл не загружен: " + error.message + " Предыдущие данные сохранены.";
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

if (typeof module !== "undefined" && module.exports) module.exports = {versionParts, compareVersions, ifixLevel, freshness, compareProduct, validateInventory, validateCatalog, ibmUrl, matchingNote, iccsapFixes, rowsFor};
if (typeof document !== "undefined") {
  try { startApp(); } catch (error) {
    const target = document.getElementById("error");
    target.textContent = "Не удалось открыть встроенные данные: " + error.message;
    target.hidden = false;
  }
}
