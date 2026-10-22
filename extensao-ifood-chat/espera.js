/**
 * Espera por condição, imune a timers esticados.
 *
 * Aba oculta/coberta: o Chrome estica `setTimeout` (~1 s, ou ~60 s no "intensive throttling"). Um laço
 * "confere, dorme 150 ms, sai se o relógio estourou" desiste com o elemento já na tela. Aqui a
 * conferência vem SEMPRE depois de cada sleep (inclusive o último) e a desistência exige um mínimo de
 * conferências, não só o relógio.
 */
(function (raiz) {
  const MIN_CONFERENCIAS = 3;

  function criarWaitUntil({ sleep, agora = Date.now, antesDeConferir = () => {}, intervaloMs = 150 }) {
    return async function waitUntil(fn, timeout) {
      const inicio = agora();
      let conferencias = 0;
      for (;;) {
        antesDeConferir();
        const v = fn();
        conferencias++;
        if (v) return v;
        if (agora() - inicio >= timeout && conferencias >= MIN_CONFERENCIAS) return null;
        await sleep(intervaloMs);
      }
    };
  }

  const api = { criarWaitUntil, MIN_CONFERENCIAS };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else raiz.ORTEX_ESPERA = api;
})(typeof window !== 'undefined' ? window : globalThis);
