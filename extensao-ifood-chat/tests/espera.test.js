// node --test extensao-ifood-chat/tests/
const test = require('node:test');
const assert = require('node:assert/strict');
const { criarWaitUntil, MIN_CONFERENCIAS } = require('../espera.js');

// Relógio falso: cada sleep avança `esticado` ms, não os 150 pedidos (throttling do Chrome).
function ambiente(esticado) {
  let t = 0;
  return { agora: () => t, sleep: async () => { t += esticado; }, avancar: (ms) => { t += ms; } };
}

test('sleep esticado: acha o elemento na conferência final, depois do último sleep', async () => {
  const amb = ambiente(60_000); // intensive throttling: cada sleep dura 1 min
  let aparece = false;
  let chamadas = 0;
  const waitUntil = criarWaitUntil(amb);
  const r = await waitUntil(() => { chamadas++; if (chamadas === 2) aparece = true; return aparece && 'el'; }, 4000);
  assert.equal(r, 'el'); // o elemento surgiu durante o 1º sleep esticado; o relógio já estourou mas conferiu de novo
});

test('relógio estourado antes da 1ª conferência ainda confere o mínimo de vezes', async () => {
  const amb = ambiente(60_000);
  let n = 0;
  const waitUntil = criarWaitUntil(amb);
  const r = await waitUntil(() => { n++; return null; }, 100);
  assert.equal(r, null);
  assert.equal(n, MIN_CONFERENCIAS);
});

test('timeout normal: desiste só depois do prazo, e confere uma última vez', async () => {
  const amb = ambiente(150);
  let n = 0;
  const waitUntil = criarWaitUntil(amb);
  assert.equal(await waitUntil(() => { n++; return null; }, 1000), null);
  assert.ok(n >= 7); // 0..1050 ms em passos de 150
});

test('devolve na primeira conferência sem dormir', async () => {
  let dormiu = false;
  const waitUntil = criarWaitUntil({ sleep: async () => { dormiu = true; }, agora: () => 0 });
  assert.equal(await waitUntil(() => 'x', 1000), 'x');
  assert.equal(dormiu, false);
});

test('interrupção (antesDeConferir lança) propaga', async () => {
  const waitUntil = criarWaitUntil({ sleep: async () => {}, agora: () => 0, antesDeConferir: () => { throw new Error('interrompido'); } });
  await assert.rejects(() => waitUntil(() => null, 1000), /interrompido/);
});
