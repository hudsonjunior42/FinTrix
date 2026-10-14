"""Editar lançamento (cartão ou conta) e transformá-lo em fixa ou parcelado."""
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
allerr = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg, errs = nova_pagina(b, viewport={"width":1280,"height":900})
    pg.goto("file://"+str(AQUI/"index.html")); pg.wait_for_selector('[data-act="onb-conta"]'); pg.click('[data-act="onb-conta"]'); pg.wait_for_selector("#o-nome")
    pg.fill("#o-nome","Nubank"); pg.click('[data-act="onb-criar"]'); pg.wait_for_selector("text=Saldo em contas")
    conta = pg.evaluate("Object.keys(S.cfg.contas)[0]")
    cat = lambda n: pg.evaluate(f"Object.entries(S.cfg.categorias).find(([,c]) => c.nome === {json.dumps(n)})[0]")
    pg.evaluate(f"""(async () => {{
      await cfgWrite({{ cartoes: {{ k1: {{ nome: 'Visa', fech: 25, venc: 5, limite: 300000, conta: '{conta}', cor: '#9085E9', arq: false }} }}, contas: {{ x2: {{ nome: 'Poupança', tipo: 'poupanca', inicial: 0, cor: '#3987E5', total: true, arq: false, ordem: 1 }} }} }});
      await new Promise(r => setTimeout(r, 60));
      const d = today(), M = d.slice(0,7), F = faturaDe(S.cfg.cartoes.k1, d);
      const b = {{ pago: true, tags: [], obs: '' }};
      await lancSave({{ ...b, id: 'c1', tipo: 'despesa', desc: 'Spotify', data: d, comp: F, conta: null, cartao: 'k1', cat: '{cat("Streaming")}', valor: 2190, criado: 1 }});
      await lancSave({{ ...b, id: 'd1', tipo: 'despesa', desc: 'Academia', data: d, comp: M, conta: '{conta}', cartao: null, cat: '{cat("Atividade física")}', valor: 9900, criado: 2 }});
      await lancSave({{ ...b, id: 'p1', tipo: 'despesa', desc: 'TV', data: d, comp: F, conta: null, cartao: 'k1', cat: '{cat("Eletrônicos e informática")}', valor: 50000, grupo: 'g', parc: {{ i: 1, n: 3 }}, criado: 3 }});
      await lancSave({{ ...b, id: 's1', tipo: 'despesa', desc: 'Mercado', data: d, comp: M, conta: '{conta}', cartao: null, cat: '{cat("Supermercado")}', valor: 10000, div: [{{ cat: '{cat("Supermercado")}', valor: 7000 }}, {{ cat: '{cat("Farmácia")}', valor: 3000 }}], criado: 4 }});
      await lancSave({{ ...b, id: 'c2', tipo: 'despesa', desc: 'Geladeira', data: d, comp: F, conta: null, cartao: 'k1', cat: '{cat("Eletrônicos e informática")}', valor: 30000, tags: [], obs: 'loja X', criado: 5 }});
      await lancSave({{ ...b, id: 'd2', tipo: 'despesa', desc: 'Curso', data: '2026-01-31', comp: '2026-01', conta: '{conta}', cartao: null, cat: '{cat("Farmácia")}', valor: 90000, criado: 6 }});
      await lancSave({{ ...b, id: 'e1', tipo: 'despesa', desc: 'Estorno loja', data: d, comp: F, conta: null, cartao: 'k1', cat: '{cat("Streaming")}', valor: -1500, criado: 7 }});
      await lancSave({{ ...b, id: 't1', tipo: 'transf', desc: 'Guardar', data: d, comp: M, conta: '{conta}', destino: 'x2', cartao: null, cat: null, valor: 10000, criado: 8 }});
    }})()"""); pg.wait_for_timeout(250)
    def abrir(id_, mais=True):
        pg.evaluate(f"abrirLanc({{ edit: acharItem('{id_}') }})"); pg.wait_for_selector("#m-valor"); pg.wait_for_timeout(100)
        if mais and not pg.evaluate("document.querySelector('details.more').open"): pg.click("details.more summary")
    def salvar():
        pg.click("#m-salvar"); pg.wait_for_selector(".mback", state="detached"); pg.wait_for_timeout(200)
    L = lambda id_: pg.evaluate(f"Object.values(S.anos).flat().find(x => x.id === '{id_}')")

    # ---------- compra no cartão vira fixa
    abrir("c1")
    lab = pg.locator('.flab', has_text="Transformar em")
    check("cartão: Transformar em (Não / Fixa / Parcelado)", [lab.is_visible(), pg.locator(REP).all_inner_texts(), pg.locator(f"{REP}.on").inner_text()], [True, ["Não", "Fixa", "Parcelado"], "Não"])
    xs = pg.evaluate("""(() => { const x = s => Math.round(document.querySelector(s).getBoundingClientRect().left);
      const f = [...document.querySelectorAll('details.more .flab')].find(e => e.textContent === 'Tags');
      return [x('details.more .toggle'), Math.round(f.getBoundingClientRect().left), x('#m-obs')]; })()""")
    check("alinhado à esquerda com Tags e Observação", len(set(xs)) == 1, True)
    check("opções escondidas até escolher", [pg.is_visible("#m-cada"), pg.is_visible("#m-n")], [False, False])
    pg.click(rep("fixa")); pg.wait_for_timeout(60)
    h = pg.inner_text("#m-rep-h")
    check("Fixa: repetir a cada e dica", [pg.is_visible("#m-cada"), pg.is_visible("#m-n"), "de todo mês" in h, "no mesmo cartão" in h], [True, False, True, True])
    check("divisão some ao virar fixa", pg.is_hidden("#m-div-w"), True)
    pg.screenshot(path=str(SHOTS/"tf1-cartao-fixa.png"))
    salvar()
    r = pg.evaluate("Object.values(S.cfg.recorr).find(x => x.desc === 'Spotify')")
    l = L("c1")
    check("fixa criada no cartão", [r["cartao"], r["conta"], r["valor"], r["cada"], r["inicio"]], ["k1", None, 2190, 1, pg.evaluate("today().slice(0,7)")])
    check("lançamento ligado à fixa", [bool(l.get("recorr")), l.get("recM")], [True, pg.evaluate("today().slice(0,7)")])
    prox = pg.evaluate("(() => { derivar(); const M = madd(today().slice(0,7), 1); const v = virtuais(M, M).find(x => x.desc === 'Spotify'); return v && [v.cartao, v.comp, v.valor]; })()")
    check("próximo mês aparece como prevista na fatura", prox, ["k1", pg.evaluate("faturaDe(S.cfg.cartoes.k1, diaEm(madd(today().slice(0,7), 1), Number(today().slice(8))))"), 2190])
    check("sem duplicar o mês atual", pg.evaluate("(() => { derivar(); const M = today().slice(0,7); return virtuais(M, M).filter(x => x.desc === 'Spotify').length; })()"), 0)
    check("aviso fixa", pg.inner_text("#toast span"), "Agora é uma fixa: os próximos meses aparecem como pendentes")
    abrir("c1")
    check("já é fixa: sem a opção, mostra o texto da fixa", [pg.locator(REP).count(), "despesa fixa" in pg.text_content("#f-lanc")], [0, True])
    pg.keyboard.press("Escape"); pg.wait_for_timeout(80)

    # ---------- despesa na conta vira fixa a cada 3 meses, valor variável
    abrir("d1"); pg.click(rep("fixa")); pg.select_option("#m-cada", "3"); pg.check("#m-varia"); pg.wait_for_timeout(60)
    check("dica a cada 3 meses", "a cada 3 meses" in pg.inner_text("#m-rep-h"), True)
    salvar()
    r = pg.evaluate("Object.values(S.cfg.recorr).find(x => x.desc === 'Academia')")
    check("fixa da conta a cada 3 meses, valor varia", [r["conta"], r["cartao"], r["cada"], r["varia"]], [conta, None, 3, True])

    # ---------- compra no cartão vira parcelado (3x, valor digitado = parcela)
    abrir("c2"); pg.click(rep("parc")); pg.wait_for_timeout(60)
    check("Parcelado: campos de parcelas", [pg.is_visible("#m-n"), pg.is_visible("#m-pa"), pg.is_visible("#m-cada")], [True, True, False])
    pg.fill("#m-n", "3"); pg.wait_for_timeout(60)
    h = pg.inner_text("#m-rep-h").replace("\xa0", " ")
    check("dica: vira 1/3 e cria 2 e 3 nas faturas seguintes", ["parcela 1/3" in h, "as parcelas 2 a 3 nas faturas seguintes" in h, "total da compra R$ 900,00" in h], [True, True, True])
    check("divisão some ao virar parcelado", pg.is_hidden("#m-div-w"), True)
    pg.screenshot(path=str(SHOTS/"tf2-cartao-parcelado.png"))
    salvar()
    check("aviso parcelado", pg.inner_text("#toast span"), "Agora é parcelado: 3 parcelas a partir desta")
    g = pg.evaluate("(() => { const c = Object.values(S.anos).flat().find(x => x.id === 'c2'); return Object.values(S.anos).flat().filter(x => x.grupo && x.grupo === c.grupo).sort((a, b) => a.parc.i - b.parc.i).map(x => [x.id === 'c2', x.parc.i + '/' + x.parc.n, x.comp, x.valor, x.cartao, x.desc, x.obs]); })()")
    F = L("c2")["comp"]
    check("3 parcelas no mesmo grupo, faturas seguidas", g, [[True, "1/3", F, 30000, "k1", "Geladeira", "loja X"], [False, "2/3", pg.evaluate(f"madd('{F}', 1)"), 30000, "k1", "Geladeira", "loja X"], [False, "3/3", pg.evaluate(f"madd('{F}', 2)"), 30000, "k1", "Geladeira", "loja X"]])
    abrir("c2")
    check("já parcelado: Repetição com Parcelado marcado e Parcela 1 de 3", [pg.locator(REP).all_inner_texts(), pg.locator(f"{REP}.on").inner_text(), "Parcela 1 de 3." in pg.text_content("#f-lanc"), pg.locator('input[name="m-sc"]').count()], [["Única", "Fixa", "Parcelado"], "Parcelado", True, 3])
    pg.keyboard.press("Escape"); pg.wait_for_timeout(80)

    # ---------- despesa na conta vira parcelado: valor digitado é o total, parcela atual 2 de 3
    abrir("d2"); pg.click(rep("parc")); pg.fill("#m-n", "3"); pg.fill("#m-pa", "2"); pg.click('[data-act="m-vale"][data-v="total"]'); pg.wait_for_timeout(60)
    h = pg.inner_text("#m-rep-h").replace("\xa0", " ")
    check("dica: parcela 2/3 de R$ 300,00 e a anterior não é lançada", ["parcela 2/3 de R$ 300,00" in h, "a parcela 3 nos meses seguintes" in h, "A parcela anterior não é lançada" in h], [True, True, True])
    salvar()
    check("aviso: 2 parcelas", pg.inner_text("#toast span"), "Agora é parcelado: 2 parcelas a partir desta")
    g = pg.evaluate("(() => { const c = Object.values(S.anos).flat().find(x => x.id === 'd2'); return Object.values(S.anos).flat().filter(x => x.grupo && x.grupo === c.grupo).sort((a, b) => a.parc.i - b.parc.i).map(x => [x.id === 'd2', x.parc.i + '/' + x.parc.n, x.data, x.comp, x.valor, x.pago]); })()")
    check("conta: esta vira 2/3 (paga), a 3/3 fica pendente no mês seguinte", g, [[True, "2/3", "2026-01-31", "2026-01", 30000, True], [False, "3/3", "2026-02-28", "2026-02", 30000, False]])

    # ---------- sem a opção: dividido, estorno, transferência
    abrir("p1"); check("parcela: Única / Fixa / Parcelado", pg.locator(REP).all_inner_texts(), ["Única", "Fixa", "Parcelado"]); pg.keyboard.press("Escape"); pg.wait_for_timeout(60)
    abrir("s1"); check("dividido: sem a opção", pg.locator(REP).count(), 0); pg.keyboard.press("Escape"); pg.wait_for_timeout(60)
    abrir("e1"); check("estorno: sem a opção", pg.locator(REP).count(), 0); pg.keyboard.press("Escape"); pg.wait_for_timeout(60)
    abrir("t1"); check("transferência: sem a opção", pg.locator(REP).count(), 0); pg.keyboard.press("Escape"); pg.wait_for_timeout(60)
    # estorno marcado na hora de editar + parcelado é recusado
    abrir("c1", mais=False); pg.keyboard.press("Escape"); pg.wait_for_timeout(60)
    pg.evaluate("lancSave({ id: 'c3', tipo: 'despesa', desc: 'Fone', data: today(), comp: faturaDe(S.cfg.cartoes.k1, today()), conta: null, cartao: 'k1', cat: Object.keys(S.cfg.categorias)[0], valor: 5000, pago: true, tags: [], obs: '', criado: 9 })"); pg.wait_for_timeout(150)
    abrir("c3"); pg.check("#m-estorno"); pg.click(rep("parc")); pg.click("#m-salvar"); pg.wait_for_timeout(150)
    check("estorno não vira parcelado", [pg.inner_text("#m-err"), pg.locator(".mback").count()], ["Estorno não pode virar fixa nem parcelado.", 1])
    pg.keyboard.press("Escape"); pg.wait_for_timeout(80)

    pg.evaluate("irPara('config')"); pg.wait_for_timeout(120)
    check("aparece em Fixas cadastradas", [pg.locator(".li", has_text="Spotify").count() > 0, pg.locator(".li", has_text="Academia").count() > 0], [True, True])
    print("erros:", errs); allerr += errs

    # ---------- celular
    pm, em = nova_pagina(b, viewport={"width":390,"height":844}, is_mobile=True, has_touch=True)
    pm.goto("file://"+str(AQUI/"index.html")); pm.wait_for_selector('[data-act="onb-conta"]'); pm.tap('[data-act="onb-conta"]'); pm.wait_for_selector("#o-nome")
    pm.fill("#o-nome","Nubank"); pm.tap('[data-act="onb-criar"]'); pm.wait_for_selector("text=Saldo em contas")
    pm.evaluate("lancSave({ id: 'm1', tipo: 'despesa', desc: 'Notebook', data: today(), comp: today().slice(0,7), conta: Object.keys(S.cfg.contas)[0], cartao: null, cat: Object.keys(S.cfg.categorias)[0], valor: 400000, pago: true, tags: [], obs: '', criado: 1 })"); pm.wait_for_timeout(150)
    pm.evaluate("abrirLanc({ edit: acharItem('m1') })"); pm.wait_for_selector("#m-valor"); pm.wait_for_timeout(100)
    pm.tap("details.more summary"); pm.tap('[data-act="m-rep"][data-v="parc"]'); pm.fill("#m-n", "10"); pm.wait_for_timeout(80)
    pm.locator("#m-rep-h").scroll_into_view_if_needed(); pm.screenshot(path=str(SHOTS/"tf3-celular.png"))
    ov = pm.evaluate("(() => { const m = document.querySelector('.modal') || document.querySelector('.mback'); return [m.scrollWidth <= m.clientWidth + 1, document.documentElement.scrollWidth <= innerWidth]; })()")
    check("celular: sem rolagem lateral", ov, [True, True])
    print("erros:", em); allerr += em
    b.close()
print("RESULTADO:", "TUDO CERTO" if not fails and not allerr else (fails, allerr))
