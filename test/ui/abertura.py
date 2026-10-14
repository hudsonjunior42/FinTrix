"""Tela de apresentação: logo animado, texto, opções Adicionar conta / Restaurar um backup."""
import pathlib, json
from playwright.sync_api import sync_playwright
AQUI = pathlib.Path(__file__).resolve().parent; RAIZ = AQUI.parents[1]
src = open(AQUI/"run.py").read()
exec(src[:src.index("\nwith sync_playwright() as p:")])
fails=[]
def check(l,g,e):
    ok=g==e; print(("OK  " if ok else "FALHA ")+f"{l}: {g!r}"+("" if ok else f" (esperado {e!r})"))
    if not ok: fails.append(l)
OP = "s => +getComputedStyle(document.querySelector(s)).opacity"
URL = "file://"+str(AQUI/"index.html")
allerr = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg, errs = nova_pagina(b, viewport={"width":1280,"height":820}, color_scheme="dark", reduced_motion="no-preference")
    pg.goto(URL); pg.wait_for_selector("#onb", state="attached")
    pg.evaluate("localStorage.setItem('lc.view', JSON.stringify('config')); S.view = 'config'"); pg.wait_for_timeout(120)
    check("sem barra lateral e topo", [pg.is_visible(".side"), pg.is_visible(".top")], [False, False])
    check("início: opções ainda escondidas", pg.evaluate(OP, ".onb-acoes .btn"), 0)
    check("início: texto ainda escondido", pg.evaluate(OP, ".onb-t"), 0)
    # quadros em instantes fixos da animação (pausada), para não depender da velocidade da máquina
    def em(ms):
        pg.evaluate(f"document.getAnimations().forEach(a => {{ a.pause(); a.currentTime = {ms}; }})"); pg.wait_for_timeout(40)
    CENTRO = "(() => { const r = document.querySelector('.onb-marca').getBoundingClientRect(), c = document.querySelector('#content').getBoundingClientRect(); return Math.round(Math.abs((r.top + r.height/2) - (c.top + c.height/2))); })()"
    for i, t in enumerate([300, 700, 1300, 1900, 3200]):
        em(t); pg.screenshot(path=str(SHOTS/f"a{i+1}-abertura-{t}ms.png"))
        if t == 700: check("0,7 s: logo no centro da tela", pg.evaluate(CENTRO) <= 2, True)
        if t == 1900: check("1,9 s: texto visível, opções ainda não", [pg.evaluate(OP, ".onb-t") > .9, pg.evaluate(OP, ".onb-acoes .btn") < .05], [True, True])
    pg.evaluate("document.getAnimations().forEach(a => a.finish())"); pg.wait_for_timeout(200)
    check("fim: peças do logo", [round(pg.evaluate(f"s => +getComputedStyle(document.querySelector('.{c}')).opacity", None), 2) for c in ["pc-t", "pc-l", "pc-r"]], [1, 1, 1])
    check("fim: opções", pg.locator(".onb-acoes .btn").all_inner_texts(), ["Adicionar conta", "Restaurar um backup"])
    check("fim: opções visíveis", pg.evaluate(OP, '[data-act="onb-restaurar"]'), 1)
    check("formulário ainda fechado", pg.is_visible("#o-nome"), False)
    pg.click('[data-act="onb-conta"]'); pg.wait_for_timeout(500)
    check("Adicionar conta abre o formulário", [pg.is_visible("#o-nome"), pg.evaluate("document.activeElement.id"), pg.is_visible(".onb-acoes")], [True, "o-nome", False])
    check("logo diminui no formulário", pg.evaluate("Math.round(document.querySelector('.onb-marca').getBoundingClientRect().width)"), 64)
    pg.screenshot(path=str(SHOTS/"a6-formulario.png"))
    pg.click('[data-act="onb-voltar"]'); pg.wait_for_timeout(300)
    check("Voltar mostra as opções", [pg.is_visible(".onb-acoes"), pg.is_visible("#o-nome"), pg.evaluate("document.activeElement.dataset.act")], [True, False, "onb-conta"])
    pg.click('[data-act="onb-conta"]'); pg.fill("#o-nome", "Itaú"); pg.keyboard.press("Enter"); pg.wait_for_selector("text=Saldo em contas")
    check("Enter cria a conta", pg.evaluate("Object.values(S.cfg.contas).map(c => c.nome)"), ["Itaú"])
    check("conta nova abre na Visão geral", [pg.evaluate("S.view"), pg.inner_text("#title"), pg.evaluate("localStorage.getItem('lc.view')")], ["geral", "Visão geral", '"geral"'])
    check("app volta com barra lateral", pg.is_visible(".side"), True)
    print("erros:", errs); allerr += errs

    # clicar durante a animação pula para o fim
    p2, e2 = nova_pagina(b, viewport={"width":1280,"height":820}, reduced_motion="no-preference")
    p2.goto(URL); p2.wait_for_selector("#onb", state="attached"); p2.wait_for_timeout(250)
    p2.mouse.click(200, 200); p2.wait_for_timeout(150)
    check("clique pula a animação", [p2.evaluate(OP, ".onb-t"), p2.evaluate(OP, '[data-act="onb-conta"]')], [1, 1])
    # restaurar backup pela tela de apresentação
    bk = {"app": "fintrix", "versao": 1, "config": {"versao": 1, "anos": ["2026"], "contas": {"a1": {"nome": "Inter", "tipo": "corrente", "inicial": 50000, "cor": "#3987E5", "total": True, "arq": False, "ordem": 0}},
          "cartoes": {}, "categorias": {"c1": {"nome": "Mercado", "tipo": "despesa", "cor": "#D95926", "ordem": 10}}, "tags": {}, "recorr": {}, "orc": {}},
          "lancamentos": [{"id": "x1", "tipo": "despesa", "desc": "Feira", "data": "2026-10-01", "comp": "2026-10", "conta": "a1", "cat": "c1", "valor": 4500, "pago": True, "tags": [], "obs": "", "criado": 1}]}
    f = AQUI/"shots/backup-teste.json"; f.write_text(json.dumps(bk))
    p2.evaluate("localStorage.setItem('lc.view', JSON.stringify('relatorios')); S.view = 'relatorios'")
    with p2.expect_file_chooser() as fc: p2.click('[data-act="onb-restaurar"]')
    fc.value.set_files(str(f)); p2.wait_for_selector('[data-act="restaurar-ok"]', timeout=5000); p2.click('[data-act="restaurar-ok"]'); p2.wait_for_selector("text=Saldo em contas", timeout=8000); p2.wait_for_timeout(200)
    check("Restaurar um backup", [p2.evaluate("Object.values(S.cfg.contas).map(c => c.nome)"), p2.evaluate("Object.values(S.anos).flat().length")], [["Inter"], 1])
    check("backup restaurado abre na Visão geral", [p2.evaluate("S.view"), p2.inner_text("#title")], ["geral", "Visão geral"])
    print("erros:", e2); allerr += e2

    # sem animação (preferência do sistema) tudo aparece de uma vez
    p3, e3 = nova_pagina(b, viewport={"width":1280,"height":820}, reduced_motion="reduce")
    p3.goto(URL); p3.wait_for_selector("#onb", state="attached"); p3.wait_for_timeout(80)
    check("movimento reduzido: tudo visível", [p3.evaluate(OP, ".onb-t"), p3.evaluate(OP, '[data-act="onb-conta"]')], [1, 1])
    allerr += e3

    # celular, tema claro
    pm, em = nova_pagina(b, viewport={"width":390,"height":760}, is_mobile=True, has_touch=True, color_scheme="light", reduced_motion="no-preference")
    pm.goto(URL); pm.wait_for_selector("#onb", state="attached"); pm.evaluate("aplicarTema('claro')"); pm.wait_for_timeout(2900)
    sw = pm.evaluate("[document.documentElement.scrollWidth, innerWidth]")
    check("celular: sem rolagem lateral", sw[0] <= sw[1], True)
    check("celular: tudo cabe na tela", pm.evaluate("document.querySelector('.onb-acoes').getBoundingClientRect().bottom <= innerHeight"), True)
    pm.screenshot(path=str(SHOTS/"a7-celular.png"))
    pm.tap('[data-act="onb-conta"]'); pm.wait_for_timeout(500); pm.screenshot(path=str(SHOTS/"a8-celular-form.png"))
    allerr += em
    b.close()
print("RESULTADO:", "TUDO CERTO" if not fails and not allerr else (fails, allerr))
