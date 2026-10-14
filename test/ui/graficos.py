import pathlib
from playwright.sync_api import sync_playwright
AQUI = pathlib.Path(__file__).resolve().parent; RAIZ = AQUI.parents[1]
src = open(AQUI/"run.py").read()
exec(src[:src.index("with sync_playwright() as p:")])
fails=[]
def check(l,g,e):
    ok=g==e; print(("OK  " if ok else "FALHA ")+f"{l}: {g!r}"+("" if ok else f" (esperado {e!r})"))
    if not ok: fails.append(l)

SEED = """async () => {
  const conta = Object.keys(S.cfg.contas)[0];
  const pais = Object.entries(S.cfg.categorias).filter(([,c]) => !c.pai && c.tipo === 'despesa').map(([id]) => id);
  const rec = Object.entries(S.cfg.categorias).filter(([,c]) => !c.pai && c.tipo === 'receita').map(([id]) => id);
  const d = today(); const vals = [182000, 96050, 54000, 31090, 22000, 15000, 9800, 6400, 3100, 1500];
  for (let i = 0; i < vals.length; i++) await lancSave({ id: rid(), tipo: 'despesa', desc: 'Teste ' + i, data: d, comp: mk(d), conta, cat: pais[i], pago: true, cartao: null, valor: vals[i], tags: [], obs: '', criado: Date.now() + i });
  await lancSave({ id: rid(), tipo: 'receita', desc: 'Salário', data: d, comp: mk(d), conta, cat: rec[0], pago: true, cartao: null, valor: 650000, tags: [], obs: '', criado: Date.now() });
  await lancSave({ id: rid(), tipo: 'receita', desc: 'Extra', data: d, comp: mk(d), conta, cat: rec[1], pago: true, cartao: null, valor: 80000, tags: [], obs: '', criado: Date.now() });
  return pais.length;
}"""
PANEL = ".panel:has(h2:text('Gastos por categoria'))"

def iniciar(b, **kw):
    pg, errs = nova_pagina(b, **kw)
    pg.goto("file://"+str(AQUI/"index.html")); pg.wait_for_selector('[data-act="onb-conta"]'); pg.click('[data-act="onb-conta"]'); pg.wait_for_selector("#o-nome")
    pg.evaluate("localStorage.clear()")
    pg.fill("#o-nome","Nubank"); pg.click('[data-act="onb-criar"]'); pg.wait_for_selector("text=Saldo em contas")
    n = pg.evaluate(SEED); pg.wait_for_timeout(250)
    return pg, errs, n

with sync_playwright() as p:
    b=p.chromium.launch()
    pg,errs,n=iniciar(b,viewport={"width":1280,"height":900},color_scheme="dark")
    print("categorias pai de despesa:", n)
    P = pg.locator(PANEL)
    check("seletor com 3 tipos", P.locator(".gsw button").count(), 3)
    check("padrão é barras", P.locator(".gsw button.on").get_attribute("data-v"), "barras")
    check("barras: 7 + Outras", P.locator(".catbar").count(), 8)
    check("linha Outras", P.locator(".catbar").last.inner_text().split("\n")[0].strip(), "Outras (3)")
    pg.screenshot(path=str(SHOTS/"g1-barras.png"), clip={"x":0,"y":0,"width":1280,"height":900})

    check("sem opção de pizza", [P.locator('.gsw button').count(), P.locator('[data-v="pizza"]').count()], [3, 0])
    P.locator('[data-v="rosca"]').click(); pg.wait_for_timeout(120)
    check("rosca: 8 fatias", P.locator(".gpie path").count(), 8)
    check("rosca: legenda 8", P.locator(".gli").count(), 8)
    pcs = P.locator(".gli .pc").all_inner_texts(); print("percentuais:", pcs)
    tot = sum(int(x.replace("%","").replace("<1","0")) for x in pcs); check("soma ~100%", 98 <= tot <= 102, True)
    check("foco segue no botão", pg.evaluate("document.activeElement.dataset.v"), "rosca")
    check("tipo guardado", pg.evaluate("lsGet('graf.geral')"), "rosca")
    pg.evaluate("lsSet('graf.geral', 'pizza'); render()"); pg.wait_for_timeout(80)
    check("quem tinha pizza vê a rosca", P.locator(".gsw button.on").get_attribute("data-v"), "rosca")
    P.scroll_into_view_if_needed(); pg.screenshot(path=str(SHOTS/"g2-rosca.png"))

    check("rosca: total no centro", P.locator(".gctr .hl-off b").inner_text(), pg.evaluate("fmt(%d)" % (182000+96050+54000+31090+22000+15000+9800+6400+3100+1500)))
    P.locator(".gpie path").nth(1).hover(); pg.wait_for_timeout(80)
    check("hover destaca", P.locator(".gchart.hov").count(), 1)
    check("centro mostra a categoria", P.locator(".gctr .hl-on [data-g=nm]").inner_text(), P.locator(".gli .nm").nth(1).inner_text())
    check("centro mostra o valor", P.locator(".gctr .hl-on [data-g=vl]").inner_text(), pg.evaluate("fmt(96050)"))
    pg.screenshot(path=str(SHOTS/"g3-rosca-hover.png"))
    pg.mouse.move(5,5); pg.wait_for_timeout(80)
    check("sair do gráfico limpa", P.locator(".gchart.hov").count(), 0)
    nm2 = P.locator(".gli .nm").nth(2).inner_text()
    P.locator(".gli").nth(2).click(); pg.wait_for_selector(".cd-kpis")
    check("clicar na legenda abre a categoria", pg.inner_text(".mhead h3"), nm2)
    pg.keyboard.press("Escape"); pg.wait_for_selector(".mback", state="detached")
    P = pg.locator(PANEL)
    P.locator(".gli").last.click(); pg.mouse.move(5,5); pg.wait_for_timeout(80)
    check("Outras: clique fixa o destaque", P.locator(".gli.hl .nm").inner_text(), "Outras (3)")
    P.locator(".gli").last.click(); pg.mouse.move(5,5); pg.wait_for_timeout(80)
    check("Outras: segundo clique solta", P.locator(".gchart.hov").count(), 0)

    P.locator('[data-v="blocos"]').click(); pg.wait_for_timeout(120)
    check("blocos: 8", P.locator(".gtb").count(), 8)
    boxes = pg.evaluate("""[...document.querySelectorAll('.gtree .gtb')].map(e=>{const r=e.getBoundingClientRect();return [r.x,r.y,r.width,r.height]})""")
    tree = pg.evaluate("(()=>{const r=document.querySelector('.gtree').getBoundingClientRect();return [r.x,r.y,r.width,r.height]})()")
    area = sum(w*h for _,_,w,h in boxes); print("área", area, tree[2]*tree[3]); check("blocos cobrem a área", abs(area - tree[2]*tree[3]) < tree[2]*tree[3]*0.005, True)
    inside = all(x>=tree[0]-0.5 and y>=tree[1]-0.5 and x+w<=tree[0]+tree[2]+0.5 and y+h<=tree[1]+tree[3]+0.5 for x,y,w,h in boxes)
    check("blocos dentro da caixa", inside, True)
    ov = any(not (a[0]+a[2]<=c[0]+.5 or c[0]+c[2]<=a[0]+.5 or a[1]+a[3]<=c[1]+.5 or c[1]+c[3]<=a[1]+.5) for i,a in enumerate(boxes) for c in boxes[i+1:])
    check("sem sobreposição", ov, False)
    rat = [boxes[i][2]*boxes[i][3]/area for i in range(len(boxes))]; print("proporções:", [round(r*100,1) for r in rat])
    P.locator(".gtb").nth(5).hover(); pg.wait_for_timeout(80)
    check("info do bloco", P.locator(".ginfo .hl-on [data-g=nm]").inner_text(), P.locator(".gtb").nth(5).get_attribute("data-nm"))
    pg.screenshot(path=str(SHOTS/"g4-blocos.png"))

    pg.click('.side [data-view="relatorios"]'); pg.wait_for_timeout(150)
    R = pg.locator(".panel:has(h2:text('Despesas por categoria'))")
    check("relatórios: barras com todas", R.locator(".catbar").count(), 10)
    R.locator('[data-v="rosca"]').click(); pg.wait_for_timeout(120)
    R = pg.locator(".panel:has(h2:text('Despesas por categoria'))")
    check("relatórios: rosca 9 + Outras", R.locator(".gpie path").count(), 10)
    RR = pg.locator("div:has(> .panel-h h2:text('Receitas por categoria'))")
    RR.locator('[data-v="rosca"]').click(); pg.wait_for_timeout(120)
    RR = pg.locator("div:has(> .panel-h h2:text('Receitas por categoria'))")
    check("receitas: rosca 2", RR.locator(".gpie path").count(), 2)
    check("geral manteve blocos", pg.evaluate("lsGet('graf.geral')"), "blocos")
    pg.screenshot(path=str(SHOTS/"g5-relatorios.png"), full_page=True)
    print("erros:", errs); allerrs=list(errs)

    # tema claro + celular
    pg2,errs2,_=iniciar(b,viewport={"width":390,"height":844},color_scheme="light",is_mobile=True,has_touch=True)
    for t in ["barras","rosca","blocos"]:
        P2 = pg2.locator(PANEL); P2.locator(f'[data-v="{t}"]').click(); pg2.wait_for_timeout(120)
        P2 = pg2.locator(PANEL); P2.scroll_into_view_if_needed()
        sw = pg2.evaluate("[document.documentElement.scrollWidth, innerWidth, document.querySelector('#content').scrollWidth, document.querySelector('#content').clientWidth]")
        check(f"celular {t}: sem rolagem lateral", sw[0] <= sw[1] and sw[2] <= sw[3], True)
        P2.screenshot(path=str(SHOTS/f"g6-m-{t}.png"))
    P2 = pg2.locator(PANEL); nm6 = P2.locator(".gtb").nth(6).get_attribute("data-nm"); P2.locator(".gtb").nth(6).tap(); pg2.wait_for_selector(".cd-kpis")
    check("toque no bloco abre a categoria", pg2.inner_text(".mhead h3"), nm6)
    check("celular: dica de toque", P2.locator(".so-toque").is_visible(), True)
    pg2.screenshot(path=str(SHOTS/"g7-m-categoria.png"))
    print("erros:", errs2); allerrs += errs2
    b.close()
print("RESULTADO:", "TUDO CERTO" if not fails and not allerrs else (fails, allerrs))
