"""Botão de ordem (crescente/decrescente) em Lançamentos."""
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
    pg.fill("#o-nome","Nubank"); pg.click('[data-act="onb-criar"]'); pg.wait_for_selector("text=Saldo em contas")
    pg.evaluate("""(async () => { const conta = Object.keys(S.cfg.contas)[0], M = today().slice(0,7), cat = Object.keys(S.cfg.categorias)[0];
      for (const [d, n] of [['02','Primeiro'],['10','Meio'],['20','Último']]) await lancSave({ id: rid(), tipo: 'despesa', desc: n, data: M + '-' + d, comp: M, conta, cat, pago: true, cartao: null, valor: 1000, tags: [], obs: '', criado: Date.now() });
      await lancSave({ id: rid(), tipo: 'despesa', desc: 'Mês passado', data: madd(M,-1) + '-15', comp: madd(M,-1), conta, cat, pago: true, cartao: null, valor: 1000, tags: [], obs: '', criado: Date.now() }); })()""")
    pg.wait_for_timeout(200); pg.click('.side [data-view="lanc"]'); pg.wait_for_timeout(100)
    nomes = lambda: pg.locator(".row .t1").all_inner_texts()
    check("mês: padrão do mais antigo", nomes(), ["Primeiro", "Meio", "Último"])
    check("botão só com ícone", [pg.inner_text('[data-act="fordem"]').strip(), pg.locator('[data-act="fordem"] svg').count()], ["", 1])
    pg.click('[data-act="fordem"]'); pg.wait_for_timeout(100)
    check("clique inverte", nomes(), ["Último", "Meio", "Primeiro"])
    check("rótulo acessível", pg.get_attribute('[data-act="fordem"]', "aria-label"), "Ordem: mais recentes primeiro")
    check("foco continua no botão", pg.evaluate("document.activeElement.dataset.act"), "fordem")
    check("guardado", pg.evaluate("localStorage.getItem('lc.ordem')"), '"desc"')
    pg.select_option("#f-per", "12m"); pg.wait_for_timeout(100)
    check("período segue a ordem escolhida", [nomes()[0], nomes()[-1], pg.locator(".mgrp").count()], ["Último", "Mês passado", 2])
    pg.click('[data-act="fordem"]'); pg.wait_for_timeout(100)
    check("período em ordem crescente (meses também)", [nomes()[0], nomes()[-1]], ["Mês passado", "Último"])
    pg.click('[data-act="flimpar"]'); pg.wait_for_timeout(100)
    check("limpar filtros mantém a ordem", nomes(), ["Primeiro", "Meio", "Último"])
    pg.locator(".filters").nth(1).screenshot(path=str(SHOTS/"o1-ordem.png"))
    print("erros:", errs); b.close()
print("RESULTADO:", "TUDO CERTO" if not fails and not errs else (fails, errs))
