"""Campo de data DD/MM/AAAA (máscara, validação, calendário) e editar conta pelo saldo atual."""
import pathlib, json
from playwright.sync_api import sync_playwright
AQUI = pathlib.Path(__file__).resolve().parent; RAIZ = AQUI.parents[1]
src = open(AQUI/"run.py").read()
exec(src[:src.index("\nwith sync_playwright() as p:")])
fails=[]
def check(l,g,e):
    ok=g==e; print(("OK  " if ok else "FALHA ")+f"{l}: {g!r}"+("" if ok else f" (esperado {e!r})"))
    if not ok: fails.append(l)
BR = lambda iso: "/".join(reversed(iso.split("-")))
with sync_playwright() as p:
    b = p.chromium.launch()
    pg, errs = nova_pagina(b, viewport={"width":1280,"height":900}, locale="en-US")
    pg.goto("file://"+str(AQUI/"index.html")); pg.wait_for_selector('[data-act="onb-conta"]'); pg.click('[data-act="onb-conta"]'); pg.wait_for_selector("#o-nome")
    pg.fill("#o-nome","Nubank"); pg.click('[data-act="onb-criar"]'); pg.wait_for_selector("text=Saldo em contas")
    conta = pg.evaluate("Object.keys(S.cfg.contas)[0]")
    H = pg.evaluate("today()")
    pg.evaluate("abrirLanc({ tipo: 'despesa' })"); pg.wait_for_selector("#m-data-txt"); pg.wait_for_timeout(100)
    check("abre com hoje em DD/MM/AAAA (navegador em inglês)", [pg.input_value("#m-data-txt"), pg.evaluate("$('#m-data').value"), pg.get_attribute("#m-data-txt", "placeholder")], [BR(H), H, "DD/MM/AAAA"])
    check("chip Hoje marcado", pg.locator('[data-act="m-data"].on').inner_text(), "Hoje")
    # digitação com máscara
    pg.fill("#m-data-txt", ""); pg.type("#m-data-txt", "05032026", delay=10)
    check("máscara: 05032026 → 05/03/2026", [pg.input_value("#m-data-txt"), pg.evaluate("$('#m-data').value")], ["05/03/2026", "2026-03-05"])
    check("chips desmarcados", pg.locator('[data-act="m-data"].on').count(), 0)
    pg.fill("#m-data-txt", ""); pg.type("#m-data-txt", "5/3/2026", delay=10)
    check("aceita 5/3/2026", pg.input_value("#m-data-txt"), "05/03/2026")
    pg.fill("#m-data-txt", ""); pg.type("#m-data-txt", "31022026", delay=10)
    check("31/02 inválido: borda vermelha e valor vazio", [pg.evaluate("$('#m-data-txt').classList.contains('bad')"), pg.evaluate("$('#m-data').value")], [True, ""])
    pg.screenshot(path=str(SHOTS/"dt1-invalida.png"))
    money(pg, "#m-valor", "1000"); pg.select_option("#m-cat", index=1)
    pg.click("#m-salvar"); pg.wait_for_timeout(120)
    check("não salva com data inválida", [pg.inner_text("#m-err"), pg.evaluate("document.activeElement.id")], ["Data inválida: use DD/MM/AAAA.", "m-data-txt"])
    # apagar com backspace não trava na barra
    pg.fill("#m-data-txt", ""); pg.type("#m-data-txt", "12", delay=10)
    check("barra automática depois do dia", pg.input_value("#m-data-txt"), "12/")
    pg.keyboard.press("Backspace"); check("Backspace remove a barra", pg.input_value("#m-data-txt"), "12")
    # chip Ontem
    pg.click('[data-act="m-data"][data-v="ontem"]'); pg.wait_for_timeout(60)
    check("chip Ontem preenche o texto", [pg.input_value("#m-data-txt"), pg.evaluate("$('#m-data').value === dadd2(today(), -1)")], [BR(pg.evaluate("dadd2(today(), -1)")), True])
    # calendário
    pg.click('[data-act="dt-cal"][data-for="m-data"]'); pg.wait_for_selector("#menu.dpick")
    check("calendário: mês, semana e dia marcado", [pg.inner_text(".dp-tit").lower(), pg.locator(".dp-sem").all_inner_texts(), pg.locator(".dp-dias button.on").inner_text(), pg.evaluate("document.activeElement.dataset.d === dadd2(today(), -1)")],
          [pg.evaluate("mesLongo(dadd2(today(), -1).slice(0,7))").lower(), ["D", "S", "T", "Q", "Q", "S", "S"], str(int(pg.evaluate("dadd2(today(), -1)")[8:])), True])
    check("calendário acima da janela", pg.evaluate("+getComputedStyle(document.querySelector('#menu')).zIndex > +getComputedStyle(document.querySelector('.mback')).zIndex"), True)
    pg.screenshot(path=str(SHOTS/"dt2-calendario.png"))
    pg.click('[data-act="dp-mes"][data-d="1"]'); pg.wait_for_timeout(60)
    alvo = pg.evaluate("madd(dadd2(today(), -1).slice(0,7), 1) + '-15'")
    check("trocar de mês não fecha", [pg.locator("#menu.dpick").count(), pg.inner_text(".dp-tit").lower()], [1, pg.evaluate(f"mesLongo('{alvo[:7]}')").lower()])
    pg.click(f'[data-act="dp-dia"][data-d="{alvo}"]'); pg.wait_for_timeout(80)
    check("escolher o dia preenche e fecha", [pg.input_value("#m-data-txt"), pg.evaluate("$('#m-data').value"), pg.locator("#menu").count(), pg.evaluate("document.activeElement.id")], [BR(alvo), alvo, 0, "m-data-txt"])
    # teclado no calendário + Escape não fecha a janela
    pg.click('[data-act="dt-cal"][data-for="m-data"]'); pg.wait_for_selector("#menu.dpick"); pg.wait_for_timeout(50)
    pg.keyboard.press("ArrowRight"); pg.keyboard.press("ArrowDown")
    check("setas andam pelos dias", pg.evaluate("document.activeElement.dataset.d"), pg.evaluate(f"dadd2('{alvo}', 8)"))
    pg.keyboard.press("Escape"); pg.wait_for_timeout(60)
    check("Escape fecha só o calendário", [pg.locator("#menu").count(), pg.locator(".mback").count(), pg.input_value("#m-data-txt")], [0, 1, BR(alvo)])
    pg.click('[data-act="dt-cal"][data-for="m-data"]'); pg.wait_for_selector("#menu.dpick"); pg.click('[data-act="dp-hoje"]'); pg.wait_for_timeout(60)
    check("Hoje no calendário", pg.input_value("#m-data-txt"), BR(H))
    # salva com a data digitada
    pg.fill("#m-data-txt", ""); pg.type("#m-data-txt", "10092026", delay=10); pg.fill("#m-desc", "Teste data")
    pg.click("#m-salvar"); pg.wait_for_selector(".mback", state="detached"); pg.wait_for_timeout(200)
    l = pg.evaluate("Object.values(S.anos).flat().find(x => x.desc === 'Teste data')")
    check("salvou com a data digitada", [l["data"], l["comp"]], ["2026-09-10", "2026-09"])
    pg.evaluate("abrirLanc({ edit: Object.values(S.anos).flat().find(x => x.desc === 'Teste data') })"); pg.wait_for_selector("#m-data-txt"); pg.wait_for_timeout(80)
    check("editar mostra DD/MM/AAAA", pg.input_value("#m-data-txt"), "10/09/2026")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(60)

    # ---------- editar conta pelo saldo atual
    pg.evaluate(f"""(async () => {{ await cfgWrite({{ contas: {{ '{conta}': {{ inicial: 100000 }} }} }}); await new Promise(r => setTimeout(r, 60));
      await lancSave({{ id: 'r1', tipo: 'receita', desc: 'Salário', data: today(), comp: today().slice(0,7), conta: '{conta}', cartao: null, cat: Object.keys(S.cfg.categorias)[0], valor: 50000, pago: true, tags: [], obs: '', criado: 1 }});
      await lancSave({{ id: 'p1', tipo: 'despesa', desc: 'Conta futura', data: today(), comp: today().slice(0,7), conta: '{conta}', cartao: null, cat: Object.keys(S.cfg.categorias)[0], valor: 30000, pago: false, tags: [], obs: '', criado: 2 }}); }})()"""); pg.wait_for_timeout(250)
    atual = pg.evaluate(f"saldoAtual('{conta}')")
    pg.evaluate(f"abrirConta('{conta}')"); pg.wait_for_selector("#c-ini"); pg.wait_for_timeout(80)
    check("Editar conta: campo Saldo atual com o saldo de hoje", [pg.inner_text('label[for="c-ini"]'), pg.input_value("#c-ini").replace("\xa0", " ")], ["Saldo atual", pg.evaluate(f"fmtR({atual})").replace("\xa0", " ")])
    check("dica sem mudança", "a diferença vai para o saldo inicial" in pg.inner_text("#c-ini-h"), True)
    money(pg, "#c-ini", "200000"); pg.wait_for_timeout(60)
    h = pg.inner_text("#c-ini-h").replace("\xa0", " ")
    novo_ini = 100000 + 200000 - atual
    check("dica com a mudança", [f"passa de R$ 1.000,00 para {pg.evaluate(f'fmt({novo_ini})')}".replace("\xa0", " ") in h, pg.evaluate(f"fmtS({novo_ini - 100000})").replace("\xa0", " ") in h], [True, True])
    pg.screenshot(path=str(SHOTS/"dt3-conta.png"))
    pg.click('[data-act="conta-salvar"]'); pg.wait_for_selector(".mback", state="detached"); pg.wait_for_timeout(200)
    check("saldo atual vira o digitado; inicial ajustado", [pg.evaluate(f"saldoAtual('{conta}')"), pg.evaluate(f"S.cfg.contas['{conta}'].inicial")], [200000, novo_ini])
    pg.evaluate(f"abrirConta('{conta}')"); pg.wait_for_selector("#c-ini"); pg.fill("#c-nome", "Nubank PJ"); pg.click('[data-act="conta-salvar"]'); pg.wait_for_selector(".mback", state="detached"); pg.wait_for_timeout(200)
    check("salvar sem mexer no saldo mantém o inicial", [pg.evaluate(f"S.cfg.contas['{conta}'].inicial"), pg.evaluate(f"S.cfg.contas['{conta}'].nome")], [novo_ini, "Nubank PJ"])
    pg.evaluate("abrirConta()"); pg.wait_for_selector("#c-ini"); pg.wait_for_timeout(60)
    check("nova conta continua com Saldo inicial", [pg.inner_text('label[for="c-ini"]'), pg.locator("#c-ini-h").count()], ["Saldo inicial", 0])
    pg.keyboard.press("Escape")
    print("erros:", errs)

    # ---------- celular: calendário cabe na tela
    pm, em = nova_pagina(b, viewport={"width":390,"height":844}, is_mobile=True, has_touch=True)
    pm.goto("file://"+str(AQUI/"index.html")); pm.wait_for_selector('[data-act="onb-conta"]'); pm.tap('[data-act="onb-conta"]'); pm.wait_for_selector("#o-nome")
    pm.fill("#o-nome","Nubank"); pm.tap('[data-act="onb-criar"]'); pm.wait_for_selector("text=Saldo em contas")
    pm.evaluate("abrirLanc({ tipo: 'despesa' })"); pm.wait_for_selector("#m-data-txt"); pm.wait_for_timeout(150)
    pm.tap('[data-act="dt-cal"][data-for="m-data"]'); pm.wait_for_selector("#menu.dpick"); pm.wait_for_timeout(80)
    r = pm.evaluate("(() => { const r = document.querySelector('#menu').getBoundingClientRect(); return [r.left >= 0, r.right <= innerWidth, r.top >= 0, r.bottom <= innerHeight]; })()")
    check("celular: calendário dentro da tela", r, [True, True, True, True])
    pm.screenshot(path=str(SHOTS/"dt4-celular.png"))
    pm.tap('.dp-dias button:not(.fora) >> nth=9'); pm.wait_for_timeout(80)
    check("celular: toque escolhe o dia", [pm.locator("#menu").count(), pm.evaluate("/^\\d{4}-\\d{2}-10$/.test($('#m-data').value)")], [0, True])
    print("erros:", em); b.close()
print("RESULTADO:", "TUDO CERTO" if not fails and not errs and not em else (fails, errs, em))
