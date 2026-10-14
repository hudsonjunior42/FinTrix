"""Gera backups sintéticos do FinTrix para testes (valores em centavos)."""
import json, random, datetime
def gerar(anos=(2022, 2026), por_mes=170, seed=1, versao=1):
    rnd = random.Random(seed)
    contas = {"a1": {"nome": "Nubank", "tipo": "corrente", "inicial": 150000, "cor": "#3987E5", "total": True, "arq": False, "ordem": 0},
              "a2": {"nome": "Inter", "tipo": "corrente", "inicial": 50000, "cor": "#D95926", "total": True, "arq": False, "ordem": 1},
              "a3": {"nome": "Tesouro", "tipo": "investimento", "inicial": 1000000, "cor": "#199E70", "total": False, "arq": False, "ordem": 2}}
    cartoes = {"k1": {"nome": "Nubank Roxo", "limite": 800000, "conta": "a1", "fech": 3, "venc": 10, "cor": "#9085E9", "arq": False},
               "k2": {"nome": "Inter Black", "limite": 500000, "conta": "a2", "fech": 25, "venc": 5, "cor": "#C2477A", "arq": False}}
    nomes_d = ["Moradia", "Alimentação", "Transporte", "Saúde", "Lazer", "Educação", "Compras", "Assinaturas", "Pets", "Viagem"]
    cats = {f"c{i}": {"nome": n, "tipo": "despesa", "cor": "#3987E5", "ordem": i, "grupo": "Essencial" if i < 4 else "Estilo de vida"} for i, n in enumerate(nomes_d)}
    cats.update({"r1": {"nome": "Salário", "tipo": "receita", "cor": "#2E9E4F", "ordem": 0}, "r2": {"nome": "Freelas", "tipo": "receita", "cor": "#2BA3B5", "ordem": 1}})
    cats["c1s"] = {"nome": "Mercado", "tipo": "despesa", "pai": "c1", "cor": "#3987E5", "ordem": 0}
    config = {"versao": versao, "criado": "2022-01-01T00:00:00Z", "anos": [], "contas": contas, "cartoes": cartoes, "categorias": cats,
              "tags": {"t1": {"nome": "viagem", "arq": False}}, "recorr": {}, "orc": {"c1": 120000, "c4": 40000}}
    L = []; n = 0
    def rid():
        nonlocal n; n += 1; return f"x{n:06d}{rnd.randrange(36**3):03x}"
    for y in range(anos[0], anos[1] + 1):
        for m in range(1, 13):
            comp = f"{y}-{m:02d}"
            L.append({"id": rid(), "tipo": "receita", "desc": "Salário", "valor": 650000, "data": f"{comp}-05", "comp": comp, "conta": "a1", "cartao": None, "cat": "r1", "pago": True, "tags": [], "obs": "", "criado": 1})
            for i in range(por_mes - 1):
                d = rnd.randint(1, 28); data = f"{comp}-{d:02d}"; r = rnd.random()
                cat = rnd.choice(list(c for c in cats if cats[c]["tipo"] == "despesa"))
                if r < .45:
                    L.append({"id": rid(), "tipo": "despesa", "desc": f"Compra {i}", "valor": rnd.randint(500, 30000), "data": data, "comp": comp, "conta": rnd.choice(["a1", "a2"]), "cartao": None, "cat": cat, "pago": True, "tags": ["t1"] if r < .02 else [], "obs": "", "criado": 1})
                elif r < .93:
                    k = rnd.choice(["k1", "k2"]); fech = cartoes[k]["fech"]
                    t = y * 12 + m - 1 + (1 if d >= fech else 0) + (1 if cartoes[k]["venc"] <= fech else 0)
                    fc = f"{t // 12}-{t % 12 + 1:02d}"
                    L.append({"id": rid(), "tipo": "despesa", "desc": f"Cartão {i}", "valor": rnd.randint(500, 20000), "data": data, "comp": fc, "conta": None, "cartao": k, "cat": cat, "pago": True, "tags": [], "obs": "", "criado": 1})
                elif r < .97:
                    L.append({"id": rid(), "tipo": "transf", "desc": "Transferência", "valor": rnd.randint(1000, 50000), "data": data, "comp": comp, "conta": "a1", "destino": "a2", "cartao": None, "cat": None, "pago": True, "tags": [], "obs": "", "criado": 1})
                else:
                    L.append({"id": rid(), "tipo": "receita", "desc": "Freela", "valor": rnd.randint(10000, 200000), "data": data, "comp": comp, "conta": "a2", "cartao": None, "cat": "r2", "pago": True, "tags": [], "obs": "", "criado": 1})
    config["anos"] = sorted({l["comp"][:4] for l in L})
    return {"app": "fintrix", "versao": versao, "exportado": "2026-10-12T12:00:00Z", "config": config, "lancamentos": L}
if __name__ == "__main__":
    import sys
    b = gerar(); json.dump(b, open(sys.argv[1] if len(sys.argv) > 1 else "grande.json", "w"))
    print(len(b["lancamentos"]))
