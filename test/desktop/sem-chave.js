// Banco existente sem a chave no chaveiro: o app pede a chave de recuperação, recusa a errada e abre com a certa.
T.rodar(async () => {
  await T.espera(() => typeof S !== "undefined" && ["sem-chave", "pronto"].includes(S.fase), "abrir", 15000);
  if (S.fase === "sem-chave") {
    T.check("pede a chave", !!T.q("#ch-in"), true);
    T.preencher("#ch-in", "0".repeat(64));
    T.q('#f-chave [type="submit"]').click();
    await T.espera(() => /incorreta/.test(T.q("#ch-msg").textContent), "recusar a chave errada");
    T.check("chave errada recusada", T.q("#ch-msg").textContent, "Chave incorreta para este banco.");
    // como a pessoa anotou: grupos com hífen, em maiúsculas
    T.preencher("#ch-in", CHAVE.match(/.{4}/g).join("-").toUpperCase());
    T.q('#f-chave [type="submit"]').click();
    return T.continuar(); // a página recarrega e o app roda este roteiro de novo
  }
  T.check("passou pela tela da chave", T.log.some(l => l.includes("pede a chave")), true);
  derivar();
  T.check("abriu com a chave digitada", Object.values(S.cfg.contas).map(c => c.nome), ["Nubank"]);
});
