// Aparelho B (novo): entra no cofre pela apresentação, recebe tudo do A e lança uma despesa.
T.rodar(async () => {
  await T.espera(() => typeof S !== "undefined" && ["onboarding", "pronto"].includes(S.fase), "abrir", 15000);
  if (S.fase === "onboarding") {
    T.q('[data-act="sync-entrar"]').click();
    await T.espera(() => T.q("#sy-cod-in"), "janela de entrar");
    T.preencher("#sy-cod-in", "FTX1.errado");
    T.q('[data-act="sync-entrar-ok"]').click();
    await T.espera(() => T.q("#m-err").textContent, "erro do código errado");
    T.check("código errado recusado", /código de pareamento/i.test(T.q("#m-err").textContent), true);
    T.preencher("#sy-cod-in", CODIGO);
    T.preencher("#sy-p", PASTA_SYNC);
    T.q('[data-act="sync-entrar-ok"]').click();
    return T.continuar(); // entra, a página recarrega e o app roda este roteiro de novo
  }
  T.check("passou pela apresentação", T.log.some(l => l.includes("código errado recusado")), true);
  derivar();
  T.check("conta veio do aparelho A", Object.values(S.cfg.contas).map(c => c.nome), ["Nubank"]);
  const l = D.L.find(l => l.desc === "Supermercado");
  T.check("lançamento veio do aparelho A", l && l.valor, 25990);
  const r = l && l.anexos?.length ? await anexoGet(l.anexos[0].id) : null;
  T.check("comprovante veio do aparelho A", r && await r.blob.text(), "%PDF-1.4 COMPROVANTE-SEGREDO-123");
  T.q('.side [data-view="geral"]').click();
  T.tecla("d");
  await T.espera(() => T.q("#m-valor"), "janela de despesa");
  T.preencher("#m-valor", "4500");
  T.preencher("#m-desc", "Farmácia do B");
  T.escolher("#m-cat", "Farmácia");
  T.q("#m-salvar").click();
  await T.espera(() => !T.q(".mback"), "salvar");
  const ciclo = await T.invoke("sync_agora", { versao: VERSAO_DADOS });
  T.check("enviou ao cofre", ciclo.enviou, true);
});
