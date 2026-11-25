// Navegação lateral, filtros e divisões de lote, sem dependências remotas.
const viewport = matchMedia("(max-width: 900px)");
const mobile = () => viewport.matches;
const menu = document.querySelector("#sidebar");
const toggle = document.querySelector("#menu-toggle");
const collapse = document.querySelector("#sidebar-collapse");
function syncMenu() {
  if (!menu) return;
  const open = mobile()
    ? document.body.classList.contains("menu-open")
    : !document.body.classList.contains("menu-collapsed");
  toggle?.setAttribute("aria-expanded", String(open));
  toggle?.setAttribute(
    "aria-label",
    mobile() ? "Abrir menu" : open ? "Recolher menu" : "Expandir menu",
  );
  collapse?.setAttribute("aria-expanded", String(open));
  collapse?.setAttribute(
    "aria-label",
    mobile() ? "Fechar menu" : open ? "Recolher menu" : "Expandir menu",
  );
  const label = collapse?.querySelector("span");
  if (label)
    label.textContent = mobile()
      ? "Fechar menu"
      : open
        ? "Recolher menu"
        : "Expandir menu";
}
function closeMenu(restoreFocus = false) {
  document.body.classList.remove("menu-open");
  syncMenu();
  if (restoreFocus) toggle?.focus();
}
if (menu) {
  if (localStorage.getItem("cacau-menu-collapsed") === "1")
    document.body.classList.add("menu-collapsed");
  function flipDesktop() {
    document.body.classList.toggle("menu-collapsed");
    localStorage.setItem(
      "cacau-menu-collapsed",
      document.body.classList.contains("menu-collapsed") ? "1" : "0",
    );
    syncMenu();
  }
  toggle?.addEventListener("click", () => {
    if (mobile()) {
      const open = document.body.classList.toggle("menu-open");
      syncMenu();
      if (open) menu.querySelector("a")?.focus();
    } else flipDesktop();
  });
  collapse?.addEventListener("click", () => {
    if (mobile()) closeMenu(true);
    else flipDesktop();
  });
  document
    .querySelector("#sidebar-overlay")
    ?.addEventListener("click", () => closeMenu(true));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && document.body.classList.contains("menu-open"))
      closeMenu(true);
    if (
      e.key === "Tab" &&
      mobile() &&
      document.body.classList.contains("menu-open")
    ) {
      const targets = [...menu.querySelectorAll("a,button")].filter(
        (el) => !el.disabled,
      );
      const first = targets[0],
        last = targets[targets.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last?.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first?.focus();
      }
    }
  });
  menu
    .querySelectorAll("a")
    .forEach((a) => a.addEventListener("click", () => closeMenu()));
  viewport.addEventListener?.("change", () => {
    document.body.classList.remove("menu-open");
    syncMenu();
  });
  syncMenu();
}
// Um link para um cadastro recolhido também abre seu formulário antes de focar.
document.querySelectorAll('a[href="#new-customer"]').forEach((link) =>
  link.addEventListener("click", () => {
    const section = document.getElementById("new-customer");
    if (section) {
      section.open = true;
      section
        .querySelector("input:not([type=hidden])")
        ?.focus({ preventScroll: true });
    }
  }),
);
if (window.gsap) {
  gsap.matchMedia().add("(prefers-reduced-motion: no-preference)", () => {
    gsap.from(".page-heading > div", {
      y: 10,
      opacity: 0,
      duration: 0.4,
      ease: "power2.out",
    });
    gsap.from(".metric", {
      y: 14,
      opacity: 0,
      duration: 0.4,
      stagger: 0.055,
      ease: "power2.out",
    });
  });
}
document.querySelectorAll("[data-select-search]").forEach((input) => {
  const select = document.getElementById(input.dataset.selectSearch);
  const source = [...select.options].map((o) => ({
    value: o.value,
    label: o.textContent,
  }));
  input.addEventListener("input", () => {
    const current = select.value;
    const q = input.value.toLocaleLowerCase("pt-BR");
    select.replaceChildren();
    source
      .filter((o) => !o.value || o.label.toLocaleLowerCase("pt-BR").includes(q))
      .forEach((o) => select.add(new Option(o.label, o.value)));
    select.value = [...select.options].some((o) => o.value === current)
      ? current
      : "";
  });
});
document.querySelectorAll("[data-lot-editor]").forEach((form) => {
  const list = form.querySelector("[data-lot-lines]");
  const prototype = list.firstElementChild.cloneNode(true);
  form.querySelector("[data-add-lot]").addEventListener("click", () => {
    const row = prototype.cloneNode(true);
    row
      .querySelectorAll("input")
      .forEach((i) => (i.value = i.type === "number" ? "0" : ""));
    list.append(row);
    row.querySelector("input").focus();
  });
  list.addEventListener("click", (e) => {
    if (e.target.closest("[data-remove-lot]"))
      e.target.closest(".lot-line").remove();
  });
});
document.querySelectorAll("[data-receipt-product]").forEach((card) => {
  const mode = card.querySelector("[data-product-mode]");
  if (!mode) return;
  const box = card.querySelector("[data-new-product]");
  function show() {
    box.hidden = mode.value !== "new";
    box.querySelectorAll("input,select").forEach((i) => {
      i.disabled = box.hidden;
    });
  }
  mode.addEventListener("change", () => {
    show();
    requireExpiry();
  });
  show();
  const list = card.querySelector("[data-receipt-parts]");
  function requireExpiry() {
    const category =
      mode.value === "new"
        ? card.querySelector("[data-new-category]").value
        : mode.selectedOptions[0]?.dataset.category;
    list
      .querySelectorAll("input[type=date]")
      .forEach((input) => (input.required = category !== "ACESSORIOS"));
  }
  card
    .querySelector("[data-new-category]")
    .addEventListener("change", requireExpiry);
  function sum() {
    const n = [...list.querySelectorAll("[data-part-quantity]")].reduce(
      (a, x) => a + Number(x.value || 0),
      0,
    );
    const total = Number(card.querySelector("[data-receipt-total]").value || 0);
    const text = card.querySelector("[data-part-summary]");
    text.textContent = `Distribuído: ${n} / ${total} unidades`;
    text.classList.toggle("negative", n !== total);
  }
  card.querySelector("[data-add-part]").addEventListener("click", () => {
    const row = list.firstElementChild.cloneNode(true);
    row.querySelectorAll("input").forEach((i) => (i.value = ""));
    list.append(row);
    requireExpiry();
    sum();
  });
  list.addEventListener("click", (e) => {
    if (e.target.closest("[data-remove-part]") && list.children.length > 1) {
      e.target.closest(".receipt-part").remove();
      sum();
    }
  });
  card.addEventListener("input", sum);
  sum();
  requireExpiry();
  card.closest("form").addEventListener(
    "submit",
    (event) => {
      const n = [...list.querySelectorAll("[data-part-quantity]")].reduce(
        (a, x) => a + Number(x.value || 0),
        0,
      );
      if (n !== Number(card.querySelector("[data-receipt-total]").value)) {
        event.preventDefault();
        event.stopImmediatePropagation();
        card.querySelector("[data-part-summary]").textContent =
          "Corrija a soma dos lotes antes de confirmar.";
        card.scrollIntoView({ block: "center", behavior: "smooth" });
      }
    },
    true,
  );
});
document.querySelectorAll("[data-copy]").forEach((button) =>
  button.addEventListener("click", async () => {
    const field = document.getElementById(button.dataset.copy);
    const status = document.querySelector("[data-copy-status]");
    try {
      await navigator.clipboard.writeText(field.value);
      status.textContent = "Senha copiada.";
    } catch {
      field.select();
      status.textContent = "Selecione e copie a senha (Ctrl+C).";
    }
  }),
);
// Rascunho de inventário: servidor + recuperação local de alterações ainda não enviadas.
const editor = document.querySelector("#count-editor");
if (editor) {
  const key = `cacau-draft:${editor.dataset.userId}:${editor.dataset.countId}`;
  const rows = [...editor.querySelectorAll("[data-count-line]")];
  const status = editor.querySelector("#count-save-status");
  const search = editor.querySelector("#count-search");
  const button = editor.querySelector("#save-count");
  const dirty = new Set();
  let timer,
    saveInProgress = false,
    conflict = false;
  let unresolved = [];
  const read = (row) => ({
    id: Number(row.dataset.countLine),
    previous: row.dataset.previous === "" ? null : Number(row.dataset.previous),
    revision: Number(row.dataset.revision),
    counted: row.querySelector("[data-quantity]").value,
    note: row.querySelector("[data-note]").value,
  });
  function persist() {
    try {
      localStorage.setItem(
        key,
        JSON.stringify({
          lines: [...dirty].map(read).concat(unresolved),
          scroll: scrollY,
          search: search.value,
        }),
      );
    } catch {
      status.textContent =
        "Não foi possível guardar rascunho local. Salve no servidor antes de sair.";
    }
  }
  function state() {
    document.body.classList.toggle("count-has-dirty", dirty.size > 0);
  }
  function filter() {
    editor
      .querySelectorAll("[data-count-product]")
      .forEach(
        (p) =>
          (p.hidden = !p.dataset.search
            .toLowerCase()
            .includes(search.value.toLowerCase())),
      );
  }
  function difference(row) {
    const n = row.querySelector("[data-quantity]").value;
    row.querySelector("[data-loss]").textContent =
      n === "" ? "—" : Math.max(0, Number(row.dataset.expected) - Number(n));
    row.querySelector("[data-surplus]").textContent =
      n === "" ? "—" : Math.max(0, Number(n) - Number(row.dataset.expected));
  }
  function schedule() {
    clearTimeout(timer);
    timer = setTimeout(save, 700);
  }
  let cached;
  try {
    cached = JSON.parse(localStorage.getItem(key) || "null");
  } catch {
    cached = null;
  }
  if (editor.dataset.countStatus === "rascunho" && cached) {
    for (const draft of cached.lines || []) {
      const row = rows.find((r) => Number(r.dataset.countLine) === draft.id);
      if (!row) continue;
      const current = read(row);
      if (current.counted === draft.counted && current.note === draft.note)
        continue;
      if (current.revision !== draft.revision) {
        conflict = true;
        unresolved.push(draft);
        continue;
      }
      row.querySelector("[data-quantity]").value = draft.counted;
      row.querySelector("[data-note]").value = draft.note;
      dirty.add(row);
      difference(row);
    }
    search.value = cached.search || "";
    filter();
    requestAnimationFrame(() => window.scrollTo(0, cached.scroll || 0));
    if (conflict)
      status.textContent =
        "Há um rascunho local em conflito com outra edição. Confira os valores atuais; o rascunho conflitante não foi aplicado.";
    else if (dirty.size) {
      status.textContent = "Rascunho local recuperado. Salvando…";
      schedule();
    }
  } else if (editor.dataset.countStatus !== "rascunho")
    localStorage.removeItem(key);
  if (unresolved.length) {
    const box = document.createElement("section");
    box.className = "notice error";
    const text = document.createElement("p");
    text.textContent =
      "Há " +
      unresolved.length +
      " linha(s) com rascunho deste aparelho diferente do servidor. Escolha os valores que deseja manter.";
    box.append(text);
    unresolved.forEach((d) => {
      const row = rows.find((r) => Number(r.dataset.countLine) === d.id);
      const line = document.createElement("p");
      line.textContent =
        row.closest("[data-count-product]").querySelector("strong")
          .textContent +
        ": seu rascunho " +
        d.counted +
        " un / servidor " +
        read(row).counted +
        " un";
      box.append(line);
    });
    function resolve(useDraft) {
      if (useDraft)
        unresolved.forEach((d) => {
          const row = rows.find((r) => Number(r.dataset.countLine) === d.id);
          row.querySelector("[data-quantity]").value = d.counted;
          row.querySelector("[data-note]").value = d.note;
          dirty.add(row);
          difference(row);
        });
      unresolved = [];
      conflict = false;
      box.remove();
      persist();
      state();
      status.textContent = useDraft
        ? "Seu rascunho será enviado para revisão."
        : "Valores atuais do servidor mantidos.";
      if (dirty.size) schedule();
    }
    const server = document.createElement("button");
    server.type = "button";
    server.className = "btn secondary";
    server.textContent = "Manter valores do servidor";
    server.addEventListener("click", () => resolve(false));
    box.append(server);
    const local = document.createElement("button");
    local.type = "button";
    local.className = "btn secondary";
    local.textContent = "Reaplicar meu rascunho";
    local.addEventListener("click", () => resolve(true));
    box.append(local);
    editor.prepend(box);
  }
  rows.forEach((row) =>
    row.addEventListener("input", () => {
      dirty.add(row);
      difference(row);
      status.textContent = "Rascunho pendente — salvamento automático…";
      persist();
      state();
      if (!conflict) schedule();
    }),
  );
  async function save() {
    if (!button || saveInProgress || !dirty.size) return;
    if (conflict) {
      status.textContent =
        "Recarregue para conferir o conflito antes de salvar.";
      return;
    }
    const batch = [...dirty].map(read);
    if (
      batch.some(
        (x) =>
          x.counted === "" ||
          !Number.isInteger(Number(x.counted)) ||
          Number(x.counted) < 0 ||
          Number(x.counted) > 1000000,
      )
    ) {
      status.textContent =
        "Informe uma quantidade inteira em todas as linhas alteradas (use zero quando necessário).";
      return;
    }
    saveInProgress = true;
    button.disabled = true;
    status.textContent = "Salvando rascunho…";
    try {
      const response = await fetch(editor.dataset.saveUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": document.querySelector("meta[name=csrf-token]")
            .content,
        },
        body: JSON.stringify({ lines: batch }),
      });
      let result;
      try {
        result = await response.json();
      } catch {
        throw Error(
          "Sessão expirada ou resposta inválida. Entre novamente para salvar.",
        );
      }
      if (!response.ok || !result.ok) {
        if (response.status === 409) conflict = true;
        throw Error(result.error || "Não foi possível salvar.");
      }
      for (const sent of batch) {
        const row = rows.find((r) => Number(r.dataset.countLine) === sent.id);
        const live = read(row);
        row.dataset.previous = sent.counted;
        row.dataset.revision = result.revisions[String(sent.id)];
        if (live.counted === sent.counted && live.note === sent.note)
          dirty.delete(row);
      }
      status.textContent = dirty.size
        ? "Novas alterações pendentes…"
        : "Rascunho salvo no servidor · " +
          new Date().toLocaleTimeString("pt-BR");
      persist();
      state();
      if (dirty.size) schedule();
    } catch (error) {
      status.textContent =
        error.message +
        " Alterações não enviadas permanecem no rascunho deste aparelho.";
      persist();
      state();
    } finally {
      saveInProgress = false;
      button.disabled = false;
    }
  }
  button?.addEventListener("click", save);
  window.addEventListener("online", () => {
    if (!conflict) save();
  });
  search.addEventListener("input", () => {
    filter();
    persist();
  });
  let scrollTimer;
  window.addEventListener(
    "scroll",
    () => {
      clearTimeout(scrollTimer);
      scrollTimer = setTimeout(persist, 150);
    },
    { passive: true },
  );
  window.addEventListener("pagehide", persist);
  window.addEventListener("beforeunload", (e) => {
    if (dirty.size) {
      persist();
      e.preventDefault();
      e.returnValue = "";
    }
  });
  document.querySelectorAll(".count-actions form").forEach((f) =>
    f.addEventListener("submit", (e) => {
      if (dirty.size || saveInProgress) {
        e.preventDefault();
        status.textContent =
          "Aguarde o rascunho ser salvo antes de enviar para aprovação.";
        save();
      }
    }),
  );
  state();
}
document.querySelectorAll('form[action="/logout"]').forEach((f) =>
  f.addEventListener("submit", () => {
    Object.keys(localStorage)
      .filter((k) => k.startsWith("cacau-draft:"))
      .forEach((k) => localStorage.removeItem(k));
  }),
);
