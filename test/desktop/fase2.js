// Segunda abertura: os dados da fase 1 voltam do SQLite cifrado e aparecem na tela.
T.rodar(async () => {
  await T.espera(() => typeof S !== "undefined" && S.fase === "pronto", "abrir com os dados", 15000);
  derivar();
  const cid = Object.keys(S.cfg.contas)[0];
  T.check("conta após reabrir", Object.values(S.cfg.contas).map(c => c.nome), ["Nubank"]);
  T.check("saldo após reabrir", saldoAtual(cid), 150000 - 25990);
  T.check("lançamento após reabrir", D.L.filter(l => l.desc === "Supermercado" && l.valor === 25990).length, 1);
  await atualizarCopias();
  T.check("cópias após reabrir", COPIAS.n, 1);
  T.check("conteúdo da cópia", (await textoCopia(COPIAS.ult.id)).includes("Supermercado"), true);
  const l = D.L.find(l => l.desc === "Supermercado");
  T.check("referência do comprovante", (l.anexos || []).map(a => a.nome), ["recibo.pdf"]);
  const r = await anexoGet(l.anexos[0].id);
  T.check("comprovante após reabrir", r && await r.blob.text(), "%PDF-1.4 COMPROVANTE-SEGREDO-123");
  // o .zip de comprovantes lê os arquivos sob demanda (getAll não traz os bytes)
  const todos = await anxTx("readonly", st => st.getAll());
  const zip = await montarZip(todos.map(r => ({ nome: r.nome, dados: r.blob })));
  T.check("zip com o comprovante", new TextDecoder().decode(new Uint8Array(await zip.arrayBuffer())).includes("COMPROVANTE-SEGREDO-123"), true);
  T.q('.side [data-view="geral"]').click(); // a fase 1 terminou em Configurações, e o app lembra a tela
  await T.espera(() => T.q(".kpi .val"), "KPI na tela");
  T.check("KPI na tela", T.q(".kpi .val").innerText.replace(/ /g, " "), "R$ 1.240,10");

  // Configurações › Seus dados › Chave de recuperação
  T.q('.side [data-view="config"]').click();
  await T.espera(() => T.q('[data-act="chave-ver"]'), "Configurações");
  // nenhum texto de navegador (nem marcador ${...} esquecido) nas telas de dados do app desktop
  const webismos = t => (t.match(/navegador|[Bb]aixar|[Bb]aixe|página|download|\$\{/g) || []);
  T.check("textos de Configurações", webismos(T.q("#content").innerText), []);
  T.q('[data-act="copias"]').click();
  await T.espera(() => T.q(".modal"), "janela de cópias");
  T.check("textos das cópias automáticas", webismos(T.q(".modal").innerText), []);
  T.q('.modal [data-act="fechar"]').click();
  await T.espera(() => !T.q(".modal"), "fechar cópias");
  const dt = new DataTransfer();
  dt.items.add(new File([JSON.stringify(montarBackup(await lerTudo()))], "b.json", { type: "application/json" }));
  const inp = T.q("#imp-json"); inp.files = dt.files; inp.dispatchEvent(new Event("change", { bubbles: true }));
  await T.espera(() => T.q('[data-act="restaurar-ok"]'), "janela de restaurar");
  T.check("textos da janela de restaurar", webismos(T.q(".modal").innerText), []);
  T.q('.modal [data-act="fechar"]').click();
  await T.espera(() => !T.q(".modal"), "fechar restaurar");
  T.q('[data-act="chave-ver"]').click();
  await T.espera(() => T.q("#ch-ver"), "janela da chave");
  T.check("chave de recuperação mostrada", T.q("#ch-ver").textContent.replace(/[^0-9a-f]/g, ""), CHAVE);
});
