"use strict";
// Browser development tests only. The delivered HTML has no npm dependencies.
const {test, before, after} = require("node:test");
const assert = require("node:assert/strict");
const {chromium} = require("playwright");
const fs = require("node:fs");
const path = require("node:path");
const html = fs.readFileSync(path.join(__dirname, "../output/IBM-Patchwatch.html"), "utf8");
let browser;
before(async () => { browser = await chromium.launch({headless:true, ...(process.env.PATCHWATCH_CHROMIUM ? {executablePath:process.env.PATCHWATCH_CHROMIUM,args:["--no-sandbox","--disable-gpu","--disable-dev-shm-usage"]} : {})}); });
after(async () => { if (browser) await browser.close(); });

const freshCatalog = () => ({schema_version:2,generated_at:new Date().toISOString(),products:{
  websphere:{available:{version:"9.0.5.29"},fix_pack_cumulative:true,fix_pack_url:"https://www.ibm.com/support/fixcentral/swg/doSelectFixes?options.selectedFixes=9.0.5-WS-WAS-FP029&continue=1",download_url:"https://www.ibm.com/support/fixcentral/swg/selectFixes?release=9.0.5.25",interim_fixes:[]},
  db2:{available:{version:"11.5.9.0",special_build:"special_87984"}},
  content_navigator:{available:{version:"3.1.0",interim_fix:12,build_level:"icn310.012.703"}}
}});
const inventory = hostname => ({schema_version:1,timestamp:new Date().toISOString(),host:{hostname},products:[
  {id:"websphere",version:"9.0.5.25",installation_directory:"/opt/WAS-A"},
  {id:"websphere",version:"9.0.5.29",installation_directory:"/opt/WAS-B"},
  {id:"db2",version:"11.5.9.0",special_build:"special_87984"},
  {id:"content_navigator",version:"3.1.0",interim_fix:6}
],discovery:{content_manager:{status:"parse_error",path:"/opt/IBM/cmlevel"}}});
const file = (name, value) => ({name,mimeType:"application/json",buffer:Buffer.from(JSON.stringify(value))});
async function withPage(fn, viewport = {width:1440,height:1000}) {
  const page = await browser.newPage({viewport});
  const failures = [], network = [];
  page.on("pageerror", e => failures.push(e.message));
  page.on("request", r => { if (/^https?:/.test(r.url())) network.push(r.url()); });
  try {
    await page.setContent(html);
    await fn(page);
    assert.deepEqual(failures, []);
    assert.deepEqual(network, [], "Reading JSON and filtering must not upload or fetch data");
  } finally { await page.close(); }
}
async function load(page, hostname = "test-server") {
  await page.locator("#catalog-file").setInputFiles(file("catalog.json", freshCatalog()));
  await page.waitForFunction(() => document.querySelector("#load-message").textContent.includes("catalog.json geladen"));
  await page.locator("#inventory-file").setInputFiles(file("inventory.json", inventory(hostname)));
  await page.waitForFunction(() => document.querySelector("#inventory-title").textContent.includes("Server:"));
}

test("local imports, status filters and target download order work in a browser", async () => withPage(async page => {
  assert.equal(await page.locator("#products tr").count(), 7);
  assert.equal(await page.locator("#onboarding").isVisible(), true);
  await load(page);
  assert.equal(await page.locator("#count-update").textContent(), "2");
  assert.equal(await page.locator("#products tr").first().getAttribute("data-status"), "update");
  assert.equal(await page.locator("#count-review").textContent(), "1");
  await page.locator("[data-filter=update]").click();
  assert.equal(await page.locator("#products tr").count(), 2);
  assert.match(await page.locator("#products tr").filter({hasText:"IBM WebSphere Application Server"}).first().locator("a").first().getAttribute("href"), /FP029/);
  await page.locator("#search").fill("WAS-B");
  assert.equal(await page.locator("#empty-results").isVisible(), true);
  await page.locator("#status-filter").selectOption("all");
  assert.equal(await page.locator("#products tr").count(), 1);
  await page.locator("#reset-filter").click();
  assert.equal(await page.locator("#products tr").count(), 8);
  if (process.env.PATCHWATCH_SCREENSHOTS) {
    fs.mkdirSync(process.env.PATCHWATCH_SCREENSHOTS, {recursive:true});
    await page.screenshot({path:path.join(process.env.PATCHWATCH_SCREENSHOTS,"desktop.png"),fullPage:true});
  }
  await page.locator("#clear-inventory").click();
  assert.equal(await page.locator("#onboarding").isVisible(), true);
  assert.equal(await page.locator("#search").inputValue(), "");
}));

test("malformed catalog is rejected without losing the loaded inventory or rows", async () => withPage(async page => {
  await load(page);
  const before = await page.locator("#products").textContent();
  const bad = freshCatalog(); bad.products.websphere.interim_fixes = [{fix_id:{toString:"not callable"}}];
  await page.locator("#catalog-file").setInputFiles(file("invalid.json", bad));
  await page.waitForFunction(() => !document.querySelector("#error").hidden);
  assert.equal(await page.locator("#products").textContent(), before);
  assert.match(await page.locator("#inventory-title").textContent(), /test-server/);
  assert.match(await page.locator("#error").textContent(), /bisherigen Daten bleiben erhalten/);
}));

test("unexpected render failure also restores the preceding imported state", async () => withPage(async page => {
  await load(page);
  const before = await page.locator("#products").textContent();
  const bad = inventory("bad-server");
  bad.products[0].build = {toString:"not callable"};
  await page.locator("#inventory-file").setInputFiles(file("render-error.json", bad));
  await page.waitForFunction(() => !document.querySelector("#error").hidden);
  assert.equal(await page.locator("#products").textContent(), before);
  assert.match(await page.locator("#inventory-title").textContent(), /test-server/);
}));

test("a slow earlier import cannot overwrite a newer choice", async () => withPage(async page => {
  await page.evaluate(({oldValue,newValue}) => {
    function choose(value, delay, name) {
      const f = new File([JSON.stringify(value)], name, {type:"application/json"});
      Object.defineProperty(f, "text", {value:() => new Promise(resolve => setTimeout(() => resolve(JSON.stringify(value)), delay))});
      const transfer = new DataTransfer(); transfer.items.add(f);
      const input = document.querySelector("#inventory-file"); input.files = transfer.files;
      input.dispatchEvent(new Event("change"));
    }
    choose(oldValue, 150, "slow.json"); choose(newValue, 0, "new.json");
  }, {oldValue:inventory("old-server"),newValue:inventory("new-server")});
  await page.waitForFunction(() => document.querySelector("#inventory-title").textContent.includes("new-server"));
  await page.waitForTimeout(200);
  assert.match(await page.locator("#inventory-title").textContent(), /new-server/);
}));

test("two JSON files can be dropped together and markup remains literal text", async () => withPage(async page => {
  await page.evaluate(({catalog,inventory}) => {
    const transfer = new DataTransfer();
    for (const [name,value] of [["catalog.json",catalog],["inventory.json",inventory]]) transfer.items.add(new File([JSON.stringify(value)],name,{type:"application/json"}));
    document.dispatchEvent(new DragEvent("drop",{dataTransfer:transfer,bubbles:true,cancelable:true}));
  }, {catalog:freshCatalog(),inventory:inventory('<img src="https://evil.example/upload">')});
  await page.waitForFunction(() => document.querySelector("#inventory-title").textContent.includes("<img"));
  assert.equal(await page.locator("img").count(), 0);
  assert.equal(await page.locator("#count-update").textContent(), "2");
}));

test("printing hides controls while retaining the comparison", async () => withPage(async page => {
  await load(page);
  await page.emulateMedia({media:"print"});
  assert.equal(await page.locator(".controls").isVisible(), false);
  assert.equal(await page.locator(".filters").isVisible(), false);
  assert.equal(await page.locator("#products").isVisible(), true);
}));

test("mobile layout has no horizontal overflow and all product actions remain visible", async () => withPage(async page => {
  await load(page);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
  const link = page.locator("#products tr").filter({hasText:"IBM WebSphere Application Server"}).first().locator("a").first();
  assert.equal(await link.isVisible(), true);
  if (process.env.PATCHWATCH_SCREENSHOTS) {
    await page.screenshot({path:path.join(process.env.PATCHWATCH_SCREENSHOTS,"mobile.png")});
    await link.scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(process.env.PATCHWATCH_SCREENSHOTS,"mobile-product.png")});
  }
}, {width:390,height:844}));
