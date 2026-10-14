"""Editar uma parcela: corrigir parcelas/parcela atual, virar lançamento único ou fixa (com Desfazer)."""
import pathlib, json
from playwright.sync_api import sync_playwright
AQUI = pathlib.Path(__file__).resolve().parent; RAIZ = AQUI.parents[1]
src = open(AQUI/"run.py").read()
exec(src[:src.index("\nwith sync_playwright() as p:")])
fails=[]
def check(l,g,e):
    ok=g==e; print(("OK  " if ok else "FALHA ")+f"{l}: {g!r}"+("" if ok else f" (esperado {e!r})"))
    if not ok: fails.append(l)
REP = '[data-act="m-rep"]'
def rep(v): return f'{REP}[data-v="{v}"]'
with sync_playwright() as p:
    b = p.chromium.launch()
    pg, errs = nova_pagina(b, viewport={"width":1280,"height":900})
    pg.goto("file://"+str(AQUI/"index.html")); pg.wait_for_selector('[data-act="onb-conta"]'); pg.click('[data-act="onb-conta"]'); pg.wait_for_selector("#o-nome")
    pg.fill("#o-nome","Nubank"); pg.click('[data-act="onb-criar"]'); pg.wait_for_selector("text=Saldo em contas")
    conta = pg.evaluate("Object.keys(S.cfg.contas)[0]")
    cat = lambda n: pg.evaluate(f"Object.entries(S.cfg.categorias).find(([,c]) => c.nome === {json.dumps(n)})[0]")
    F = pg.evaluate("""(async () => {
      await cfgWrite({ cartoes: { k1: { nome: 'Visa', fech: 25, venc: 5, limite: 900000, conta: '%s', cor: '#9085E9', arq: false } } });
      await new Promise(r => setTimeout(r, 60)); return faturaDe(S.cfg.cartoes.k1, today()); })()""" % conta)
    def grupo_cartao(g, desc, n, valor, ids):
        pg.evaluate(f"""(async () => {{ const d = today();
          for (let i = 1; i <= {n}; i++) await lancSave({{ id: '{ids}' + i, tipo: 'despesa', desc: '{desc}', data: d, comp: madd('{F}', i - 1), conta: null, cartao: 'k1', cat: '{cat("Eletrônicos e informática")}', valor: {valor}, pago: true, grupo: '{g}', parc: {{ i, n: {n} }}, tags: [], obs: '', criado: i }}); }})()""")
    grupo_cartao("gA", "TV", 3, 50000, "a")
    pg.evaluate(f"""(async () => {{ for (let i = 1; i <= 3; i++) await lancSave({{ id: 'b' + i, tipo: 'despesa', desc: 'Sofá', data: dadd('2026-08-10', i - 1), comp: mk(dadd('2026-08-10', i - 1)), conta: '{conta}', cartao: null, cat: '{cat("Supermercado")}', valor: 10000, pago: i === 1, grupo: 'gB', parc: {{ i, n: 3 }}, tags: [], obs: '', criado: 10 + i }}); }})()""")
    grupo_cartao("gC", "Streaming anual", 4, 3990, "c")
    pg.wait_for_timeout(300)
    G = lambda g: pg.evaluate(f"Object.values(S.anos).flat().filter(x => x.grupo === '{g}').sort((a, b) => a.parc.i - b.parc.i).map(x => [x.id, x.parc.i + '/' + x.parc.n, x.comp, x.valor, x.desc])")
    L = lambda id_: pg.evaluate(f"Object.values(S.anos).flat().find(x => x.id === '{id_}') || null")
    def abrir(id_):
        pg.evaluate(f"abrirLanc({{ edit: acharItem('{id_}') }})"); pg.wait_for_selector("#m-valor"); pg.wait_for_timeout(100)
        if not pg.evaluate("document.querySelector('details.more').open"): pg.click("details.more summary")
    def salvar():
        pg.click("#m-salvar"); pg.wait_for_selector(".mback", state="detached"); pg.wait_for_timeout(250)
    def desfazer():
        pg.click('[data-act="toast-acao"]'); pg.wait_for_timeout(300)
    M = lambda o: pg.evaluate(f"madd('{F}', {o})")
    H = lambda: pg.inner_text("#m-rep-h").replace("\xa0", " ")

    # ---------- abrir uma parcela
    abrir("a1")
    check("Repetição: Única / Fixa / Parcelado, com Parcelado marcado", [pg.locator(".flab", has_text="Repetição").is_visible(), pg.locator(REP).all_inner_texts(), pg.locator(f"{REP}.on").inner_text()], [True, ["Única", "Fixa", "Parcelado"], "Parcelado"])
    check("campos preenchidos com 3 parcelas, atual 1", [pg.input_value("#m-n"), pg.input_value("#m-pa"), pg.locator('[data-act="m-vale"]').count()], ["3", "1", 0])
    check("dica sem mudança", H().startswith("Parcela 1 de 3."), True)
    check("escopo visível", pg.is_visible("#m-scope"), True)
    pg.screenshot(path=str(SHOTS/"pe1-parcela.png"))

    # ---------- parcela atual 1 → 2 (a última sai)
    pg.fill("#m-pa", "2"); pg.wait_for_timeout(60)
    h = H()
    check("dica: vira 2/3 e a última é excluída", ["passa a ser a parcela 2/3" in h, "1 parcela fica fora de 1 a 3 e é excluída" in h, pg.evaluate(f"mesCurto(madd('{F}', 2))") in h], [True, True, True])
    salvar()
    check("aviso", pg.inner_text("#toast span"), "Parcelamento corrigido: agora é a parcela 2/3")
    check("grupo renumerado", G("gA"), [["a1", "2/3", F, 50000, "TV"], ["a2", "3/3", M(1), 50000, "TV"]])
    desfazer()
    check("Desfazer volta as 3 parcelas", G("gA"), [["a1", "1/3", F, 50000, "TV"], ["a2", "2/3", M(1), 50000, "TV"], ["a3", "3/3", M(2), 50000, "TV"]])

    # ---------- 3 → 5 parcelas (cria 4 e 5 nas faturas seguintes) e muda a descrição em todas
    abrir("a1"); pg.fill("#m-n", "5"); pg.fill("#m-desc", "TV 55"); pg.check('input[name="m-sc"][value="todas"]'); pg.wait_for_timeout(60)
    check("dica: cria 4 a 5", "São criadas as parcelas 4 a 5 nas faturas seguintes" in H(), True)
    salvar()
    g = G("gA")
    check("5 parcelas, faturas seguidas, descrição nova em todas", [[x[1], x[2], x[4]] for x in g], [["1/5", F, "TV 55"], ["2/5", M(1), "TV 55"], ["3/5", M(2), "TV 55"], ["4/5", M(3), "TV 55"], ["5/5", M(4), "TV 55"]])
    check("novas parcelas com o valor da parcela", [x[3] for x in g], [50000] * 5)

    # ---------- parcela 3 vira a 1 (as anteriores saem, cria 4 e 5 depois da última)
    abrir("a3"); pg.fill("#m-pa", "1"); pg.wait_for_timeout(60)
    h = H()
    check("dica: 2 parcelas excluídas e criadas 4 a 5", ["2 parcelas ficam fora de 1 a 5 e são excluídas" in h, "São criadas as parcelas 4 a 5" in h], [True, True])
    salvar()
    check("3ª vira 1/5", [[x[1], x[2]] for x in G("gA")], [["1/5", M(2)], ["2/5", M(3)], ["3/5", M(4)], ["4/5", M(5)], ["5/5", M(6)]])
    check("a1 e a2 excluídas", [L("a1"), L("a2")], [None, None])

    # ---------- parcela da conta vira lançamento único, usando o total
    abrir("b2"); pg.click(rep("nao")); pg.wait_for_timeout(60)
    check("Única: dica e escopo escondido", ["as outras 2 parcelas são excluídas" in H(), pg.is_visible("#m-scope"), pg.is_visible("#m-n")], [True, False, False])
    check("botão Usar o total", pg.inner_text("#m-usar-total").replace("\xa0", " "), "Usar o total da compra (R$ 300,00)")
    pg.screenshot(path=str(SHOTS/"pe2-unica.png"))
    pg.click("#m-usar-total"); pg.wait_for_timeout(60)
    check("valor vira o total e o botão some", [pg.input_value("#m-valor").replace("\xa0", " "), pg.is_visible("#m-usar-total")], ["R$ 300,00", False])
    salvar()
    check("aviso única", pg.inner_text("#toast span"), "Agora é um lançamento único: 2 parcelas excluídas")
    l = L("b2")
    check("lançamento único com o total", [l.get("grupo"), l.get("parc"), l["valor"], l["data"], G("gB")], [None, None, 30000, "2026-09-10", []])
    desfazer()
    check("Desfazer volta o parcelado", [[x[0], x[1], x[3]] for x in G("gB")], [["b1", "1/3", 10000], ["b2", "2/3", 10000], ["b3", "3/3", 10000]])

    # ---------- parcela do cartão vira fixa
    abrir("c2"); pg.click(rep("fixa")); pg.wait_for_timeout(60)
    h = H()
    check("Fixa: dica", ["As 2 parcelas seguintes são excluídas" in h, "A parcela anterior fica como lançamento avulso" in h, "no mesmo cartão" in h, pg.is_visible("#m-cada")], [True, True, True, True])
    pg.screenshot(path=str(SHOTS/"pe3-fixa.png"))
    salvar()
    check("aviso fixa", pg.inner_text("#toast span"), "Agora é uma fixa: os próximos meses aparecem como pendentes")
    l = L("c2"); r = pg.evaluate("Object.entries(S.cfg.recorr).find(([, x]) => x.desc === 'Streaming anual')")
    check("c2 ligado à fixa, na mesma fatura", [l.get("grupo"), l.get("parc"), l.get("recorr") == r[0], l["comp"], pg.evaluate(f"faturaDe(S.cfg.cartoes.k1, '{l['data']}')"), l.get("recM") == r[1]["inicio"]], [None, None, True, M(1), M(1), True])
    check("fixa no cartão, valor da parcela", [r[1]["cartao"], r[1]["valor"], r[1]["cada"]], ["k1", 3990, 1])
    c1 = L("c1")
    check("anterior fica avulsa; seguintes excluídas", [c1.get("grupo"), c1.get("parc"), c1["comp"], L("c3"), L("c4")], [None, None, F, None, None])
    v = pg.evaluate(f"(() => {{ derivar(); const M = madd('{l['recM']}', 1); return virtuais(M, M).filter(x => x.desc === 'Streaming anual').map(x => x.comp); }})()")
    check("próximo mês prevista na fatura seguinte", v, [M(2)])
    check("sem duplicar o mês da parcela", pg.evaluate(f"(() => {{ derivar(); const M = '{l['recM']}'; return virtuais(M, M).filter(x => x.desc === 'Streaming anual').length; }})()"), 0)
    desfazer()
    check("Desfazer: parcelas de volta e fixa sai", [[x[0], x[1]] for x in G("gC")], [["c1", "1/4"], ["c2", "2/4"], ["c3", "3/4"], ["c4", "4/4"]])
    check("fixa desfeita não gera previsões", [pg.evaluate(f"S.cfg.recorr['{r[0]}'].arq"), pg.evaluate(f"(() => {{ derivar(); const M = madd('{l['recM']}', 1); return virtuais(M, M).filter(x => x.desc === 'Streaming anual').length; }})()")], [True, 0])

    # ---------- parcela com valor negativo: editar sem transformar continua salvando
    pg.evaluate(f"lancSave({{ id: 'e1', tipo: 'despesa', desc: 'Estorno parcelado', data: today(), comp: '{F}', conta: null, cartao: 'k1', cat: '{cat("Eletrônicos e informática")}', valor: -2000, pago: true, grupo: 'gE', parc: {{ i: 1, n: 2 }}, tags: [], obs: '', criado: 50 }})"); pg.wait_for_timeout(150)
    abrir("e1"); pg.fill("#m-desc", "Estorno parcelado 2"); salvar()
    check("parcela negativa salva normalmente", L("e1")["desc"], "Estorno parcelado 2")
    abrir("e1"); pg.click(rep("fixa")); pg.click("#m-salvar"); pg.wait_for_timeout(150)
    check("parcela negativa não vira fixa", pg.inner_text("#m-err"), "Estorno não pode virar fixa nem parcelado.")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(80)
    print("erros:", errs)

    # ---------- celular
    pm, em = nova_pagina(b, viewport={"width":390,"height":844}, is_mobile=True, has_touch=True)
    pm.goto("file://"+str(AQUI/"index.html")); pm.wait_for_selector('[data-act="onb-conta"]'); pm.tap('[data-act="onb-conta"]'); pm.wait_for_selector("#o-nome")
    pm.fill("#o-nome","Nubank"); pm.tap('[data-act="onb-criar"]'); pm.wait_for_selector("text=Saldo em contas")
    pm.evaluate("(async () => { const c = Object.keys(S.cfg.contas)[0], k = Object.keys(S.cfg.categorias)[0]; for (let i = 1; i <= 3; i++) await lancSave({ id: 'm' + i, tipo: 'despesa', desc: 'Curso', data: dadd(today(), i - 1), comp: mk(dadd(today(), i - 1)), conta: c, cartao: null, cat: k, valor: 25000, pago: false, grupo: 'gm', parc: { i, n: 3 }, tags: [], obs: '', criado: i }); })()"); pm.wait_for_timeout(200)
    pm.evaluate("abrirLanc({ edit: acharItem('m1') })"); pm.wait_for_selector("#m-valor"); pm.wait_for_timeout(100)
    pm.tap("details.more summary"); pm.fill("#m-n", "6"); pm.wait_for_timeout(80)
    pm.locator("#m-rep-h").scroll_into_view_if_needed(); pm.screenshot(path=str(SHOTS/"pe4-celular.png"))
    check("celular: sem rolagem lateral", pm.evaluate("(() => { const m = document.querySelector('.modal'); return [m.scrollWidth <= m.clientWidth + 1, document.documentElement.scrollWidth <= innerWidth]; })()"), [True, True])
    print("erros:", em); b.close()
print("RESULTADO:", "TUDO CERTO" if not fails and not errs and not em else (fails, errs, em))
