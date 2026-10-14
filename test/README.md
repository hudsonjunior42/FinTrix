# Testes

Os testes abrem o app num Chromium controlado pelo [Playwright](https://playwright.dev/python/) e conferem telas, cálculos e dados gravados. Nenhum teste usa dados reais: tudo é criado na hora ou gerado por `gerar.py`.

## Preparar (uma vez)

```bash
pip install -r test/requirements.txt
python3 -m playwright install chromium
```

Opcional: para os testes de interface usarem as mesmas fontes do app (sem isso, usam as fontes do sistema e as capturas ficam um pouco diferentes):

```bash
cd test/ui/fonts && npm install
```

## Rodar

```bash
python3 test/rodar_todos.py                # todos os testes de interface (alguns minutos)
python3 test/rodar_todos.py --integracao   # + v1.py, v11.py e pwa_v1.py
python3 test/ui/parcela_editar.py          # um arquivo só
```

Todos testam o `index.html` da raiz do repositório.

| Arquivo | O que cobre |
| --- | --- |
| `ui/run.py` | Fluxo principal: lançamentos, saldos, faturas. Os outros arquivos de `ui/` reaproveitam o começo dele. |
| `ui/fakedb.js` | Banco simulado no formato do claude.ai, carregado antes do app |
| `ui/*.py` | Uma funcionalidade por arquivo (gráficos, seleção múltipla, parcelas, fixas, datas, patrimônio…) |
| `v1.py` | Versão 1.0: segurança dos dados, restauração, migração, backup automático, 10 mil lançamentos |
| `v11.py` | Versão 1.1: orçamento com histórico, patrimônio e metas, comprovantes, importação de CSV e OFX |
| `regressao.py` | `python3 test/regressao.py antigo.html index.html` compara duas versões com a mesma base grande (saldos, faturas, relatórios, CSV) |
| `pwa_v1.py` | Pacote instalável: instalação, uso offline, aviso de versão nova |
| `gerar.py` | Gera backups sintéticos para os testes de integração |
| `mock_claude.js` | Outro banco simulado, usado pelos testes de integração |

As capturas de tela dos testes de interface ficam em `test/ui/shots/` e os arquivos temporários em `test/tmp/`. As duas pastas ficam fora do Git.
