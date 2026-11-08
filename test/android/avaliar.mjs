// avalia uma expressão na WebView do app (DevTools pelo adb forward) e imprime o resultado
const [porta, expr] = process.argv.slice(2);
const alvo = (await (await fetch(`http://localhost:${porta}/json`)).json()).find(p => p.type === "page");
const ws = new WebSocket(alvo.webSocketDebuggerUrl);
ws.onopen = () => ws.send(JSON.stringify({ id: 1, method: "Runtime.evaluate", params: { expression: expr, awaitPromise: true, returnByValue: true } }));
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id === 1) { console.log(JSON.stringify(m.result.result?.value ?? m.result)); ws.close(); } };
