"""Excluir uma fixa: com todos os lançamentos registrados ou só a fixa (Configurações e janela do lançamento), com Desfazer."""
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
    cat = pg.evaluate("Object.entries(S.cfg.categorias).find(([,c]) => c.nome === 'Atividade física')[0]")
    M = pg.evaluate("today().slice(0,7)")
    def criar(rid, desc, meses, valor=9900):
        pg.evaluate(f"""(async () => {{ const M = today().slice(0,7), ini = madd(M, -2);
          await cfgWrite({{ recorr: {{ {rid}: {{ tipo: 'despesa', desc: '{desc}', valor: {valor}, cat: '{cat}', conta: '{conta}', cartao: null, dia: 5, inicio: ini, fim: null, tags: [], pulos: [], arq: false, criado: 1, cada: 1, varia: false }} }} }});
          await new Promise(r => setTimeout(r, 60));
          for (const o of {json.dumps(meses)}) {{ const k = madd(ini, o); await lancSave({{ id: '{rid}' + o, tipo: 'despesa', desc: '{desc}', data: k + '-05', comp: k, conta: '{conta}', cartao: null, cat: '{cat}', valor: {valor}, pago: true, tags: [], obs: '', recorr: '{rid}', recM: k, criado: 10 + o }}); }}
        }})()"""); pg.wait_for_timeout(250)
    regs = lambda rid: pg.evaluate(f"Object.values(S.anos).flat().filter(x => x.recorr === '{rid}').length")
    prev = lambda rid: pg.evaluate(f"(() => {{ derivar(); const M = madd(today().slice(0,7), 1); return virtuais(M, M).filter(x => x.recorr === '{rid}').length; }})()")
    arq = lambda rid: pg.evaluate(f"!!S.cfg.recorr['{rid}'].arq")
    def config():
        pg.evaluate("irPara('config')"); pg.wait_for_timeout(150)
    criar("rA", "Academia", [0, 1, 2])
    check("início: 3 registrados e previsão no mês seguinte", [regs("rA"), prev("rA")], [3, 1])

    # ---------- Configurações › Editar fixa › Excluir (com os lançamentos)
    config(); pg.locator(".li", has_text="Academia").locator('[data-act="fixa-editar"]').click(); pg.wait_for_selector("#f-fixa")
    check("rodapé: Excluir e Encerrar", pg.locator(".mfoot .btn").all_inner_texts()[:2], ["Excluir", "Encerrar"])
    pg.click('.mfoot [data-act="fixa-excluir"]'); pg.wait_for_timeout(80)
    t = pg.inner_text("#m-confirm").replace("\xa0", " ")
    check("confirmação mostra os registrados", ["3 lançamentos registrados" in t, f"{pg.evaluate(f'mesCurto(madd(\"{M}\", -2))')} a {pg.evaluate(f'mesCurto(\"{M}\")')}" in t, "R$ 297,00" in t], [True, True, True])
    check("botões", pg.locator("#m-confirm .btn").all_inner_texts(), ["Excluir a fixa e os 3 lançamentos", "Só a fixa (manter os lançamentos)", "Cancelar"])
    pg.screenshot(path=str(SHOTS/"xf1-confirmacao.png"))
    pg.click('#m-confirm [data-act="m-del-cancel"]'); pg.wait_for_timeout(60)
    check("Cancelar fecha a confirmação", pg.inner_text("#m-confirm"), "")
    pg.click('.mfoot [data-act="fixa-excluir"]'); pg.click('[data-act="fixa-del"][data-v="tudo"]'); pg.wait_for_selector(".mback", state="detached"); pg.wait_for_timeout(250)
    check("aviso", pg.inner_text("#toast span"), "Fixa excluída com 3 lançamentos")
    check("apagou tudo", [regs("rA"), prev("rA"), arq("rA"), pg.locator(".li", has_text="Academia").count()], [0, 0, True, 0])
    pg.click('[data-act="toast-acao"]'); pg.wait_for_timeout(350)
    check("Desfazer devolve fixa e lançamentos", [regs("rA"), prev("rA"), arq("rA"), pg.locator(".li", has_text="Academia").count()], [3, 1, False, 1])

    # ---------- só a fixa
    pg.locator(".li", has_text="Academia").locator('[data-act="fixa-editar"]').click(); pg.wait_for_selector("#f-fixa")
    pg.click('.mfoot [data-act="fixa-excluir"]'); pg.click('[data-act="fixa-del"][data-v="so"]'); pg.wait_for_selector(".mback", state="detached"); pg.wait_for_timeout(250)
    check("só a fixa: lançamentos mantidos", [pg.inner_text("#toast span"), regs("rA"), prev("rA"), arq("rA")], ["Fixa excluída. Os lançamentos registrados foram mantidos", 3, 0, True])

    # ---------- janela do lançamento: Excluir a fixa inteira
    criar("rB", "Pilates", [0, 1, 2])
    pg.evaluate("abrirLanc({ edit: acharItem('rB2') })"); pg.wait_for_selector("#m-valor"); pg.wait_for_timeout(100)
    pg.click('[data-act="m-excluir"]'); pg.wait_for_timeout(80)
    check("lançamento: três opções", pg.locator("#m-confirm .btn").all_inner_texts(), ["Só este mês", "Excluir e encerrar a fixa", "Excluir a fixa inteira (3 lançamentos)", "Cancelar"])
    pg.screenshot(path=str(SHOTS/"xf2-lancamento.png"))
    pg.click('[data-act="m-del"][data-sc="fixa"]'); pg.wait_for_selector(".mback", state="detached"); pg.wait_for_timeout(250)
    check("fixa inteira apagada pelo lançamento", [pg.inner_text("#toast span"), regs("rB"), prev("rB"), arq("rB")], ["Fixa excluída com 3 lançamentos", 0, 0, True])

    # ---------- prevista (pendente): Excluir a fixa inteira
    criar("rC", "Natação", [0])
    pg.evaluate("(() => { derivar(); const M = madd(today().slice(0,7), 1); const v = virtuais(M, M).find(x => x.recorr === 'rC'); abrirLanc({ edit: v }); })()"); pg.wait_for_selector("#m-valor"); pg.wait_for_timeout(100)
    pg.click('[data-act="m-excluir"]'); pg.wait_for_timeout(80)
    check("pendente: opção da fixa inteira", pg.locator("#m-confirm .btn").all_inner_texts(), ["Pular este mês", "Encerrar a fixa", "Excluir a fixa inteira (1 lançamento)"])
    pg.click('[data-act="m-del"][data-sc="fixa"]'); pg.wait_for_selector(".mback", state="detached"); pg.wait_for_timeout(250)
    check("pendente: fixa e registro apagados", [regs("rC"), prev("rC"), arq("rC")], [0, 0, True])

    # ---------- fixa encerrada: Excluir da lista abre a confirmação; fixa sem registros
    criar("rD", "Anuidade teste", [])
    pg.evaluate("cfgWrite({ recorr: { rD: { fim: today().slice(0,7) } } })"); pg.wait_for_timeout(150)
    config()
    row = pg.locator(".li", has_text="Anuidade teste")
    check("encerrada: botão Excluir na lista", row.locator('[data-act="fixa-excluir"]').inner_text(), "Excluir")
    row.locator('[data-act="fixa-excluir"]').click(); pg.wait_for_selector("#f-fixa"); pg.wait_for_timeout(80)
    check("abre a janela já com a confirmação, sem Encerrar", ["ainda não tem lançamentos registrados" in pg.inner_text("#m-confirm"), pg.locator("#m-confirm .btn").all_inner_texts(), pg.locator('.mfoot [data-act="fixa-encerrar"]').count()], [True, ["Excluir a fixa", "Cancelar"], 0])
    pg.click('[data-act="fixa-del"]'); pg.wait_for_selector(".mback", state="detached"); pg.wait_for_timeout(200)
    check("fixa sem registros excluída", [pg.inner_text("#toast span"), arq("rD"), pg.locator(".li", has_text="Anuidade teste").count()], ["Fixa excluída", True, 0])

    # ---------- Encerrar continua funcionando
    criar("rE", "Faxina", [2])
    config(); pg.locator(".li", has_text="Faxina").locator('[data-act="fixa-encerrar"]').click(); pg.wait_for_timeout(200)
    check("Encerrar na lista", [pg.inner_text("#toast span"), pg.evaluate("S.cfg.recorr.rE.fim"), prev("rE"), regs("rE")], ["Fixa encerrada neste mês", M, 0, 1])
    print("erros:", errs)

    pm, em = nova_pagina(b, viewport={"width":390,"height":844}, is_mobile=True, has_touch=True)
    pm.goto("file://"+str(AQUI/"index.html")); pm.wait_for_selector('[data-act="onb-conta"]'); pm.tap('[data-act="onb-conta"]'); pm.wait_for_selector("#o-nome")
    pm.fill("#o-nome","Nubank"); pm.tap('[data-act="onb-criar"]'); pm.wait_for_selector("text=Saldo em contas")
    pg = pm; conta = pm.evaluate("Object.keys(S.cfg.contas)[0]"); cat = pm.evaluate("Object.keys(S.cfg.categorias)[0]")
    criar("rM", "Academia", [0, 1, 2])
    pm.evaluate("abrirFixa('rM')"); pm.wait_for_selector("#f-fixa"); pm.tap('.mfoot [data-act="fixa-excluir"]'); pm.wait_for_timeout(120)
    pm.screenshot(path=str(SHOTS/"xf3-celular.png"))
    check("celular: sem rolagem lateral", pm.evaluate("(() => { const m = document.querySelector('.modal'); return [m.scrollWidth <= m.clientWidth + 1, document.documentElement.scrollWidth <= innerWidth]; })()"), [True, True])
    print("erros:", em); b.close()
print("RESULTADO:", "TUDO CERTO" if not fails and not errs and not em else (fails, errs, em))
