/**
 * content.js — roda dentro de gestordepedidos.ifood.com.br
 * POC v0.2 (20/out/2026)
 *
 *   DIAGNOSE   → testa seletores e faz inventário do DOM (para calibrar)
 *   SEND_TEST  → abre o chat do pedido e escreve a mensagem
 *                (modo seguro: só preenche, NÃO envia)
 *
 * Mudanças da v0.1:
 *   - Fluxo 0 (novo, preferencial): abre o pedido direto pela URL com o ID iFood.
 *   - Ordem dos fluxos: URL → card → lista do painel (o fluxo da lista está quebrado).
 *   - Card localizado pelo número EXATO "#NNNN" (antes, "0567" casava com "R$ 105,67").
 *   - Trava de segurança: antes de escrever, confere que a conversa aberta é a do
 *     pedido pedido ("#NNNN" no cabeçalho). Se não for, aborta sem escrever.
 *   - Diagnóstico ampliado: mensagens da conversa com lado (cliente × loja),
 *     formato do número nos cards e itens "#NNNN" da página.
 */
(() => {
  if (window.__ORTEX_CHAT_POC_V2__) return;
  window.__ORTEX_CHAT_POC_V2__ = true;

  const S = () => window.ORTEX_SELECTORS || {};
  const ROTA = () => window.ORTEX_ROTA_DETALHE || '#/home/order-display/expedition/';
  const LOG = (...a) => console.log('[Ortex POC]', ...a);

  // Tempos máximos de espera (ms). Esperamos por elemento, não por tempo fixo.
  const T = {
    abrirPainel: 4000,
    abrirConversa: 4000,
    abrirDetalhes: 6000,
    abrirChatDetalhes: 5000,
    aposPreencher: 400,
    aposEnviar: 1000,
    scrollPasso: 400,
    fechar: 500,
  };

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const soDigitos = (s) => String(s || '').replace(/\D/g, '');

  // ── Helpers de seletor ───────────────────────────────────────────────────

  function queryFirst(key, root = document) {
    for (const sel of S()[key] || []) {
      try {
        const el = root.querySelector(sel);
        if (el) return { el, sel };
      } catch (e) { /* seletor inválido */ }
    }
    return { el: null, sel: null };
  }

  function queryAll(key, root = document) {
    for (const sel of S()[key] || []) {
      try {
        const els = root.querySelectorAll(sel);
        if (els.length) return { els: Array.from(els), sel };
      } catch (e) { /* seletor inválido */ }
    }
    return { els: [], sel: null };
  }

  function isVisible(el) {
    if (!el) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }

  async function waitFor(key, timeout = 3000) {
    const inicio = Date.now();
    while (Date.now() - inicio < timeout) {
      const r = queryFirst(key);
      if (r.el && isVisible(r.el)) return r;
      await sleep(150);
    }
    return { el: null, sel: null };
  }

  async function waitUntil(fn, timeout = 3000) {
    const inicio = Date.now();
    while (Date.now() - inicio < timeout) {
      const v = fn();
      if (v) return v;
      await sleep(150);
    }
    return null;
  }

  // ── Número do pedido ─────────────────────────────────────────────────────

  /** Extrai "4595" de "#4595 Walter", "# 4595" etc. Null se não começar com #. */
  function numeroDeRotulo(txt) {
    const m = String(txt || '').trim().match(/^#\s*(\d{2,6})\b/);
    return m ? m[1] : null;
  }

  /**
   * Número do pedido da conversa aberta: sobe a partir do campo de mensagem até
   * achar o cabeçalho com aria-label "#NNNN ...". (Estrutura vista em 20/out.)
   */
  function numeroDaConversaAberta() {
    const input = queryFirst('messageInput').el;
    if (!input || !isVisible(input)) return null;
    let no = input;
    for (let i = 0; i < 12 && no.parentElement; i++) {
      no = no.parentElement;
      for (const h of no.querySelectorAll('[aria-label^="#"]')) {
        const n = numeroDeRotulo(h.getAttribute('aria-label'));
        if (n) return n;
      }
    }
    return null;
  }

  /** Card cujo número EXATO é o pedido (texto-folha ou aria-label começando com #NNNN). */
  function acharCard(numero) {
    const alvo = soDigitos(numero);
    const { els } = queryAll('orderCard');
    for (const card of els) {
      for (const e of card.querySelectorAll('*')) {
        const aria = e.getAttribute('aria-label');
        if (aria && numeroDeRotulo(aria) === alvo) return card;
        if (e.childElementCount === 0 && numeroDeRotulo(e.textContent) === alvo) return card;
      }
    }
    return null;
  }

  // ── Escrita em input controlado pelo React ───────────────────────────────

  function preencher(el, texto) {
    el.focus();
    const proto = el.tagName === 'TEXTAREA'
      ? window.HTMLTextAreaElement.prototype
      : window.HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
    if (setter) setter.call(el, texto); else el.value = texto;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }

  // ── Navegação ────────────────────────────────────────────────────────────

  async function fecharConversa() {
    const input = queryFirst('messageInput').el;
    if (input && isVisible(input)) {
      const c = queryFirst('closeConversationButton').el;
      if (c) { c.click(); await sleep(T.fechar); }
    }
  }

  /** Fluxo 0: navega direto para o detalhe do pedido pelo ID iFood. */
  async function abrirPorId(orderId, passos) {
    if (!orderId) return false;
    await fecharConversa();
    location.hash = ROTA() + orderId.trim();
    passos.push(`fluxo0: navegou para ${ROTA()}${orderId.trim()}`);
    const chat = await waitFor('orderDetailsChatButton', T.abrirDetalhes);
    if (!chat.el) { passos.push('fluxo0: detalhes não abriram (botão de chat não apareceu)'); return false; }
    chat.el.click();
    passos.push(`fluxo0: clicou no chat via ${chat.sel}`);
    const input = await waitFor('messageInput', T.abrirChatDetalhes);
    if (!input.el) { passos.push('fluxo0: campo de mensagem não apareceu'); return false; }
    return true;
  }

  /** Fluxo 1: card na tela de expedição → detalhes → botão de chat. */
  async function abrirPeloCard(numero, passos) {
    await fecharConversa();
    const card = acharCard(numero);
    if (!card) { passos.push(`fluxo1: card #${numero} não encontrado (número exato)`); return false; }
    card.click();
    passos.push('fluxo1: clicou no card');
    const chat = await waitFor('orderDetailsChatButton', T.abrirDetalhes);
    if (!chat.el) { passos.push('fluxo1: botão de chat nos detalhes não apareceu'); return false; }
    chat.el.click();
    passos.push(`fluxo1: clicou no chat via ${chat.sel}`);
    const input = await waitFor('messageInput', T.abrirChatDetalhes);
    if (!input.el) { passos.push('fluxo1: campo de mensagem não apareceu'); return false; }
    return true;
  }

  /** Fluxo 2: painel "Conversas" do header → item "#NNNN" na lista. Seletores a validar. */
  async function abrirPelaLista(numero, passos) {
    await fecharConversa();
    const alvo = soDigitos(numero);
    const botao = queryFirst('chatToggleButton');
    if (!botao.el) { passos.push('fluxo2: botão de conversas não encontrado'); return false; }
    botao.el.click();
    passos.push(`fluxo2: abriu painel via ${botao.sel}`);

    const acharItem = () => {
      for (const e of queryAll('conversationOrderNumber').els) {
        if (!isVisible(e)) continue;
        const n = numeroDeRotulo(e.getAttribute('aria-label')) || numeroDeRotulo(e.textContent);
        if (n === alvo) return e.closest('button,[role="button"],li,a') || e;
      }
      return null;
    };

    let item = await waitUntil(acharItem, T.abrirPainel);
    const scroll = queryFirst('conversationListScroll').el;
    if (!item && scroll) {
      scroll.scrollTop = 0;
      for (let i = 0; i < 15 && !item; i++) {
        const antes = scroll.scrollTop;
        scroll.scrollTop += 250;
        await sleep(T.scrollPasso);
        item = acharItem();
        if (scroll.scrollTop === antes) break;
      }
    }
    if (!item) {
      passos.push(`fluxo2: conversa #${numero} não está na lista`);
      const f = queryFirst('closeChatButton').el;
      if (f) { f.click(); await sleep(T.fechar); }
      return false;
    }
    item.click();
    const input = await waitFor('messageInput', T.abrirConversa);
    if (!input.el) { passos.push('fluxo2: campo de mensagem não apareceu'); return false; }
    passos.push('fluxo2: conversa aberta');
    return true;
  }

  async function enviarTeste({ numero, orderId, mensagem, modoSeguro }) {
    const passos = [];
    const alvo = soDigitos(numero);
    try {
      let ok = false;
      if (orderId) ok = await abrirPorId(orderId, passos);
      if (!ok) ok = await abrirPeloCard(alvo, passos);
      if (!ok) ok = await abrirPelaLista(alvo, passos);
      if (!ok) return { ok: false, erro: 'nao_abriu', passos };

      // ── Trava de segurança: a conversa aberta é a do pedido certo? ──
      const aberto = await waitUntil(numeroDaConversaAberta, 2000);
      if (!aberto) {
        passos.push('ABORTADO: não consegui ler o número da conversa aberta');
        return { ok: false, erro: 'conversa_nao_identificada', passos };
      }
      if (aberto !== alvo) {
        passos.push(`ABORTADO: conversa aberta é #${aberto}, esperado #${alvo}`);
        return { ok: false, erro: 'conversa_errada', passos };
      }
      passos.push(`conferido: conversa aberta é #${aberto}`);

      const input = queryFirst('messageInput');
      preencher(input.el, mensagem);
      await sleep(T.aposPreencher);
      passos.push(`mensagem preenchida via ${input.sel}`);

      if (modoSeguro) {
        passos.push('MODO SEGURO: preenchida e NÃO enviada. Apague o texto manualmente.');
        return { ok: true, enviado: false, passos };
      }

      const btn = await waitFor('sendButton', 2000);
      if (!btn.el) { passos.push('botão de enviar não encontrado'); return { ok: false, erro: 'sem_botao_enviar', passos }; }
      btn.el.click();
      passos.push(`enviado via ${btn.sel}`);
      await sleep(T.aposEnviar);
      return { ok: true, enviado: true, passos };
    } catch (e) {
      passos.push(`erro: ${e.message}`);
      return { ok: false, erro: 'excecao', passos };
    }
  }

  // ── Diagnóstico ──────────────────────────────────────────────────────────

  function resumo(el) {
    const o = { tag: el.tagName.toLowerCase() };
    for (const a of ['data-test-id', 'data-testid', 'aria-label', 'placeholder', 'role']) {
      const v = el.getAttribute(a);
      if (v) o[a] = v.slice(0, 80);
    }
    if (el.childElementCount === 0) {
      const t = el.textContent.trim();
      if (t) o.texto = t.slice(0, 120);
    }
    return o;
  }

  function cadeia(el, niveis = 8) {
    const out = [];
    let n = el;
    for (let i = 0; i < niveis && n && n !== document.body; i++) {
      const r = resumo(n);
      delete r.texto;
      const cls = typeof n.className === 'string' ? n.className.trim().slice(0, 50) : '';
      if (cls) r.classe = cls;
      if (n.style && n.style.position) r.position = n.style.position;
      out.push(r);
      n = n.parentElement;
    }
    return out;
  }

  /** Mensagens da conversa aberta: textos-folha com o lado em que aparecem. */
  function mensagensDaConversa() {
    const pane = queryFirst('conversationPane').el;
    if (!pane) return null;
    const pr = pane.getBoundingClientRect();
    const meio = pr.left + pr.width / 2;
    const itens = [];
    for (const e of pane.querySelectorAll('*')) {
      if (e.childElementCount !== 0 || !isVisible(e)) continue;
      if (e.closest('textarea')) continue;
      const t = e.textContent.trim();
      if (!t) continue;
      const r = e.getBoundingClientRect();
      const centro = r.left + r.width / 2;
      itens.push({
        texto: t.slice(0, 160),
        lado: centro < meio - 10 ? 'esquerda' : centro > meio + 10 ? 'direita' : 'centro',
        tag: e.tagName.toLowerCase(),
        cadeia: cadeia(e, 6),
      });
      if (itens.length >= 40) break;
    }
    return { numeroConversa: numeroDaConversaAberta(), itens };
  }

  function ancorasNumero() {
    const out = [];
    for (const e of document.querySelectorAll('body *')) {
      if (!isVisible(e)) continue;
      const aria = e.getAttribute('aria-label');
      const folha = e.childElementCount === 0 ? e.textContent.trim() : '';
      const n = numeroDeRotulo(aria) || numeroDeRotulo(folha);
      if (!n) continue;
      out.push({ numero: n, aria: aria || undefined, texto: folha || undefined, cadeia: cadeia(e, 8) });
      if (out.length >= 30) break;
    }
    return out;
  }

  function diagnosticar() {
    const seletores = {};
    for (const key of Object.keys(S())) {
      const { els, sel } = queryAll(key);
      seletores[key] = sel
        ? { ok: true, seletor: sel, qtd: els.length, visiveis: els.filter(isVisible).length }
        : { ok: false };
    }

    const testIds = new Set();
    document.querySelectorAll('[data-test-id],[data-testid]').forEach((e) => {
      testIds.add(e.getAttribute('data-test-id') || e.getAttribute('data-testid'));
    });

    const cards = queryAll('orderCard').els.slice(0, 6).map((c) => ({
      rotulosComHash: Array.from(c.querySelectorAll('*'))
        .filter((e) => e.childElementCount === 0 && e.textContent.includes('#'))
        .map((e) => e.textContent.trim().slice(0, 60))
        .slice(0, 3),
    }));

    const titulos = Array.from(document.querySelectorAll('h1,h2,h3,span,p,div'))
      .filter((e) => e.childElementCount === 0 && /convers/i.test(e.textContent) && isVisible(e))
      .map((e) => ({ texto: e.textContent.trim().slice(0, 60), cadeia: cadeia(e, 4) }))
      .slice(0, 10);

    const scrollaveis = Array.from(document.querySelectorAll('div'))
      .filter((d) => isVisible(d) && d.scrollHeight > d.clientHeight + 20
        && /(auto|scroll)/.test(getComputedStyle(d).overflowY))
      .map((d) => ({ ...resumo(d), styleAttr: (d.getAttribute('style') || '').slice(0, 80),
        filhos: d.childElementCount }))
      .slice(0, 15);

    return {
      versaoPoc: '0.2',
      url: location.href,
      quando: new Date().toISOString(),
      seletores,
      numeroConversaAberta: numeroDaConversaAberta(),
      conversa: mensagensDaConversa(),
      ancorasNumero: ancorasNumero(),
      cards,
      titulosConversa: titulos,
      scrollaveis,
      testIds: Array.from(testIds).sort(),
      botoesAriaLabel: Array.from(new Set(
        Array.from(document.querySelectorAll('button[aria-label]')).map((b) => b.getAttribute('aria-label')),
      )),
    };
  }

  // ── Mensagens do popup ───────────────────────────────────────────────────

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg?.type === 'PING') { sendResponse({ ok: true, versao: '0.2' }); return; }
    if (msg?.type === 'DIAGNOSE') { sendResponse(diagnosticar()); return; }
    if (msg?.type === 'SEND_TEST') {
      enviarTeste({
        numero: msg.numero, orderId: msg.orderId, mensagem: msg.mensagem,
        modoSeguro: msg.modoSeguro !== false,
      }).then(sendResponse);
      return true;
    }
  });

  LOG('content script v0.2 carregado');
})();
