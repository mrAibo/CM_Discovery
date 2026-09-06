"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const api = require("../web/app.js");
const now = Date.parse("2026-09-06T12:00:00Z");
const catalog = {generated_at:"2026-09-06T10:00:00Z", products:{}};
const entry = (available, extra = {}) => ({available, ...extra});
const code = (id, installed, available, extra = {}) => api.compareProduct(id, installed, entry(available, extra), catalog, now).code;

test("numeric comparison accepts exact versions and rejects embedded errors", () => {
  assert.equal(api.compareVersions("8.7.00.400", "8.7.0.400"), 0);
  assert.equal(api.compareVersions("3.1.0", "3.1.0.0"), 0);
  assert.equal(api.compareVersions("9.0.5.9", "9.0.5.28"), -1);
  for (const value of [null, {}, "failed 9.0.5.28", "9..28", "", "1e3.5", "9007199254740993.1"]) assert.equal(api.compareVersions(value, "9.0.5.28"), null);
});

test("known maintenance differences; no upgrades across streams", () => {
  assert.equal(code("websphere", {version:"9.0.5.25"}, {version:"9.0.5.28"}), "update");
  assert.equal(code("websphere", {version:"9.0.5.29"}, {version:"9.0.5.28"}), "different");
  assert.equal(code("websphere", {version:"8.5.5.30"}, {version:"9.0.5.28"}), "different");
  assert.equal(code("content_navigator", {version:"3.0.11"}, {version:"3.1.0",interim_fix:12}), "different");
  assert.equal(code("content_manager", {version:"8.7.00.400"}, {version:"8.7.00.400"}), "review");
  assert.equal(code("websphere", {version:"9.0.5.28"}, {version:"9.0.5.28"}), "level");
});

test("ICN build parsing detects ambiguity and normalizes zero-padded iFix", () => {
  const target = {version:"3.1.0", interim_fix:12, build_level:"icn310.012.703"};
  assert.equal(code("content_navigator", {version:"3.1.0",build_level:"icn310.006.430"}, target), "update");
  assert.equal(code("content_navigator", {version:"3.1.0"}, target), "review");
  assert.equal(code("content_navigator", {version:"3.1.0",interim_fix:""}, target), "review");
  assert.equal(code("content_navigator", {version:"3.1.0",build_level:"icn310.006.430",interim_fix:12}, target), "review");
  assert.equal(code("content_navigator", {version:"3.1.0",build_level:"icn320.012.703"}, target), "review");
  assert.equal(code("content_navigator", {version:"3.1.0",build_level:"icn310.012.999"}, target), "review");
  assert.equal(code("content_navigator", {version:"3.1.0.0",build_level:"icn310.012.703"}, target), "match");
});

test("bundled Daeja and ICCSAP do not become independent update recommendations", () => {
  assert.equal(code("daeja_viewone_virtual", {version:"5.0.15",interim_fix:2,source:"ecmclient_version_txt"}, {version:"5.0.15",interim_fix:6}), "review");
  assert.equal(code("daeja_viewone_virtual", {version:"5.0.15",interim_fix:2,source:"standalone"}, {version:"5.0.15",interim_fix:6}), "update");
  assert.equal(code("iccsap", {version:"4.0.0.4",installed_fixes:["JRE_fix_20260812"]}, {version:"4.0.0.4",jre_version:"8.0.8.70",jre_fix_date:"20260812"}), "review");
  assert.equal(code("iccsap", {version:"4.0.0.4",jre_version:"8.0.8.51"}, {version:"4.0.0.4",jre_version:"8.0.8.70"}), "update");
});

test("Db2 unknown special builds never use numeric ordering", () => {
  for (const special_build of ["special_63280", "special_99999", null]) assert.equal(code("db2", {version:"11.5.9.0",special_build}, {version:"11.5.9.0",special_build:"special_87984"}), "review");
  assert.equal(code("db2", {version:"11.5.9.0",special_build:"special_87984"}, {version:"11.5.9.0",special_build:"special_87984"}), "match");
});

test("failed, stale, future and undated sources cannot yield a match", () => {
  for (const extra of [{refresh_error:{message:"timeout"}}, {refreshed_at:"2025-01-01T00:00:00Z"}, {refreshed_at:"2027-01-01T00:00:00Z"}, {refreshed_at:"invalid"}]) assert.equal(code("ibm_java", {version:"8.0.8.71"}, {version:"8.0.8.71"}, extra), "stale");
  assert.equal(api.compareProduct("ibm_java", {version:"8.0.8.71"}, entry({version:"8.0.8.71"}), {}, now).code, "stale");
  assert.equal(code("ibm_java", {version:"8.0.8.71",_discoveryError:"parse_error"}, {version:"8.0.8.71"}), "error");
});

test("inventory schema, unknown products and duplicate installations are preserved", () => {
  for (const value of [null, [], {schema_version:2,host:{},products:[]}, {schema_version:1,host:{},products:{}}, {schema_version:1,host:{},products:[null]}]) assert.throws(() => api.validateInventory(value));
  const inv = api.validateInventory({schema_version:1,host:{},products:[{id:"websphere",version:"9.0.5.25"},{id:"websphere",version:"9.0.5.28"},{id:"other",version:"1.0"}]});
  const rows = api.rowsFor(inv, catalog);
  assert.equal(rows.filter(r => r.id === "websphere").length, 2);
  assert.equal(rows.filter(r => r.id === "other").length, 1);
  assert.equal(rows.find(r => r.id === "content_manager").installed, null);
});

test("only ICCSAP current Fixes are read from raw IM output", () => {
  const inv = {installation_manager:{packages_raw:["[Package]", "Name: Java (com.ibm.java.jdk.v8)", "Fixes:", "JRE_fix_20990101", "[Paket]", "Name: Collector (com.ibm.im.iccsap.offering)", "Fixes:", "JRE_fix_20241212", "Rollbackversionen:", "JRE_fix_20200101"]}};
  assert.deepEqual(api.iccsapFixes(inv), ["JRE_fix_20241212"]);
});

test("catalog files cannot inject off-domain, credentialed or executable links", () => {
  for (const url of ["javascript:alert(1)", "https://ibm.com.evil.test/", "http://www.ibm.com/", "https://user:password@ibm.com/", "//ibm.com/", "https://ibm.com:8443/"]) assert.equal(api.ibmUrl(url), null);
  assert.equal(api.ibmUrl("https://www.ibm.com/support/pages/node/7087189"), "https://www.ibm.com/support/pages/node/7087189");
  assert.equal(api.ibmUrl("https://delivery04.dhe.ibm.com/readme.htm"), "https://delivery04.dhe.ibm.com/readme.htm");
});

test("dated links for old target disappear after a catalog version change", () => {
  const notes = {products:{websphere:{for_available:{version:"9.0.5.28"},links:[]}}};
  assert.ok(api.matchingNote("websphere", entry({version:"9.0.5.28"}), notes));
  assert.equal(api.matchingNote("websphere", entry({version:"9.0.5.29"}), notes), null);
});
