#!/usr/bin/env python3
"""Copia o app web (index.html e assets) para dist/tauri/, a pasta que o Tauri empacota.

Rode da raiz do repositório. O Tauri chama este script sozinho (beforeBuildCommand/beforeDevCommand).
"""
import shutil
from pathlib import Path

raiz = Path(__file__).resolve().parent.parent
saida = raiz / "dist" / "tauri"
shutil.rmtree(saida, ignore_errors=True)
saida.mkdir(parents=True)
shutil.copy2(raiz / "index.html", saida / "index.html")
shutil.copytree(raiz / "assets", saida / "assets")
print(f"app web copiado para {saida}")
