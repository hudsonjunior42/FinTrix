"""Parcelado com parcela atual (compra que já começou)."""
import pathlib, json
from playwright.sync_api import sync_playwright
AQUI = pathlib.Path(__file__).resolve().parent; RAIZ = AQUI.parents[1]
src = open(AQUI/"run.py").read()
exec(src[:src.index("\nwith sync_playwright() as p:")])
fails=[]
def check(l,g,e):
    ok=g==e; print(("OK  " if ok else "FALHA ")+f"{l}: {g!r}"+("" if ok else f" (esperado {e!r})"))
    if not ok: fails.append(l)
DOCS = "d => [...window.__store.values()].filter(v => v.desc === d).sort((a,b) => a.parc.i - b.parc.i).map(v => [v.parc.i, v.parc.n, v.valor, v.comp, v.pago])"
with sync_playwright() as p:
    b = p.chromium.launch()
    pg, errs = nova_pagina(b, viewport={"width":1280,"height":900})
    pg.goto("file://"+str(AQUI/"index.html")); pg.wait_for_selector('[data-act="onb-conta"]'); pg.click('[data-act="onb-conta"]'); pg.wait_for_selector("#o-nome")
    pg.fill("#o-nome","Nubank"); pg.click('[data-act="onb-criar"]'); pg.wait_for_selector("text=Saldo em contas")
    conta = pg.evaluate("Object.keys(S.cfg.contas)[0]")
    pg.evaluate(f"cfgWrite({{ cartoes: {{ k1: {{ nome: 'Visa', fech: 25, venc: 5, limite: 500000, conta: '{conta}', cor: '#9085E9', arq: false }} }} }})"); pg.wait_for_timeout(120)
    cat = pg.evaluate("Object.entries(S.cfg.categorias).find(([,c]) => c.nome === 'Eletrônicos e informática')[0]")
    M = pg.evaluate("today().slice(0,7)")
    def abrir(tipo="d"):
        pg.click("#title"); pg.keyboard.press(tipo); pg.wait_for_selector("#m-valor"); pg.wait_for_timeout(80)
    # despesa na conta: 10x de R$ 100, parcela atual 4
    abrir(); pg.keyboard.type("10000"); pg.fill("#m-desc", "Notebook"); pg.select_option("#m-cat", cat)
    pg.click("details.more summary"); pg.click('[data-act="m-rep"][data-v="parc"]'); pg.fill("#m-n", "10"); pg.fill("#m-pa", "4"); pg.wait_for_timeout(60)
    h = pg.inner_text("#m-rep-h").replace("\xa0", " "); print("   dica:", h)
    check("dica fala das parcelas lançadas", ["Lança da parcela 4 até a 10 (7 lançamentos)" in h, "As 3 parcelas anteriores não são lançadas" in h, "faltam R$ 700,00 de R$ 1.000,00" in h], [True, True, True])
    pg.screenshot(path=str(SHOTS/"pa1-janela.png"))
    pg.click("#m-salvar"); pg.wait_for_selector(".mback", state="detached"); pg.wait_for_timeout(150)
    d = pg.evaluate(DOCS, "Notebook")
    check("cria da 4ª à 10ª", [x[0] for x in d], list(range(4, 11)))
    check("valor e total de parcelas", {(x[1], x[2]) for x in d}, {(10, 10000)})
    check("meses a partir de agora", [x[3] for x in d], [pg.evaluate(f"madd('{M}', {i})") for i in range(7)])
    check("só a atual paga", [x[4] for x in d], [True] + [False] * 6)
    # cartão, valor total com centavos que sobram, parcela atual 2 de 3
    abrir("c"); pg.keyboard.type("10001"); pg.fill("#m-desc", "Fone"); pg.select_option("#m-cat", cat)
    pg.click("details.more summary"); pg.click('[data-act="m-rep"][data-v="parc"]'); pg.click('[data-act="m-vale"][data-v="total"]'); pg.fill("#m-n", "3"); pg.fill("#m-pa", "2"); pg.wait_for_timeout(60)
    fat = pg.evaluate("MS.fat")
    pg.click("#m-salvar"); pg.wait_for_selector(".mback", state="detached"); pg.wait_for_timeout(150)
    d = pg.evaluate(DOCS, "Fone")
    check("cartão: parcelas 2 e 3 com o valor certo", [(x[0], x[2]) for x in d], [(2, 3333), (3, 3333)])
    check("cartão: faturas seguidas a partir da atual", [x[3] for x in d], [fat, pg.evaluate(f"madd('{fat}', 1)")])
    # validação
    abrir(); pg.keyboard.type("5000"); pg.select_option("#m-cat", cat)
    pg.click("details.more summary"); pg.click('[data-act="m-rep"][data-v="parc"]'); pg.fill("#m-n", "5"); pg.fill("#m-pa", "7"); pg.wait_for_timeout(60)
    check("parcela atual maior que o total: aviso", pg.inner_text("#m-rep-h"), "A parcela atual não pode passar de 5.")
    pg.click("#m-salvar"); pg.wait_for_timeout(80)
    check("parcela atual maior que o total: não salva", pg.inner_text("#m-err"), "A parcela atual não pode passar de 5.")
    pg.keyboard.press("Escape")
    # editar "esta e as próximas" continua funcionando com a numeração
    pg.click('.side [data-view="lanc"]'); pg.wait_for_timeout(100)
    pg.locator(".row .grow", has_text="Notebook").first.click(); pg.wait_for_selector("#m-scope")
    check("edição mostra a parcela", "Parcela 4 de 10" in pg.text_content("#f-lanc"), True)
    print("erros:", errs); b.close()
print("RESULTADO:", "TUDO CERTO" if not fails and not errs else (fails, errs))
