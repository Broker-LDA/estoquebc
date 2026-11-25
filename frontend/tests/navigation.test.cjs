// Testa as interações usadas no desktop, tablet e teclado sem acessar um banco real.
const { test } = require("node:test");
const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { resolve } = require("node:path");
const { JSDOM } = require("jsdom");
const script = readFileSync(
  resolve(__dirname, "../../app/static/js/experience.js"),
  "utf8",
);
function setup(width = 1280, collapsed = false) {
  const dom = new JSDOM(
    `<button id="menu-toggle"></button><button id="sidebar-overlay"></button>
  <aside id="sidebar"><a href="/">Início</a><button id="sidebar-collapse"><span></span></button><a href="/profile">Perfil</a><button id="exit">Sair</button></aside>
  <a href="#new-customer">Cadastrar cliente</a><details id="new-customer"><summary>Novo cliente</summary><input name="name"></details>`,
    { url: "https://estoque.test", runScripts: "outside-only" },
  );
  const { window: w } = dom;
  let onChange;
  const query = {
    matches: width <= 900,
    addEventListener: (_, cb) => (onChange = cb),
  };
  w.matchMedia = () => query;
  if (collapsed) w.localStorage.setItem("cacau-menu-collapsed", "1");
  w.eval(script);
  return {
    dom,
    w,
    doc: w.document,
    resize: (n) => {
      query.matches = n <= 900;
      onChange();
    },
  };
}
test("desktop retoma o menu recolhido e persiste a expansão", () => {
  const { dom, w, doc } = setup(1280, true);
  assert.equal(
    doc.querySelector("#menu-toggle").getAttribute("aria-expanded"),
    "false",
  );
  doc.querySelector("#menu-toggle").click();
  assert.equal(doc.body.classList.contains("menu-collapsed"), false);
  assert.equal(w.localStorage.getItem("cacau-menu-collapsed"), "0");
  assert.equal(
    doc.querySelector("#sidebar-collapse span").textContent,
    "Recolher menu",
  );
  dom.window.close();
});
test("tablet de 880 px abre a gaveta mesmo com preferência de desktop recolhido", () => {
  const { dom, doc } = setup(880, true);
  doc.querySelector("#menu-toggle").click();
  assert.equal(doc.body.classList.contains("menu-open"), true);
  assert.equal(
    doc.querySelector("#menu-toggle").getAttribute("aria-expanded"),
    "true",
  );
  assert.equal(doc.activeElement.textContent, "Início");
  assert.equal(
    doc.querySelector("#sidebar-collapse span").textContent,
    "Fechar menu",
  );
  dom.window.close();
});
test("Escape fecha a gaveta e devolve o foco ao botão que a abriu", () => {
  const { dom, w, doc } = setup(390);
  doc.querySelector("#menu-toggle").click();
  doc.dispatchEvent(
    new w.KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
  );
  assert.equal(doc.body.classList.contains("menu-open"), false);
  assert.equal(doc.activeElement.id, "menu-toggle");
  dom.window.close();
});
test("Tab e Shift+Tab mantêm a navegação dentro da gaveta aberta", () => {
  const { dom, w, doc } = setup(390);
  doc.querySelector("#menu-toggle").click();
  doc.dispatchEvent(
    new w.KeyboardEvent("keydown", {
      key: "Tab",
      shiftKey: true,
      bubbles: true,
      cancelable: true,
    }),
  );
  assert.equal(doc.activeElement.id, "exit");
  doc.dispatchEvent(
    new w.KeyboardEvent("keydown", {
      key: "Tab",
      bubbles: true,
      cancelable: true,
    }),
  );
  assert.equal(doc.activeElement.textContent, "Início");
  dom.window.close();
});
test("a mudança para desktop remove o estado de gaveta aberta", () => {
  const { dom, doc, resize } = setup(880);
  doc.querySelector("#menu-toggle").click();
  resize(1280);
  assert.equal(doc.body.classList.contains("menu-open"), false);
  assert.equal(
    doc.querySelector("#sidebar-collapse span").textContent,
    "Recolher menu",
  );
  dom.window.close();
});
test("Cadastrar cliente revela o formulário antes de posicionar o foco", () => {
  const { dom, doc } = setup();
  doc.querySelector('a[href="#new-customer"]').click();
  assert.equal(doc.querySelector("#new-customer").open, true);
  assert.equal(doc.activeElement.name, "name");
  dom.window.close();
});
