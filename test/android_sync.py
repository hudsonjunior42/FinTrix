"""Sincronização entre o app desktop e o celular, com pareamento pelo QR code, num S3 local (test/s3_local.py).

1. computador (FinTrix de teste, dados temporários): cria conta, despesa e comprovante (test/desktop/fase1.js)
2. computador: liga a sincronização no S3 local e mostra o QR code (test/desktop/android-a.js)
3. celular (build de debug, pela USB): na apresentação, "Parear com outro aparelho" › "Ler QR code", apontar
   para a tela; depois lançar a despesa "Farmácia do celular" de R$ 45,00 (à mão, ou por test/android/avaliar.mjs)
4. computador: recebe a despesa; o cofre tem os dois aparelhos e nada em claro

Precisa de tela, do celular com o FinTrix de debug instalado e sem dados (apresentação) e do adb.
Rode da raiz: python3 test/android_sync.py
"""
import json, os, pathlib, secrets, shutil, subprocess, sys, tempfile, time, urllib.request

RAIZ = pathlib.Path(__file__).resolve().parents[1]
AQUI = RAIZ / "test" / "desktop"
CARGO = shutil.which("cargo") or str(pathlib.Path.home() / ".cargo/bin/cargo")
APP = RAIZ / "target/debug/fintrix"
PORTA = 9000
SEGREDOS = (b"Supermercado", b"Nubank", b"COMPROVANTE-SEGREDO", b"Farm\xc3\xa1cia do celular")

falhas = []
def check(rotulo, got, exp):
    ok = got == exp
    print(("OK  " if ok else "FALHA ") + f"{rotulo}: {got!r}" + ("" if ok else f" (esperado {exp!r})"))
    if not ok:
        falhas.append(rotulo)

subprocess.run([sys.executable, str(RAIZ / "tools/tauri_prep.py")], check=True)
subprocess.run([CARGO, "build", "-q", "-p", "fintrix"], cwd=RAIZ, check=True)

(RAIZ / "test/tmp").mkdir(parents=True, exist_ok=True)
tmp = pathlib.Path(tempfile.mkdtemp(prefix="android-", dir=RAIZ / "test/tmp"))
saida = tmp / "salvos"; saida.mkdir()
s3 = tmp / "s3"
comum = (AQUI / "comum.js").read_text()

def abrir(rotulo, roteiro, dados, chave, extra="", tempo=90):
    arq = tmp / "roteiro.js"
    consts = f"const CHAVE = {json.dumps(chave)}; const SAIDA = {json.dumps(str(saida))}; const PASTA_SYNC = '';{extra}\n"
    arq.write_text(comum + "\n" + consts + (AQUI / roteiro).read_text())
    env = dict(os.environ, FINTRIX_DADOS=str(dados), FINTRIX_CHAVE=chave, FINTRIX_TESTE=str(arq), FINTRIX_SALVAR_EM=str(saida))
    try:
        r = subprocess.run([str(APP)], env=env, capture_output=True, text=True, timeout=tempo)
        cod, texto = r.returncode, r.stdout + r.stderr
    except subprocess.TimeoutExpired as e:
        cod, texto = None, (e.stdout or b"").decode() + "\n(tempo esgotado: o roteiro não chamou teste_fim)"
    finally:
        arq.unlink(missing_ok=True)
    texto = "\n".join(l for l in texto.splitlines() if l.strip() and "Locale not supported" not in l and "fallback 'C' locale" not in l)
    print(f"--- {rotulo}\n{texto}")
    check(f"{rotulo} terminou bem", cod, 0)

servidor = subprocess.Popen([sys.executable, str(RAIZ / "test/s3_local.py"), str(s3), str(PORTA)], stderr=subprocess.DEVNULL)
try:
    time.sleep(1)
    urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{PORTA}/fintrix-teste", method="PUT"))
    subprocess.run(["adb", "reverse", f"tcp:{PORTA}", f"tcp:{PORTA}"], check=True, capture_output=True)

    dados, chave = tmp / "app", secrets.token_hex(32)
    abrir("computador: dados de exemplo", "fase1.js", dados, chave)
    print("\n>>> No celular: apresentação › Parear com outro aparelho › Ler QR code, e aponte para a tela do computador.")
    print(">>> Depois, lance no celular a despesa \"Farmácia do celular\" de R$ 45,00.\n", flush=True)
    abrir("computador: QR code e espera o celular", "android-a.js", dados, chave, extra=f" const S3_ENDPOINT = 'http://127.0.0.1:{PORTA}';", tempo=400)

    check("cofre tem os dois aparelhos", len(list(s3.rglob("estado/*.bin"))), 2)
    vazou = [str(p.relative_to(tmp)) for p in s3.rglob("*") if p.is_file() and any(s in p.read_bytes() for s in SEGREDOS)]
    check("arquivos do cofre com dados em claro", vazou, [])
finally:
    servidor.terminate()
    subprocess.run(["adb", "reverse", "--remove", f"tcp:{PORTA}"], capture_output=True)
    shutil.rmtree(tmp, ignore_errors=True)

print("\nRESULTADO: " + ("TUDO CERTO" if not falhas else f"{len(falhas)} falha(s): {', '.join(falhas)}"))
sys.exit(1 if falhas else 0)
