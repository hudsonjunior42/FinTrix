"""Seleção múltipla em Lançamentos: selecionar (clique, Shift, todos, Ctrl+clique, toque longo), editar em lote, excluir em lote, desfazer."""
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
def iniciar(b, **kw):
    pg, errs = nova_pagina(b, **kw)
    pg.goto("file://"+str(AQUI/"index.html")); pg.wait_for_selector('[data-act="onb-conta"]'); pg.click('[data-act="onb-conta"]'); pg.wait_for_selector("#o-nome")
    pg.fill("#o-nome","Nubank"); pg.click('[data-act="onb-criar"]'); pg.wait_for_selector("text=Saldo em contas")
    cat = lambda n: pg.evaluate(f"({CAT})({json.dumps(n)})")
    conta = pg.evaluate("Object.keys(S.cfg.contas)[0]")
    pg.evaluate(f"""(async () => {{
      await cfgWrite({{ contas: {{ a2: {{ nome: 'Carteira', tipo: 'carteira', inicial: 0, cor: '#2E9E4F', total: true, arq: false, ordem: 1 }} }},
        cartoes: {{ k1: {{ nome: 'Visa', fech: 25, venc: 5, limite: 300000, conta: '{conta}', cor: '#9085E9', arq: false }} }},
        tags: {{ t1: {{ nome: 'viagem', arq: false }} }},
        recorr: {{ r1: {{ tipo: 'despesa', desc: 'Academia', valor: 9000, cat: '{cat("Atividade física")}', conta: '{conta}', dia: 28, inicio: today().slice(0,7), fim: null, tags: [], pulos: [], arq: false }},
                   r2: {{ tipo: 'despesa', desc: 'Internet', valor: 10000, cat: '{cat("Internet")}', conta: '{conta}', dia: 3, inicio: today().slice(0,7), fim: null, tags: [], pulos: [], arq: false }} }} }});
      const M = today().slice(0,7), b = {{ conta: '{conta}', pago: true, cartao: null, tags: [], obs: '', comp: M }};
      const d = n => M + '-' + String(n).padStart(2, '0');
      await lancSave({{ ...b, id: 'l1', tipo: 'despesa', desc: 'Padaria', data: d(2), cat: '{cat("Feira, padaria e açougue")}', valor: 1500, criado: 1 }});
      await lancSave({{ ...b, id: 'l2', tipo: 'despesa', desc: 'Mercado', data: d(3), cat: '{cat("Supermercado")}', valor: 20000, criado: 2 }});
      await lancSave({{ ...b, id: 'l3', tipo: 'despesa', desc: 'Lanche', data: d(4), cat: '{cat("Lanches e café")}', valor: 2500, criado: 3 }});
      await lancSave({{ ...b, id: 'l4', tipo: 'receita', desc: 'Salário', data: d(5), cat: '{cat("Salário")}', valor: 500000, criado: 4 }});
      await lancSave({{ ...b, id: 'l5', tipo: 'transf', desc: 'Saque', data: d(6), cat: null, destino: 'a2', valor: 10000, criado: 5 }});
      await lancSave({{ ...b, id: 'l6', tipo: 'despesa', desc: 'Internet', data: d(3), cat: '{cat("Internet")}', valor: 10000, recorr: 'r2', recM: M, criado: 6 }});
      await lancSave({{ ...b, id: 'k1c', tipo: 'despesa', desc: 'Livro', data: madd(M, -1) + '-01', comp: faturaDe(S.cfg.cartoes.k1, madd(M, -1) + '-01'), conta: null, cartao: 'k1', cat: '{cat("Livros e material")}', valor: 8000, criado: 7 }});
    }})()"""); pg.wait_for_timeout(250)
    pg.click('.side [data-view="lanc"]') if pg.is_visible(".side") else pg.evaluate("irPara('lanc')")
    pg.wait_for_timeout(120)
    return pg, errs, cat

allerr = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg, errs, cat = iniciar(b, viewport={"width":1280,"height":900})
    row = lambda n: pg.locator(".row", has_text=n).first
    pg.click('[data-act="sel-modo"]'); pg.wait_for_timeout(80)
    check("modo seleção: caixas e barra", [pg.locator(".selrow").count() > 0, pg.locator(".selbar").count()], [True, 1])
    check("fixa não registrada não é selecionável", "nosel" in row("Academia").get_attribute("class"), True)
    row("Padaria").click(); row("Lanche").click(); pg.wait_for_timeout(60)
    check("2 selecionados com total", pg.inner_text(".selbar-n").replace("\xa0", " "), "2 selecionados · −R$ 40,00")
    row("Padaria").click(); row("Lanche").click()
    row("Padaria").click(); row("Salário").click(modifiers=["Shift"]); pg.wait_for_timeout(60)
    check("Shift+clique seleciona o intervalo", sorted(pg.evaluate("[...S.sel]")), sorted(["l1", "l2", "l6", "l3", "l4"]))
    pg.click('[data-act="sel-todos"]'); pg.wait_for_timeout(60)
    n_todos = pg.evaluate("S._todos.length")
    check("selecionar todos", pg.evaluate("S.sel.size"), n_todos)
    pg.click('[data-act="sel-todos"]'); pg.wait_for_timeout(60)
    check("segundo clique limpa", pg.evaluate("S.sel.size"), 0)
    pg.screenshot(path=str(SHOTS/"s1-selecao.png"))

    # editar em lote: 3 despesas
    for n in ["Padaria", "Mercado", "Lanche"]: row(n).click()
    pg.click('[data-act="sel-editar"]'); pg.wait_for_selector("#lt-cat")
    COMB = cat("Combustível")
    pg.select_option("#lt-cat", COMB); pg.select_option("#lt-sit", "0"); pg.select_option("#lt-tag-add", "t1")
    pg.screenshot(path=str(SHOTS/"s2-editar-lote.png"))
    pg.click('[data-act="lote-salvar"]'); pg.wait_for_selector(".mback", state="detached"); pg.wait_for_timeout(150)
    d = pg.evaluate(DOCS)
    check("lote: categoria, situação e tag", [[d[n]["cat"], d[n]["pago"], d[n]["tags"]] for n in ["Padaria", "Mercado", "Lanche"]], [[COMB, False, ["t1"]]] * 3)
    check("lote: outros não mudam", [d["Salário"]["cat"] == cat("Salário"), d["Saque"].get("tags")], [True, []])
    check("lote: seleção continua", pg.evaluate("S.sel.size"), 3)
    pg.click('#toast [data-act="toast-acao"]'); pg.wait_for_timeout(250)
    d = pg.evaluate(DOCS)
    check("lote: desfazer", [[d[n]["cat"], d[n]["pago"], d[n]["tags"]] for n in ["Padaria"]], [[cat("Feira, padaria e açougue"), True, []]])
    # seleção mista: categoria desabilitada; conta só fora do cartão
    pg.click('[data-act="sel-sair"]'); pg.wait_for_timeout(60)
    check("sair da seleção", [pg.locator(".selbar").count(), pg.evaluate("S.sel.size")], [0, 0])
    pg.select_option("#f-conta", ""); pg.fill("#f-q", "a"); pg.wait_for_timeout(300)   # com busca as compras no cartão aparecem
    pg.click('[data-act="sel-modo"]')
    for n in ["Padaria", "Salário", "Livro"]: row(n).click()
    pg.click('[data-act="sel-editar"]'); pg.wait_for_selector("#lt-cat")
    check("mista: categoria desabilitada", pg.is_disabled("#lt-cat"), True)
    check("mista: aviso da conta", "Vale para 2 de 3" in pg.inner_text("#f-lote"), True)
    novo_dia = pg.evaluate("madd(today().slice(0,7), 1) + '-26'")
    pg.fill("#lt-data-txt", "/".join(reversed(novo_dia.split("-")))); pg.select_option("#lt-conta", "a2")
    pg.click('[data-act="lote-salvar"]'); pg.wait_for_selector(".mback", state="detached"); pg.wait_for_timeout(150)
    d = pg.evaluate(DOCS)
    check("data: comp do cartão recalculado pela fatura", [d["Livro"]["data"], d["Livro"]["comp"], d["Livro"]["conta"]], [novo_dia, pg.evaluate(f"faturaDe(S.cfg.cartoes.k1, '{novo_dia}')"), None])
    check("data e conta fora do cartão", [d["Padaria"]["comp"], d["Padaria"]["conta"], d["Salário"]["conta"]], [novo_dia[:7], "a2", "a2"])
    pg.click('#toast [data-act="toast-acao"]'); pg.wait_for_timeout(250)
    check("desfazer volta a data e a fatura do cartão", [pg.evaluate(DOCS)["Livro"]["data"][:7], pg.evaluate(DOCS)["Livro"]["comp"]], [pg.evaluate("madd(today().slice(0,7), -1)"), pg.evaluate("today().slice(0,7)")])
    pg.keyboard.press("Escape"); pg.wait_for_timeout(60)
    check("Esc sai da seleção", pg.evaluate("S.selModo"), False)
    pg.click('[data-act="flimpar"]'); pg.wait_for_timeout(100)

    # excluir em lote (inclui fixa registrada) e desfazer
    pg.locator(".row .grow", has_text="Mercado").first.click(modifiers=["Control"]); pg.wait_for_timeout(80)
    check("Ctrl+clique entra na seleção", [pg.evaluate("S.selModo"), pg.evaluate("[...S.sel]")], [True, ["l2"]])
    row("Internet").click(); pg.wait_for_timeout(60)
    pg.click('[data-act="sel-excluir"]'); pg.wait_for_selector("#lt-del-ok")
    check("confirmação fala da fixa", "pulado" in pg.inner_text(".modal"), True)
    pg.click("#lt-del-ok"); pg.wait_for_selector(".mback", state="detached"); pg.wait_for_timeout(150)
    d = pg.evaluate(DOCS)
    check("excluiu 2", ["Mercado" in d, "Internet" in d, pg.evaluate("S.selModo")], [False, False, False])
    check("mês da fixa pulado (não volta como pendente)", pg.evaluate("S.cfg.recorr.r2.pulos"), [pg.evaluate("today().slice(0,7)")])
    pg.click('#toast [data-act="toast-acao"]'); pg.wait_for_timeout(250)
    d = pg.evaluate(DOCS)
    check("desfazer exclusão em lote", ["Mercado" in d, "Internet" in d, pg.evaluate("S.cfg.recorr.r2.pulos")], [True, True, []])
    print("erros:", errs); allerr += errs

    # celular: toque longo
    pm, em, _ = iniciar(b, viewport={"width":390,"height":844}, is_mobile=True, has_touch=True, color_scheme="light")
    g = pm.locator(".row .grow", has_text="Mercado").first; bb = g.bounding_box()
    pm.mouse.move(bb["x"] + 20, bb["y"] + 10); pm.mouse.down(); pm.wait_for_timeout(650); pm.mouse.up(); pm.wait_for_timeout(150)
    check("toque longo entra na seleção com a linha marcada", [pm.evaluate("S.selModo"), pm.evaluate("[...S.sel]"), pm.locator(".mback").count()], [True, ["l2"], 0])
    check("celular: botão + escondido", pm.is_visible("#fab"), False)
    pm.locator(".row", has_text="Lanche").first.tap(); pm.wait_for_timeout(80)
    bar = pm.locator(".selbar").bounding_box(); tab = pm.locator("#tabbar").bounding_box()
    check("celular: barra acima das abas", bar["y"] + bar["height"] <= tab["y"] + 1, True)
    sw = pm.evaluate("[document.documentElement.scrollWidth, innerWidth]")
    check("celular: sem rolagem lateral", sw[0] <= sw[1], True)
    pm.screenshot(path=str(SHOTS/"s3-celular.png"))
    print("erros:", em); allerr += em
    b.close()
print("RESULTADO:", "TUDO CERTO" if not fails and not allerr else (fails, allerr))
