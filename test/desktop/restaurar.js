// Outro computador (pasta e chave novas): restaura o backup salvo na fase 1 pela apresentação.
T.rodar(async () => {
  await T.espera(() => typeof S !== "undefined" && S.fase === "onboarding", "apresentação");
  const dt = new DataTransfer();
  dt.items.add(new File([BACKUP], "fintrix-backup.json", { type: "application/json" }));
  const inp = T.q("#imp-json"); inp.files = dt.files; inp.dispatchEvent(new Event("change", { bubbles: true }));
  await T.espera(() => T.q('[data-act="restaurar-ok"]'), "janela de restaurar");
  T.q('[data-act="restaurar-ok"]').click();
  await T.espera(() => S.fase === "pronto", "dados restaurados", 15000);
  await T.dormir(300);
  derivar();
  const cid = Object.keys(S.cfg.contas)[0];
  T.check("conta restaurada", Object.values(S.cfg.contas).map(c => c.nome), ["Nubank"]);
  T.check("saldo restaurado", saldoAtual(cid), 150000 - 25990);
  T.check("lançamento restaurado", D.L.filter(l => l.desc === "Supermercado").length, 1);
});
