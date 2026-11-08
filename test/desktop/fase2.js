// Segunda abertura: os dados da fase 1 voltam do SQLite cifrado e aparecem na tela.
T.rodar(async () => {
  await T.espera(() => typeof S !== "undefined" && S.fase === "pronto", "abrir com os dados", 15000);
  derivar();
  const cid = Object.keys(S.cfg.contas)[0];
  T.check("conta após reabrir", Object.values(S.cfg.contas).map(c => c.nome), ["Nubank"]);
  T.check("saldo após reabrir", saldoAtual(cid), 150000 - 25990);
  T.check("lançamento após reabrir", D.L.filter(l => l.desc === "Supermercado" && l.valor === 25990).length, 1);
  await T.espera(() => T.q(".kpi .val"), "KPI na tela");
  T.check("KPI na tela", T.q(".kpi .val").innerText.replace(/ /g, " "), "R$ 1.240,10");
});
