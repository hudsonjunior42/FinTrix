import pathlib
from playwright.sync_api import sync_playwright
AQUI = pathlib.Path(__file__).resolve().parent; RAIZ = AQUI.parents[1]
src = open(AQUI/"run.py").read()
exec(src[:src.index("with sync_playwright() as p:")])
fails=[]
def check(l,g,e):
    ok=g==e; print(("OK  " if ok else "FALHA ")+f"{l}: {g!r}"+("" if ok else f" (esperado {e!r})"))
    if not ok: fails.append(l)
with sync_playwright() as p:
    b=p.chromium.launch()
    for vp, nome in (({"width":1280,"height":820}, "desk"), ({"width":390,"height":844}, "mob")):
        pg,errs=nova_pagina(b,viewport=vp,color_scheme="dark" if nome=="desk" else "light", is_mobile=nome=="mob", has_touch=nome=="mob")
        pg.goto("file://"+str(AQUI/"index.html")); pg.wait_for_selector('[data-act="onb-conta"]'); pg.click('[data-act="onb-conta"]'); pg.wait_for_selector("#o-nome")
        pg.fill("#o-nome","Nubank"); pg.click('[data-act="onb-criar"]'); pg.wait_for_selector("text=Saldo em contas")
        if nome=="desk":
            pg.click("#title"); pg.keyboard.press("d"); pg.wait_for_selector("#m-valor:focus"); pg.keyboard.type("5000"); pg.select_option("#m-cat",label="Farmácia"); pg.keyboard.press("Enter"); pg.wait_for_selector(".mback",state="detached")
        pg.click("#mpbtn"); pg.wait_for_selector("#menu.mpick")
        check(f"{nome}: ano inicial", pg.inner_text(".mp-head b"), "2026")
        check(f"{nome}: mês marcado", pg.inner_text(".mp-grid button.on").strip(), "Out")
        pg.wait_for_timeout(350); pg.screenshot(path=str(SHOTS/f"60-seletor-{nome}.png"))
        pg.click('[data-act="mp-ano"][data-d="-1"]')
        check(f"{nome}: continua aberto ao trocar o ano", pg.locator("#menu.mpick").count(), 1)
        check(f"{nome}: ano anterior", pg.inner_text(".mp-head b"), "2025")
        pg.click('[data-act="mp-mes"][data-k="2025-03"]')
        check(f"{nome}: mês escolhido", pg.evaluate("S.mes"), "2025-03")
        check(f"{nome}: rótulo", pg.inner_text("#mlabel").lower(), "março 2025")
        check(f"{nome}: fechou", pg.locator("#menu").count(), 0)
        pg.click("#mpbtn"); pg.click('[data-act="mp-hoje"]')
        check(f"{nome}: voltar ao mês atual", pg.evaluate("S.mes"), "2026-10")
        pg.click("#mpbtn"); pg.mouse.click(vp["width"]//2, vp["height"]-200)
        check(f"{nome}: clique fora fecha", pg.locator("#menu").count(), 0)
        if nome=="desk":
            pg.click("#mpbtn"); check("desk: ponto em mês com lançamento", pg.locator('.mp-grid button[data-k="2026-10"] i').count(), 1); pg.keyboard.press("Escape")
            check("desk: Esc fecha", pg.locator("#menu").count(), 0)
        over = pg.evaluate("document.documentElement.scrollWidth > window.innerWidth")
        check(f"{nome}: sem rolagem lateral", over, False)
        print(nome, "erros:", errs)
        if errs: fails.append("console")
    b.close()
print("RESULTADO:", "TUDO CERTO" if not fails else fails)
