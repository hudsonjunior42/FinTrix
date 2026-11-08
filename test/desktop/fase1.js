// Primeira abertura: cria a conta pela apresentação e lança uma despesa pela janela (tecla D).
T.rodar(async () => {
  await T.espera(() => typeof S !== "undefined" && S.fase === "onboarding", "apresentação");
  T.check("backend nativo", nativoTauri(), true);

  T.q('[data-act="onb-conta"]').click();
  await T.espera(() => T.q("#o-nome"), "formulário da conta");
  T.preencher("#o-nome", "Nubank");
  T.preencher("#o-saldo", "150000");
  T.q('[data-act="onb-criar"]').click();
  await T.espera(() => S.fase === "pronto" && document.body.innerText.includes("Saldo em contas"), "visão geral");

  T.tecla("d");
  await T.espera(() => T.q("#m-valor"), "janela de despesa");
  T.preencher("#m-valor", "25990");
  T.preencher("#m-desc", "Supermercado");
  T.escolher("#m-cat", "Supermercado");
  T.q("#m-salvar").click();
  await T.espera(() => !T.q(".mback"), "janela fechar");
  await T.dormir(300);

  derivar();
  const cid = Object.keys(S.cfg.contas)[0];
  T.check("saldo no app", saldoAtual(cid), 150000 - 25990);
  const docs = await T.invoke("db_todos");
  T.check("config no SQLite", docs.some(([p, d]) => p === "data/users/local/livro" && d.contas?.[cid]?.nome === "Nubank"), true);
  T.check("lançamento no SQLite", docs.filter(([p, d]) => /\/livro\/l\d{4}\//.test(p) && d.desc === "Supermercado" && d.valor === 25990).length, 1);
});
