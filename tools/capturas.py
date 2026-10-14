"""Gera as capturas de tela do README (docs/img/) com dados fictícios, usando o banco simulado dos testes.
Rode na raiz do repositório: python3 tools/capturas.py   (precisa do Playwright; fontes opcionais em test/ui/fonts)"""
import pathlib, json
from playwright.sync_api import sync_playwright
RAIZ = pathlib.Path(__file__).resolve().parents[1]; UI = RAIZ / "test" / "ui"
src = open(UI/"run.py").read(); exec(src[:src.index("\nwith sync_playwright() as p:")].replace("__file__", repr(str(UI/"run.py"))))
OUT = RAIZ / "docs" / "img"; OUT.mkdir(parents=True, exist_ok=True)
SEED = """(async () => {
  const cat = n => Object.entries(S.cfg.categorias).find(([, c]) => c.nome === n)[0];
  const cc = Object.keys(S.cfg.contas)[0];
  await cfgWrite({ contas: { pp: { nome: 'Poupança', tipo: 'poupanca', inicial: 420000, cor: '#199E70', total: true, arq: false, ordem: 1 }, iv: { nome: 'Tesouro Selic', tipo: 'investimento', inicial: 850000, cor: '#C98500', total: false, arq: false, ordem: 2 } },
    cartoes: { k1: { nome: 'Cartão Roxo', fech: 3, venc: 10, limite: 400000, conta: cc, cor: '#9085E9', arq: false } } });
  await cfgWrite({ contas: { [cc]: { ...S.cfg.contas[cc], nome: 'Conta corrente', inicial: 180000 } } });
  await new Promise(r => setTimeout(r, 80));
  const H = today(), M = H.slice(0, 7); let n = 0; const fat = {};
  const L = (o) => { if (o.cartao) fat[o.comp] = (fat[o.comp] || 0) + o.valor; return lancSave({ id: 'd' + (n++), pago: true, tags: [], obs: '', criado: n, cartao: null, ...o }); };
  const lim = { [cat('Alimentação')]: { '0000-01': 120000 }, [cat('Lazer')]: { '0000-01': 40000 }, [cat('Transporte')]: { '0000-01': 50000 } };
  await cfgWrite({ orc: lim });
  for (let k = -3; k <= 0; k++) {
    const m = madd(M, k), d = dd => m + '-' + String(dd).padStart(2, '0'), dmax = k === 0 ? Number(H.slice(8)) : 28, ok = dd => dd <= dmax;
    await L({ tipo: 'receita', desc: 'Salário', data: d(5), comp: m, conta: cc, cat: cat('Salário'), valor: 450000, pago: ok(5) });
    await L({ tipo: 'despesa', desc: 'Aluguel', data: d(8), comp: m, conta: cc, cat: cat('Aluguel ou financiamento'), valor: 135000, pago: ok(8) });
    await L({ tipo: 'despesa', desc: 'Energia', data: d(12), comp: m, conta: cc, cat: cat('Energia'), valor: 18900 + 900 * k, pago: ok(12) });
    await L({ tipo: 'despesa', desc: 'Internet', data: d(15), comp: m, conta: cc, cat: cat('Internet'), valor: 9990, pago: ok(15) });
    const F = faturaDe(S.cfg.cartoes.k1, d(4));
    const compras = [['Supermercado', 'Supermercado', 38750], ['Feira', 'Feira, padaria e açougue', 9420], ['Restaurante', 'Restaurantes', 12800], ['Aplicativo de transporte', 'Aplicativo e táxi', 6430], ['Combustível', 'Combustível', 22000], ['Streaming', 'Streaming', 3990], ['Farmácia', 'Farmácia', 5870], ['Cinema', 'Cinema e cultura', 7200], ['Livros', 'Livros e material', 8990]];
    let dd = 2;
    for (const [desc, c, v] of compras) { dd += 2; if (!ok(dd)) break; const dt = d(dd); await L({ tipo: 'despesa', desc, data: dt, comp: faturaDe(S.cfg.cartoes.k1, dt), conta: null, cartao: 'k1', cat: cat(c), valor: v + 450 * (k + 3) }); }
    await L({ tipo: 'transf', desc: 'Guardar', data: d(6), comp: m, conta: cc, destino: 'pp', cat: null, valor: 50000, pago: ok(6) });
  }
  await L({ tipo: 'despesa', desc: 'Fone de ouvido', data: madd(M, -1) + '-20', comp: faturaDe(S.cfg.cartoes.k1, madd(M, -1) + '-20'), conta: null, cartao: 'k1', cat: cat('Eletrônicos e informática'), valor: 15000, grupo: 'gf', parc: { i: 2, n: 4 } });
  for (const [m, v] of Object.entries(fat)) { const dt = m + '-10'; if (dt <= H) await L({ tipo: 'transf', desc: 'Pagamento fatura Cartão Roxo', data: dt, comp: m, conta: cc, destino: 'k1', fatPag: m, cat: null, valor: v }); }
})()"""
with sync_playwright() as p:
    b = p.chromium.launch()
    def pagina(**kw):
        pg, errs = nova_pagina(b, **kw)
        pg.goto("file://" + str(UI/"index.html")); pg.wait_for_selector('[data-act="onb-conta"]')
        pg.click('[data-act="onb-conta"]') if not kw.get("is_mobile") else pg.tap('[data-act="onb-conta"]')
        pg.wait_for_selector("#o-nome"); pg.fill("#o-nome", "Conta corrente"); pg.click('[data-act="onb-criar"]'); pg.wait_for_selector("text=Saldo em contas")
        pg.evaluate(SEED); pg.wait_for_timeout(500); pg.evaluate("render()"); pg.wait_for_timeout(200)
        return pg, errs
    pg, errs = pagina(viewport={"width": 1280, "height": 800}, color_scheme="dark")
    pg.mouse.move(5, 795); pg.wait_for_timeout(100); pg.screenshot(path=str(OUT/"visao-geral.png"))
    pg.evaluate("aplicarTema('claro'); irPara('lanc')"); pg.wait_for_timeout(250); pg.screenshot(path=str(OUT/"lancamentos-claro.png"))
    print("erros", errs)
    pm, em = pagina(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
    pm.screenshot(path=str(OUT/"celular.png"))
    pm.evaluate("abrirLanc({ tipo: 'despesa' })"); pm.wait_for_timeout(300); pm.screenshot(path=str(OUT/"celular-lancamento.png"))
    print("erros", em)
    b.close()
