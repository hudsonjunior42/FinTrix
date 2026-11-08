#!/usr/bin/env python3
"""Copia o app web (index.html e assets) para dist/tauri/, a pasta que o Tauri empacota.

Na cópia, o link do Google Fonts vira assets/fonts/fonts.css: o app desktop abre sem internet
e não faz nenhum pedido para fora (a política de conteúdo do tauri.conf.json bloqueia).
Rode da raiz do repositório. O Tauri chama este script sozinho (beforeBuildCommand/beforeDevCommand).
"""
import re
import shutil
from pathlib import Path

raiz = Path(__file__).resolve().parent.parent
saida = raiz / "dist" / "tauri"
shutil.rmtree(saida, ignore_errors=True)
saida.mkdir(parents=True)

html = (raiz / "index.html").read_text()
html, n = re.subn(r'<link rel="preconnect" href="https://fonts\.googleapis\.com">\s*'
                  r'<link rel="preconnect" href="https://fonts\.gstatic\.com" crossorigin>\s*'
                  r'<link rel="stylesheet" href="https://fonts\.googleapis\.com/[^"]*">',
                  '<link rel="stylesheet" href="assets/fonts/fonts.css">', html)
if n != 1:
    raise SystemExit("tauri_prep: não achei o link do Google Fonts no index.html; ajuste o padrão")
(saida / "index.html").write_text(html)
shutil.copytree(raiz / "assets", saida / "assets")
print(f"app web copiado para {saida}")
