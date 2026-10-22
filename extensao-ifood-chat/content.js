/**
 * content.js — roda dentro de gestordepedidos.ifood.com.br.
 *
 * Dirige o relógio (setInterval): a cada ciclo pergunta ao background se esta é a aba designada,
 * reserva UMA mensagem da fila do CRM, abre o chat do pedido, confere que a conversa é a certa,
 * escreve, envia e reporta. Toda a rede passa pelo background (CORS).
 *
 * Entrega no máximo uma vez: qualquer dúvida vira falha/incerta, nunca reenvio automático.
 */
(() => {
  if (window.__ORTEX_CHAT__) return;
  window.__ORTEX_CHAT__ = true;

  const VERSAO = chrome.runtime.getManifest().version;
  const LOG = (...a) => console.log('[Ortex Chat]', ...a);

  // ── Configuração (embutida + remota por cima, chave a chave) ──────────────

  const SELETORES = { ...(window.ORTEX_SELECTORS || {}) };
  const ROTA = window.ORTEX_ROTA_DETALHE || '#/home/order-display/expedition/';
  const CRITICOS = window.ORTEX_SELETORES_CRITICOS || ['messageInput', 'sendButton', 'chatToggleButton'];

  // Timeouts MÁXIMOS (esperamos por elemento, não por tempo fixo). Sleep fixo só onde não há o que esperar.
  const T = {
    abrirPainel: 4000,
    abrirConversa: 4000,
    abrirDetalhes: 6000,
    abrirChatDetalhes: 5000,
    aposNavegar: 400,
    aposPreencher: 400,
    aposEnviar: 1000,
    scrollPasso: 400,
    fechar: 500,
    entreMensagens: 2500,
  };

  const CFG = { intervalo_segundos: 5, pausa_interacao_segundos: 15 };
  const HEARTBEAT_MS = 30_000;
  const CONFIG_MS = 5 * 60_000;

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const soDigitos = (s) => String(s || '').replace(/\D/g, '');

  // ── Erros de fluxo (viram `erro` no resultado) ────────────────────────────

  class FluxoErro extends Error {
    constructor(codigo, passo) { super(codigo); this.codigo = codigo; this.passo = passo; }
  }

  // ── Interação humana ──────────────────────────────────────────────────────
  // Cliques da própria extensão têm isTrusted === false; só gesto real do usuário conta.

  let ultimoHumanoEm = 0;
  const marcarHumano = (e) => { if (e.isTrusted) ultimoHumanoEm = Date.now(); };
  for (const ev of ['mousedown', 'keydown', 'wheel']) document.addEventListener(ev, marcarHumano, true);

  const humanoRecente = () => Date.now() - ultimoHumanoEm < CFG.pausa_interacao_segundos * 1000;

  let fluxoIniciadoEm = 0;
  function checarInterrupcao() {
    if (fluxoIniciadoEm && ultimoHumanoEm > fluxoIniciadoEm) throw new FluxoErro('interrompido_por_usuario');
  }

  // ── Helpers de seletor ────────────────────────────────────────────────────

  const lista = (key) => {
    const v = SELETORES[key];
    return Array.isArray(v) ? v : (typeof v === 'string' ? [v] : []);
  };

  function queryFirst(key, root = document) {
    for (const sel of lista(key)) {
      try {
        const el = root.querySelector(sel);
        if (el) return { el, sel };
      } catch { /* seletor inválido vindo do backend */ }
    }
    return { el: null, sel: null };
  }

  function queryAll(key, root = document) {
    for (const sel of lista(key)) {
      try {
        const els = root.querySelectorAll(sel);
        if (els.length) return { els: Array.from(els), sel };
      } catch { /* idem */ }
    }
    return { els: [], sel: null };
  }

  function isVisible(el) {
    if (!el) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }

  // Confere SEMPRE depois do último sleep e só desiste após um mínimo de conferências (ver espera.js):
  // com a aba oculta/coberta o Chrome estica os timers e o relógio sozinho não é confiável.
  const waitUntil = window.ORTEX_ESPERA.criarWaitUntil({ sleep, antesDeConferir: () => checarInterrupcao() });

  async function waitFor(key, timeout) {
    const r = await waitUntil(() => {
      const q = queryAll(key);
      const el = q.els.find(isVisible);
      return el ? { el, sel: q.sel } : null;
    }, timeout);
    return r || { el: null, sel: null };
  }

  // ── Leitura de tela ───────────────────────────────────────────────────────

  /** "#4595 Walter" → "4595". Null se não começar com "#". Mantém zeros à esquerda. */
  function numeroDeRotulo(txt) {
    const m = String(txt || '').trim().match(/^#\s*(\d{2,6})\b/);
    return m ? m[1] : null;
  }

  /** Número da conversa aberta: sobe do campo de mensagem até achar o cabeçalho "#NNNN ...". */
  function numeroDaConversaAberta() {
    const input = queryFirst('messageInput').el;
    if (!input || !isVisible(input)) return null;
    let no = input;
    for (let i = 0; i < 12 && no.parentElement; i++) {
      no = no.parentElement;
      for (const sel of lista('conversationHeader')) {
        let achados = [];
        try { achados = no.querySelectorAll(sel); } catch { /* inválido */ }
        for (const h of achados) {
          const n = numeroDeRotulo(h.getAttribute('aria-label'));
          if (n) return n;
        }
      }
    }
    return null;
  }

  /** Título "Conversas" visível = painel aberto. Devolve o elemento ou null. */
  function tituloPainel() {
    return queryAll('conversationPanelTitle').els
      .find((e) => isVisible(e) && /^conversas$/i.test(e.textContent.trim())) || null;
  }

  function hashAtual() { return location.hash || ''; }

  // ── Escrita em input controlado pelo React ────────────────────────────────

  function preencher(el, texto) {
    el.focus();
    const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set;
    if (setter) setter.call(el, texto); else el.value = texto;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }

  // ── Limpeza de estado ─────────────────────────────────────────────────────

  /** Fecha a conversa e o painel, se abertos. Nunca lança: roda também depois de falhas. */
  async function limparEstado() {
    try {
      const input = queryFirst('messageInput').el;
      if (input && isVisible(input)) {
        const c = queryAll('closeConversationButton').els.find(isVisible);
        if (c) { c.click(); await sleep(T.fechar); }
      }
      const titulo = tituloPainel();
      if (titulo) {
        // "visível mais próxima do painel": sobe do título até um ancestral que contenha um botão de fechar visível
        let no = titulo;
        for (let i = 0; i < 10 && no.parentElement; i++) {
          no = no.parentElement;
          const btn = queryAll('closeChatButton', no).els.find(isVisible);
          if (btn) { (btn.closest('button,[role="button"]') || btn).click(); await sleep(T.fechar); break; }
        }
      }
    } catch (e) { LOG('limparEstado falhou', e); }
  }

  // ── Fluxos para abrir a conversa ──────────────────────────────────────────

  /** Fluxo principal: rota de detalhe com o ID iFood. Cria a conversa se não existir. */
  async function abrirPorRota(orderId, passos) {
    location.hash = ROTA + String(orderId).trim();
    passos.push(`rota: navegou para ${ROTA}${orderId}`);
    await sleep(T.aposNavegar); // deixa a tela trocar antes de procurar o botão (evita o botão do pedido anterior)
    const chat = await waitFor('orderDetailsChatButton', T.abrirDetalhes);
    if (!chat.el) { passos.push('rota: botão de chat dos detalhes não apareceu'); throw new FluxoErro('rota_nao_abriu'); }
    chat.el.click();
    passos.push(`rota: clicou no chat via ${chat.sel}`);
    const input = await waitFor('messageInput', T.abrirChatDetalhes);
    if (!input.el) { passos.push('rota: campo de mensagem não apareceu'); throw new FluxoErro('rota_nao_abriu'); }
  }

  /** Reserva: painel "Conversas" → h2 "#NNNN" na lista virtual. Só acha pedido que já tem conversa. */
  async function abrirPelaLista(displayId, passos) {
    const botao = queryFirst('chatToggleButton');
    if (!botao.el) { passos.push('lista: botão de conversas não encontrado'); throw new FluxoErro('painel_nao_abriu'); }
    botao.el.click();
    passos.push(`lista: clicou em ${botao.sel}`);
    const titulo = await waitUntil(tituloPainel, T.abrirPainel);
    if (!titulo) { passos.push('lista: título "Conversas" não apareceu'); throw new FluxoErro('painel_nao_abriu'); }
    passos.push('lista: painel aberto');

    const alvo = `#${displayId}`;
    const acharItem = () => {
      for (const e of queryAll('conversationOrderNumber').els) {
        if (!isVisible(e) || e.textContent.trim() !== alvo) continue;
        let no = e;
        while (no && no !== document.body) { // item clicável = ancestral com position:absolute (lista virtual)
          if (no.style && no.style.position === 'absolute') return no;
          no = no.parentElement;
        }
        return e;
      }
      return null;
    };

    let item = await waitUntil(acharItem, T.abrirPainel);
    if (!item) {
      let no = titulo; let scroll = null;
      for (let i = 0; i < 10 && no.parentElement && !scroll; i++) {
        no = no.parentElement;
        scroll = queryAll('conversationListScroll', no).els.find((s) => isVisible(s) && s.scrollHeight > s.clientHeight) || null;
      }
      if (scroll) {
        scroll.scrollTop = 0;
        for (let i = 0; i < 15 && !item; i++) {
          checarInterrupcao();
          const antes = scroll.scrollTop;
          scroll.scrollTop += 250;
          await sleep(T.scrollPasso);
          item = acharItem();
          if (scroll.scrollTop === antes) break;
        }
      }
    }
    if (!item) { passos.push(`lista: conversa ${alvo} não está na lista`); throw new FluxoErro('conversa_nao_encontrada'); }
    item.click();
    const input = await waitFor('messageInput', T.abrirConversa);
    if (!input.el) { passos.push('lista: campo de mensagem não apareceu'); throw new FluxoErro('conversa_nao_identificada'); }
    passos.push('lista: conversa aberta');
  }

  // O fluxo por card está desligado até o formato do número no card ser confirmado (ver spec).

  // ── Processar uma mensagem ────────────────────────────────────────────────

  async function processar(m, modoSeguro) {
    // Cada passo também vai pro Console da aba (diagnóstico sem depender do CRM)
    const passos = [];
    const empurrar = passos.push.bind(passos);
    passos.push = (...novos) => { for (const p of novos) LOG(`#${m.display_id}`, p); return empurrar(...novos); };
    fluxoIniciadoEm = Date.now();
    try {
      await limparEstado();
      checarInterrupcao();

      // 1) Abrir: rota por ID (principal) → lista do painel (reserva)
      let falhaRota = null;
      if (m.ifood_order_id) {
        try { await abrirPorRota(m.ifood_order_id, passos); } catch (e) {
          if (!(e instanceof FluxoErro) || e.codigo === 'interrompido_por_usuario') throw e;
          falhaRota = e;
          await limparEstado();
        }
      } else {
        passos.push('rota: sem ifood_order_id, pulando');
      }
      if (!m.ifood_order_id || falhaRota) {
        try { await abrirPelaLista(m.display_id, passos); } catch (e) {
          // rota falhou E a lista também: a causa raiz é a rota (é o caminho principal, e o alerta
          // `rota_nao_abriu` do CRM depende disso); a falha da lista fica registrada nos passos
          if (e instanceof FluxoErro && falhaRota && e.codigo !== 'interrompido_por_usuario') {
            passos.push(`lista: também falhou (${e.codigo})`);
            throw falhaRota;
          }
          throw e;
        }
      }

      // 2) Trava: a conversa aberta é a do pedido certo?
      const aberto = await waitUntil(numeroDaConversaAberta, 2000);
      if (!aberto) { passos.push('ABORTADO: número da conversa aberta ilegível'); throw new FluxoErro('conversa_nao_identificada'); }
      if (aberto !== String(m.display_id)) { passos.push(`ABORTADO: conversa aberta é #${aberto}, esperado #${m.display_id}`); throw new FluxoErro('conversa_errada'); }
      passos.push(`conferido: conversa #${aberto}`);

      // 3) Escrever
      checarInterrupcao();
      const input = queryFirst('messageInput');
      preencher(input.el, m.texto);
      await sleep(T.aposPreencher);
      passos.push(`mensagem preenchida via ${input.sel}`);

      if (modoSeguro) {
        preencher(input.el, '');
        passos.push('MODO SEGURO: preenchida e NÃO enviada (campo limpo)');
        throw new FluxoErro('modo_seguro');
      }

      // 4) Enviar (última chance de abortar por interação humana)
      const btn = await waitUntil(() => {
        const q = queryAll('sendButton');
        const el = q.els.find((b) => isVisible(b) && !b.disabled);
        return el ? { el, sel: q.sel } : null;
      }, 2000);
      if (!btn) { passos.push('botão de enviar não encontrado/habilitado'); throw new FluxoErro('sem_botao_enviar'); }
      checarInterrupcao();
      fluxoIniciadoEm = 0; // a partir do clique não há mais como abortar
      btn.el.click();
      passos.push(`enviado via ${btn.sel}`);
      await sleep(T.aposEnviar);
      passos.push(`campo após envio: ${input.el.value === '' ? 'limpo' : 'ainda preenchido'}`);
      return { ok: true, passos, erro: '' };
    } catch (e) {
      if (e instanceof FluxoErro) {
        passos.push(`erro: ${e.codigo}`);
        return { ok: false, passos, erro: e.codigo };
      }
      passos.push(`exceção: ${e && e.message}`);
      LOG('exceção no fluxo', e);
      return { ok: false, passos, erro: 'excecao' };
    } finally {
      fluxoIniciadoEm = 0;
      await limparEstado();
    }
  }

  // ── Heartbeat e diagnóstico leve ──────────────────────────────────────────

  /** Cada chave testada sem clicar em nada. Só inclui chaves que fazem sentido na tela atual. */
  function seletoresOk() {
    const ok = {};
    const existe = (k) => queryAll(k).els.length > 0;
    ok.chatToggleButton = existe('chatToggleButton');
    const conversaAberta = queryAll('conversationPane').els.some(isVisible);
    if (conversaAberta) {
      for (const k of ['conversationPane', 'messageInput', 'sendButton', 'closeConversationButton']) ok[k] = existe(k);
    }
    if (hashAtual().startsWith(ROTA) && !conversaAberta) ok.orderDetailsChatButton = existe('orderDetailsChatButton');
    return ok;
  }

  const visivel = () => document.visibilityState === 'visible';

  function nivelEstado(ok, pausada) {
    const quebrado = CRITICOS.filter((k) => ok[k] === false);
    if (quebrado.length) return { nivel: 'vermelho', motivo: `Seletor quebrado: ${quebrado.join(', ')}` };
    if (!visivel()) return { nivel: 'amarelo', motivo: 'Aba do Gestor oculta: envios atrasados' };
    if (pausada) return { nivel: 'amarelo', motivo: 'Pausada: alguém está usando a aba' };
    return { nivel: 'verde', motivo: '' };
  }

  let ultimoHeartbeat = 0;
  async function heartbeat() {
    ultimoHeartbeat = Date.now();
    const ok = seletoresOk();
    await bg({ type: 'HEARTBEAT', dados: { aba_ok: ok.chatToggleButton === true, aba_visivel: visivel(), seletores_ok: ok, url: location.href.split('?')[0] } });
    await bg({ type: 'ESTADO', ...nivelEstado(ok, humanoRecente()), visivel: visivel(), seletores_ok: ok });
  }

  let ultimaConfig = 0;
  async function carregarConfig() {
    ultimaConfig = Date.now();
    const r = await bg({ type: 'CONFIG' });
    if (!r?.ok || !r.dados) return;
    const d = r.dados;
    if (d.seletores && typeof d.seletores === 'object') {
      for (const [k, v] of Object.entries(d.seletores)) if (Array.isArray(v) || typeof v === 'string') SELETORES[k] = v;
    }
    if (d.tempos_ms && typeof d.tempos_ms === 'object') {
      for (const [k, v] of Object.entries(d.tempos_ms)) if (Number.isFinite(v) && v >= 0) T[k] = v;
    }
    const novo = Number(d.intervalo_segundos) || CFG.intervalo_segundos;
    CFG.pausa_interacao_segundos = Number(d.pausa_interacao_segundos) || CFG.pausa_interacao_segundos;
    if (novo !== CFG.intervalo_segundos) { CFG.intervalo_segundos = novo; reiniciarRelogio(); }
  }

  // ── Ponte com o background ────────────────────────────────────────────────

  let parado = false;
  async function bg(msg) {
    try { return await chrome.runtime.sendMessage(msg); } catch (e) {
      // Extensão recarregada/atualizada: este content script ficou órfão. Para de vez.
      if (/context invalidated/i.test(String(e && e.message))) pararRelogio();
      return null;
    }
  }

  // ── Ciclo ─────────────────────────────────────────────────────────────────

  let processando = false;

  async function ciclo() {
    if (processando || parado) return;
    processando = true;
    try {
      const ctx = await bg({ type: 'CICLO' });
      if (!ctx?.ok || !ctx.designada || !ctx.ativo || !ctx.configurado) return;

      if (Date.now() - ultimaConfig > CONFIG_MS) await carregarConfig();
      if (Date.now() - ultimoHeartbeat > HEARTBEAT_MS) await heartbeat();
      if (humanoRecente()) return;

      // Esvazia a fila em série: uma mensagem por vez, 2,5 s entre elas.
      for (;;) {
        if (humanoRecente()) return;
        const r = await bg({ type: 'RESERVAR' });
        if (!r?.ok || r.status === 204 || !r.dados) return;
        const m = r.dados;
        LOG('processando', m.id, `#${m.display_id}`);
        const res = await processar(m, ctx.modoSeguro);
        const enviado = await bg({ type: 'RESULTADO', id: m.id, ok: res.ok, passos: res.passos, erro: res.erro });
        if (!enviado?.ok) LOG('resultado não registrado', enviado); // lease vencido → `incerta`, nunca reenvia
        await heartbeat();
        await sleep(T.entreMensagens);
      }
    } catch (e) {
      LOG('erro no ciclo', e);
    } finally {
      processando = false;
    }
  }

  let relogio = null;
  function reiniciarRelogio() {
    if (relogio) clearInterval(relogio);
    relogio = setInterval(ciclo, CFG.intervalo_segundos * 1000);
  }
  function pararRelogio() {
    parado = true;
    if (relogio) clearInterval(relogio);
    relogio = null;
  }

  document.addEventListener('visibilitychange', () => {
    // Aba oculta: avisa na hora (o CRM mostra "envios atrasados"); voltou: limpa o aviso na hora.
    bg({ type: 'CICLO' }).then((ctx) => { if (ctx?.ok && ctx.designada && ctx.ativo && ctx.configurado) heartbeat(); });
  });

  // ── Diagnóstico completo (popup) ──────────────────────────────────────────

  function resumo(el) {
    const o = { tag: el.tagName.toLowerCase() };
    for (const a of ['data-test-id', 'data-testid', 'aria-label', 'placeholder', 'role']) {
      const v = el.getAttribute(a);
      if (v) o[a] = v.slice(0, 80);
    }
    return o;
  }

  function diagnosticar() {
    const seletores = {};
    for (const key of Object.keys(SELETORES)) {
      const { els, sel } = queryAll(key);
      seletores[key] = sel ? { ok: true, seletor: sel, qtd: els.length, visiveis: els.filter(isVisible).length } : { ok: false };
    }
    const testIds = new Set();
    document.querySelectorAll('[data-test-id],[data-testid]').forEach((e) => testIds.add(e.getAttribute('data-test-id') || e.getAttribute('data-testid')));
    return {
      versao: VERSAO,
      url: location.href,
      quando: new Date().toISOString(),
      visivel: visivel(),
      seletores,
      numeroConversaAberta: numeroDaConversaAberta(),
      painelConversasAberto: !!tituloPainel(),
      testIds: Array.from(testIds).sort(),
      botoesAriaLabel: Array.from(new Set(Array.from(document.querySelectorAll('button[aria-label]')).map((b) => resumo(b)['aria-label']))),
    };
  }

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg?.type === 'DIAGNOSE') { sendResponse(diagnosticar()); return; }
  });

  reiniciarRelogio();
  ciclo();
  LOG(`content script v${VERSAO} carregado`);
})();
