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
  await T.espera(() => T.q(".kpi .val"), "KPI na tela");
  T.check("KPI na tela", T.q(".kpi .val").innerText.replace(/ /g, " "), "R$ 1.240,10");
});
