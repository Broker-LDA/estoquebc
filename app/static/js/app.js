document.querySelectorAll('[data-confirm]').forEach(form => {
  form.addEventListener('submit', event => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  });
});
const autoRefresh = document.querySelector('[data-autorefresh]');
if (autoRefresh) {
  window.setInterval(() => {
    if (document.visibilityState === 'visible' && document.activeElement?.tagName !== 'INPUT') {
      window.location.reload();
    }
  }, Number(autoRefresh.dataset.autorefresh) * 1000);
}
const kind = document.querySelector('#movement-kind');
if (kind) {
  const from = document.querySelector('#movement-source');
  const to = document.querySelector('#movement-destination');
  const hint = document.querySelector('#movement-hint');
  function update() {
    const rules = {
      entrada: ['', 'ARMAZENADO', 'Recebimento externo: normalmente entra no armazenado.'],
      transferencia: ['ARMAZENADO', 'LOJA', 'Reposição da exposição; transfere sem alterar o total.'],
      venda: ['LOJA', '', 'Venda ao cliente: baixa somente da loja.'],
      bonificacao: ['LOJA', '', 'Bonificação: ação comercial, divulgação, degustação ou proximidade da validade.'],
      perda: ['LOJA', '', 'Quebra, vencimento ou perda: descreva o ocorrido.'],
      devolucao: ['', 'LOJA', 'Retorno de produto ao estoque: informe a origem no motivo.']
    };
    const [source, destination, message] = rules[kind.value] || rules.entrada;
    from.value = source; to.value = destination; hint.textContent = message;
  }
  kind.addEventListener('change', update);
  update();
  const product = document.querySelector('#movement-product');
  const quantity = document.querySelector('#movement-quantity');
  const multiple = document.querySelector('#multiple-hint');
  function updateMultiple() {
    const factor = Number(product.selectedOptions[0]?.dataset.multiple || 1);
    multiple.textContent = factor > 1 ? `Fator configurado: ${factor} unidades por venda. Informe a quantidade real de unidades a baixar.${quantity.value ? ` Exemplo: ${quantity.value} unidades = ${(Number(quantity.value) / factor).toLocaleString('pt-BR')} venda(s) desse conjunto.` : ''}` : 'Registre a quantidade em unidades físicas.';
  }
  product.addEventListener('change', updateMultiple);
  quantity.addEventListener('input', updateMultiple);
  updateMultiple();
}

// Registro e instalação do PWA ficam em pwa.js.
const saleLines = document.querySelector('#sale-lines');
if (saleLines) {
  document.querySelector('#add-sale-line').addEventListener('click', () => {
    const row = saleLines.firstElementChild.cloneNode(true);
    row.querySelector('select').value=''; row.querySelector('input').value='';
    saleLines.append(row);
  });
  saleLines.addEventListener('click', e => {
    if (e.target.closest('[data-remove-line]')) {const row=e.target.closest('.sale-line');if(saleLines.children.length>1)row.remove();else{row.querySelector('select').value='';row.querySelector('input').value='';}}
  });
}
