import pathlib
from playwright.sync_api import sync_playwright
AQUI = pathlib.Path(__file__).resolve().parent; RAIZ = AQUI.parents[1]
src = open(AQUI/"run.py").read()
exec(src[:src.index("with sync_playwright() as p:")])
fails=[]
def check(l,g,e):
    ok=g==e; print(("OK  " if ok else "FALHA ")+f"{l}: {g!r}"+("" if ok else f" (esperado {e!r})"))
    if not ok: fails.append(l)
MED = """(()=>{const r=document.querySelector('.mes-sel'); if(!r) return null; const t=[...r.parentNode.querySelectorAll('text')].find(t=>t.getAttribute('font-weight')==='600');
 const a=t.getBBox(), b=r.getBBox(); return {txt:t.textContent, tx:[+a.x.toFixed(1),+(a.x+a.width).toFixed(1)], rx:[b.x,b.x+b.width], gap:+(b.y-(a.y+a.height)).toFixed(1), vb:r.ownerSVGElement.viewBox.baseVal.height, fundo:+(b.y+b.height).toFixed(1)}})()"""
allerr=[]
with sync_playwright() as p:
    b=p.chromium.launch()
    for nome,kw in [("desk",dict(viewport={"width":1280,"height":900},color_scheme="dark")),("mob",dict(viewport={"width":390,"height":844},color_scheme="light",is_mobile=True))]:
        pg,errs=nova_pagina(b,**kw)
        pg.goto("file://"+str(AQUI/"index.html")); pg.wait_for_selector('[data-act="onb-conta"]'); pg.click('[data-act="onb-conta"]'); pg.wait_for_selector("#o-nome")
        pg.fill("#o-nome","Nubank"); pg.click('[data-act="onb-criar"]'); pg.wait_for_selector("text=Saldo em contas")
        pg.evaluate("S.view='relatorios'; render()"); pg.wait_for_timeout(150)
        m=pg.evaluate(MED); print(nome, m)
        check(f"{nome}: um sublinhado", pg.locator(".mes-sel").count(), 1)
        check(f"{nome}: sublinha o mês aberto", m["txt"], pg.evaluate("mesCurto(S.mes)"))
        check(f"{nome}: cobre o texto", m["rx"][0] <= m["tx"][0]+1 and m["rx"][1] >= m["tx"][1]-1, True)
        check(f"{nome}: dentro do gráfico", m["fundo"] <= m["vb"], True)
        pg.click('[data-act="mes"][data-d="-1"]') if pg.locator('[data-act="mes"][data-d="-1"]').count() else pg.evaluate("S.mes=madd(S.mes,-1);render()")
        pg.wait_for_timeout(120); m2=pg.evaluate(MED)
        check(f"{nome}: acompanha a troca de mês", m2["txt"], pg.evaluate("mesCurto(S.mes)"))
        pg.locator(".chart").first.screenshot(path=str(SHOTS/f"s-{nome}.png"))
        print("erros:", errs); allerr+=errs
    b.close()
print("RESULTADO:", "TUDO CERTO" if not fails and not allerr else (fails, allerr))
