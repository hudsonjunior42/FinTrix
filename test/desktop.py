"""Testa o app desktop (Tauri) pela interface, com dados em pastas temporárias e sem tocar no chaveiro real.

1. primeira abertura: cria conta, lança uma despesa com comprovante, guarda uma cópia automática e salva um
   backup pela tela de Configurações; confere fontes locais e a política de conteúdo (test/desktop/fase1.js)
2. reabre: dados, comprovante e cópia voltam do SQLite cifrado; mostra a chave de recuperação (fase2.js)
3. reabre sem a chave no chaveiro: o app pede a chave, recusa a errada e abre com a certa (sem-chave.js)
4. reabre com a chave errada no chaveiro: o app não mostra os dados e pede a chave
5. outro "computador" (pasta e chave novas): restaura o backup da etapa 1 (restaurar.js)
6. sincronização por uma pasta: o aparelho A liga e gera o código (sync-a1.js); o aparelho B, novo, entra
   pela apresentação, recebe tudo e lança uma despesa (sync-b.js); o A reabre e recebe a despesa (sync-a2.js)
7. a pasta de dados é só do usuário (700) e nenhum arquivo dela, nem do cofre, tem os textos lançados em claro

Precisa de tela (X11/Wayland). Rode da raiz: python3 test/desktop.py
"""
import json, os, pathlib, secrets, shutil, stat, subprocess, sys, tempfile

RAIZ = pathlib.Path(__file__).resolve().parents[1]
AQUI = RAIZ / "test" / "desktop"
CARGO = shutil.which("cargo") or str(pathlib.Path.home() / ".cargo/bin/cargo")
APP = RAIZ / "target/debug/fintrix"
SEGREDOS = (b"Supermercado", b"Nubank", b"COMPROVANTE-SEGREDO", b"recibo.pdf")

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
tmp = pathlib.Path(tempfile.mkdtemp(prefix="desktop-", dir=RAIZ / "test/tmp"))
saida = tmp / "salvos"; saida.mkdir()
cofre = tmp / "cofre"  # a "pasta sincronizada" que os dois aparelhos compartilham
comum = (AQUI / "comum.js").read_text()

def abrir(rotulo, roteiro, dados, chave_chaveiro, chave_real, extra=""):
    """Abre o app com o roteiro; chave_chaveiro é o que o "chaveiro" tem (vazio = nada), chave_real vai para o roteiro."""
    arq = tmp / "roteiro.js"
    consts = f"const CHAVE = {json.dumps(chave_real)}; const SAIDA = {json.dumps(str(saida))}; const PASTA_SYNC = {json.dumps(str(cofre))};{extra}\n"
    arq.write_text(comum + "\n" + consts + (AQUI / roteiro).read_text())
    env = dict(os.environ, FINTRIX_DADOS=str(dados), FINTRIX_CHAVE=chave_chaveiro, FINTRIX_TESTE=str(arq), FINTRIX_SALVAR_EM=str(saida))
    try:
        r = subprocess.run([str(APP)], env=env, capture_output=True, text=True, timeout=90)
        cod, texto = r.returncode, r.stdout + r.stderr
    except subprocess.TimeoutExpired as e:
        cod, texto = None, (e.stdout or b"").decode() + "\n(tempo esgotado: o roteiro não chamou teste_fim)"
    finally:
        arq.unlink(missing_ok=True)
    texto = "\n".join(l for l in texto.splitlines() if l.strip() and "Locale not supported" not in l and "fallback 'C' locale" not in l)
    print(f"--- {rotulo}\n{texto}")
    check(f"{rotulo} terminou bem", cod, 0)

try:
    dados, chave = tmp / "app", secrets.token_hex(32)
    abrir("fase1", "fase1.js", dados, chave, chave)
    abrir("fase2", "fase2.js", dados, chave, chave)
    abrir("sem chave no chaveiro", "sem-chave.js", dados, "", chave)
    abrir("chave errada no chaveiro", "sem-chave.js", dados, secrets.token_hex(32), chave)

    backups = sorted(saida.glob("*.json"))
    check("backup salvo pelo app", len(backups), 1)
    if backups:
        nova = secrets.token_hex(32)
        abrir("restaurar em outro computador", "restaurar.js", tmp / "outro", nova, nova,
              extra=f" const BACKUP = {json.dumps(backups[0].read_text())};")

    abrir("sincronização: A liga", "sync-a1.js", dados, chave, chave)
    codigo = (saida / "codigo.txt").read_text() if (saida / "codigo.txt").exists() else ""
    chave_b = secrets.token_hex(32)
    abrir("sincronização: B entra e lança", "sync-b.js", tmp / "aparelho-b", chave_b, chave_b, extra=f" const CODIGO = {json.dumps(codigo)};")
    abrir("sincronização: A recebe", "sync-a2.js", dados, chave, chave)

    check("pasta de dados só do usuário", oct(stat.S_IMODE(dados.stat().st_mode)), "0o700")
    check("banco cifrado (cabeçalho)", (dados / "fintrix.db").read_bytes()[:15] == b"SQLite format 3", False)
    # nada do que foi digitado pode aparecer em claro nos arquivos do app (o backup salvo de propósito fica fora)
    check("cofre tem os dois aparelhos", len(list(cofre.rglob("estado/*.bin"))), 2)
    vazou = sorted(str(f.relative_to(tmp)) for d in (dados, tmp / "outro", tmp / "aparelho-b", cofre) for f in d.rglob("*")
                   if f.is_file() and any(t in f.read_bytes() for t in SEGREDOS))
    check("arquivos com dados em claro", vazou, [])
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\nRESULTADO:", "TUDO CERTO" if not falhas else f"{len(falhas)} falha(s): {falhas}")
sys.exit(1 if falhas else 0)
