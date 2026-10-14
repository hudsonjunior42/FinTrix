"""Testa o pacote PWA: instalável, build visível, abre offline com os dados, atalho do ícone e o aviso de versão nova
(gera uma segunda build com outra versão, o service worker instala em segundo plano e o app oferece Atualizar agora).
Uso: python3 pwa_v1.py [raiz do repositório]   (padrão: a pasta acima de test/; usa index.html, tools/pwa_build.py e docs/pwa.md)"""
import sys, shutil, subprocess, pathlib, threading, functools, http.server, re, time
from playwright.sync_api import sync_playwright
ORIG = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else pathlib.Path(__file__).resolve().parents[1]).resolve()
# copia o necessário para uma pasta temporária com a mesma estrutura do repositório e gera o pacote lá (dist/pwa)
W = pathlib.Path(__file__).parent / "tmp" / "pwa-build"; shutil.rmtree(W, ignore_errors=True); (W / "tools").mkdir(parents=True); (W / "docs").mkdir()
for f in ("index.html", "tools/pwa_build.py", "docs/pwa.md"): shutil.copy(ORIG / f, W / f)
def build(): return re.search(r"versão (\w+)", subprocess.run([sys.executable, str(W / "tools" / "pwa_build.py")], capture_output=True, text=True, check=True).stdout).group(1)
b1 = build()
falhas, oks = [], 0
def ok(c, m):
    global oks
    if c: oks += 1; print("  ok ·", m)
    else: falhas.append(m); print("  FALHOU ·", m)
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 8790), functools.partial(H, directory=str(W / "dist" / "pwa")))
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = "http://localhost:8790/"
erros = []
with sync_playwright() as p:
    br = p.chromium.launch(); ctx = br.new_context(); pg = ctx.new_page()
    pg.on("pageerror", lambda e: erros.append(str(e)))
    pg.goto(URL); pg.wait_for_function("navigator.serviceWorker.controller !== null", timeout=15000)
    cdp = ctx.new_cdp_session(pg)
    inst = cdp.send("Page.getInstallabilityErrors")["installabilityErrors"]
    ok(not inst, f"instalável pelo Chrome {inst or ''}")
    ok(pg.evaluate("window.FINTRIX_BUILD") == b1, f"número da build no app ({b1})")
    pg.wait_for_selector('[data-act="onb-conta"]'); pg.click('[data-act="onb-conta"]'); pg.fill("#o-nome", "PWA"); pg.click('[data-act="onb-criar"]')
    pg.wait_for_function("S.fase === 'pronto'")
    VER = pg.evaluate("APP_VERSAO")
    pg.evaluate("irPara('config')"); ok(b1 in pg.inner_text(".sobre") and VER in pg.inner_text(".sobre"), f"Sobre mostra versão ({VER}) e build")
    pg.evaluate("abrirLanc({ tipo: 'despesa' })"); pg.fill("#m-valor", "1500"); pg.select_option("#m-cat", index=1); pg.keyboard.press("Enter"); pg.wait_for_function("D.L.length === 1")
    if pg.evaluate("typeof anexosOk === 'function' && anexosOk()"):
        pg.evaluate("anexoGuardar({ id: 'xpwa1', nome: 'r.pdf', tipo: 'application/pdf', tam: 3, criado: Date.now(), blob: new Blob(['abc'], { type: 'application/pdf' }) })")
        ok(pg.evaluate("anexoGet('xpwa1').then(r => r && r.tam === 3)"), "comprovantes guardados na versão instalada")
    ctx.set_offline(True); pg.reload(); pg.wait_for_function("S.fase === 'pronto' && D && D.L.length === 1", timeout=15000)
    ok(True, "abre sem internet, com os dados"); ctx.set_offline(False)
    pg.goto(URL + "?novo=receita"); pg.wait_for_selector("#m-valor"); ok("receita" in (pg.get_attribute(".mhead", "class") or ""), "atalho do ícone abre a janela de receita")
    pg.keyboard.press("Escape")
    # versão nova
    lc = W / "index.html"; lc.write_text(lc.read_text().replace(f'const APP_VERSAO = "{VER}";', f'const APP_VERSAO = "{VER}-teste";'))
    b2 = build(); ok(b2 != b1, f"a build muda quando o app muda ({b2})")
    pg.evaluate("navigator.serviceWorker.getRegistration().then(r => r.update())")
    pg.wait_for_selector('[data-barra="versao"]', timeout=20000); ok(True, "o app avisa que há uma versão nova")
    with pg.expect_navigation(): pg.click('[data-barra="versao"] [data-act="recarregar"]')
    pg.wait_for_function("typeof S !== 'undefined' && S.fase === 'pronto'", timeout=15000)
    ok(pg.evaluate("APP_VERSAO") == f"{VER}-teste" and pg.evaluate("window.FINTRIX_BUILD") == b2, "Atualizar agora carrega a versão nova")
    ok(pg.evaluate("D.L.length") == 1, "os dados continuam depois da atualização")
    pg.reload(); pg.wait_for_function("typeof S !== 'undefined' && S.fase === 'pronto'"); ok(pg.query_selector('[data-barra="versao"]') is None, "sem aviso repetido depois de atualizado")
    br.close()
print("erros de página:", erros or "nenhum"); print(f"{oks} ok, {len(falhas)} falhas")
sys.exit(1 if falhas or erros else 0)
