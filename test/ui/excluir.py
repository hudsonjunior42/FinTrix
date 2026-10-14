import pathlib
from playwright.sync_api import sync_playwright
AQUI = pathlib.Path(__file__).resolve().parent; RAIZ = AQUI.parents[1]
src = open(AQUI/"run.py").read()
exec(src[:src.index("with sync_playwright() as p:")])
fails=[]
def check(l,g,e):
    ok=g==e; print(("OK  " if ok else "FALHA ")+f"{l}: {g!r}"+("" if ok else f" (esperado {e!r})")); 
    if not ok: fails.append(l)
with sync_playwright() as p:
    b=p.chromium.launch(); pg,errs=nova_pagina(b,viewport={"width":1280,"height":860},color_scheme="dark")
    pg.goto("file://"+str(AQUI/"index.html")); pg.wait_for_selector('[data-act="onb-conta"]'); pg.click('[data-act="onb-conta"]'); pg.wait_for_selector("#o-nome")
    pg.fill("#o-nome","Nubank"); money(pg,"#o-saldo","100000"); pg.click('[data-act="onb-criar"]'); pg.wait_for_selector("text=Saldo em contas")
    for nome in ("Carteira","Poupança"):
        pg.click('.side [data-view="contas"]'); pg.click('text=Nova conta'); pg.wait_for_timeout(120); pg.fill("#c-nome",nome); pg.click('[data-act="conta-salvar"]'); pg.wait_for_selector(".mback",state="detached")
    pg.click("#title"); pg.keyboard.press("t"); pg.wait_for_selector("#m-valor:focus"); pg.keyboard.type("5000"); pg.select_option("#m-para",label="Carteira"); pg.keyboard.press("Enter"); pg.wait_for_selector(".mback",state="detached"); pg.wait_for_timeout(200)
    ids=pg.evaluate("Object.fromEntries(Object.entries(S.cfg.contas).map(([id,c])=>[c.nome,id]))")
    pg.evaluate("derivar()"); check("Nubank depois da transferência", pg.evaluate(f"saldoAtual('{ids['Nubank']}')"), 95000)
    # excluir conta com lançamento
    pg.click('.panel:has-text("Carteira") [data-act="conta-editar"]'); pg.wait_for_timeout(120); pg.click('[data-act="conta-excluir"]')
    txt=pg.inner_text("#m-confirm"); print("aviso:", txt.splitlines()[0][:160])
    pg.screenshot(path=str(SHOTS/"50-excluir-conta.png"))
    pg.click('[data-act="conta-excluir-ok"]'); pg.wait_for_selector(".mback",state="detached"); pg.wait_for_timeout(250)
    pg.evaluate("derivar()")
    check("Carteira removida", "Carteira" in pg.evaluate("Object.values(S.cfg.contas).map(c=>c.nome)"), False)
    check("transferência apagada", pg.evaluate("D.L.length"), 0)
    check("Nubank volta ao saldo inicial", pg.evaluate(f"saldoAtual('{ids['Nubank']}')"), 100000)
    # excluir conta sem lançamentos
    pg.click('.panel:has-text("Poupança") [data-act="conta-editar"]'); pg.wait_for_timeout(120); pg.click('[data-act="conta-excluir"]')
    check("aviso simples", pg.inner_text("#m-confirm").startswith("Excluir a conta Poupança?"), True)
    pg.click('[data-act="conta-excluir-ok"]'); pg.wait_for_selector(".mback",state="detached"); pg.wait_for_timeout(250)
    check("contas restantes", pg.evaluate("Object.values(S.cfg.contas).map(c=>c.nome)"), ["Nubank"])
    check("categorias preservadas", pg.evaluate("Object.keys(S.cfg.categorias).length")>50, True)
    print("erros:", errs); b.close()
print("RESULTADO:", "TUDO CERTO" if not fails and not errs else fails)
