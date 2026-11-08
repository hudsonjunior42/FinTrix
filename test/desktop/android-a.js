// Teste com o celular (test/android_sync.py): o computador liga a sincronização no S3 local, mostra o QR code
// do pareamento e espera o celular parear por ele, lançar "Farmácia do celular" e sincronizar.
T.rodar(async () => {
  await T.espera(() => typeof S !== "undefined" && S.fase === "pronto", "abrir", 15000);
  T.q('.side [data-view="config"]').click();
  await T.espera(() => T.q('[data-act="sync-criar"]'), "botão Ligar");
  T.q('[data-act="sync-criar"]').click();
  await T.espera(() => T.q("#sy-p"), "janela de ligar");
  const s3 = T.q('[name="sy-tipo"][value="s3"]'); s3.checked = true; s3.dispatchEvent(new Event("change", { bubbles: true }));
  T.preencher("#sy-end", S3_ENDPOINT);
  T.preencher("#sy-bucket", "fintrix-teste");
  T.preencher("#sy-acc", "teste"); T.q("#sy-sec").value = "teste";
  T.q('[data-act="sync-criar-ok"]').click();
  await T.espera(() => T.q("#sy-qr svg"), "QR code", 20000);
  T.check("QR code na janela do código", !!T.q("#sy-qr svg"), true);
  // o celular pareia e lança; aqui sincroniza a cada 3 s até a despesa chegar (até 5 minutos)
  const t0 = Date.now();
  while (Date.now() - t0 < 300000) {
    await T.invoke("sync_agora", { versao: VERSAO_DADOS }).catch(() => {});
    derivar();
    if (D.L.some(l => l.desc === "Farmácia do celular")) break;
    await T.dormir(3000);
  }
  T.check("chegou a despesa do celular", D.L.filter(l => l.desc === "Farmácia do celular").map(l => l.valor), [4500]);
  T.check("um outro aparelho no cofre", (await T.invoke("sync_estado")).outros, 1);
});
