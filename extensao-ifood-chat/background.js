/**
 * background.js — service worker MV3. Única peça que fala com o backend (evita CORS).
 *
 * Os listeners do Chrome ficam no TOPO, registrados de forma síncrona: dentro de callback ou
 * função async eles se perdem quando o service worker acorda. O estado vive em chrome.storage
 * (o worker dorme e perde variáveis).
 */
const HOST_GESTOR = 'gestordepedidos.ifood.com.br';
const PADRAO_GESTOR = `https://${HOST_GESTOR}/*`;
const API = '/api/v1/atendimento/extensao/';
const VERSAO = chrome.runtime.getManifest().version;

const COR = { verde: '#2e7d32', amarelo: '#f9a825', vermelho: '#c62828', cinza: '#757575' };

// ── Listeners (síncronos, no topo) ──────────────────────────────────────────

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  tratarMensagem(msg, sender).then(sendResponse).catch((e) => sendResponse({ ok: false, erro: String(e && e.message || e) }));
  return true;
});
chrome.tabs.onRemoved.addListener((tabId) => aoFecharAba(tabId));
chrome.tabs.onUpdated.addListener((tabId, info) => { if (info.url || info.status === 'complete') aoAtualizarAba(tabId); });
chrome.runtime.onStartup.addListener(() => { redesignar().then(atualizarBadge); });
chrome.runtime.onInstalled.addListener(() => { redesignar().then(atualizarBadge); });
chrome.storage.onChanged.addListener(() => { atualizarBadge(); });

// ── Estado ──────────────────────────────────────────────────────────────────

const local = (chaves) => chrome.storage.local.get(chaves);
const sessao = (chaves) => chrome.storage.session.get(chaves);

function ehGestor(url) {
  try { return new URL(url).host === HOST_GESTOR; } catch { return false; }
}

async function abasGestor() {
  const abas = await chrome.tabs.query({ url: PADRAO_GESTOR });
  return abas.map((t) => ({ id: t.id, titulo: t.title || '', url: t.url || '', janela: t.windowId, ativa: t.active }));
}

// ── Aba designada ───────────────────────────────────────────────────────────

/** Mantém a designação válida: aba existente do Gestor, ou a única aberta, ou nenhuma. */
async function redesignar() {
  const abas = await abasGestor();
  const { abaDesignadaId } = await sessao(['abaDesignadaId']);
  if (abaDesignadaId != null && abas.some((a) => a.id === abaDesignadaId)) return abaDesignadaId;
  const nova = abas.length === 1 ? abas[0].id : null;
  if (nova == null) await chrome.storage.session.remove('abaDesignadaId');
  else await chrome.storage.session.set({ abaDesignadaId: nova });
  return nova;
}

async function aoFecharAba(tabId) {
  const { abaDesignadaId } = await sessao(['abaDesignadaId']);
  if (abaDesignadaId === tabId) {
    await chrome.storage.session.remove('abaDesignadaId');
  }
  await redesignar();
  await atualizarBadge();
}

async function aoAtualizarAba(tabId) {
  const { abaDesignadaId } = await sessao(['abaDesignadaId']);
  if (abaDesignadaId === tabId) {
    const t = await chrome.tabs.get(tabId).catch(() => null);
    if (!t || !ehGestor(t.url)) await chrome.storage.session.remove('abaDesignadaId'); // saiu do domínio
  }
  await redesignar();
  await atualizarBadge();
}

// ── Rede ────────────────────────────────────────────────────────────────────

function normalizarUrl(u) {
  try { return new URL(u).origin; } catch { return null; }
}

async function api(caminho, { get = false, dados = {} } = {}) {
  const { backendUrl, token } = await local(['backendUrl', 'token']);
  const base = normalizarUrl(backendUrl);
  if (!base || !token) { await marcarErroApi('nao_configurado'); return { ok: false, erro: 'nao_configurado' }; }
  try {
    const r = await fetch(base + API + caminho, {
      method: get ? 'GET' : 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Extensao-Token': token },
      body: get ? undefined : JSON.stringify(dados),
    });
    if (r.status === 401 || r.status === 403) { await marcarErroApi('token_invalido'); return { ok: false, erro: 'token_invalido', status: r.status }; }
    await marcarErroApi(null);
    if (r.status === 204) return { ok: true, status: 204 };
    const dados = await r.json().catch(() => null);
    return { ok: r.ok, status: r.status, dados };
  } catch (e) {
    await marcarErroApi('sem_backend');
    return { ok: false, erro: 'sem_backend' };
  }
}

async function marcarErroApi(erro) {
  await chrome.storage.session.set({ erroApi: erro });
  await atualizarBadge();
}

// ── Badge ───────────────────────────────────────────────────────────────────

async function atualizarBadge() {
  const { ativo, backendUrl, token } = await local(['ativo', 'backendUrl', 'token']);
  const { erroApi, estadoContent, abaDesignadaId } = await sessao(['erroApi', 'estadoContent', 'abaDesignadaId']);
  let cor = COR.verde; let titulo = 'Ortex – iFood Chat: conectado';
  if (!backendUrl || !token) { cor = COR.cinza; titulo = 'Configure a URL e o token no popup'; }
  else if (ativo === false) { cor = COR.cinza; titulo = 'Desligada'; }
  else if (erroApi && erroApi !== 'nao_configurado') { cor = COR.vermelho; titulo = erroApi === 'token_invalido' ? 'Token inválido ou revogado' : 'Sem conexão com o backend'; }
  else if (abaDesignadaId == null) { cor = COR.amarelo; titulo = 'Nenhuma aba do Gestor designada'; }
  else if (estadoContent?.nivel === 'vermelho') { cor = COR.vermelho; titulo = estadoContent.motivo || 'Seletor crítico quebrado'; }
  else if (estadoContent?.nivel === 'amarelo') { cor = COR.amarelo; titulo = estadoContent.motivo || 'Atenção'; }
  await chrome.action.setBadgeBackgroundColor({ color: cor });
  await chrome.action.setBadgeText({ text: '●' });
  await chrome.action.setTitle({ title: `Ortex – iFood Chat: ${titulo}` });
}

// ── Mensagens do content script e do popup ──────────────────────────────────

async function tratarMensagem(msg, sender) {
  switch (msg?.type) {
    // content script: início de ciclo — sou a aba designada? a extensão está ligada?
    case 'CICLO': {
      const designada = await redesignar();
      const { ativo, modoSeguro, backendUrl, token } = await local(['ativo', 'modoSeguro', 'backendUrl', 'token']);
      return {
        ok: true,
        designada: sender.tab?.id != null && sender.tab.id === designada,
        ativo: ativo !== false,
        modoSeguro: modoSeguro !== false, // default: seguro
        configurado: !!(backendUrl && token),
      };
    }
    case 'ESTADO': {
      await chrome.storage.session.set({ estadoContent: { nivel: msg.nivel, motivo: msg.motivo || '', quando: Date.now(), visivel: msg.visivel, seletores_ok: msg.seletores_ok } });
      await atualizarBadge();
      return { ok: true };
    }
    case 'HEARTBEAT': return api('heartbeat/', { dados: { versao: VERSAO, ...msg.dados } });
    case 'CONFIG': {
      return api('config/', { get: true });
    }
    case 'RESERVAR': return api('fila/reservar/');
    case 'RESULTADO': return api(`fila/${Number(msg.id)}/resultado/`, { dados: { ok: !!msg.ok, passos: msg.passos || [], erro: msg.erro || '' } });

    // popup
    case 'STATUS': {
      const abas = await abasGestor();
      const designada = await redesignar();
      const cfg = await local(['backendUrl', 'token', 'modoSeguro', 'ativo']);
      const s = await sessao(['erroApi', 'estadoContent']);
      return { ok: true, versao: VERSAO, abas, designada, config: { backendUrl: cfg.backendUrl || '', temToken: !!cfg.token, modoSeguro: cfg.modoSeguro !== false, ativo: cfg.ativo !== false }, erroApi: s.erroApi || null, estadoContent: s.estadoContent || null };
    }
    case 'DESIGNAR': {
      await chrome.storage.session.set({ abaDesignadaId: msg.tabId });
      await atualizarBadge();
      return { ok: true };
    }
    case 'TESTAR_CONEXAO': {
      const r = await api('config/', { get: true });
      return { ok: r.ok, erro: r.erro || (r.ok ? null : `http_${r.status}`) };
    }
    default: return { ok: false, erro: 'tipo_desconhecido' };
  }
}

atualizarBadge();
