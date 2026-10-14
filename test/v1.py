"""Testes da 1.0: segurança dos dados, restauração, migração, backup automático, tela de erro, ajuste de fatura,
dia do fechamento, carga com 10 mil lançamentos e o modo claude.ai (banco simulado, sem gravação em lote).
Uso: python3 v1.py [arquivo .html ou pasta com index.html]   (padrão: o index.html da raiz do repositório)"""
import json, pathlib, sys, threading, time, functools, http.server, re, shutil
from playwright.sync_api import sync_playwright
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from gerar import gerar

AQUI = pathlib.Path(__file__).parent
TMP = AQUI / "tmp"; TMP.mkdir(exist_ok=True)
ARG = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else AQUI.parent / "index.html").resolve()
if ARG.is_file(): WWW = TMP / "www"; WWW.mkdir(exist_ok=True); shutil.copy(ARG, WWW / "index.html")
else: WWW = ARG
falhas, oks = [], 0
def ok(c, msg):
    global oks
    if c: oks += 1; print("  ok ·", msg)
    else: falhas.append(msg); print("  FALHOU ·", msg)

class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def end_headers(self): self.send_header("Cache-Control", "no-store"); super().end_headers()
def servir(pasta, porta):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", porta), functools.partial(H, directory=str(pasta)))
    threading.Thread(target=srv.serve_forever, daemon=True).start(); return srv

def variante(nome, troca):
    """cópia do app com uma troca de texto (para testar migração)"""
    d = TMP / nome; d.mkdir(exist_ok=True)
    s = (WWW / "index.html").read_text()
    for a, b in troca: assert s.count(a) == 1, a; s = s.replace(a, b)
    (d / "index.html").write_text(s); return d

def arquivo(nome, obj):
    p = TMP / nome; p.write_text(json.dumps(obj)); return str(p)

erros_pagina = []
def nova(ctx, url, rotulo):
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: "teste-erro" not in str(e) and erros_pagina.append(f"{rotulo}: {e}"))
    pg.on("console", lambda m: m.type == "error" and not any(x in m.text for x in ("falha simulada", "teste-erro", "fonts.g", "ERR_", "Failed to load resource", "Falta a migração", "migração falhou de propósito")) and erros_pagina.append(f"{rotulo} console: {m.text}"))
    pg.goto(url); return pg

def pronto(pg, t=15000):
    pg.wait_for_function("S.fase === 'pronto' && Object.keys(S.anos).length >= (C().anos||[]).length", timeout=t)
    pg.evaluate("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")  # espera o próximo desenho (D é recalculado nele)
def onboarding_conta(pg, nome="Conta teste"):
    pg.wait_for_selector('[data-act="onb-conta"]'); pg.click('[data-act="onb-conta"]')
    pg.fill("#o-nome", nome); pg.click('[data-act="onb-criar"]'); pronto(pg)
def ir(pg, view): pg.evaluate(f"irPara('{view}')")

srv = servir(WWW, 8765)
srv2 = None
URL = "http://localhost:8765/"
with sync_playwright() as p:
    b = p.chromium.launch()

    print("\n1. restauração com 10 mil lançamentos (carga)")
    ctx = b.new_context(viewport={"width": 1400, "height": 900}); pg = nova(ctx, URL, "carga")
    pg.wait_for_selector('[data-act="onb-restaurar"]')
    g = gerar(); f = arquivo("grande.json", g)
    t0 = time.time(); pg.set_input_files("#imp-json", f); pg.wait_for_selector("#f-rest")
    t_val = time.time() - t0
    txt = pg.inner_text("#f-rest")
    cs = sorted(l["comp"] for l in g["lancamentos"]); mc = lambda k: ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"][int(k[5:])-1] + "/" + k[2:4]
    ok("10.200" in txt and f"{mc(cs[0])} a {mc(cs[-1])}" in txt, f"resumo do backup antes de gravar ({t_val:.2f} s para ler e conferir)")
    ok(not pg.query_selector('input[name="rest-modo"]'), "sem dados atuais, não pergunta substituir/mesclar")
    t0 = time.time(); pg.click('[data-act="restaurar-ok"]'); pronto(pg, 60000); t_rest = time.time() - t0
    n = pg.evaluate("D ? D.L.length : derivar() || D.L.length")
    ok(n == 10200, f"restaurou {n} lançamentos em {t_rest:.2f} s")
    tempos = {}
    for v in ["geral", "lanc", "contas", "cartoes", "relatorios", "orcamento", "config"] + (["patrimonio"] if "vPatrimonio" in (WWW / "index.html").read_text() else []):
        tempos[v] = pg.evaluate(f"(() => {{ irPara('{v}'); const t = performance.now(); for (let i = 0; i < 5; i++) render(); return (performance.now() - t) / 5; }})()")
    pg.evaluate("S.relAno = true; irPara('relatorios')"); tempos["relatorios-ano"] = pg.evaluate("(() => { const t = performance.now(); render(); return performance.now() - t; })()")
    pg.evaluate("S.relAno = false")
    print("   tempo de desenho por tela (ms):", {k: round(v) for k, v in tempos.items()})
    ok(max(tempos.values()) < 1500, "todas as telas desenham em menos de 1,5 s com 10 mil lançamentos")
    ctx2 = None
    t0 = time.time(); pg.reload(); pronto(pg, 30000); t_abre = time.time() - t0
    ok(True, f"abre de novo com 10 mil lançamentos em {t_abre:.2f} s")
    ir(pg, "geral"); pg.keyboard.press("d"); pg.wait_for_selector("#m-valor"); pg.wait_for_function("document.activeElement && document.activeElement.id === 'm-valor'")
    pg.fill("#m-valor", "1234"); pg.fill("#m-desc", "Café"); pg.select_option("#m-cat", index=1)
    t0 = time.time(); pg.keyboard.press("Enter"); pg.wait_for_function("D && D.L.length === 10201"); t_salva = time.time() - t0
    ok(t_salva < 2, f"salvar um lançamento com a base grande leva {t_salva:.2f} s")
    ok(pg.query_selector(".aviso") is not None and "backup" in pg.inner_text(".aviso"), "aviso de backup na Visão geral (nenhum backup e muitos lançamentos)")
    with pg.expect_download() as dl: pg.click('.aviso [data-act="exp-json"]')
    caminho = TMP / "baixado.json"; dl.value.save_as(caminho); bk = json.loads(caminho.read_text())
    ok(len(bk["lancamentos"]) == 10201 and bk["versao"] == int(re.search(r"const VERSAO_DADOS = (\d+);", (WWW / "index.html").read_text()).group(1)) and bk["app_versao"], "backup baixado pelo aviso tem tudo e marca a versão")
    ok(pg.query_selector(".aviso") is None, "o aviso some depois do backup")
    ctx.close()

    print("\n2. restaurar sobre dados existentes: substituir, mesclar, cópia automática, arquivo ruim")
    ctx = b.new_context(); pg = nova(ctx, URL, "restaurar")
    onboarding_conta(pg)
    peq = gerar(anos=(2025, 2025), por_mes=20, seed=2); f_peq = arquivo("peq.json", peq)
    ir(pg, "config"); pg.set_input_files("#imp-json", f_peq); pg.wait_for_selector("#f-rest")
    ok(pg.query_selector('input[name="rest-modo"][value="sub"]').is_checked(), "com dados atuais, 'Substituir tudo' vem marcado")
    pg.click('[data-act="restaurar-ok"]'); pg.wait_for_selector("#f-rest", state="detached"); pronto(pg)
    ok(pg.evaluate("D.L.length") == 240 and pg.evaluate("Object.keys(C().contas).length") == 3, "substituir: fica igual ao backup (a conta criada antes some)")
    ok(pg.evaluate("COPIAS.n") == 1, "guardou uma cópia automática antes de substituir")
    outro = gerar(anos=(2024, 2024), por_mes=10, seed=3)
    for l in outro["lancamentos"]: l["id"] = "m" + l["id"]
    pg.set_input_files("#imp-json", arquivo("outro.json", outro)); pg.wait_for_selector("#f-rest")
    pg.check('input[name="rest-modo"][value="mesc"]'); pg.click('[data-act="restaurar-ok"]'); pg.wait_for_selector("#f-rest", state="detached"); pronto(pg)
    ok(pg.evaluate("D.L.length") == 360, "mesclar: soma os dois (240 + 120)")
    anos_esp = ",".join(sorted({l["comp"][:4] for l in peq["lancamentos"] + outro["lancamentos"]}))
    ok(pg.evaluate("C().anos.join()") == anos_esp, "mesclar: lista de anos inclui os dois")
    ruim = json.loads(json.dumps(peq)); ruim["lancamentos"][5]["comp"] = "2025-13"; ruim["lancamentos"][7]["valor"] = 12.5; ruim["lancamentos"][9]["id"] = ruim["lancamentos"][8]["id"]
    pg.set_input_files("#imp-json", arquivo("ruim.json", ruim)); pg.wait_for_selector(".erros-lista")
    t = pg.inner_text(".modal")
    ok("Nada foi gravado" in t and "mês de referência inválido" in t and "valor inválido" in t and "identificador repetido" in t, "arquivo com problemas: lista os erros e não grava")
    ok(pg.evaluate("D.L.length") == 360, "arquivo com problemas: dados intactos"); pg.click('.modal [data-act="fechar"]')
    novo = json.loads(json.dumps(peq)); novo["config"]["versao"] = 7
    pg.set_input_files("#imp-json", arquivo("novo.json", novo)); pg.wait_for_selector(".erros-lista")
    ok("versão mais nova" in pg.inner_text(".modal"), "backup de versão mais nova é recusado"); pg.click('.modal [data-act="fechar"]')
    pg.set_input_files("#imp-json", arquivo("lixo.json", {"x": 1})); pg.wait_for_selector(".erros-lista")
    ok("não é um backup do FinTrix" in pg.inner_text(".modal"), "arquivo que não é backup é recusado"); pg.click('.modal [data-act="fechar"]')
    # cópia automática: restaurar a primeira (antes de substituir) traz de volta a conta teste
    pg.click('[data-act="copias"]'); pg.wait_for_selector('[data-act="copia-restaurar"]')
    ok(len(pg.query_selector_all('[data-act="copia-restaurar"]')) == 2, "lista de cópias automáticas (uma por restauração)")
    pg.query_selector_all('[data-act="copia-restaurar"]')[-1].click(); pg.wait_for_selector("#f-rest"); pg.click('[data-act="restaurar-ok"]'); pg.wait_for_selector("#f-rest", state="detached"); pronto(pg)
    ok(pg.evaluate("Object.values(C().contas).map(c => c.nome).join()") == "Conta teste" and pg.evaluate("D.L.length") == 0, "restaurar uma cópia automática devolve o estado anterior")
    # apagar tudo guarda cópia e a apresentação oferece recuperar
    pg.click('[data-act="apagar-tudo"]'); pg.fill("#ap-c", "APAGAR"); pg.click('[data-act="apagar-confirma"]')
    pg.wait_for_selector('[data-act="onb-restaurar"]')
    ok(pg.query_selector('#onb [data-act="copias"]') is not None, "depois de apagar tudo, a apresentação oferece recuperar uma cópia")
    ok(pg.evaluate("lerTudo().then(d => d.config === null && d.lancamentos.length === 0)"), "apagar tudo apagou de verdade")
    ctx.close()

    N = int(re.search(r"const VERSAO_DADOS = (\d+);", (WWW / "index.html").read_text()).group(1)); N1 = N + 1
    print(f"\n3. migração do formato dos dados (variante do app com VERSAO_DADOS = {N1})")
    v2 = variante("v2", [(f"const VERSAO_DADOS = {N};", f"const VERSAO_DADOS = {N1};"),
        ("const MIGRACOES = {\n", f"const MIGRACOES = {{\n  {N1}: d => ({{ config: {{ ...d.config, teste: true }}, lancamentos: d.lancamentos.map(l => ({{ ...l, m2: true }})) }}),\n")])
    v2ruim = variante("v2ruim", [(f"const VERSAO_DADOS = {N};", f"const VERSAO_DADOS = {N1};"),
        ("const MIGRACOES = {\n", f"const MIGRACOES = {{\n  {N1}: d => {{ throw new Error('migração falhou de propósito'); }},\n")])
    shutil.copytree(WWW, TMP / "srv", dirs_exist_ok=True)
    for n in ("v2", "v2ruim"): shutil.copytree(TMP / n, TMP / "srv" / n, dirs_exist_ok=True)
    srv2 = servir(TMP / "srv", 8766); U2 = "http://localhost:8766/"
    ctx = b.new_context(); pg = nova(ctx, U2, "migração")
    pg.wait_for_selector('[data-act="onb-restaurar"]'); pg.set_input_files("#imp-json", f_peq); pg.wait_for_selector("#f-rest"); pg.click('[data-act="restaurar-ok"]'); pronto(pg)
    pg.goto(U2 + "v2ruim/")
    pg.wait_for_function("S.fase === 'erro-migracao'")
    ok("Nada foi alterado" in pg.inner_text("#content"), "migração com erro: tela explica e oferece backup de emergência")
    ok(pg.evaluate(f"lerTudo().then(d => d.config.versao === {N} && !d.lancamentos.some(l => l.m2))"), "migração com erro: dados intactos (transação desfeita)")
    with pg.expect_download() as dl: pg.click('[data-act="bk-emergencia"]')
    dl.value.save_as(TMP / "emerg.json"); ok(len(json.loads((TMP / "emerg.json").read_text())["lancamentos"]) == 240, "backup de emergência na tela de erro da migração")
    pg.goto(U2 + "v2/"); pronto(pg)
    ok(pg.evaluate("C().versao") == N1 and pg.evaluate("D.L.every(l => l.m2) && D.L.length === 240") and pg.evaluate("C().teste === true"), f"migração v{N} → v{N1} aplicada em todos os lançamentos")
    ok(pg.evaluate(f"COPIAS.ult && COPIAS.ult.motivo.includes('v{N} para a v{N1}')"), "cópia automática guardada antes de migrar")
    pg.goto(U2); pg.wait_for_function("S.fase === 'versao-nova'")
    ok("versão mais nova" in pg.inner_text("#content"), "app antigo com dados novos: não abre (protege os dados)")
    ok(pg.evaluate(f"lerTudo().then(d => d.config.versao === {N1})"), "app antigo não gravou nada nos dados novos")
    # backup v1 restaurado no app v2 é migrado na hora
    pg.goto(U2 + "v2/"); pronto(pg); ir(pg, "config")
    pg.set_input_files("#imp-json", f_peq); pg.wait_for_selector("#f-rest")
    ok("será atualizado" in pg.inner_text("#f-rest"), "backup antigo: avisa que será atualizado")
    pg.click('[data-act="restaurar-ok"]'); pg.wait_for_selector("#f-rest", state="detached"); pronto(pg)
    ok(pg.evaluate(f"C().versao === {N1} && D.L.every(l => l.m2)"), "backup antigo restaurado já no formato novo")
    ctx.close()

    print("\n4. backup automático numa pasta (pasta simulada com o sistema de arquivos privado do navegador)")
    ctx = b.new_context()
    ctx.add_init_script("window.showDirectoryPicker = async () => (await navigator.storage.getDirectory()).getDirectoryHandle('backups', { create: true });")
    pg = nova(ctx, URL, "pasta")
    pg.wait_for_selector('[data-act="onb-restaurar"]'); pg.set_input_files("#imp-json", f_peq); pg.wait_for_selector("#f-rest"); pg.click('[data-act="restaurar-ok"]'); pronto(pg)
    ir(pg, "config"); pg.click('[data-act="bk-pasta"]'); pg.wait_for_function("BK.pasta && !BK.gravando && bkEstado()?.via === 'auto'")
    arqs = lambda: pg.evaluate("(async () => { const d = await (await navigator.storage.getDirectory()).getDirectoryHandle('backups'); const o = []; for await (const [n] of d.entries()) o.push(n); return o.sort(); })()")
    ok(arqs() == [f"fintrix-backup-{time.strftime('%Y-%m-%d')}.json"], "escolher a pasta já grava o backup do dia")
    ok("ligado" in pg.inner_text(".dados-st"), "Configurações mostra o backup automático ligado")
    pg.evaluate("(async () => { const d = await (await navigator.storage.getDirectory()).getDirectoryHandle('backups'); for (let i = 1; i <= 20; i++) { const f = await d.getFileHandle(`fintrix-backup-2025-01-${String(i).padStart(2,'0')}.json`, { create: true }); const w = await f.createWritable(); await w.write('{}'); await w.close(); } })()")
    pg.evaluate("abrirLanc({ tipo: 'despesa' })"); pg.wait_for_function("document.activeElement && document.activeElement.id === 'm-valor'"); pg.fill("#m-valor", "990"); pg.select_option("#m-cat", index=1); pg.keyboard.press("Enter"); pg.wait_for_function("D.L.length === 241")
    pg.evaluate("backupAuto(false)"); pg.wait_for_function("!BK.gravando")
    a = arqs(); ok(len(a) == 15 and a[-1].startswith("fintrix-backup-2026") is False or len(a) == 15, f"mantém só os últimos 15 arquivos ({len(a)})")
    hoje = pg.evaluate("(async () => { const d = await (await navigator.storage.getDirectory()).getDirectoryHandle('backups'); return JSON.parse(await (await (await d.getFileHandle(`fintrix-backup-${today()}.json`)).getFile()).text()).lancamentos.length; })()")
    ok(hoje == 241, "o arquivo do dia é atualizado quando algo muda")
    pg.reload(); pronto(pg)
    ok(pg.evaluate("!!BK.pasta && BK.perm === 'granted'"), "a pasta continua lembrada depois de recarregar")
    pg.evaluate("BK.perm = 'prompt'; irPara('geral')")
    ok("pausado" in pg.inner_text(".aviso"), "sem permissão, a Visão geral avisa que o backup automático está pausado")
    ctx.close()

    print("\n5. tela de segurança e erros inesperados")
    ctx = b.new_context(); pg = nova(ctx, URL, "segurança")
    onboarding_conta(pg)
    pg.evaluate("window.vCartoes = () => { throw new Error('teste-erro na tela') }; irPara('cartoes')")
    ok("encontrou um erro" in pg.inner_text("#content"), "erro ao desenhar uma tela mostra a tela de segurança")
    with pg.expect_download() as dl: pg.click('[data-act="bk-emergencia"]')
    ok(dl.value.suggested_filename.startswith("fintrix-emergencia-"), "backup de emergência na tela de segurança")
    pg.click('[data-act="seg-geral"]'); ok(pg.evaluate("S.view") == "geral" and "Saldo em contas" in pg.inner_text("#content"), "voltar para a Visão geral funciona")
    pg.evaluate("setTimeout(() => { throw new Error('teste-erro solto') })"); pg.wait_for_selector('[data-barra="erro"]')
    ok("Algo deu errado" in pg.inner_text('[data-barra="erro"]'), "erro inesperado mostra a barra de aviso")
    pg.click('[data-barra="erro"] [data-act="ver-erro"]'); ok("teste-erro solto" in pg.inner_text(".erro-pre"), "detalhes do erro para copiar"); pg.click('.mfoot [data-act="fechar"]')
    pg.click('[data-barra="erro"] [data-act="barra-fechar"]'); ok(pg.query_selector('[data-barra="erro"]') is None, "a barra fecha")
    pg.evaluate("fintrixNovaVersao()"); ok("versão nova" in pg.inner_text('[data-barra="versao"]'), "aviso de versão nova (chamado pelo service worker)")
    # backup de emergência lendo o banco direto, sem o app ter aberto
    ok(pg.evaluate("lerIndexedDbBruto().then(d => d.config && Object.keys(d.config.contas).length === 1)"), "leitura direta do banco local (para quando a abertura falha)")
    ctx.close()

    print("\n6. cartões: dia do fechamento, fechamento no dia 31 e ajustar fatura")
    ctx = b.new_context(); pg = nova(ctx, URL, "cartões")
    onboarding_conta(pg)
    r = pg.evaluate("""[faturaDe({ fech: 10, venc: 17 }, '2026-10-10'), faturaDe({ fech: 10, venc: 17, fechAtual: true }, '2026-10-10'), faturaDe({ fech: 10, venc: 17, fechAtual: true }, '2026-10-11'),
      faturaDe({ fech: 31, venc: 8 }, '2026-04-30'), faturaDe({ fech: 31, venc: 8 }, '2026-04-29'), faturaDe({ fech: 25, venc: 5 }, '2026-10-24')]""")
    ok(r == ["2026-11", "2026-10", "2026-11", "2026-06", "2026-05", "2026-11"], f"regras de fatura {r}")
    ir(pg, "cartoes"); pg.click('[data-act="cartao-novo"]'); pg.fill("#k-nome", "Teste"); pg.fill("#k-fech", "10"); pg.fill("#k-venc", "17")
    ex1 = pg.inner_text("#k-ex"); pg.check("#k-fatual"); ex2 = pg.inner_text("#k-ex")
    ok("dia do fechamento" in ex1 and ex1 != ex2, "o exemplo do cartão mostra onde cai a compra do dia do fechamento e muda com a opção")
    pg.click('[data-act="cartao-salvar"]'); pg.wait_for_function("Object.values(C().cartoes).some(c => c.fechAtual === true)")
    ok(True, "opção do dia do fechamento salva no cartão")
    cid = pg.evaluate("Object.keys(C().cartoes)[0]")
    pg.evaluate("S.mes = '2026-11'; render()")
    pg.click('[data-act="novo"][data-tipo="cartao"]'); pg.wait_for_function("document.activeElement && document.activeElement.id === 'm-valor'"); pg.fill("#m-valor", "10000"); pg.fill("#m-desc", "Mercado"); pg.select_option("#m-cat", index=1)
    pg.evaluate("v => { const e = document.querySelector('#m-data'); e.value = v; e.dispatchEvent(new Event('change', { bubbles: true })); }", "2026-10-15"); pg.keyboard.press("Enter"); pg.wait_for_function("D.L.length === 1")
    F = pg.evaluate("D.L[0].comp"); pg.evaluate(f"S.mes = '{F}'; render()")
    pg.click('[data-act="fatura-ajustar"]'); pg.fill("#ajf-v", "10350"); pg.wait_for_function("document.querySelector('#ajf-d').textContent.includes('3,50')")
    pg.click('[data-act="ajuste-fat-salvar"]'); pg.wait_for_function("D.L.length === 2")
    ok(pg.evaluate(f"fatura('{cid}', '{F}').total") == 10350, "ajustar fatura deixa o total igual ao do banco")
    ok(pg.evaluate(f"totais(itensMes('{F}')).desp") == 10000 and pg.evaluate(f"gastosPorCat(itensMes('{F}')).reduce((a, x) => a + x.v, 0)") == 10000, "o ajuste não entra nos relatórios")
    ok(pg.evaluate("limiteUsado(Object.keys(C().cartoes)[0])") == 10350, "o ajuste conta no limite usado")
    ok("±" in pg.inner_text("#content") and "Ajuste de fatura" in pg.inner_text("#content"), "o ajuste aparece na fatura como 'Ajuste de fatura'")
    pg.click('[data-act="fatura-ajustar"]'); pg.fill("#ajf-v", "10000"); pg.click('[data-act="ajuste-fat-salvar"]'); pg.wait_for_function("D.L.length === 3")
    ok(pg.evaluate(f"fatura('{cid}', '{F}').total") == 10000, "ajuste para baixo (crédito) também funciona")
    ctx.close()

    print("\n7. modo claude.ai (banco simulado, gravação um a um)")
    ctx = b.new_context(); ctx.add_init_script(path=str(AQUI / "mock_claude.js")); pg = nova(ctx, URL, "claude")
    pg.wait_for_selector('[data-act="onb-restaurar"]')
    ok(pg.evaluate("S.modo") == "claude" and not pg.evaluate("!!S.db.batch"), "abre no modo claude.ai, sem gravação em lote")
    pg.set_input_files("#imp-json", f_peq); pg.wait_for_selector("#f-rest"); pg.click('[data-act="restaurar-ok"]'); pronto(pg)
    ok(pg.evaluate("D.L.length") == 240, "restaurar no modo claude.ai (um documento por vez)")
    pg.evaluate("__mock.falharApos = __mock.writes + 30")
    ir(pg, "config"); pg.set_input_files("#imp-json", arquivo("outro2.json", outro)); pg.wait_for_selector("#f-rest"); pg.click('[data-act="restaurar-ok"]')
    pg.wait_for_function("document.querySelector('#m-err') && document.querySelector('#m-err').textContent.length > 0")
    ok("pela metade" in pg.inner_text("#m-err"), "falha no meio (claude.ai): explica que pode ter ficado pela metade e permite repetir")
    pg.evaluate("__mock.falharApos = null"); pg.click('[data-act="restaurar-ok"]'); pg.wait_for_selector("#f-rest", state="detached")
    a_outro = ",".join(sorted({l["comp"][:4] for l in outro["lancamentos"]}))
    pg.wait_for_function(f"D && D.L.length === 120 && C().anos.join() === '{a_outro}'", timeout=20000)
    ok(True, "repetir a restauração termina igual ao backup")
    pg.evaluate("exportJSON()"); pg.wait_for_function("window.__downloads.length === 1")
    ok(len(json.loads(pg.evaluate("__downloads[0].data"))["lancamentos"]) == 120, "backup no modo claude.ai lê do banco")
    ctx.close()

    print("\n8. celular: sem rolagem lateral nas telas novas")
    ctx = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True); pg = nova(ctx, URL, "celular")
    pg.wait_for_selector('[data-act="onb-restaurar"]'); pg.set_input_files("#imp-json", f_peq); pg.wait_for_selector("#f-rest")
    ok(pg.evaluate("document.documentElement.scrollWidth <= innerWidth"), "janela de restauração cabe na largura")
    pg.click('[data-act="restaurar-ok"]'); pronto(pg)
    for v in ["geral", "config", "cartoes"]:
        ir(pg, v); ok(pg.evaluate("document.documentElement.scrollWidth <= innerWidth && document.querySelector('#content').scrollWidth <= document.querySelector('#content').clientWidth + 1"), f"tela {v} sem rolagem lateral")
    pg.screenshot(path=str(TMP / "celular-config.png"), full_page=False)
    ir(pg, "geral"); pg.screenshot(path=str(TMP / "celular-geral.png"))
    ctx.close()
    b.close()

print("\nErros de página/console:", erros_pagina or "nenhum")
print(f"\n{oks} ok, {len(falhas)} falhas")
for f in falhas: print("  -", f)
sys.exit(1 if falhas or erros_pagina else 0)
