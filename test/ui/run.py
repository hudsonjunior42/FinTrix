"""Fluxo principal do FinTrix com banco simulado (fakedb.js): lançamentos, saldos, faturas e capturas de tela.
Os outros testes desta pasta reaproveitam o começo deste arquivo (até o bloco "with sync_playwright()")."""
import json, sys, pathlib
from playwright.sync_api import sync_playwright

AQUI = pathlib.Path(__file__).resolve().parent; RAIZ = AQUI.parents[1]
FONTS = AQUI/"fonts/node_modules"
SHOTS = AQUI/"shots"; SHOTS.mkdir(exist_ok=True)
# a página de teste é uma cópia do index.html da raiz do repositório (o app inteiro, num arquivo só)
(AQUI/"index.html").write_text((RAIZ / "index.html").read_text())

FONT_FILES = {
    "plex400": FONTS / "@fontsource/ibm-plex-sans/files/ibm-plex-sans-latin-400-normal.woff2",
    "plex500": FONTS / "@fontsource/ibm-plex-sans/files/ibm-plex-sans-latin-500-normal.woff2",
    "plex600": FONTS / "@fontsource/ibm-plex-sans/files/ibm-plex-sans-latin-600-normal.woff2",
    "mono400": FONTS / "@fontsource/ibm-plex-mono/files/ibm-plex-mono-latin-400-normal.woff2",
    "mono500": FONTS / "@fontsource/ibm-plex-mono/files/ibm-plex-mono-latin-500-normal.woff2",
    "bric": FONTS / "@fontsource-variable/bricolage-grotesque/files/bricolage-grotesque-latin-wght-normal.woff2",
}
CSS = "".join([
    "@font-face{font-family:'IBM Plex Sans';font-weight:400;src:url(https://fonts.gstatic.com/x/plex400.woff2)}",
    "@font-face{font-family:'IBM Plex Sans';font-weight:500;src:url(https://fonts.gstatic.com/x/plex500.woff2)}",
    "@font-face{font-family:'IBM Plex Sans';font-weight:600 700;src:url(https://fonts.gstatic.com/x/plex600.woff2)}",
    "@font-face{font-family:'IBM Plex Mono';font-weight:400;src:url(https://fonts.gstatic.com/x/mono400.woff2)}",
    "@font-face{font-family:'IBM Plex Mono';font-weight:500;src:url(https://fonts.gstatic.com/x/mono500.woff2)}",
    "@font-face{font-family:'Bricolage Grotesque';font-weight:200 800;src:url(https://fonts.gstatic.com/x/bric.woff2)}",
])

fails = []
def check(label, got, exp):
    ok = got == exp
    print(("OK  " if ok else "FALHA ") + f"{label}: {got!r}" + ("" if ok else f" (esperado {exp!r})"))
    if not ok:
        fails.append(label)

def route_fonts(page):
    # sem as fontes instaladas (test/ui/fonts), o CSS vem vazio e o app usa as fontes do sistema, sem pedir nada à rede
    css = CSS if all(f.exists() for f in FONT_FILES.values()) else ""
    page.route("https://fonts.googleapis.com/**", lambda r: r.fulfill(status=200, content_type="text/css", body=css))
    def gstatic(r):
        name = r.request.url.rsplit("/", 1)[-1].replace(".woff2", "")
        f = FONT_FILES.get(name)
        r.fulfill(status=200, content_type="font/woff2", body=f.read_bytes()) if f and f.exists() else r.abort()
    page.route("https://fonts.gstatic.com/**", gstatic)

def nova_pagina(b, **kw):
    kw.setdefault("reduced_motion", "reduce")  # a animação de abertura tem teste próprio
    pg = b.new_page(**kw)
    errs = []
    pg.on("pageerror", lambda e: errs.append("pageerror: " + str(e)))
    pg.on("console", lambda m: errs.append("console: " + m.text) if m.type == "error" else None)
    route_fonts(pg)
    pg.add_init_script(path=str(AQUI/"fakedb.js"))
    return pg, errs

def money(pg, sel, digits):
    pg.focus(sel); pg.wait_for_timeout(30); pg.keyboard.type(digits)

def ev(pg, js):
    return pg.evaluate(js)

with sync_playwright() as p:
    b = p.chromium.launch()
    pg, errs = nova_pagina(b, viewport={"width": 1366, "height": 880}, color_scheme="dark")
    pg.goto("file://" + str(AQUI/"index.html"))
    pg.wait_for_selector('[data-act="onb-conta"]'); pg.click('[data-act="onb-conta"]'); pg.wait_for_selector("#o-nome")
    pg.screenshot(path=str(SHOTS / "00-onboarding.png"))
    pg.fill("#o-nome", "Nubank")
    money(pg, "#o-saldo", "150000")
    check("valor digitado no onboarding", pg.input_value("#o-saldo").replace("\xa0", " "), "R$ 1.500,00")
    pg.click('[data-act="onb-criar"]')
    pg.wait_for_selector("text=Saldo em contas")

    # segunda conta
    pg.click('.side [data-view="contas"]'); pg.click('text=Nova conta'); pg.wait_for_timeout(120)
    pg.fill("#c-nome", "Carteira"); pg.select_option("#c-tipo", "carteira"); money(pg, "#c-ini", "10000")
    pg.keyboard.press("Enter"); pg.wait_for_selector(".mback", state="detached")
    # cartão
    pg.click('.side [data-view="cartoes"]'); pg.click('text=Adicionar cartão'); pg.wait_for_timeout(120)
    pg.fill("#k-nome", "Roxinho"); money(pg, "#k-lim", "300000"); pg.fill("#k-fech", "3"); pg.fill("#k-venc", "10")
    pg.click('[data-act="cartao-salvar"]'); pg.wait_for_selector(".mback", state="detached")
    pg.click('.side [data-view="geral"]')

    # despesa (tecla D)
    pg.click("#title"); pg.keyboard.press("d"); pg.wait_for_selector("#m-valor:focus")
    pg.keyboard.type("25990"); pg.fill("#m-desc", "Supermercado"); pg.select_option("#m-cat", label="Supermercado")
    pg.screenshot(path=str(SHOTS / "10-janela-despesa.png"))
    pg.press("#m-cat", "Enter"); pg.wait_for_selector(".mback", state="detached")
    # receita (tecla R)
    pg.keyboard.press("r"); pg.wait_for_selector("#m-valor:focus")
    pg.keyboard.type("320000"); pg.fill("#m-desc", "Salário"); pg.select_option("#m-cat", label="Salário")
    pg.press("#m-desc", "Enter"); pg.wait_for_selector(".mback", state="detached")
    # cartão parcelado 3x pelo total (tecla C)
    pg.keyboard.press("c"); pg.wait_for_selector("#m-valor:focus")
    pg.keyboard.type("100000"); pg.fill("#m-desc", "Cadeira"); pg.select_option("#m-cat", label="Casa e decoração")
    pg.click("details.more summary"); pg.click('[data-act="m-rep"][data-v="parc"]'); pg.fill("#m-n", "3"); pg.click('[data-act="m-vale"][data-v="total"]')
    hint = pg.inner_text("#m-rep-h").replace("\xa0", " ")
    print("dica parcelas:", hint)
    check("fatura sugerida", pg.inner_text("#m-fat-l").split("·")[0].strip().lower(), "entra na fatura de novembro 2026")
    pg.screenshot(path=str(SHOTS / "11-janela-cartao.png"))
    pg.click("#m-salvar"); pg.wait_for_selector(".mback", state="detached")
    # transferência (tecla T)
    pg.keyboard.press("t"); pg.wait_for_selector("#m-valor:focus")
    pg.keyboard.type("20000")
    check("para padrão", pg.eval_on_selector("#m-para", "e => e.options[e.selectedIndex].text"), "Carteira")
    pg.screenshot(path=str(SHOTS / "12-janela-transf.png"))
    pg.keyboard.press("Enter"); pg.wait_for_selector(".mback", state="detached")
    # fixa mensal + salvar e novo
    pg.keyboard.press("d"); pg.wait_for_selector("#m-valor:focus")
    pg.keyboard.type("10000"); pg.fill("#m-desc", "Internet"); pg.select_option("#m-cat", label="Internet")
    pg.click("details.more summary"); pg.click('[data-act="m-rep"][data-v="fixa"]')
    pg.click('[data-act="m-salvar"][data-novo="1"]'); pg.wait_for_timeout(300)
    check("salvar e novo reabre a janela", pg.locator("#m-valor").count(), 1)
    pg.keyboard.type("4500"); pg.fill("#m-desc", "Farmácia"); pg.select_option("#m-cat", label="Farmácia")
    pg.click('[data-act="m-pago"][data-v="0"]')
    pg.keyboard.press("Escape"); pg.wait_for_selector(".mback", state="detached")
    pg.wait_for_timeout(300)

    ids = ev(pg, "(() => { const c = {}; for (const [id, x] of Object.entries(S.cfg.contas)) c[x.nome] = id; for (const [id, x] of Object.entries(S.cfg.cartoes)) c[x.nome] = id; return c; })()")
    ev(pg, "derivar()")
    check("saldo Nubank", ev(pg, f"saldoAtual('{ids['Nubank']}')"), 150000 - 25990 + 320000 - 20000 - 10000)
    check("saldo Carteira", ev(pg, f"saldoAtual('{ids['Carteira']}')"), 10000 + 20000)
    check("totais outubro", ev(pg, "totais(itensMes('2026-10'))"), {"rec": 320000, "desp": 25990 + 10000})
    fat = ev(pg, f"(() => {{ const f = fatura('{ids['Roxinho']}', '2026-11'); return {{ total: f.total, n: f.itens.length, status: f.status }}; }})()")
    check("fatura nov (1ª parcela com centavo)", fat, {"total": 33334, "n": 1, "status": "aberta"})
    check("parcelas nas faturas", [ev(pg, f"fatura('{ids['Roxinho']}', '2026-{m}').total") for m in ("12",)] + [ev(pg, f"fatura('{ids['Roxinho']}', '2027-01').total")], [33333, 33333])
    check("limite usado", ev(pg, f"limiteUsado('{ids['Roxinho']}')"), 100000)
    check("fixa virtual em nov", ev(pg, "virtuais('2026-11','2026-11').map(v => [v.desc, v.valor, v.data])"), [["Internet", 10000, "2026-11-" + ev(pg, "today()")[8:]]])
    prev_nov = ev(pg, f"saldoPrevisto('{ids['Nubank']}', '2026-11')")
    check("previsto Nubank nov", prev_nov, 150000 - 25990 + 320000 - 20000 - 10000 - 10000 - 33334)
    texto_kpi = pg.inner_text(".kpi .val").replace("\xa0", " ")
    check("KPI saldo em contas", texto_kpi, "R$ 4.440,10")
    pg.screenshot(path=str(SHOTS / "20-geral-out.png"), full_page=False)

    # lançamentos de outubro
    pg.click('.side [data-view="lanc"]'); pg.wait_for_timeout(150)
    pg.screenshot(path=str(SHOTS / "21-lanc-out.png"))
    # novembro: fatura + fixa pendente; pagar a fatura
    pg.click("#title"); pg.keyboard.press("ArrowRight"); pg.wait_for_timeout(150)
    rows = pg.locator(".row .t1").all_inner_texts()
    print("linhas nov:", rows)
    check("nov tem fatura e fixa", sorted(r.split("fixa")[0].strip() for r in rows), ["Fatura Roxinho", "Internet"])
    # Pagar desconta direto da conta do cartão (sem janela), com aviso e Desfazer
    pg.click('.row [data-act="pagar-fatura"]'); pg.wait_for_timeout(300)
    check("pagar fatura: sem janela", pg.locator(".mback").count(), 0)
    check("pagar fatura: aviso", pg.inner_text("#toast span").replace("\xa0", " "), "Fatura de nov/26 paga: R$ 333,34 saiu de Nubank")
    pg.screenshot(path=str(SHOTS / "13-fatura-paga.png"))
    ev(pg, "derivar()")
    check("fatura nov paga", ev(pg, f"fatura('{ids['Roxinho']}', '2026-11').status"), "paga")
    check("limite após pagamento", ev(pg, f"limiteUsado('{ids['Roxinho']}')"), 100000 - 33334)
    check("saldo Nubank após pagar", ev(pg, f"saldoAtual('{ids['Nubank']}')"), 414010 - 33334)
    # confirmar a fixa de novembro com um clique
    pg.click('.row:has-text("Internet") [data-act="pagar"]'); pg.wait_for_selector("#pc-ok")
    check("pede confirmação antes de pagar", ev(pg, "D.L.filter(l => l.recorr && l.recM === '2026-11').length"), 0)
    pg.screenshot(path=str(SHOTS / "24-confirmar-pago.png"))
    pg.keyboard.press("Enter"); pg.wait_for_selector(".mback", state="detached"); pg.wait_for_timeout(250)
    ev(pg, "derivar()")
    check("fixa nov registrada", ev(pg, "D.L.filter(l => l.recorr && l.recM === '2026-11').length"), 1)
    check("sem virtual em nov", ev(pg, "virtuais('2026-11','2026-11').length"), 0)
    pg.screenshot(path=str(SHOTS / "22-lanc-nov.png"))
    # editar parcela 2/3 só ela
    pg.keyboard.press("ArrowRight"); pg.click('.side [data-view="cartoes"]'); pg.wait_for_timeout(150)
    pg.screenshot(path=str(SHOTS / "23-cartoes-dez.png"))
    pg.click('.row:has-text("Cadeira") .grow'); pg.wait_for_selector("#m-scope")
    pg.fill("#m-desc", "Cadeira gamer"); pg.click('input[name="m-sc"][value="prox"]'); pg.click("#m-salvar"); pg.wait_for_selector(".mback", state="detached"); pg.wait_for_timeout(200)
    ev(pg, "derivar()")
    check("edição nas próximas parcelas", ev(pg, "D.L.filter(l => l.grupo).sort((a,b)=>a.parc.i-b.parc.i).map(l => l.desc)"), ["Cadeira", "Cadeira gamer", "Cadeira gamer"])
    # relatórios, orçamento, config
    pg.keyboard.press("ArrowLeft"); pg.keyboard.press("ArrowLeft")
    for v in ("relatorios", "orcamento", "config", "contas"):
        pg.click(f'.side [data-view="{v}"]'); pg.wait_for_timeout(150); pg.screenshot(path=str(SHOTS / f"3{['relatorios','orcamento','config','contas'].index(v)}-{v}.png"))
    STORE_SNAP = ev(pg, "JSON.stringify([...window.__store.entries()])")
    pg.click('.side [data-view="orcamento"]'); pg.wait_for_timeout(100)
    inp = pg.locator("[data-orc]").first; inp.focus(); pg.keyboard.type("80000"); pg.keyboard.press("Enter"); pg.wait_for_timeout(200)
    check("orçamento salvo", ev(pg, "Object.values(S.cfg.orc).map(v => typeof v === 'object' ? Object.values(v)[0] : v)"), [80000])  # limite por mês desde a 1.1
    pg.click('.side [data-view="config"]'); pg.click('[data-act="exp-csv"]'); pg.wait_for_timeout(200)
    dl = ev(pg, "window.__download")
    print("csv:", dl["filename"], dl["head"].splitlines()[:3])
    check("csv gerado", dl["filename"].endswith(".csv"), True)
    pg.click('[data-act="exp-json"]'); pg.wait_for_timeout(200)
    check("backup json", ev(pg, "window.__download.filename.endsWith('.json') && window.__download.head.includes('fintrix')"), True)
    pg.click('.side [data-view="contas"]'); pg.click('.panel:has-text("Carteira") [data-act="ajustar"]'); pg.wait_for_timeout(120)
    pg.keyboard.type("25000"); pg.keyboard.press("Enter"); pg.wait_for_timeout(250)
    ev(pg, "derivar()")
    check("ajuste de saldo", ev(pg, f"saldoAtual('{ids['Carteira']}')"), 25000)
    check("ajuste fora dos totais", ev(pg, "totais(itensMes('2026-10')).desp"), 35990)
    pg.click('.side [data-view="config"]'); pg.click('[data-act="apagar-tudo"]'); pg.wait_for_timeout(100); pg.fill("#ap-c", "apagar"); pg.click('[data-act="apagar-confirma"]')
    pg.wait_for_selector('[data-act="onb-conta"]', timeout=5000)
    check("apagar tudo volta ao início", ev(pg, "window.__store.size"), 0)
    # tema claro + celular
    pg2, errs2 = nova_pagina(b, viewport={"width": 390, "height": 844}, color_scheme="light", is_mobile=True, has_touch=True, device_scale_factor=2)
    store = STORE_SNAP
    pg2.add_init_script(f"setTimeout(() => {{ for (const [k, v] of JSON.parse({json.dumps(store)})) window.__store.set(k, v); }}, 0);")
    pg2.goto("file://" + str(AQUI/"index.html"))
    pg2.wait_for_selector("text=Saldo em contas"); pg2.wait_for_timeout(300)
    pg2.screenshot(path=str(SHOTS / "40-mobile-geral.png"))
    pg2.click("#fab"); pg2.wait_for_timeout(100); pg2.screenshot(path=str(SHOTS / "41-mobile-menu.png"))
    pg2.click('#menu [data-tipo="despesa"]'); pg2.wait_for_timeout(200); pg2.screenshot(path=str(SHOTS / "42-mobile-janela.png"))
    pg2.keyboard.press("Escape")
    pg2.click('.tabbar [data-view="lanc"]'); pg2.wait_for_timeout(150); pg2.screenshot(path=str(SHOTS / "43-mobile-lanc.png"))
    over = pg2.evaluate("document.documentElement.scrollWidth > window.innerWidth || document.querySelector('#content').scrollWidth > document.querySelector('#content').clientWidth")
    check("sem rolagem horizontal no celular", over, False)
    print("erros de console:", errs + errs2)
    if errs or errs2:
        fails.append("console")
    b.close()
print("\nRESULTADO:", "TUDO CERTO" if not fails else f"{len(fails)} falha(s): {fails}")
