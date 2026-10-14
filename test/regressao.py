"""Uso: python3 regressao.py <app antigo> <app novo>   (cada um: .html ou pasta com index.html)
Compara o app original e o novo com a mesma base grande: saldos, previstos, faturas, limites, relatórios, previsões e CSV
precisam dar exatamente o mesmo resultado (as mudanças da 1.0 não podem alterar contas)."""
import json, sys, threading, functools, http.server, pathlib, time
from playwright.sync_api import sync_playwright
T = pathlib.Path(__file__).parent / "tmp"
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
import shutil
def pasta(arg, nome):  # aceita a pasta com index.html ou o próprio .html
    a = pathlib.Path(arg).resolve()
    if a.is_dir(): return str(a)
    d = T / nome; d.mkdir(parents=True, exist_ok=True); shutil.copy(a, d / "index.html"); return str(d)
T.mkdir(exist_ok=True)
if not (T / "medio.json").exists():
    sys.path.insert(0, str(pathlib.Path(__file__).parent)); from gerar import gerar
    (T / "medio.json").write_text(json.dumps(gerar(anos=(2024, 2026), por_mes=60, seed=5)))
for port, d in ((8781, pasta(sys.argv[1], "reg-antigo")), (8782, pasta(sys.argv[2], "reg-novo"))):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(H, directory=d))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
METRICAS = """(() => {
  derivar(); const out = {};
  const meses = []; for (let k = '2022-01'; k <= '2027-03'; k = madd(k, 1)) meses.push(k);
  for (const m of meses) {
    out[m] = { tot: totais(itensMes(m)), cats: gastosPorCat(itensMes(m)), tags: porTag(itensMes(m)),
      saldos: contas(true).map(([id]) => saldoPrevisto(id, m)),
      fats: cartoes(true).map(([id]) => { const f = fatura(id, m); return [f.total, f.pago, f.restante, f.status, f.itens.length]; }),
      prev: Object.keys(cats()).filter(id => !cats()[id].pai).map(id => previsaoCat(id, m)) };
  }
  out.saldoAtual = contas(true).map(([id]) => saldoAtual(id));
  // limites do orçamento mês a mês (a 1.1 guarda por vigência; o resultado tem que ser o mesmo)
  out.orc = meses.map(m => Object.keys(cats()).sort().map(id => typeof limiteEm === "function" ? limiteEm(id, m) : ((C().orc || {})[id] || 0)));
  out.limite = cartoes(true).map(([id]) => limiteUsado(id));
  out.fatDe = ['2026-02-28','2026-04-30','2026-10-03','2026-10-25','2026-12-31'].flatMap(d => cartoes(true).map(([, c]) => faturaDe(c, d)));
  return out;
})()"""
res = {}
with sync_playwright() as p:
    b = p.chromium.launch()
    for port in (8781, 8782):
        ctx = b.new_context(); pg = ctx.new_page(); pg.goto(f"http://localhost:{port}/")
        pg.wait_for_selector('[data-act="onb-restaurar"]'); pg.set_input_files("#imp-json", str(T / "medio.json"))
        try: pg.wait_for_selector("#f-rest", timeout=3000); pg.click('[data-act="restaurar-ok"]')  # versões com a janela de restauração
        except Exception: pass
        pg.wait_for_function("S.fase === 'pronto' && Object.keys(S.anos).length === C().anos.length && Object.values(S.anos).reduce((a, x) => a + x.length, 0) === 2160", timeout=120000)
        # mesmos lançamentos novos pela janela: despesa, compra parcelada 3x pelo total, transferência e fixa
        pg.evaluate("S.mes = '2026-10'; irPara('geral')")
        pg.evaluate("abrirLanc({ tipo: 'cartao' })"); pg.wait_for_function("document.activeElement && document.activeElement.id === 'm-valor'"); pg.fill("#m-valor", "30001"); pg.fill("#m-desc", "TV"); pg.select_option("#m-cat", index=2)
        pg.evaluate("v => { const e = document.querySelector('#m-data'); e.value = v; e.dispatchEvent(new Event('change', { bubbles: true })); }", "2026-10-02")
        pg.evaluate("document.querySelector('details.more').open = true")
        pg.click('[data-act="m-rep"][data-v="parc"]'); pg.fill("#m-n", "3"); pg.click('[data-act="m-vale"][data-v="total"]')
        pg.focus("#m-valor"); pg.keyboard.press("Enter"); time.sleep(.5)
        pg.evaluate("abrirLanc({ tipo: 'despesa' })"); pg.wait_for_function("document.activeElement && document.activeElement.id === 'm-valor'"); pg.fill("#m-valor", "4590"); pg.fill("#m-desc", "Luz"); pg.select_option("#m-cat", index=1)
        pg.evaluate("document.querySelector('details.more').open = true")
        pg.click('[data-act="m-rep"][data-v="fixa"]'); pg.focus("#m-valor"); pg.keyboard.press("Enter"); time.sleep(.5)
        pg.evaluate("abrirLanc({ tipo: 'transf' })"); pg.wait_for_function("document.activeElement && document.activeElement.id === 'm-valor'"); pg.fill("#m-valor", "12345"); pg.keyboard.press("Enter"); time.sleep(.5)
        res[port] = pg.evaluate(METRICAS)
        res[port]["n"] = pg.evaluate("D.L.length"); res[port]["recorr"] = pg.evaluate("Object.keys(C().recorr).length"); res[port]["parc"] = pg.evaluate("D.L.filter(l => l.parc).map(l => [l.parc.i, l.parc.n, l.valor, l.comp]).sort().join()")
        # CSV
        if port == 8781:
            with pg.expect_download() as dl: pg.evaluate("exportCSV()")
        else:
            pg.evaluate("irPara('config')")
            with pg.expect_download() as dl: pg.evaluate("exportCSV()")
        p_ = T / f"csv{port}.csv"; dl.value.save_as(p_); res[port]["csv"] = sorted(l.split(";", 1)[1] for l in p_.read_text(encoding="utf-8-sig").splitlines()[1:])
        ctx.close()
    b.close()
a, c = res[8781], res[8782]
dif = [k for k in a if a[k] != c[k]]
print("lançamentos:", a["n"], c["n"]); print("diferenças:", dif or "nenhuma")
for k in dif[:5]: print(k, json.dumps(a[k])[:300], "\n   ", json.dumps(c[k])[:300])
sys.exit(1 if dif else 0)
