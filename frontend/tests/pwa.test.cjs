const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { resolve } = require("node:path");
const { JSDOM } = require("jsdom");
const script = readFileSync(
  resolve(__dirname, "../../app/static/js/pwa.js"),
  "utf8",
);
function setup() {
  const dom = new JSDOM(
    '<button id="pwa-install-button" hidden></button><p id="pwa-install-status"></p><p id="network-status" hidden></p>',
    { url: "https://estoque.test/instalar", runScripts: "outside-only" },
  );
  dom.window.matchMedia = () => ({ matches: false });
  dom.window.eval(script);
  return dom;
}
test("não mostra instalação sem oferta do navegador e solicita só após o clique", async () => {
  const dom = setup();
  const w = dom.window,
    doc = w.document;
  const button = doc.querySelector("button");
  assert.equal(button.hidden, true);
  let prompts = 0;
  const event = new w.Event("beforeinstallprompt", { cancelable: true });
  event.prompt = async () => prompts++;
  event.userChoice = Promise.resolve({ outcome: "accepted" });
  w.dispatchEvent(event);
  assert.equal(event.defaultPrevented, true);
  assert.equal(button.hidden, false);
  assert.equal(prompts, 0);
  button.click();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(prompts, 1);
  assert.equal(button.hidden, true);
  assert.match(
    doc.querySelector("#pwa-install-status").textContent,
    /solicitada/,
  );
  w.dispatchEvent(new w.Event("appinstalled"));
  assert.match(
    doc.querySelector("#pwa-install-status").textContent,
    /instalado/,
  );
  w.close();
});
test("avisa a perda de conexão e retira o aviso na reconexão", () => {
  const dom = setup();
  const w = dom.window,
    doc = w.document;
  Object.defineProperty(w.navigator, "onLine", {
    configurable: true,
    value: false,
  });
  w.dispatchEvent(new w.Event("offline"));
  assert.equal(doc.querySelector("#network-status").hidden, false);
  Object.defineProperty(w.navigator, "onLine", {
    configurable: true,
    value: true,
  });
  w.dispatchEvent(new w.Event("online"));
  assert.equal(doc.querySelector("#network-status").hidden, true);
  w.close();
});

const vm = require("node:vm");
const swSource = readFileSync(
  resolve(__dirname, "../../app/static/sw.js"),
  "utf8",
);
function worker() {
  const handlers = {};
  const context = {
    self: { addEventListener: (name, fn) => (handlers[name] = fn) },
    fetch: async () => {
      throw Error("offline");
    },
    Response,
  };
  vm.runInNewContext(swSource, context);
  return handlers;
}
test("service worker não intercepta envio de estoque ou chamadas de API", () => {
  const handlers = worker();
  let intercepted = false;
  handlers.fetch({
    request: { mode: "navigate", method: "POST" },
    respondWith: () => (intercepted = true),
  });
  handlers.fetch({
    request: { mode: "cors", method: "GET" },
    respondWith: () => (intercepted = true),
  });
  assert.equal(intercepted, false);
});
test("navegação offline recebe página genérica sem cache nem dados da requisição", async () => {
  const handlers = worker();
  let result;
  handlers.fetch({
    request: {
      mode: "navigate",
      method: "GET",
      url: "https://estoque.test/?token=nao-exibir",
    },
    respondWith: (p) => (result = p),
  });
  const response = await result;
  assert.equal(response.status, 503);
  assert.equal(response.headers.get("Cache-Control"), "no-store");
  const html = await response.text();
  assert.match(html, /sem conexão/);
  assert.equal(html.includes("nao-exibir"), false);
});
