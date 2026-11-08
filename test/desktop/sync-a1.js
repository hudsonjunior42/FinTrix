// Aparelho A (com dados): liga a sincronização numa pasta e salva o código de pareamento para o aparelho B.
T.rodar(async () => {
  await T.espera(() => typeof S !== "undefined" && S.fase === "pronto", "abrir", 15000);
  T.q('.side [data-view="config"]').click();
  await T.espera(() => T.q('[data-act="sync-criar"]'), "botão Ligar");
  T.q('[data-act="sync-criar"]').click();
  await T.espera(() => T.q("#sy-p"), "janela de ligar");
  // bucket S3: endpoint do R2 sem o Account ID é recusado antes de qualquer conexão
  const s3 = T.q('[name="sy-tipo"][value="s3"]'); s3.checked = true; s3.dispatchEvent(new Event("change", { bubbles: true }));
  T.preencher("#sy-end", "https://minhaconta.r2.cloudflarestorage.com/meu-bucket");
  T.preencher("#sy-acc", "chave"); T.q("#sy-sec").value = "segredo";
  T.q('[data-act="sync-criar-ok"]').click();
  T.check("endpoint do R2 conferido", /Account ID/.test(T.q("#m-err").textContent), true);
  T.preencher("#sy-end", "0123456789abcdef0123456789ABCDEF.r2.cloudflarestorage.com/meu-bucket/");
  T.check("bucket tirado do endpoint", destinoDoForm().destino, { tipo: "s3", endpoint: "https://0123456789abcdef0123456789abcdef.r2.cloudflarestorage.com", bucket: "meu-bucket", regiao: "", access: "chave", secret: "segredo" });
  const pasta = T.q('[name="sy-tipo"][value="pasta"]'); pasta.checked = true; pasta.dispatchEvent(new Event("change", { bubbles: true }));
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
