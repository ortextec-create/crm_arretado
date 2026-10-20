const HOST = 'gestordepedidos.ifood.com.br';
const $ = (id) => document.getElementById(id);

let abaId = null;

function setStatus(texto, tipo = '') {
  const el = $('status');
  el.textContent = texto;
  el.className = `status ${tipo}`;
}

function mostrar(obj) {
  const pre = $('saida');
  pre.textContent = typeof obj === 'string' ? obj : JSON.stringify(obj, null, 2);
  pre.hidden = false;
  $('btnCopiar').hidden = false;
}

async function garantirContentScript(tabId) {
  try {
    await chrome.tabs.sendMessage(tabId, { type: 'PING' });
  } catch {
    // Aba aberta antes da instalação: injeta manualmente
    await chrome.scripting.executeScript({ target: { tabId }, files: ['selectors.js', 'content.js'] });
  }
}

async function enviar(msg) {
  await garantirContentScript(abaId);
  return chrome.tabs.sendMessage(abaId, msg);
}

async function init() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const ok = tab?.url && new URL(tab.url).host === HOST;
  if (!ok) {
    setStatus('Abra o Gestor de Pedidos iFood (web) nesta aba e clique na extensão de novo.', 'err');
    $('btnDiag').disabled = true;
    $('btnEnviar').disabled = true;
    return;
  }
  abaId = tab.id;
  setStatus('Gestor de Pedidos detectado ✓', 'ok');

  const salvo = await chrome.storage.local.get(['numero', 'orderId', 'mensagem']);
  if (salvo.numero) $('numero').value = salvo.numero;
  if (salvo.orderId) $('orderId').value = salvo.orderId;
  if (salvo.mensagem) $('mensagem').value = salvo.mensagem;

  // Se a aba já está no detalhe de um pedido, sugere o ID da URL
  const m = tab.url.match(/expedition\/([0-9a-f-]{36})/i);
  if (m && !$('orderId').value) $('orderId').value = m[1];
}

$('modoSeguro').addEventListener('change', (e) => {
  $('avisoEnvio').hidden = e.target.checked;
});

$('btnDiag').addEventListener('click', async () => {
  $('btnDiag').disabled = true;
  try {
    mostrar(await enviar({ type: 'DIAGNOSE' }));
  } catch (e) {
    mostrar(`Erro: ${e.message}`);
  } finally {
    $('btnDiag').disabled = false;
  }
});

$('btnEnviar').addEventListener('click', async () => {
  const numero = $('numero').value.trim().replace(/^#/, '');
  const orderId = $('orderId').value.trim();
  const mensagem = $('mensagem').value.trim();
  const modoSeguro = $('modoSeguro').checked;
  if (!numero || !mensagem) { mostrar('Informe o número do pedido e a mensagem (o número é obrigatório mesmo com o ID: é ele que confere a conversa certa).'); return; }
  if (!modoSeguro && !confirm(`Enviar DE VERDADE para o pedido #${numero}?`)) return;

  await chrome.storage.local.set({ numero, orderId, mensagem });
  $('btnEnviar').disabled = true;
  mostrar('Executando… não mexa na aba do Gestor.');
  try {
    mostrar(await enviar({ type: 'SEND_TEST', numero, orderId, mensagem, modoSeguro }));
  } catch (e) {
    mostrar(`Erro: ${e.message}`);
  } finally {
    $('btnEnviar').disabled = false;
  }
});

$('btnCopiar').addEventListener('click', async () => {
  await navigator.clipboard.writeText($('saida').textContent);
  $('btnCopiar').textContent = 'Copiado ✓';
  setTimeout(() => ($('btnCopiar').textContent = 'Copiar resultado'), 1500);
});

init();
