// Ajudantes dos roteiros do app desktop. test/desktop.py junta este arquivo com o roteiro da fase
// e o app (build de debug) executa tudo na página ao abrir (variável FINTRIX_TESTE).
// o log sobrevive a um location.reload() (roteiros que recarregam a página: T.continuar)
const _salvo = JSON.parse(sessionStorage.getItem("t.estado") || "null");
sessionStorage.removeItem("t.estado");
const T = {
  log: _salvo ? _salvo.log : [], falhas: _salvo ? _salvo.falhas : [],
  check(nome, got, exp) {
    const ok = JSON.stringify(got) === JSON.stringify(exp);
    T.log.push((ok ? "OK  " : "FALHA ") + `${nome}: ${JSON.stringify(got)}` + (ok ? "" : ` (esperado ${JSON.stringify(exp)})`));
    if (!ok) T.falhas.push(nome);
  },
  async espera(fn, rotulo, ms = 10000) {
    const t0 = Date.now();
    while (Date.now() - t0 < ms) { try { if (fn()) return; } catch {} await T.dormir(50); }
    throw new Error("tempo esgotado: " + rotulo);
  },
  dormir: ms => new Promise(r => setTimeout(r, ms)),
  q: s => document.querySelector(s),
  preencher(sel, v) { const el = T.q(sel); el.focus(); el.value = v; el.dispatchEvent(new Event("input", { bubbles: true })); },
  escolher(sel, texto) {
    const el = T.q(sel), o = [...el.options].find(o => o.text === texto);
    if (!o) throw new Error(`opção "${texto}" não existe em ${sel}`);
    el.value = o.value; el.dispatchEvent(new Event("change", { bubbles: true }));
  },
  tecla: k => document.body.dispatchEvent(new KeyboardEvent("keydown", { key: k, bubbles: true })),
  invoke: (cmd, args) => window.__TAURI__.core.invoke(cmd, args),
  // a página vai recarregar e o app roda o roteiro de novo: guarda o log e não encerra
  continuar() { sessionStorage.setItem("t.estado", JSON.stringify({ log: T.log, falhas: T.falhas })); return "continua"; },
  async rodar(fn) {
    try { if (await fn() === "continua") return; } catch (e) { T.falhas.push("exceção"); T.log.push("EXCEÇÃO: " + (e && e.message || e) + "\n" + (e && e.stack || "")); }
    const resumo = T.falhas.length ? `${T.falhas.length} falha(s): ${T.falhas.join(", ")}` : "TUDO CERTO";
    await T.invoke("teste_fim", { ok: !T.falhas.length, relatorio: T.log.join("\n") + "\nRESULTADO: " + resumo });
  },
};
