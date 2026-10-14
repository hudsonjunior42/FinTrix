"""Relatórios: por tag e análise anual (KPIs, gráfico de 12 meses, categorias, matriz mês a mês, janela da categoria no ano)."""
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
def iniciar(b, **kw):
    pg, errs = nova_pagina(b, **kw)
    pg.goto("file://"+str(AQUI/"index.html")); pg.wait_for_selector('[data-act="onb-conta"]'); pg.click('[data-act="onb-conta"]'); pg.wait_for_selector("#o-nome")
    pg.fill("#o-nome","Nubank"); pg.click('[data-act="onb-criar"]'); pg.wait_for_selector("text=Saldo em contas")
    cat = lambda n: pg.evaluate(f"({CAT})({json.dumps(n)})")
    pg.evaluate(f"""(async () => {{
      await cfgWrite({{ tags: {{ tv: {{ nome: 'viagem', arq: false }}, tr: {{ nome: 'reforma', arq: false }} }} }});
      const conta = Object.keys(S.cfg.contas)[0], H = today().slice(0,7), Y = H.slice(0,4), nm = Number(H.slice(5));
      const b = {{ conta, pago: true, cartao: null, obs: '', criado: 1 }};
      for (let k = 1; k <= 12; k++) {{
        const m = Y + '-' + String(k).padStart(2,'0'), ma = (Number(Y) - 1) + '-' + String(k).padStart(2,'0');
        await lancSave({{ ...b, id: 'a' + k, tipo: 'despesa', desc: 'Mercado ' + k, data: m + '-05', comp: m, cat: '{cat("Supermercado")}', valor: 10000 * k, tags: [], pago: m <= H }});
        await lancSave({{ ...b, id: 's' + k, tipo: 'receita', desc: 'Salário ' + k, data: m + '-05', comp: m, cat: '{cat("Salário")}', valor: 500000, tags: [], pago: m <= H }});
        await lancSave({{ ...b, id: 'p' + k, tipo: 'despesa', desc: 'Mercado antigo ' + k, data: ma + '-05', comp: ma, cat: '{cat("Supermercado")}', valor: 5000 * k, tags: [] }});
      }}
      await lancSave({{ ...b, id: 'v1', tipo: 'despesa', desc: 'Hotel', data: Y + '-03-10', comp: Y + '-03', cat: '{cat("Viagens")}', valor: 80000, tags: ['tv'] }});
      await lancSave({{ ...b, id: 'v2', tipo: 'despesa', desc: 'Passagem', data: H + '-02', comp: H, cat: '{cat("Viagens")}', valor: 60000, tags: ['tv', 'tr'] }});
      await lancSave({{ ...b, id: 'v3', tipo: 'receita', desc: 'Reembolso viagem', data: H + '-03', comp: H, cat: '{cat("Reembolsos")}', valor: 20000, tags: ['tv'] }});
    }})()"""); pg.wait_for_timeout(300)
    pg.evaluate("localStorage.setItem('lc.relAno', 'false'); S.relAno = false; irPara('relatorios')"); pg.wait_for_timeout(150)
    return pg, errs, cat

allerr = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg, errs, cat = iniciar(b, viewport={"width":1280,"height":900})
    H = pg.evaluate("today().slice(0,7)"); Y = H[:4]; nm = int(H[5:])
    T = lambda: pg.locator('.panel:has(h2:text("Por tag")) .tagbar')
    # ---------- por tag (mês)
    check("tags no mês", T().locator(".nm").all_inner_texts(), ["#viagem", "#reforma"])
    check("viagem: despesa, receita e contagem", T().first.locator(".num").inner_text().replace("\xa0", " ").split("\n"), ["R$ 600,00 2 lanç.", "+R$ 200,00 em receitas"])
    pg.screenshot(path=str(SHOTS/"r1-tags-mes.png"), full_page=True)
    T().first.click(); pg.wait_for_timeout(150)
    check("clicar na tag abre Lançamentos filtrados", [pg.evaluate("S.view"), pg.evaluate("S.f.tag"), pg.evaluate("S.f.per"), pg.locator(".row .t1").count()], ["lanc", "tv", "mes", 2])
    pg.evaluate("irPara('relatorios')"); pg.wait_for_timeout(100)

    # ---------- anual
    pg.click('[data-act="rel-per"][data-v="ano"]'); pg.wait_for_timeout(150)
    check("ano guardado", pg.evaluate("localStorage.getItem('lc.relAno')"), "true")
    check("topo mostra o ano", pg.inner_text("#mlabel"), Y)
    desp_ano = sum(10000 * k for k in range(1, nm + 1)) + 80000 + 60000
    rec_ano = 500000 * nm + 20000
    k = pg.locator(".kpi .val").all_inner_texts()
    check("KPIs do ano (até o mês atual)", [x.replace("\xa0", " ") for x in k[:2]], [pg.evaluate(f"fmt({rec_ano})").replace("\xa0", " "), pg.evaluate(f"fmt({desp_ano})").replace("\xa0", " ")])
    check("gráfico com 12 meses", [x.strip() for x in pg.locator(".chart svg text").all_text_contents()][-12:], ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"])
    check("meses futuros mais claros", pg.locator('.chart svg g[opacity]').count(), 12 - nm)
    g = pg.evaluate("Object.fromEntries(gastosPorCat(itensDe(mesesDoAno(today().slice(0,4)))).map(x => [x.k, x.v]))")
    check("categorias somam o ano até o mês atual", [g.get(cat("Alimentação")), g.get(cat("Lazer"))], [sum(10000 * k for k in range(1, nm + 1)), 140000])
    check("tags no ano", T().locator(".nm").all_inner_texts(), ["#viagem", "#reforma"])
    check("viagem no ano", T().first.locator(".num").inner_text().replace("\xa0", " ").split("\n")[0], "R$ 1.400,00 3 lanç.")
    rows = pg.locator(".matriz tbody tr")
    check("matriz: linhas e colunas", [rows.count(), pg.locator(".matriz thead th").count()], [2, 1 + nm + 2])
    check("matriz: total de Alimentação", rows.first.locator("td.tot").inner_text(), f"{sum(100 * k for k in range(1, nm + 1)):,}".replace(",", "."))
    pg.screenshot(path=str(SHOTS/"r2-anual.png"), full_page=True)
    # janela da categoria no ano
    rows.first.click(); pg.wait_for_selector(".cd-kpis")
    check("janela no ano: navegação mostra o ano", pg.inner_text(".cd-nav span"), Y)
    check("janela no ano: total", pg.locator(".cd-kpis b").first.inner_text().replace("\xa0", " "), pg.evaluate(f"fmt({sum(10000 * k for k in range(1, nm + 1))})").replace("\xa0", " "))
    check("janela no ano: comparação com o ano anterior", pg.locator(".cd-kpis span").nth(2).inner_text(), f"Mesmo período de {int(Y) - 1}")
    check("janela no ano: mês a mês", pg.locator(".cd-mini rect").count(), 12)
    check("janela no ano: lançamentos", pg.locator(".cd-list .row").count(), nm)
    pg.screenshot(path=str(SHOTS/"r3-categoria-ano.png"))
    pg.click('[data-act="cd-mes"][data-d="-12"]'); pg.wait_for_timeout(100)
    check("janela: ano anterior", [pg.inner_text(".cd-nav span"), pg.locator(".cd-list .row").count()], [str(int(Y) - 1), 12])
    pg.click('[data-act="cd-mes"][data-d="12"]'); pg.click('[data-act="cd-lanc"]'); pg.wait_for_timeout(150)
    check("ver em Lançamentos usa o ano", [pg.evaluate("S.view"), pg.evaluate("S.f.per"), pg.evaluate("S.f.cat")], ["lanc", "ano", cat("Alimentação")])
    pg.evaluate("S.f = filtrosVazios(); irPara('relatorios')"); pg.wait_for_timeout(100)
    # seta do topo troca o ano
    pg.click('#monthnav [data-act="mes"][data-d="-1"]'); pg.wait_for_timeout(120)
    check("seta: ano anterior", [pg.inner_text("#mlabel"), pg.evaluate("S.mes")], [str(int(Y) - 1), f"{int(Y) - 1}-{H[5:]}"])
    check("ano passado soma os 12 meses", pg.locator(".matriz thead th").count(), 1 + 12 + 2)
    pg.click('#monthnav [data-act="mes"][data-d="1"]'); pg.wait_for_timeout(100)
    T().first.click(); pg.wait_for_timeout(150)
    check("tag no ano abre Lançamentos do ano", [pg.evaluate("S.f.per"), pg.locator(".row .t1").count()], ["ano", 3])
    pg.evaluate("S.f = filtrosVazios(); irPara('relatorios')"); pg.wait_for_timeout(100)
    pg.click('[data-act="rel-per"][data-v="mes"]'); pg.wait_for_timeout(100)
    check("volta ao mês", [pg.inner_text("#mlabel").lower(), pg.locator(".matriz").count()], [pg.evaluate("mesLongo(S.mes)"), 0])
    print("erros:", errs); allerr += errs

    pm, em, _ = iniciar(b, viewport={"width":390,"height":844}, is_mobile=True, has_touch=True)
    pm.click('[data-act="rel-per"][data-v="ano"]'); pm.wait_for_timeout(150)
    sw = pm.evaluate("[document.documentElement.scrollWidth, innerWidth, document.querySelector('#content').scrollWidth, document.querySelector('#content').clientWidth]")
    check("celular: sem rolagem lateral da página", sw[0] <= sw[1] and sw[2] <= sw[3], True)
    check("celular: matriz rola dentro do quadro", pm.evaluate("(() => { const w = document.querySelector('.matriz-w'); return w.scrollWidth > w.clientWidth; })()"), True)
    pm.locator(".matriz").scroll_into_view_if_needed(); pm.screenshot(path=str(SHOTS/"r4-celular-matriz.png"))
    print("erros:", em); allerr += em
    b.close()
print("RESULTADO:", "TUDO CERTO" if not fails and not allerr else (fails, allerr))
