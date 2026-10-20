const $ = (id) => document.getElementById(id);

const bg = (msg) => chrome.runtime.sendMessage(msg);

function setStatus(texto, tipo = '') {
  $('status').textContent = texto;
  $('status').className = `status ${tipo}`;
}

function textoStatus(s) {
  const c = s.config;
  if (!c.backendUrl || !c.temToken) return ['Configure a URL do CRM e o token.', 'warn'];
  if (!c.ativo) return ['Desligada.', 'warn'];
  if (s.erroApi === 'token_invalido') return ['Token inválido ou revogado. Gere outro no CRM.', 'err'];
  if (s.erroApi === 'sem_backend') return [`Sem conexão com o CRM.${s.erroApiDetalhe ? ' Detalhe: ' + s.erroApiDetalhe : ''}`, 'err'];
  if (s.designada == null) return [s.abas.length ? 'Escolha a aba do Gestor que processa a fila.' : 'Abra o Gestor de Pedidos iFood (web) e entre na conta.', 'warn'];
  const e = s.estadoContent;
  if (e?.nivel === 'vermelho') return [e.motivo, 'err'];
  if (e?.nivel === 'amarelo') return [e.motivo, 'warn'];
  return [c.modoSeguro ? 'Conectada (modo seguro: nada é enviado).' : 'Conectada e enviando.', 'ok'];
}

async function carregar() {
  const s = await bg({ type: 'STATUS' });
  $('versao').textContent = `Ortex Solutions · v${s.versao}`;
  const [t, tipo] = textoStatus(s);
  setStatus(t, tipo);

  if (document.activeElement !== $('url')) $('url').value = s.config.backendUrl;
  $('token').placeholder = s.config.temToken ? '•••••••• (salvo; cole outro para trocar)' : 'cole o token (mostrado uma única vez no CRM)';
  $('ativo').checked = s.config.ativo;
  $('modoSeguro').checked = s.config.modoSeguro;
  $('avisoEnvio').hidden = s.config.modoSeguro;

  const box = $('abas');
  box.textContent = '';
  if (!s.abas.length) box.textContent = 'Nenhuma aba do Gestor aberta.';
  for (const a of s.abas) {
    const linha = document.createElement('label');
    linha.className = 'aba';
    const r = document.createElement('input');
    r.type = 'radio'; r.name = 'aba'; r.checked = a.id === s.designada;
    r.addEventListener('change', async () => { await bg({ type: 'DESIGNAR', tabId: a.id }); carregar(); });
    const sp = document.createElement('span');
    sp.textContent = `${a.titulo || 'Gestor'} — ${a.url.replace('https://gestordepedidos.ifood.com.br', '')}`;
    sp.title = a.url;
    linha.append(r, sp);
    box.append(linha);
  }
}

$('btnSalvar').addEventListener('click', async () => {
  const msg = $('msgSalvar');
  msg.hidden = true;
  let origem;
  try { origem = new URL($('url').value.trim()).origin; } catch { msg.textContent = 'URL inválida.'; msg.hidden = false; return; }
  // Permissão da origem do backend (a URL é por instalação, então é opcional no manifest).
  const concedida = await chrome.permissions.request({ origins: [`${origem}/*`] });
  if (!concedida) { msg.textContent = 'Sem permissão para acessar essa URL.'; msg.hidden = false; return; }
  const dados = { backendUrl: origem };
  const token = $('token').value.trim();
  if (token) dados.token = token;
  await chrome.storage.local.set(dados);
  $('token').value = '';
  const r = await bg({ type: 'TESTAR_CONEXAO' });
  if (!r.ok) { msg.textContent = r.erro === 'token_invalido' ? 'Token inválido ou revogado.' : `Falha ao conectar (${r.erro})${r.detalhe ? ': ' + r.detalhe : ''}.`; msg.hidden = false; }
  carregar();
});

$('ativo').addEventListener('change', async (e) => { await chrome.storage.local.set({ ativo: e.target.checked }); carregar(); });
$('modoSeguro').addEventListener('change', async (e) => {
  if (!e.target.checked && !confirm('Desligar o modo seguro? As mensagens da fila serão ENVIADAS de verdade aos clientes.')) { e.target.checked = true; return; }
  await chrome.storage.local.set({ modoSeguro: e.target.checked });
  carregar();
});

function mostrar(obj) {
  $('saida').textContent = typeof obj === 'string' ? obj : JSON.stringify(obj, null, 2);
  $('saida').hidden = false;
  $('btnCopiar').hidden = false;
}

$('btnDiag').addEventListener('click', async () => {
  const s = await bg({ type: 'STATUS' });
  if (s.designada == null) { mostrar('Nenhuma aba designada.'); return; }
  try { mostrar(await chrome.tabs.sendMessage(s.designada, { type: 'DIAGNOSE' })); } catch (e) {
    mostrar(`Erro: ${e.message}. Recarregue a aba do Gestor (F5).`);
  }
});

$('btnCopiar').addEventListener('click', async () => {
  await navigator.clipboard.writeText($('saida').textContent);
  $('btnCopiar').textContent = 'Copiado ✓';
  setTimeout(() => ($('btnCopiar').textContent = 'Copiar resultado'), 1500);
});

carregar();
setInterval(carregar, 3000);
