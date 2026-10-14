import pathlib
from playwright.sync_api import sync_playwright
AQUI = pathlib.Path(__file__).resolve().parent; RAIZ = AQUI.parents[1]
src = open(AQUI/"graficos.py").read()
exec(src[:src.index("\nwith sync_playwright() as p:")])
AUDIT = """(sel)=>{const ch=document.querySelector(sel); const bs=[...ch.querySelectorAll('.gtb')];
 const chips=[...ch.querySelectorAll('.gch')].map(c=>c.dataset.nm);
 return bs.map(b=>{const n=b.querySelector('b'), inn=b.querySelector('.in'); const nmVis=getComputedStyle(n).display!=='none';
   const vis=[...inn.children].filter(e=>getComputedStyle(e).display!=='none');
   const corta=vis.some(e=>{const r=e.getBoundingClientRect(), q=inn.getBoundingClientRect(); return r.bottom>q.bottom+0.5||r.right>q.right+0.5;});
   return {nm:b.dataset.nm, lv:+b.dataset.lv, w:Math.round(b.clientWidth), h:Math.round(b.clientHeight), nomeInteiro: nmVis && n.scrollWidth<=n.clientWidth+1, naLegenda: chips.includes(b.dataset.nm), corta};});}"""
allerr=[]
with sync_playwright() as p:
    b=p.chromium.launch()
    for nome,kw in [("desk",dict(viewport={"width":1280,"height":900},color_scheme="dark")),("mob",dict(viewport={"width":390,"height":844},is_mobile=True,has_touch=True))]:
        pg,errs,_=iniciar(b,**kw)
        pg.evaluate("lsSet('graf.geral','blocos'); lsSet('graf.relD','blocos'); render()"); pg.wait_for_timeout(120)
        for vis,sel in [("geral",".gchart[data-k=geral]"),("relatorios",".gchart[data-k=relD]")]:
            pg.evaluate(f"S.view='{vis}'; render()"); pg.wait_for_timeout(120)
            a=pg.evaluate(AUDIT, sel)
            for x in a: print(nome, vis, x)
            check(f"{nome} {vis}: sem legenda abaixo", pg.locator(sel+" .gchips, "+sel+" .gch").count(), 0)
            check(f"{nome} {vis}: nenhum texto cortado na altura/largura", any(x["corta"] for x in a), False)
            pg.locator(sel).scroll_into_view_if_needed(); pg.locator(sel).screenshot(path=str(SHOTS/f"b-{nome}-{vis}.png"))
        # passar o mouse / tocar num bloco pequeno mostra nome e valor
        pequeno=pg.locator(".gchart[data-k=relD] .gtb").last
        nmc=pequeno.get_attribute("data-nm"); (pequeno.tap() if nome=="mob" else pequeno.hover()); pg.wait_for_timeout(80)
        check(f"{nome}: bloco pequeno mostra o nome", pg.locator(".gchart[data-k=relD] .ginfo .hl-on [data-g=nm]").inner_text(), nmc)
        check(f"{nome}: e o valor", pg.locator(".gchart[data-k=relD] .ginfo .hl-on [data-g=vl]").inner_text(), pequeno.get_attribute("data-vl"))
        # redimensionar recalcula
        if nome=="desk":
            pg.set_viewport_size({"width":900,"height":900}); pg.wait_for_timeout(300)
            a=pg.evaluate(AUDIT, ".gchart[data-k=relD]")
            check("após redimensionar: nada cortado", not any(x["corta"] for x in a), True)
        print("erros:", errs); allerr+=errs
    b.close()
print("RESULTADO:", "TUDO CERTO" if not fails and not allerr else (fails, allerr))
