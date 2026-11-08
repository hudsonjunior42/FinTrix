// Aparelho A (com dados): liga a sincronização numa pasta e salva o código de pareamento para o aparelho B.
T.rodar(async () => {
  await T.espera(() => typeof S !== "undefined" && S.fase === "pronto", "abrir", 15000);
  T.q('.side [data-view="config"]').click();
  await T.espera(() => T.q('[data-act="sync-criar"]'), "botão Ligar");
  T.q('[data-act="sync-criar"]').click();
  await T.espera(() => T.q("#sy-p"), "janela de ligar");
  T.preencher("#sy-p", PASTA_SYNC);
  T.q('[data-act="sync-criar-ok"]').click();
  await T.espera(() => T.q("#sy-cod"), "código de pareamento", 20000);
  const codigo = T.q("#sy-cod").value;
  T.check("código de pareamento", codigo.startsWith("FTX1."), true);
  await downloadsTauri().save({ filename: "codigo.txt", data: codigo });
  T.q('.modal [data-act="fechar"]').click();
  await T.espera(() => /Ligada/.test(T.q("#content").innerText), "status ligado");
  T.check("status na tela", /Ligada · pasta/.test(T.q("#content").innerText), true);
});
