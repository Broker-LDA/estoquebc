// Online por definição: nenhuma página autenticada, resposta de API ou operação é guardada.
self.addEventListener("install", (event) =>
  event.waitUntil(self.skipWaiting()),
);
self.addEventListener("activate", (event) =>
  event.waitUntil(self.clients.claim()),
);
self.addEventListener("fetch", (event) => {
  if (event.request.mode !== "navigate" || event.request.method !== "GET")
    return;
  event.respondWith(
    fetch(event.request).catch(
      () =>
        new Response(
          `<!doctype html>
    <html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Sem conexão · Brasil Cacau</title><style>
    body{font:16px/1.7 system-ui;margin:0;background:#f7f4f2;color:#39151e;min-height:100vh;display:grid;place-items:center}
    main{max-width:410px;padding:32px;margin:20px;background:#fff;border:1px solid #eae2df;border-radius:18px}
    h1{font-size:27px;line-height:1.3}a{display:inline-block;margin-top:12px;padding:12px 18px;background:#5b1d2a;color:white;border-radius:10px;text-decoration:none}
    </style><main><small>BRASIL CACAU · ESTOQUE</small><h1>Você está sem conexão.</h1>
    <p>Reconecte à internet para consultar ou alterar o estoque. Nenhum saldo é exibido offline.</p>
    <p>Ao retornar à conferência, o sistema recupera as alterações pendentes guardadas neste aparelho.</p><a href="/">Tentar novamente</a></main></html>`,
          {
            status: 503,
            headers: {
              "Content-Type": "text/html; charset=utf-8",
              "Cache-Control": "no-store",
              "Content-Security-Policy":
                "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'",
              "X-Content-Type-Options": "nosniff",
            },
          },
        ),
    ),
  );
});
