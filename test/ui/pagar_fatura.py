"""Pagar fatura: desconta da conta do cartão na hora, com Desfazer; outro valor ou conta pela janela."""
import pathlib, json
from playwright.sync_api import sync_playwright
AQUI = pathlib.Path(__file__).resolve().parent; RAIZ = AQUI.parents[1]
src = open(AQUI/"run.py").read()
exec(src[:src.index("\nwith sync_playwright() as p:")])
fails=[]
def check(l,g,e):
    ok=g==e; print(("OK  " if ok else "FALHA ")+f"{l}: {g!r}"+("" if ok else f" (esperado {e!r})"))
    if not ok: fails.append(l)
with sync_playwright() as p:
    b = p.chromium.launch()
    pg, errs = nova_pagina(b, viewport={"width":1280,"height":900})
    pg.goto("file://"+str(AQUI/"index.html")); pg.wait_for_selector('[data-act="onb-conta"]'); pg.click('[data-act="onb-conta"]'); pg.wait_for_selector("#o-nome")
    pg.fill("#o-nome","Nubank"); pg.click('[data-act="onb-criar"]'); pg.wait_for_selector("text=Saldo em contas")
    conta = pg.evaluate("Object.keys(S.cfg.contas)[0]")
    cat = pg.evaluate("Object.entries(S.cfg.categorias).find(([,c]) => c.nome === 'Supermercado')[0]")
    pg.evaluate(f"""(async () => {{
      await cfgWrite({{ contas: {{ '{conta}': {{ ...S.cfg.contas['{conta}'], inicial: 100000 }}, a2: {{ nome: 'Inter', tipo: 'corrente', inicial: 50000, cor: '#D95926', total: true, arq: false, ordem: 1 }} }},
        cartoes: {{ k1: {{ nome: 'Roxo', fech: 25, venc: 5, limite: 300000, conta: '{conta}', cor: '#9085E9', arq: false }}, k2: {{ nome: 'Sem conta', fech: 25, venc: 5, limite: 100000, conta: 'apagada', cor: '#C2477A', arq: false }} }} }});
      await new Promise(r => setTimeout(r, 60));
      const F = faturaDe(S.cfg.cartoes.k1, today());
      for (const [i, v] of [[1, 20000], [2, 10998]]) await lancSave({{ id: 'c' + i, tipo: 'despesa', desc: 'Compra ' + i, data: today(), comp: F, conta: null, cartao: 'k1', cat: '{cat}', valor: v, pago: true, tags: [], obs: '', criado: i }});
      await lancSave({{ id: 'z1', tipo: 'despesa', desc: 'Compra sem conta', data: today(), comp: F, conta: null, cartao: 'k2', cat: '{cat}', valor: 5000, pago: true, tags: [], obs: '', criado: 9 }});
    }})()"""); pg.wait_for_timeout(250)
    F = pg.evaluate("faturaDe(S.cfg.cartoes.k1, today())")
    saldo = lambda: pg.evaluate(f"(derivar(), saldoAtual('{conta}'))")
    pags = lambda c="k1": pg.evaluate(f"Object.values(S.anos).flat().filter(l => l.tipo === 'transf' && l.destino === '{c}').map(l => [l.conta, l.valor, l.pago, l.fatPag, l.data, l.desc])")
    def ir_fatura(c="k1"):
        pg.evaluate(f"S.cartaoSel = '{c}'; S.mes = '{F}'; irPara('cartoes')"); pg.wait_for_timeout(150)
    s0 = saldo()
    ir_fatura()
    check("botões da fatura", [t.replace("\xa0", " ") for t in pg.locator('.panel [data-act^="pagar-fatura"]').all_inner_texts()], ["Pagar R$ 309,98", "Outro valor ou conta"])
    check("dica do botão diz de onde sai", pg.get_attribute('[data-act="pagar-fatura"]', "title"), "Desconta de Nubank hoje")
    pg.click('.btn.pri[data-act="pagar-fatura"]'); pg.wait_for_timeout(250)
    check("não abre janela", pg.locator(".mback").count(), 0)
    check("aviso", pg.inner_text("#toast span").replace("\xa0", " "), f"Fatura de {pg.evaluate(f'mesCurto(\"{F}\")')} paga: R$ 309,98 saiu de Nubank")
    check("pagamento lançado da conta do cartão", pags(), [[conta, 30998, True, F, pg.evaluate("today()"), "Pagamento fatura Roxo"]])
    check("saldo da conta desconta o valor", saldo(), s0 - 30998)
    check("fatura paga e botão some", [pg.evaluate(f"(derivar(), fatura('k1', '{F}').status)"), pg.locator('[data-act="pagar-fatura"]').count()], ["paga", 0])
    pg.screenshot(path=str(SHOTS/"pf1-paga.png"))
    pg.click('[data-act="toast-acao"]'); pg.wait_for_timeout(250)
    check("Desfazer apaga o pagamento", [pags(), saldo(), pg.locator('[data-act="pagar-fatura"]').count()], [[], s0, 1])

    # outro valor ou conta: abre a janela de transferência preenchida
    pg.click('[data-act="pagar-fatura-form"]'); pg.wait_for_selector("#m-valor"); pg.wait_for_timeout(100)
    check("janela preenchida", [pg.input_value("#m-valor").replace("\xa0", " "), pg.input_value("#m-de"), pg.input_value("#m-para"), "Paga a fatura de" in pg.inner_text("#m-fatpag-l")], ["R$ 309,98", conta, "k1", True])
    pg.fill("#m-valor", ""); money(pg, "#m-valor", "10000"); pg.select_option("#m-de", "a2"); pg.click("#m-salvar"); pg.wait_for_selector(".mback", state="detached"); pg.wait_for_timeout(200)
    check("pagamento parcial de outra conta", pags(), [["a2", 10000, True, F, pg.evaluate("today()"), "Pagamento fatura Roxo"]])
    check("botão mostra o restante", pg.inner_text('.btn.pri[data-act="pagar-fatura"]').replace("\xa0", " "), "Pagar R$ 209,98")
    pg.click('.btn.pri[data-act="pagar-fatura"]'); pg.wait_for_timeout(250)
    check("pagar o restante pela conta do cartão", sorted(pags()), sorted([["a2", 10000, True, F, pg.evaluate("today()"), "Pagamento fatura Roxo"], [conta, 20998, True, F, pg.evaluate("today()"), "Pagamento fatura Roxo"]]))
    pg.click('[data-act="toast-acao"]'); pg.wait_for_timeout(250)

    # pagamento agendado (pendente): confirma ele e lança só o que falta
    pg.evaluate(f"lancSave({{ id: 'ag1', tipo: 'transf', desc: 'Pagamento agendado', data: dadd2(today(), 3), comp: mk(dadd2(today(), 3)), conta: '{conta}', destino: 'k1', fatPag: '{F}', cat: null, cartao: null, valor: 15000, pago: false, tags: [], obs: '', criado: 20 }})"); pg.wait_for_timeout(200)
    ir_fatura(); pg.click('.btn.pri[data-act="pagar-fatura"]'); pg.wait_for_timeout(300)
    d = {x[5]: x for x in pags()}
    check("agendado confirmado + restante lançado", [d["Pagamento agendado"][2], d["Pagamento agendado"][1], d["Pagamento fatura Roxo"][1] if "Pagamento fatura Roxo" in d else None, sum(x[1] for x in pags() if x[0] == conta)], [True, 15000, 309_98 - 10000 - 15000, 309_98 - 10000])
    check("fatura paga", pg.evaluate(f"(derivar(), fatura('k1', '{F}').status)"), "paga")
    pg.click('[data-act="toast-acao"]'); pg.wait_for_timeout(300)
    d = {x[5]: x for x in pags()}
    check("Desfazer volta o agendado para pendente", [d["Pagamento agendado"][2], any(x[0] == conta and x[5] == "Pagamento fatura Roxo" for x in pags())], [False, False])

    # cartão sem conta de pagamento válida: abre a janela para escolher
    ir_fatura("k2"); pg.click('.btn.pri[data-act="pagar-fatura"]'); pg.wait_for_selector("#m-valor"); pg.wait_for_timeout(100)
    check("sem conta: abre a janela e avisa", [pg.locator(".mback").count(), pg.inner_text("#toast span"), pg.input_value("#m-para")], [1, "Escolha a conta: Sem conta não tem conta de pagamento definida", "k2"])
    pg.keyboard.press("Escape"); pg.wait_for_timeout(80)
    # Visão geral: botão Pagar das faturas a pagar também desconta direto
    pg.evaluate(f"S.mes = '{F}'; irPara('geral')"); pg.wait_for_timeout(150)
    bt = pg.locator('[data-act="pagar-fatura"][data-id="k1"]')
    if bt.count():
        bt.first.click(); pg.wait_for_timeout(250)
        check("Visão geral: Pagar desconta direto", [pg.locator(".mback").count(), any(x[0] == conta and x[5] == "Pagamento fatura Roxo" for x in pags())], [0, True])
    else:
        print("(fatura do k1 não aparece em A pagar neste dia do mês)")
    print("erros:", errs); b.close()
print("RESULTADO:", "TUDO CERTO" if not fails and not errs else (fails, errs))
