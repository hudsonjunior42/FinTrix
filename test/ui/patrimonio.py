"""Patrimônio sem contas correntes nem gastos no cartão."""
import pathlib
from playwright.sync_api import sync_playwright
AQUI = pathlib.Path(__file__).resolve().parent; RAIZ = AQUI.parents[1]
src = open(AQUI/"run.py").read()
exec(src[:src.index("\nwith sync_playwright() as p:")])
fails=[]
def check(l,g,e):
    ok=g==e; print(("OK  " if ok else "FALHA ")+f"{l}: {g!r}"+("" if ok else f" (esperado {e!r})"))
    if not ok: fails.append(l)
with sync_playwright() as p:
    b = p.chromium.launch()
    pg, errs = nova_pagina(b, viewport={"width":1280,"height":900})
    pg.goto("file://"+str(AQUI/"index.html")); pg.wait_for_selector('[data-act="onb-conta"]'); pg.click('[data-act="onb-conta"]'); pg.wait_for_selector("#o-nome")
    pg.fill("#o-nome","Nubank"); money(pg, "#o-saldo", "250000"); pg.click('[data-act="onb-criar"]'); pg.wait_for_selector("text=Saldo em contas")
    conta = pg.evaluate("Object.keys(S.cfg.contas)[0]")
    pg.evaluate(f"""(async () => {{
      await cfgWrite({{ contas: {{ pp: {{ nome: 'Poupança', tipo: 'poupanca', inicial: 100000, cor: '#199E70', total: true, arq: false, ordem: 1 }},
                                 iv: {{ nome: 'Tesouro', tipo: 'investimento', inicial: 500000, cor: '#C98500', total: false, arq: false, ordem: 2 }} }},
        cartoes: {{ k1: {{ nome: 'Visa', fech: 25, venc: 5, limite: 300000, conta: '{conta}', cor: '#9085E9', arq: false }} }} }});
      await new Promise(r => setTimeout(r, 60));
      const d = today();
      await lancSave({{ id: 'c1', tipo: 'despesa', desc: 'Loja', data: d, comp: faturaDe(S.cfg.cartoes.k1, d), conta: null, cartao: 'k1', cat: null, valor: 30000, pago: true, tags: [], obs: '', criado: 1 }});
      await lancSave({{ id: 't1', tipo: 'transf', desc: 'Guardar', data: d, comp: d.slice(0,7), conta: '{conta}', destino: 'pp', cat: null, cartao: null, valor: 20000, pago: true, tags: [], obs: '', criado: 2 }});
    }})()"""); pg.wait_for_timeout(250)
    pg.evaluate("irPara('patrimonio')"); pg.wait_for_timeout(150)
    k = [x.replace("\xa0", " ") for x in pg.locator(".kpi .val").all_inner_texts()]
    check("patrimônio = poupança + investimento", k[0], "R$ 6.200,00")
    check("em contas: só a poupança", k[1], "R$ 1.200,00")
    check("sem KPI de dívida do cartão", pg.locator(".kpi .lab", has_text="Dívida").count(), 0)
    comp = pg.locator('.panel:has(h2:text("Composição hoje"))')
    check("composição sem conta corrente e sem cartão", [comp.locator(".li", has_text="Nubank").count(), comp.locator(".li", has_text="Visa").count(), comp.locator(".li", has_text="Poupança").count(), comp.locator(".li", has_text="Tesouro").count()], [0, 0, 1, 1])
    check("aviso do que não entra", "contas correntes (Nubank)" in comp.inner_text() and "gastos no cartão" in comp.inner_text(), True)
    check("série do mês atual", pg.evaluate("seriePatrimonio([today().slice(0,7)])[0].liq"), 620000)
    pg.screenshot(path=str(SHOTS/"pt1-patrimonio.png"))
    print("erros:", errs); b.close()
print("RESULTADO:", "TUDO CERTO" if not fails and not errs else (fails, errs))
