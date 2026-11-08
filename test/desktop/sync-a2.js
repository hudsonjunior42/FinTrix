// Aparelho A de novo: ao abrir, recebe a despesa lançada no B, sem fazer nada.
T.rodar(async () => {
  await T.espera(() => typeof S !== "undefined" && S.fase === "pronto", "abrir", 15000);
  await T.espera(() => { derivar(); return D.L.some(l => l.desc === "Farmácia do B"); }, "despesa do aparelho B", 20000);
  T.check("chegou a despesa do aparelho B", D.L.filter(l => l.desc === "Farmácia do B").map(l => l.valor), [4500]);
  T.check("lançamentos do A continuam", D.L.filter(l => l.desc === "Supermercado").length, 1);
  T.check("um outro aparelho no cofre", (await T.invoke("sync_estado")).outros, 1);
});
