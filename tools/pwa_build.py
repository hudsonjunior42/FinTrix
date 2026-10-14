"""Gera o pacote PWA do FinTrix (app instalável e offline) a partir do index.html da raiz do repositório.
Saída: dist/pwa/ (index.html, manifest.webmanifest, sw.js, icons/, LEIAME.md copiado de docs/pwa.md).
Rode na raiz do repositório: python3 tools/pwa_build.py   (precisa do Playwright para desenhar os ícones)
Aceita o app como fragmento (começando em <title>, como é publicado no claude.ai) ou como documento completo
(<!doctype html>…<body> na frente): nesse caso aproveita o <style> do cabeçalho."""
import hashlib, json, pathlib, re, shutil
from playwright.sync_api import sync_playwright
RAIZ = pathlib.Path(__file__).resolve().parents[1]
OUT = RAIZ / "dist" / "pwa"; (OUT / "icons").mkdir(parents=True, exist_ok=True)
src = (RAIZ / "index.html").read_text()
# documento completo (como o claude.ai devolve): tira o invólucro, mantendo o estilo dele
extra = ""
m = re.match(r"\s*<!doctype html>.*?<head>(.*?)</head>\s*<body>", src, re.S | re.I)
if m:
    extra = "".join(re.findall(r"<style>.*?</style>", m.group(1), re.S))
    src = src[m.end():]
src = re.sub(r"</body>\s*</html>\s*$", "", src.rstrip()) + "\n"
corte = src.index('<svg width="0" height="0" style="position:absolute"')
cabeca, corpo = src[:corte], src[corte:]

HEAD = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="description" content="Controle financeiro pessoal: contas, cartões, faturas, orçamento e relatórios. Os dados ficam neste aparelho.">
<meta name="theme-color" content="#0E1117">
<link rel="manifest" href="manifest.webmanifest">
<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">
<link rel="icon" type="image/png" sizes="32x32" href="icons/favicon-32.png">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="FinTrix">
<style>body{margin:0;font:14px system-ui}img{max-width:100%}[hidden]{display:none!important}</style>
"""
SW_REG = """
<script>
// modo offline: guarda o app neste aparelho para abrir sem internet.
// Quando uma versão nova é instalada em segundo plano, o app mostra "Há uma versão nova" com o botão Atualizar agora.
if ("serviceWorker" in navigator) addEventListener("load", () => {
  const tinhaVersao = !!navigator.serviceWorker.controller; // na primeira instalação não há o que avisar
  let avisou = false;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (!tinhaVersao || avisou) return;
    avisou = true;
    if (window.fintrixNovaVersao) window.fintrixNovaVersao();
  });
  navigator.serviceWorker.register("sw.js").then(reg => {
    const verificar = () => reg.update().catch(() => {});
    setInterval(verificar, 60 * 60 * 1000); // app aberto por muito tempo: procura versão nova a cada hora
    document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") verificar(); });
  }).catch(e => console.warn("sw", e));
});
</script>
"""

LOGO = """<g stroke-linejoin="round" stroke-width="22">
<path d="M89 285 627 557 627 692 211 477 211 597 630 810 630 965 211 748 211 1060 89 1000Z" fill="url(#l)" stroke="url(#l)"/>
<path d="M627 557 1165 285 1165 424 973 520 973 1096 845 1162 845 583 627 692Z" fill="url(#r)" stroke="url(#r)"/>
<path d="M626 6 1165 285 627 557 89 285ZM627 107 272 299 627 485 982 299Z" fill="url(#t)" stroke="url(#t)" fill-rule="evenodd"/></g>"""
GRAD = """<defs><linearGradient id="t" gradientUnits="userSpaceOnUse" x1="420" y1="40" x2="860" y2="560"><stop offset="0" stop-color="#C9D0FF"/><stop offset="1" stop-color="#9AA7FF"/></linearGradient>
<linearGradient id="l" gradientUnits="userSpaceOnUse" x1="0" y1="300" x2="0" y2="1060"><stop offset="0" stop-color="#7B8CFF"/><stop offset="1" stop-color="#5E6FEA"/></linearGradient>
<linearGradient id="r" gradientUnits="userSpaceOnUse" x1="0" y1="300" x2="0" y2="1160"><stop offset="0" stop-color="#5A6BEA"/><stop offset="1" stop-color="#3F50C9"/></linearGradient></defs>"""
def icone(tam, logo_frac, cantos, fundo=True):
    vb_w, vb_h = 1134, 1190
    lw = tam * logo_frac; lh = lw * vb_h / vb_w
    bg = f'<rect width="{tam}" height="{tam}" rx="{tam * cantos}" fill="url(#bg)"/>' if fundo else ""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{tam}" height="{tam}" viewBox="0 0 {tam} {tam}">
<defs><radialGradient id="bg" cx="50%" cy="38%" r="75%"><stop offset="0" stop-color="#1B2130"/><stop offset="1" stop-color="#0E1117"/></radialGradient></defs>
{bg}<svg x="{(tam - lw) / 2}" y="{(tam - lh) / 2}" width="{lw}" height="{lh}" viewBox="60 -10 {vb_w} {vb_h}">{GRAD}{LOGO}</svg></svg>"""
ICONES = {"icon-192.png": (192, .66, .22), "icon-512.png": (512, .66, .22), "icon-maskable-512.png": (512, .52, 0), "apple-touch-icon.png": (180, .64, 0), "favicon-32.png": (32, .84, .22)}
with sync_playwright() as p:
    b = p.chromium.launch()
    for nome, (tam, frac, cantos) in ICONES.items():
        pg = b.new_page(viewport={"width": tam, "height": tam})
        pg.set_content(f'<html><body style="margin:0;background:transparent">{icone(tam, frac, cantos)}</body></html>')
        pg.screenshot(path=str(OUT / "icons" / nome), omit_background=True)
        pg.close()
    b.close()
(OUT / "icons" / "icon.svg").write_text(icone(512, .66, .22))

manifest = {
    "name": "FinTrix", "short_name": "FinTrix", "lang": "pt-BR", "dir": "ltr",
    "description": "Controle financeiro pessoal: contas, cartões, faturas, orçamento e relatórios.",
    "start_url": "./", "scope": "./", "id": "./", "display": "standalone", "orientation": "any",
    "background_color": "#0E1117", "theme_color": "#0E1117", "categories": ["finance", "productivity"],
    "icons": [
        {"src": "icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
        {"src": "icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
        {"src": "icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        {"src": "icons/icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"}],
    "shortcuts": [{"name": n, "short_name": c, "url": f"./?novo={t}", "icons": [{"src": "icons/icon-192.png", "sizes": "192x192"}]}
                  for t, n, c in [("despesa", "Nova despesa", "Despesa"), ("receita", "Nova receita", "Receita"), ("cartao", "Compra no cartão", "Cartão"), ("transf", "Transferência", "Transferir")]],
}
(OUT / "manifest.webmanifest").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))

versao = hashlib.sha256((src + extra + json.dumps(manifest, sort_keys=True)).encode()).hexdigest()[:10]
BUILD = f'<script>window.FINTRIX_BUILD = "{versao}";</script>\n'
index = HEAD + (f"{extra}\n" if extra else "") + BUILD + cabeca + "</head>\n<body>\n" + corpo + SW_REG + "</body>\n</html>\n"
(OUT / "index.html").write_text(index)
SW = """// FinTrix: guarda o app no aparelho para abrir sem internet. Versão gerada a cada build.
const CACHE = "fintrix-%s";
const APP = ["./", "index.html", "manifest.webmanifest", "icons/icon-192.png", "icons/icon-512.png", "icons/icon-maskable-512.png", "icons/apple-touch-icon.png", "icons/favicon-32.png", "icons/icon.svg"];
// cache: "reload" busca os arquivos novos no servidor, sem reaproveitar uma cópia velha do cache HTTP do navegador
self.addEventListener("install", e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(APP.map(u => new Request(u, { cache: "reload" })))).then(() => self.skipWaiting())); });
self.addEventListener("activate", e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k.startsWith("fintrix-") && k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
// abre na hora com a cópia guardada e atualiza em segundo plano (a versão nova vale na próxima abertura)
self.addEventListener("fetch", e => {
  const req = e.request; if (req.method !== "GET") return;
  const url = new URL(req.url);
  const fonte = url.hostname === "fonts.googleapis.com" || url.hostname === "fonts.gstatic.com";
  if (url.origin !== location.origin && !fonte) return;
  const chave = req.mode === "navigate" ? "index.html" : req;
  e.respondWith(caches.open(CACHE).then(async c => {
    const guardado = await c.match(chave, { ignoreSearch: req.mode === "navigate" });
    const rede = fetch(req).then(r => { if (r && (r.ok || r.type === "opaque")) c.put(chave, r.clone()); return r; }).catch(() => guardado || Response.error());
    return guardado || rede;
  }));
});
""" % versao
(OUT / "sw.js").write_text(SW)
leia = [l for l in (RAIZ / "docs" / "pwa.md").read_text().splitlines(keepends=True) if not l.startswith("> **No repositório:**")]
(OUT / "LEIAME.md").write_text("".join(leia).replace("\n\n\n", "\n\n"))
print("pacote PWA em", OUT, "versão", versao)
