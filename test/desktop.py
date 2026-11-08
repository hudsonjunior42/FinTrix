"""Testa o app desktop (Tauri) pela interface, com dados numa pasta temporária e sem tocar no chaveiro real.

1. primeira abertura: cria conta e lança uma despesa (test/desktop/fase1.js)
2. reabre: os dados voltam do SQLite cifrado (fase2.js)
3. reabre com a chave errada: o app não abre
4. nenhum arquivo da pasta de dados tem os textos lançados em claro

Precisa de tela (X11/Wayland). Rode da raiz: python3 test/desktop.py
"""
import os, pathlib, secrets, shutil, subprocess, sys, tempfile

RAIZ = pathlib.Path(__file__).resolve().parents[1]
AQUI = RAIZ / "test" / "desktop"
CARGO = shutil.which("cargo") or str(pathlib.Path.home() / ".cargo/bin/cargo")
APP = RAIZ / "target/debug/fintrix"

falhas = []
def check(rotulo, got, exp):
    ok = got == exp
    print(("OK  " if ok else "FALHA ") + f"{rotulo}: {got!r}" + ("" if ok else f" (esperado {exp!r})"))
    if not ok:
        falhas.append(rotulo)

# o app embute o index.html na compilação: copiar e compilar de novo pega a versão atual
subprocess.run([sys.executable, str(RAIZ / "tools/tauri_prep.py")], check=True)
subprocess.run([CARGO, "build", "-q", "-p", "fintrix"], cwd=RAIZ, check=True)

(RAIZ / "test/tmp").mkdir(parents=True, exist_ok=True)
dados = pathlib.Path(tempfile.mkdtemp(prefix="desktop-", dir=RAIZ / "test/tmp"))
chave = secrets.token_hex(32)
comum = (AQUI / "comum.js").read_text()

def abrir(fase, chave_usada):
    roteiro = dados / f"roteiro-{fase}.js"
    roteiro.write_text(comum + "\n" + (AQUI / f"{fase}.js").read_text() if fase else "")
    env = dict(os.environ, FINTRIX_DADOS=str(dados / "app"), FINTRIX_CHAVE=chave_usada, FINTRIX_TESTE=str(roteiro))
    try:
        r = subprocess.run([str(APP)], env=env, capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired:
        return None, "tempo esgotado (o roteiro não chamou teste_fim)"
    finally:
        roteiro.unlink(missing_ok=True)
    saida = "\n".join(l for l in (r.stdout + r.stderr).splitlines() if "Locale not supported" not in l and "fallback 'C' locale" not in l)
    return r.returncode, saida

try:
    for fase in ("fase1", "fase2"):
        cod, saida = abrir(fase, chave)
        print(f"--- {fase}\n{saida}")
        check(f"{fase} terminou bem", cod, 0)

    cod, saida = abrir("fase2", secrets.token_hex(32))
    print("--- chave errada\n" + saida.strip().splitlines()[-1] if saida.strip() else "--- chave errada (sem saída)")
    check("chave errada não abre", cod not in (0, None), True)

    # nada do que foi digitado pode aparecer em claro em nenhum arquivo do app
    vazou = sorted(str(f.relative_to(dados)) for f in dados.rglob("*") if f.is_file()
                   and any(t in f.read_bytes() for t in (b"Supermercado", b"Nubank")))
    check("banco cifrado (cabeçalho)", (dados / "app/fintrix.db").read_bytes()[:15] == b"SQLite format 3", False)
    check("arquivos com dados em claro", vazou, [])
finally:
    shutil.rmtree(dados, ignore_errors=True)

print("\nRESULTADO:", "TUDO CERTO" if not falhas else f"{len(falhas)} falha(s): {falhas}")
sys.exit(1 if falhas else 0)
