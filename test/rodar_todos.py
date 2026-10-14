"""Roda todos os testes de interface (test/ui) e mostra um resumo. Uso: python3 test/rodar_todos.py [--integracao]
Com --integracao, roda também v1.py, v11.py e pwa_v1.py (mais lentos)."""
import subprocess, sys, pathlib, time
AQUI = pathlib.Path(__file__).resolve().parent
testes = sorted((AQUI / "ui").glob("*.py"))
if "--integracao" in sys.argv: testes += [AQUI / n for n in ("v1.py", "v11.py", "pwa_v1.py")]
falhas = []
for t in testes:
    ini = time.time()
    r = subprocess.run([sys.executable, str(t)], cwd=t.parent, capture_output=True, text=True)
    saida = r.stdout + r.stderr
    ok = r.returncode == 0 and "FALHA" not in saida and "FALHOU" not in saida and "Traceback" not in saida \
        and (t.parent.name != "ui" or "RESULTADO: TUDO CERTO" in saida)
    print(f"{'ok   ' if ok else 'FALHA'} {t.relative_to(AQUI)}  ({time.time() - ini:.0f} s)")
    if not ok: falhas.append((t, saida))
for t, saida in falhas:
    print(f"\n===== {t.relative_to(AQUI)}"); print("\n".join(l for l in saida.splitlines() if any(k in l for k in ("FALHA", "FALHOU", "Error", "RESULTADO")))[-3000:])
print(f"\n{len(testes) - len(falhas)} de {len(testes)} arquivos sem falhas")
sys.exit(1 if falhas else 0)
