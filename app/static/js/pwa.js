// A instalação depende do suporte do navegador e sempre parte de uma ação da pessoa.
(() => {
  const button = document.querySelector("#pwa-install-button");
  const status = document.querySelector("#pwa-install-status");
  const network = document.querySelector("#network-status");
  let deferredPrompt;

  function installed() {
    deferredPrompt = undefined;
    if (button) button.hidden = true;
    if (status)
      status.textContent =
        "Aplicativo instalado. Abra pelo ícone na tela inicial.";
  }
  if (
    window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone
  ) {
    if (status)
      status.textContent = "Você já está usando o aplicativo instalado.";
  }
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredPrompt = event;
    if (button) button.hidden = false;
    if (status)
      status.textContent =
        "Este navegador permite instalar. Toque no botão abaixo.";
  });
  button?.addEventListener("click", async () => {
    if (!deferredPrompt) return;
    button.disabled = true;
    try {
      await deferredPrompt.prompt();
      const choice = await deferredPrompt.userChoice;
      if (status)
        status.textContent =
          choice.outcome === "accepted"
            ? "Instalação solicitada. Conclua as etapas do navegador."
            : "Instalação adiada. Você pode usar o menu do navegador quando quiser.";
    } catch {
      if (status)
        status.textContent = "Use a opção de instalar no menu do navegador.";
    } finally {
      deferredPrompt = undefined;
      button.hidden = true;
      button.disabled = false;
    }
  });
  window.addEventListener("appinstalled", installed);

  function connectionStatus() {
    if (!network) return;
    network.hidden = navigator.onLine;
    network.textContent =
      "Sem conexão. Reconecte para consultar ou salvar no servidor; confira o estado do rascunho antes de sair.";
  }
  window.addEventListener("online", connectionStatus);
  window.addEventListener("offline", connectionStatus);
  connectionStatus();

  if ("serviceWorker" in navigator && window.isSecureContext) {
    navigator.serviceWorker
      .register("/sw.js", { updateViaCache: "none" })
      .catch(() => {
        if (status)
          status.textContent =
            "Não foi possível preparar o aplicativo. Recarregue com conexão ou use o sistema pelo navegador.";
      });
  }
})();
