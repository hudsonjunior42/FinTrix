"""Recursos novos: calculadora, divisão entre categorias, aviso de limite, duplicar, desfazer, busca por período,
janela da categoria, previsão, modo discreto, fixas de valor variável e a cada N meses."""
import pathlib, json
from playwright.sync_api import sync_playwright
AQUI = pathlib.Path(__file__).resolve().parent; RAIZ = AQUI.parents[1]
src = open(AQUI/"run.py").read()
exec(src[:src.index("\nwith sync_playwright() as p:")])
fails=[]
def check(l,g,e):
    ok=g==e; print(("OK  " if ok else "FALHA ")+f"{l}: {g!r}"+("" if ok else f" (esperado {e!r})"))
    if not ok: fails.append(l)

CAT = "name => Object.entries(S.cfg.categorias).find(([,c]) => c.nome === name)[0]"
DOCS = "() => [...window.__store.entries()].filter(([k]) => /\\/l\\d{4}\\//.test(k)).map(([k,v]) => ({...v, _k:k}))"
def docs(pg): return pg.evaluate(DOCS)
def cat(pg, n): return pg.evaluate(f"({CAT})({json.dumps(n)})")
def abrir_d(pg):
    pg.click("#title"); pg.keyboard.press("d"); pg.wait_for_selector("#m-valor"); pg.wait_for_timeout(80)
def fechar(pg):
    pg.wait_for_selector(".mback", state="detached", timeout=3000)
SEED = """async (a) => {
  const conta = Object.keys(S.cfg.contas)[0];
  for (const l of a) await lancSave({ id: rid(), tags: [], obs: '', pago: true, cartao: null, conta, criado: Date.now(), ...l });
}"""
allerr = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg, errs = nova_pagina(b, viewport={"width":1280,"height":900}, color_scheme="dark")
    pg.goto("file://"+str(AQUI/"index.html")); pg.wait_for_selector('[data-act="onb-conta"]'); pg.click('[data-act="onb-conta"]'); pg.wait_for_selector("#o-nome")
    pg.evaluate("localStorage.clear()")
    pg.fill("#o-nome","Nubank"); pg.click('[data-act="onb-criar"]'); pg.wait_for_selector("text=Saldo em contas")
    HOJE = pg.evaluate("today()"); M = HOJE[:7]
    ALI, SUP, FAR, SAU, TRA, APP_ = cat(pg,"Alimentação"), cat(pg,"Supermercado"), cat(pg,"Farmácia"), cat(pg,"Saúde"), cat(pg,"Transporte"), cat(pg,"Aplicativo e táxi")
    conta = pg.evaluate("Object.keys(S.cfg.contas)[0]")
    pg.evaluate(f"cfgWrite({{cartoes: {{k1: {{nome: 'Visa', fech: 25, venc: 5, limite: 300000, conta: '{conta}', cor: '#9085E9', arq: false}}}}, orc: {{ '{ALI}': 50000 }} }})")
    pg.wait_for_timeout(150)

    # ---------- calculadora
    abrir_d(pg)
    pg.keyboard.type("2590"); pg.keyboard.press("+"); pg.wait_for_timeout(50)
    check("calc: entrou no modo conta", pg.eval_on_selector("#m-valor", "e => e.value"), "25,90+")
    pg.keyboard.type("12,50"); pg.wait_for_timeout(50)
    check("calc: prévia", pg.inner_text(".calc-res").replace("\xa0"," "), "= R$ 38,40")
    pg.keyboard.press("Enter"); pg.wait_for_timeout(80)
    check("calc: Enter fecha a conta sem salvar", [pg.eval_on_selector("#m-valor", "e => e.value").replace("\xa0"," "), pg.locator(".mback").count()], ["R$ 38,40", 1])
    pg.fill("#m-desc", "Padaria"); pg.select_option("#m-cat", ALI)
    pg.screenshot(path=str(SHOTS/"n1-calc.png"))
    pg.focus("#m-valor"); pg.keyboard.press("Enter"); fechar(pg); pg.wait_for_timeout(100)
    d = [x for x in docs(pg) if x.get("desc") == "Padaria"]
    check("calc: salvou o resultado", [x["valor"] for x in d], [3840])
    # botões da calculadora (celular)
    abrir_d(pg); pg.keyboard.type("1000")
    pg.click('[data-act="calc-on"]'); pg.click('[data-act="calc-op"][data-op="×"]'); pg.keyboard.type("3"); pg.click('[data-act="calc-ok"]'); pg.wait_for_timeout(60)
    check("calc: botões ×, =", pg.eval_on_selector("#m-valor", "e => e.value").replace("\xa0"," "), "R$ 30,00")
    pg.click('[data-act="calc-on"]'); pg.keyboard.type("-50"); pg.click('[data-act="calc-ok"]'); pg.wait_for_timeout(60)
    check("calc: resultado negativo é recusado", "negativo" in pg.inner_text(".calc-res"), True)
    pg.keyboard.press("Escape"); fechar(pg)
    # salvar direto com a conta aberta grava o resultado
    abrir_d(pg); pg.keyboard.type("1000"); pg.keyboard.press("+"); pg.keyboard.type("5"); pg.fill("#m-desc", "Conta aberta"); pg.select_option("#m-cat", ALI)
    pg.evaluate("document.querySelector('#m-valor').dataset.expr = '1'; document.querySelector('#m-valor').value = '10,00+5'")
    pg.click("#m-salvar"); fechar(pg); pg.wait_for_timeout(100)
    ca = [x for x in docs(pg) if x.get("desc") == "Conta aberta"]
    check("calc: Salvar com a conta aberta", [x["valor"] for x in ca], [1500])
    pg.evaluate(f"(async () => {{ const l = Object.values(S.anos).flat().find(x => x.desc === 'Conta aberta'); await lancDel(l); }})()"); pg.wait_for_timeout(100)

    # ---------- divisão entre categorias
    abrir_d(pg); pg.keyboard.type("15000"); pg.fill("#m-desc", "Supermercado"); pg.select_option("#m-cat", SUP)
    pg.click('[data-act="div-add"]'); pg.select_option('[data-div-cat="0"]', FAR)
    pg.focus('[data-div-v="0"]'); pg.keyboard.type("3000"); pg.wait_for_timeout(60)
    check("divisão: principal fica com o restante", pg.inner_text("#m-div-h").replace("\xa0"," "), "Supermercado fica com o restante: R$ 120,00")
    check("divisão: rótulo da principal", pg.inner_text("#m-cat-lab"), "Categoria principal")
    pg.screenshot(path=str(SHOTS/"n2-divisao.png"))
    pg.click("#m-salvar"); fechar(pg); pg.wait_for_timeout(100)
    sup = [x for x in docs(pg) if x.get("desc") == "Supermercado"][0]
    check("divisão: gravada", sup.get("div"), [{"cat": SUP, "valor": 12000}, {"cat": FAR, "valor": 3000}])
    g = pg.evaluate("Object.fromEntries(gastosPorCat(itensMes(S.mes)).map(x => [x.k, x.v]))")
    check("divisão: relatórios contam cada parte", [g.get(ALI), g.get(SAU)], [3840 + 12000, 3000])
    # parte maior que o total
    abrir_d(pg); pg.keyboard.type("1000"); pg.select_option("#m-cat", SUP); pg.click('[data-act="div-add"]'); pg.select_option('[data-div-cat="0"]', FAR); pg.focus('[data-div-v="0"]'); pg.keyboard.type("2000")
    pg.click("#m-salvar"); pg.wait_for_timeout(80)
    check("divisão: recusa partes maiores que o total", pg.inner_text("#m-err"), "As outras partes somam mais que o valor total.")
    pg.keyboard.press("Escape"); fechar(pg)

    # ---------- aviso de limite (Alimentação: R$ 500, já tem R$ 158,40)
    abrir_d(pg); pg.select_option("#m-cat", ALI); pg.focus("#m-valor"); pg.keyboard.type("25000"); pg.wait_for_timeout(60)
    check("limite: 80%", pg.locator(".orc-al.warn").count(), 1)
    print("   aviso:", pg.inner_text("#m-orc").replace("\xa0"," "))
    pg.focus("#m-valor"); pg.keyboard.press("Control+a"); pg.keyboard.type("40000"); pg.wait_for_timeout(60)
    check("limite: passou de 100%", pg.locator(".orc-al.over").count(), 1)
    pg.screenshot(path=str(SHOTS/"n3-limite.png"))
    pg.focus("#m-valor"); pg.keyboard.press("Control+a"); pg.keyboard.type("1000"); pg.wait_for_timeout(60)
    check("limite: sem aviso abaixo de 80%", pg.locator(".orc-al").count(), 0)
    pg.keyboard.press("Escape"); fechar(pg)

    # ---------- duplicar
    pg.click('.side [data-view="lanc"]'); pg.wait_for_timeout(100)
    pg.locator(".row .grow", has_text="Supermercado").first.click(); pg.wait_for_selector('[data-act="m-duplicar"]')
    pg.click('[data-act="m-duplicar"]'); pg.wait_for_selector("#m-valor"); pg.wait_for_timeout(60)
    check("duplicar: janela de cópia", [pg.eval_on_selector("#m-valor", "e => e.value").replace("\xa0"," "), pg.eval_on_selector("#m-desc", "e => e.value"), pg.locator('[data-div-cat]').count(), pg.locator('[data-act="m-excluir"]').count()], ["R$ 150,00", "Supermercado", 1, 0])
    pg.click("#m-salvar"); fechar(pg); pg.wait_for_timeout(100)
    sups = [x for x in docs(pg) if x.get("desc") == "Supermercado"]
    check("duplicar: dois lançamentos iguais", [len(sups), len({x["_k"] for x in sups}), all(x.get("div") for x in sups)], [2, 2, True])
    # editar a divisão de um lançamento
    pg.locator(".row .grow", has_text="Supermercado").first.click(); pg.wait_for_selector('[data-div-v="0"]'); pg.wait_for_timeout(120)
    check("editar: partes carregadas", pg.eval_on_selector('[data-div-v="0"]', "e => e.value").replace("\xa0"," "), "R$ 30,00")
    pg.focus('[data-div-v="0"]'); pg.keyboard.press("Control+a"); pg.keyboard.type("4500"); pg.click("#m-salvar"); fechar(pg); pg.wait_for_timeout(120)
    divs = sorted(json.dumps(x.get("div")) for x in docs(pg) if x.get("desc") == "Supermercado")
    check("editar: divisão atualizada", json.dumps([{"cat": SUP, "valor": 10500}, {"cat": FAR, "valor": 4500}]) in divs, True)
    pg.locator(".row .grow", has_text="Supermercado").first.click(); pg.wait_for_selector('[data-act="div-del"]')
    ed_id = pg.evaluate("MS.edit.id")
    pg.click('[data-act="div-del"]'); pg.click("#m-salvar"); fechar(pg); pg.wait_for_timeout(120)
    sem = [x for x in docs(pg) if x.get("desc") == "Supermercado" and x["_k"].endswith(ed_id)][0]
    check("editar: remover a parte desfaz a divisão", [sem.get("div"), sem["cat"], sem["valor"]], [None, SUP, 15000])
    pg.evaluate(f"(async () => {{ const l = Object.values(S.anos).flat().find(x => x.id === '{ed_id}'); await lancSave({{ ...l, div: [{{ cat: '{SUP}', valor: 12000 }}, {{ cat: '{FAR}', valor: 3000 }}] }}); }})()"); pg.wait_for_timeout(120)
    check("lista: rótulo da divisão", pg.locator(".row", has_text="Supermercado").first.locator(".t2").inner_text().split(" · ")[0], "Dividido: Supermercado + Farmácia")

    # ---------- desfazer exclusão
    n0 = len(docs(pg))
    pg.locator(".row .grow", has_text="Padaria").first.click(); pg.wait_for_selector('[data-act="m-excluir"]')
    pg.click('[data-act="m-excluir"]'); pg.click('[data-act="m-del"][data-sc="esta"]'); fechar(pg); pg.wait_for_timeout(100)
    check("desfazer: excluiu", len(docs(pg)), n0 - 1)
    check("desfazer: aviso com botão", pg.locator('#toast [data-act="toast-acao"]').inner_text(), "Desfazer")
    pg.screenshot(path=str(SHOTS/"n4-desfazer.png"))
    pg.click('#toast [data-act="toast-acao"]'); pg.wait_for_timeout(200)
    pad = [x for x in docs(pg) if x.get("desc") == "Padaria"]
    check("desfazer: restaurou com o mesmo conteúdo", [len(docs(pg)), pad[0]["valor"] if pad else None], [n0, 3840])
    # parcelas: excluir todas e desfazer
    pg.evaluate(f"""(async () => {{ const g = rid(); for (let i = 1; i <= 3; i++) await lancSave({{ id: rid(), tipo: 'despesa', desc: 'Curso', data: dadd(today(), i - 1), comp: madd(S.mes, i - 1), conta: '{conta}', cat: '{cat(pg,"Cursos e idiomas")}', pago: i === 1, cartao: null, valor: 10000, grupo: g, parc: {{ i, n: 3 }}, tags: [], obs: '', criado: Date.now() + i }}); }})()""")
    pg.wait_for_timeout(150); pg.locator(".row .grow", has_text="Curso").first.click(); pg.wait_for_selector('[data-act="m-excluir"]')
    pg.click('[data-act="m-excluir"]'); pg.click('[data-act="m-del"][data-sc="todas"]'); fechar(pg); pg.wait_for_timeout(150)
    check("desfazer parcelas: excluiu as 3", len([x for x in docs(pg) if x.get("desc") == "Curso"]), 0)
    pg.click('#toast [data-act="toast-acao"]'); pg.wait_for_timeout(250)
    check("desfazer parcelas: voltaram as 3", sorted(x["parc"]["i"] for x in docs(pg) if x.get("desc") == "Curso"), [1, 2, 3])

    # ---------- busca por período
    Y = M[:4]; ANT = f"{int(Y)-1}"
    pg.evaluate(SEED, [
        {"tipo": "despesa", "desc": "Uber centro", "data": f"{Y}-01-15", "comp": f"{Y}-01", "cat": APP_, "valor": 2000},
        {"tipo": "despesa", "desc": "Uber aeroporto", "data": f"{Y}-03-10", "comp": f"{Y}-04", "cat": APP_, "valor": 3000, "conta": None, "cartao": "k1"},
        {"tipo": "despesa", "desc": "Uber casa", "data": HOJE, "comp": M, "cat": APP_, "valor": 2500},
        {"tipo": "despesa", "desc": "Uber antigo", "data": f"{ANT}-06-01", "comp": f"{ANT}-06", "cat": APP_, "valor": 1800},
    ] + [{"tipo": "despesa", "desc": f"Café {i}", "data": f"{ANT}-02-{(i % 27) + 1:02d}", "comp": f"{ANT}-02", "cat": ALI, "valor": 500} for i in range(320)])
    pg.wait_for_timeout(300); pg.evaluate("S.mes = today().slice(0,7); render()")
    pg.fill("#f-q", "uber"); pg.wait_for_timeout(350)
    check("busca no mês: só o mês aberto", pg.locator(".row .t1").all_inner_texts(), ["Uber casa"])
    pg.select_option("#f-per", "ano"); pg.wait_for_timeout(150)
    t1 = pg.locator(".row .t1").all_inner_texts()
    check("busca no ano: 3 lançamentos (com a compra no cartão)", sorted(t1), ["Uber aeroporto", "Uber casa", "Uber centro"])
    check("busca no ano: total de despesas", pg.locator(".foot-sum div").nth(1).locator("b").inner_text().replace("\xa0"," "), "R$ 75,00")
    check("busca no ano: compra no cartão com a fatura", "fatura de abr" in pg.locator(".row", has_text="Uber aeroporto").inner_text(), True)
    check("busca no ano: cabeçalhos de mês", pg.locator(".mgrp").count(), 3)
    pg.screenshot(path=str(SHOTS/"n5-busca-ano.png"))
    pg.select_option("#f-per", "tudo"); pg.wait_for_timeout(150)
    check("busca em tudo: inclui o ano anterior", len(pg.locator(".row .t1").all_inner_texts()), 4)
    pg.select_option("#f-per", "pers"); pg.wait_for_timeout(100)
    pg.fill("#f-de", f"{Y}-02"); pg.dispatch_event("#f-de", "change"); pg.fill("#f-ate", f"{Y}-05"); pg.dispatch_event("#f-ate", "change"); pg.wait_for_timeout(150)
    check("período escolhido: fev–mai", pg.locator(".row .t1").all_inner_texts(), ["Uber aeroporto"])
    pg.click('[data-act="flimpar"]'); pg.wait_for_timeout(100)
    pg.select_option("#f-per", "tudo"); pg.wait_for_timeout(200)
    check("tudo sem busca: mostra 300 e o botão", [pg.locator(".row").count(), pg.locator('[data-act="fmais"]').count()], [300, 1])
    pg.click('[data-act="fmais"]'); pg.wait_for_timeout(200)
    check("mostrar mais", pg.locator('[data-act="fmais"]').count(), 0)
    pg.select_option("#f-cat", SAU); pg.wait_for_timeout(150)
    check("filtro pela categoria da parte: valor da parte", pg.locator(".foot-sum div").nth(1).locator("b").inner_text().replace("\xa0"," "), "R$ 60,00")
    check("filtro pela categoria da parte: etiqueta", pg.locator(".row .tag", has_text="parte").count(), 2)
    pg.click('[data-act="flimpar"]'); pg.wait_for_timeout(100)

    # ---------- janela da categoria
    pg.click('.side [data-view="relatorios"]'); pg.wait_for_timeout(150)
    pg.locator(f'.catbar[data-cat="{ALI}"]').first.click(); pg.wait_for_selector(".cd-kpis")
    check("categoria: título", pg.inner_text(".mhead h3"), "Alimentação")
    subs = pg.locator(".cd-sec").first.locator(".catbar .nm").all_inner_texts()
    check("categoria: subcategorias", sorted(x.strip() for x in subs), ["Alimentação (geral)", "Supermercado"])
    check("categoria: lançamentos", pg.locator(".cd-list .row").count(), 3)
    pg.screenshot(path=str(SHOTS/"n6-categoria.png"))
    pg.click('[data-act="cd-mes"][data-d="-1"]'); pg.wait_for_timeout(80)
    check("categoria: mês anterior", pg.inner_text(".cd-nav span").lower(), pg.evaluate("mesLongo(madd(today().slice(0,7), -1))"))
    pg.click('[data-act="cd-mes"][data-d="1"]'); pg.click('[data-act="cd-lanc"]'); pg.wait_for_timeout(150)
    check("categoria: ver em Lançamentos", [pg.evaluate("S.view"), pg.evaluate("S.f.cat")], ["lanc", ALI])
    pg.click('[data-act="flimpar"]')
    pg.click('.side [data-view="relatorios"]'); pg.wait_for_timeout(100)
    pg.locator('.panel:has(h2:text("Despesas por categoria")) [data-v="rosca"]').click(); pg.wait_for_timeout(100)
    pg.locator(f'.gli[data-cat="{SAU}"]').click(); pg.wait_for_selector(".cd-kpis")
    check("categoria pela legenda da rosca", pg.inner_text(".mhead h3"), "Saúde")
    check("categoria: parte de lançamento dividido", pg.locator(".cd-list .row .tag", has_text="parte").count(), 2)
    pg.keyboard.press("Escape"); fechar(pg)
    pg.click('.side [data-view="orcamento"]'); pg.wait_for_timeout(100)
    pg.locator(f'.li .grow[data-cat="{ALI}"]').click(); pg.wait_for_selector(".cd-kpis")
    check("categoria pelo orçamento", pg.inner_text(".mhead h3"), "Alimentação")
    pg.keyboard.press("Escape"); fechar(pg)

    # ---------- previsão
    pv = pg.evaluate(f"previsaoCat('{ALI}', today().slice(0,7))")
    dia = int(HOJE[8:]); import calendar; dm = calendar.monthrange(int(Y), int(M[5:]))[1]
    atual = 3840 + 12000 * 2
    var = atual  # tudo variável, no débito, até hoje
    esp = atual + (round(var / dia * (dm - dia)) if dia >= 7 else 0)
    print("   previsão:", pv, "esperado prev", esp, "dia", dia)
    check("previsão: gasto atual", pv["atual"], atual)
    if dia >= 7: check("previsão: no ritmo atual", pv["prev"], esp)
    pt = pg.evaluate(f"previsaoCat('{TRA}', today().slice(0,7))")
    check("previsão: um gasto isolado não vira ritmo", pt["prev"], pt["atual"])
    check("orçamento: texto da previsão", ("Previsão" in pg.locator(".li", has_text="Alimentação").inner_text()) == (pv["prev"] != pv["atual"]), True)
    pg.screenshot(path=str(SHOTS/"n7-orcamento.png"))

    # ---------- modo discreto
    pg.click('.side [data-view="geral"]'); pg.wait_for_timeout(100)
    pg.click("#eyebtn"); pg.wait_for_timeout(100)
    check("discreto: KPI escondido", pg.locator(".kpi .val").first.inner_text(), "R$ ••••")
    check("discreto: nenhum valor visível na tela", "R$ 1" in pg.inner_text("#content") or "R$ 2" in pg.inner_text("#content"), False)
    check("discreto: lembrado", pg.evaluate("localStorage.getItem('lc.disc')"), "true")
    pg.screenshot(path=str(SHOTS/"n8-discreto.png"))
    abrir_d(pg); pg.keyboard.type("1234")
    check("discreto: campo de valor mostra o que é digitado", pg.eval_on_selector("#m-valor", "e => e.value").replace("\xa0"," "), "R$ 12,34")
    pg.keyboard.press("Escape"); fechar(pg)
    pg.click("#eyebtn"); pg.wait_for_timeout(100)
    check("discreto: desligado", pg.locator(".kpi .val").first.inner_text().startswith("R$ ••"), False)

    # ---------- fixas: valor variável e a cada N meses
    abrir_d(pg); pg.keyboard.type("10000"); pg.fill("#m-desc", "Luz"); pg.select_option("#m-cat", cat(pg, "Energia"))
    pg.click("details.more summary"); pg.click('[data-act="m-rep"][data-v="fixa"]'); pg.check("#m-varia"); pg.wait_for_timeout(60)
    check("fixa: dica do valor variável", "média dos últimos 3" in pg.inner_text("#m-rep-h"), True)
    check("fixa: sem divisão em fixa", pg.locator("#m-div-w").is_hidden(), True)
    pg.click("#m-salvar"); fechar(pg); pg.wait_for_timeout(150)
    rid_luz = pg.evaluate("Object.entries(S.cfg.recorr).find(([,r]) => r.desc === 'Luz')[0]")
    check("fixa: gravou varia e cada", pg.evaluate(f"[S.cfg.recorr['{rid_luz}'].varia, S.cfg.recorr['{rid_luz}'].cada]"), [True, 1])
    nov = pg.evaluate("madd(today().slice(0,7), 1)"); dez = pg.evaluate("madd(today().slice(0,7), 2)")
    # registra novembro com R$ 140
    pg.evaluate(f"(async () => {{ const v = virtuais('{nov}', '{nov}').find(x => x.recorr === '{rid_luz}'); await lancSave({{ ...limpo(v), id: rid(), valor: 14000, criado: Date.now() }}); }})()"); pg.wait_for_timeout(150)
    vd = pg.evaluate(f"(() => {{ derivar(); const v = virtuais('{dez}', '{dez}').find(x => x.recorr === '{rid_luz}'); return [v.valor, v.estimado]; }})()")
    check("fixa variável: previsão = média dos registros", vd, [12000, True])
    # IPVA anual
    abrir_d(pg); pg.keyboard.type("90000"); pg.fill("#m-desc", "IPVA"); pg.select_option("#m-cat", cat(pg, "IPVA, seguro e licenciamento"))
    pg.click("details.more summary"); pg.click('[data-act="m-rep"][data-v="fixa"]'); pg.select_option("#m-cada", "12"); pg.wait_for_timeout(60)
    check("fixa anual: dica", "a cada 12 meses" in pg.inner_text("#m-rep-h"), True)
    pg.screenshot(path=str(SHOTS/"n9-fixa-anual.png"))
    pg.click("#m-salvar"); fechar(pg); pg.wait_for_timeout(150)
    rid_ipva = pg.evaluate("Object.entries(S.cfg.recorr).find(([,r]) => r.desc === 'IPVA')[0]")
    meses = pg.evaluate(f"(() => {{ derivar(); return virtuais(madd(today().slice(0,7), 1), madd(today().slice(0,7), 24)).filter(v => v.recorr === '{rid_ipva}').map(v => v.recM); }})()")
    check("fixa anual: só a cada 12 meses", meses, [pg.evaluate("madd(today().slice(0,7), 12)"), pg.evaluate("madd(today().slice(0,7), 24)")])
    pg.click('.side [data-view="config"]'); pg.wait_for_timeout(100)
    check("fixas cadastradas: frequência", "anual" in pg.locator(".panel:has(h2:text('Fixas cadastradas')) .li", has_text="IPVA").inner_text(), True)
    check("fixas cadastradas: média", "média" in pg.locator(".panel:has(h2:text('Fixas cadastradas')) .li", has_text="Luz").inner_text(), True)
    pg.click(f'[data-act="fixa-editar"][data-id="{rid_ipva}"]'); pg.wait_for_selector("#fx-cada")
    pg.select_option("#fx-cada", "6"); pg.click('[data-act="fixa-salvar"]'); fechar(pg); pg.wait_for_timeout(150)
    meses = pg.evaluate(f"(() => {{ derivar(); return virtuais(madd(today().slice(0,7), 1), madd(today().slice(0,7), 12)).filter(v => v.recorr === '{rid_ipva}').map(v => v.recM); }})()")
    check("editar fixa: semestral", meses, [pg.evaluate("madd(today().slice(0,7), 6)"), pg.evaluate("madd(today().slice(0,7), 12)")])
    pg.locator(".panel:has(h2:text('Fixas cadastradas'))").scroll_into_view_if_needed(); pg.screenshot(path=str(SHOTS/"n10-fixas.png"))
    print("erros:", errs); allerr += errs

    # ---------- celular: janela com divisão e calculadora
    pm, e2 = nova_pagina(b, viewport={"width":390,"height":844}, is_mobile=True, has_touch=True, color_scheme="light")
    pm.goto("file://"+str(AQUI/"index.html")); pm.wait_for_selector('[data-act="onb-conta"]'); pm.click('[data-act="onb-conta"]'); pm.wait_for_selector("#o-nome")
    pm.fill("#o-nome","Nubank"); pm.click('[data-act="onb-criar"]'); pm.wait_for_selector("text=Saldo em contas")
    pm.click("#fab"); pm.click('#menu button:has-text("Despesa")'); pm.wait_for_selector("#m-valor")
    pm.click('[data-act="calc-on"]'); pm.keyboard.type("25,90"); pm.click('[data-act="calc-op"][data-op="+"]'); pm.keyboard.type("12,50")
    pm.click('[data-act="div-add"]'); pm.wait_for_timeout(100)
    sw = pm.evaluate("[document.querySelector('.modal').scrollWidth, document.querySelector('.modal').clientWidth]")
    check("celular: janela sem rolagem lateral", sw[0] <= sw[1], True)
    pm.screenshot(path=str(SHOTS/"n11-celular-janela.png"))
    pm.keyboard.press("Escape")
    pm.click("#eyebtn"); pm.wait_for_timeout(80); pm.screenshot(path=str(SHOTS/"n12-celular-discreto.png"))
    sw = pm.evaluate("[document.documentElement.scrollWidth, innerWidth]")
    check("celular: topo com o olho sem rolagem", sw[0] <= sw[1], True)
    print("erros:", e2); allerr += e2
    b.close()
print("RESULTADO:", "TUDO CERTO" if not fails and not allerr else (fails, allerr))
