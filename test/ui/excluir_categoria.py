"""Excluir categoria: sem uso (confirma), com lançamentos/fixas (move para outra), subcategoria (vai para a principal), divisão se junta."""
import pathlib, json
from playwright.sync_api import sync_playwright
AQUI = pathlib.Path(__file__).resolve().parent; RAIZ = AQUI.parents[1]
src = open(AQUI/"run.py").read()
exec(src[:src.index("\nwith sync_playwright() as p:")])
fails=[]
def check(l,g,e):
    ok=g==e; print(("OK  " if ok else "FALHA ")+f"{l}: {g!r}"+("" if ok else f" (esperado {e!r})"))
    if not ok: fails.append(l)
CAT = "name => Object.entries(S.cfg.categorias).find(([,c]) => c.nome === name)?.[0] || null"
DOCS = "() => Object.fromEntries([...window.__store.entries()].filter(([k]) => /\\/l\\d{4}\\//.test(k)).map(([k,v]) => [v.desc, v]))"
with sync_playwright() as p:
    b = p.chromium.launch()
    pg, errs = nova_pagina(b, viewport={"width":1280,"height":900})
    pg.goto("file://"+str(AQUI/"index.html")); pg.wait_for_selector('[data-act="onb-conta"]'); pg.click('[data-act="onb-conta"]'); pg.wait_for_selector("#o-nome")
    pg.fill("#o-nome","Nubank"); pg.click('[data-act="onb-criar"]'); pg.wait_for_selector("text=Saldo em contas")
    cat = lambda n: pg.evaluate(f"({CAT})({json.dumps(n)})")
    LAZ, JOG, CIN, SAI, ALI, SUP, FAR = cat("Lazer"), cat("Jogos"), cat("Cinema e cultura"), cat("Saídas e bares"), cat("Alimentação"), cat("Supermercado"), cat("Farmácia")
    conta = pg.evaluate("Object.keys(S.cfg.contas)[0]")
    pg.evaluate(f"""(async () => {{
      const b = {{ tipo: 'despesa', data: today(), comp: today().slice(0,7), conta: '{conta}', pago: true, cartao: null, tags: [], obs: '', criado: Date.now() }};
      await lancSave({{ ...b, id: 'j1', desc: 'Steam', cat: '{JOG}', valor: 5000 }});
      await lancSave({{ ...b, id: 'c1', desc: 'Cinema', cat: '{CIN}', valor: 3000 }});
      await lancSave({{ ...b, id: 'f1', desc: 'Mercado', cat: '{SUP}', valor: 15000, div: [{{ cat: '{SUP}', valor: 12000 }}, {{ cat: '{FAR}', valor: 3000 }}] }});
      await cfgWrite({{ recorr: {{ r1: {{ tipo: 'despesa', desc: 'Game Pass', valor: 4500, cat: '{JOG}', conta: '{conta}', dia: 5, inicio: today().slice(0,7), fim: null, tags: [], pulos: [], arq: false }} }}, orc: {{ '{LAZ}': 30000 }} }});
    }})()"""); pg.wait_for_timeout(200)
    pg.click('.side [data-view="config"]'); pg.wait_for_timeout(100)

    # sem uso
    pg.click(f'[data-act="cat-editar"][data-id="{SAI}"]'); pg.wait_for_selector('[data-act="cat-excluir"]')
    pg.click('[data-act="cat-excluir"]'); pg.wait_for_timeout(50)
    check("sem uso: só confirma", [pg.locator("#cx-dest").count(), "Nenhum lançamento" in pg.inner_text("#m-confirm")], [0, True])
    pg.click('[data-act="cat-excluir-ok"]'); pg.wait_for_selector(".mback", state="detached"); pg.wait_for_timeout(100)
    check("sem uso: excluída", cat("Saídas e bares"), None)

    # subcategoria com lançamento e fixa: vai para a principal por padrão
    pg.click(f'[data-act="cat-editar"][data-id="{JOG}"]'); pg.wait_for_selector('[data-act="cat-excluir"]')
    pg.click('[data-act="cat-excluir"]'); pg.wait_for_timeout(50)
    check("subcategoria: destino padrão é a principal", pg.eval_on_selector("#cx-dest", "e => e.value"), LAZ)
    check("subcategoria: ela não aparece como destino", pg.locator(f'#cx-dest option[value="{JOG}"]').count(), 0)
    print("   aviso:", pg.inner_text("#m-confirm").split("\n")[0])
    pg.screenshot(path=str(SHOTS/"ec1-mover.png"))
    pg.click('[data-act="cat-excluir-ok"]'); pg.wait_for_selector(".mback", state="detached"); pg.wait_for_timeout(150)
    d = pg.evaluate(DOCS)
    check("subcategoria: lançamento movido", d["Steam"]["cat"], LAZ)
    check("subcategoria: fixa movida", pg.evaluate("S.cfg.recorr.r1.cat"), LAZ)
    check("subcategoria: excluída", cat("Jogos"), None)

    # principal com subcategorias: exige destino
    pg.click(f'[data-act="cat-editar"][data-id="{LAZ}"]'); pg.wait_for_selector('[data-act="cat-excluir"]')
    pg.click('[data-act="cat-excluir"]'); pg.wait_for_timeout(50)
    check("principal: sem destino escolhido", pg.eval_on_selector("#cx-dest", "e => e.value"), "")
    check("principal: o grupo dela some do seletor", pg.locator(f'#cx-dest option[value="{CIN}"]').count(), 0)
    pg.click('[data-act="cat-excluir-ok"]'); pg.wait_for_timeout(80)
    check("principal: pede destino", pg.inner_text("#m-err"), "Escolha para qual categoria os lançamentos vão.")
    pg.select_option("#cx-dest", ALI); pg.click('[data-act="cat-excluir-ok"]'); pg.wait_for_selector(".mback", state="detached"); pg.wait_for_timeout(150)
    d = pg.evaluate(DOCS)
    check("principal: tudo movido", [d["Steam"]["cat"], d["Cinema"]["cat"], pg.evaluate("S.cfg.recorr.r1.cat")], [ALI, ALI, ALI])
    check("principal: ela e as subs excluídas, limite removido", [cat("Lazer"), cat("Cinema e cultura"), pg.evaluate(f"'{LAZ}' in (S.cfg.orc || {{}})")], [None, None, False])

    # divisão: excluir Farmácia e mover para Supermercado junta as partes
    pg.click(f'[data-act="cat-editar"][data-id="{FAR}"]'); pg.wait_for_selector('[data-act="cat-excluir"]')
    pg.click('[data-act="cat-excluir"]'); pg.wait_for_timeout(50); pg.select_option("#cx-dest", SUP)
    pg.click('[data-act="cat-excluir-ok"]'); pg.wait_for_selector(".mback", state="detached"); pg.wait_for_timeout(150)
    m = pg.evaluate(DOCS)["Mercado"]
    check("divisão: partes da mesma categoria se juntam", [m["cat"], m.get("div"), m["valor"]], [SUP, None, 15000])

    # arquivar em vez de excluir
    SAU = cat("Saúde")
    pg.evaluate(f"lancSave({{ id: 'p1', tipo: 'despesa', desc: 'Consulta', data: today(), comp: today().slice(0,7), conta: '{conta}', cat: '{SAU}', pago: true, cartao: null, valor: 20000, tags: [], obs: '', criado: Date.now() }})"); pg.wait_for_timeout(150)
    pg.click(f'[data-act="cat-editar"][data-id="{SAU}"]'); pg.wait_for_selector('[data-act="cat-excluir"]')
    pg.click('[data-act="cat-excluir"]'); pg.click('[data-act="cat-arquivar"]'); pg.wait_for_selector(".mback", state="detached"); pg.wait_for_timeout(120)
    check("arquivar: categoria arquivada e lançamento intacto", [pg.evaluate(f"S.cfg.categorias['{SAU}'].arq"), pg.evaluate(DOCS)["Consulta"]["cat"]], [True, SAU])
    print("erros:", errs)
    b.close()
print("RESULTADO:", "TUDO CERTO" if not fails and not errs else (fails, errs))
