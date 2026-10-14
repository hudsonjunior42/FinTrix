import pathlib
from playwright.sync_api import sync_playwright
AQUI = pathlib.Path(__file__).resolve().parent; RAIZ = AQUI.parents[1]
src = open(AQUI/"run.py").read()
exec(src[:src.index("with sync_playwright() as p:")])
fails=[]
def check(l,g,e):
    ok=g==e; print(("OK  " if ok else "FALHA ")+f"{l}: {g!r}"+("" if ok else f" (esperado {e!r})"))
    if not ok: fails.append(l)
BG = "getComputedStyle(document.body).backgroundColor"
ESC, CLA = "rgb(14, 17, 23)", "rgb(242, 243, 246)"
CFG = "(window.__store.get([...window.__store.keys()].find(k=>k.endsWith('/livro')))||{}).prefs"
with sync_playwright() as p:
    b=p.chromium.launch()
    ctx=b.new_context(viewport={"width":1280,"height":900},color_scheme="light")
    pg=ctx.new_page(); errs=[]
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: errs.append(m.text) if m.type=="error" else None)
    route_fonts(pg); pg.add_init_script(path=str(AQUI/"fakedb.js"))
    pg.goto("file://"+str(AQUI/"index.html")); pg.wait_for_selector('[data-act="onb-conta"]'); pg.click('[data-act="onb-conta"]'); pg.wait_for_selector("#o-nome")
    check("sistema claro, padrão continua escuro", pg.evaluate(BG), ESC)
    check("onboarding no escuro", pg.evaluate("document.documentElement.dataset.tema"), "escuro")
    pg.evaluate("document.documentElement.dataset.theme='light'"); pg.wait_for_timeout(30)
    check("claude.ai no claro não muda o padrão", pg.evaluate(BG), ESC)
    pg.fill("#o-nome","Nubank"); pg.click('[data-act="onb-criar"]'); pg.wait_for_selector("text=Saldo em contas")
    pg.click('.side [data-view="config"]'); pg.wait_for_timeout(100)
    check("painel Aparência", pg.locator(".panel:has(h2:text('Aparência')) .seg button").all_inner_texts(), ["Escuro","Claro","Automático"])
    check("Escuro marcado", pg.locator('[data-act="tema"].on').get_attribute("data-v"), "escuro")
    pg.click('[data-act="tema"][data-v="claro"]'); pg.wait_for_timeout(150)
    check("claro aplicado", pg.evaluate(BG), CLA)
    check("botão Claro marcado", pg.locator('[data-act="tema"].on').get_attribute("data-v"), "claro")
    check("foco no botão", pg.evaluate("document.activeElement.dataset.v"), "claro")
    check("guardado no navegador", pg.evaluate("localStorage.getItem('lc.tema')"), '"claro"')
    check("guardado na conta", pg.evaluate(CFG), {"tema":"claro"})
    pg.locator(".panel:has(h2:text('Aparência'))").scroll_into_view_if_needed()
    pg.screenshot(path=str(SHOTS/"t1-config-claro.png"))
    pg.click('.side [data-view="geral"]'); pg.wait_for_timeout(100); pg.screenshot(path=str(SHOTS/"t2-geral-claro.png"))
    pg.click('.side [data-view="config"]'); pg.click('[data-act="tema"][data-v="auto"]'); pg.wait_for_timeout(150)
    check("auto + claude.ai claro = claro", pg.evaluate(BG), CLA)
    pg.evaluate("document.documentElement.dataset.theme='dark'"); pg.wait_for_timeout(30)
    check("auto + claude.ai escuro = escuro", pg.evaluate(BG), ESC)
    pg.evaluate("delete document.documentElement.dataset.theme"); pg.wait_for_timeout(30)
    check("auto + sistema claro = claro", pg.evaluate(BG), CLA)
    pg.emulate_media(color_scheme="dark"); pg.wait_for_timeout(30)
    check("auto + sistema escuro = escuro", pg.evaluate(BG), ESC)
    pg.emulate_media(color_scheme="light")
    pg.click('[data-act="tema"][data-v="claro"]'); pg.wait_for_timeout(150)
    # outro aparelho mudou para escuro: a conta vale
    pg.evaluate("cfgWrite({prefs:{tema:'escuro'}})"); pg.wait_for_timeout(150)
    check("tema da conta sincroniza", [pg.evaluate(BG), pg.evaluate("localStorage.getItem('lc.tema')"), pg.locator('[data-act="tema"].on').get_attribute("data-v")], [ESC, '"escuro"', "escuro"])
    pg.click('[data-act="tema"][data-v="claro"]'); pg.wait_for_timeout(150)
    pg.reload(); pg.wait_for_selector('[data-act="onb-conta"]'); pg.click('[data-act="onb-conta"]'); pg.wait_for_selector("#o-nome")
    check("ao reabrir, claro já vem aplicado", pg.evaluate(BG), CLA)
    print("erros:", errs); b.close()
print("RESULTADO:", "TUDO CERTO" if not fails and not errs else (fails, errs))
