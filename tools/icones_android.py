#!/usr/bin/env python3
"""Ícones do app Android a partir de assets/logo.svg (precisa do rsvg-convert e do Pillow).

Gera em src-tauri/gen/android/app/src/main/res/:
- ícone adaptativo (Android 8+): fundo na cor do tema escuro do app e o logo dentro da área segura
  (o launcher recorta a camada de 108 dp em círculo, gota etc. e só garante os 66 dp do centro);
- camada monocromática para os ícones temáticos do Android 13+;
- ic_launcher.png e ic_launcher_round.png para launchers antigos (Android 7).

Uso: python3 tools/icones_android.py
"""
import pathlib
import subprocess
import tempfile

from PIL import Image, ImageDraw

RAIZ = pathlib.Path(__file__).resolve().parent.parent
RES = RAIZ / "src-tauri/gen/android/app/src/main/res"
FUNDO = (0x0E, 0x11, 0x17, 255)  # --bg do tema escuro em index.html
DENSIDADES = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}


def logo() -> Image.Image:
    with tempfile.TemporaryDirectory() as d:
        png = pathlib.Path(d) / "logo.png"
        subprocess.run(["rsvg-convert", "-h", "2048", str(RAIZ / "assets/logo.svg"), "-o", str(png)], check=True)
        im = Image.open(png).convert("RGBA")
        return im.crop(im.getbbox())


def no_centro(lado: int, marca: Image.Image, fracao: float, fundo=(0, 0, 0, 0)) -> Image.Image:
    """Quadrado de `lado` px com o logo centralizado, a maior medida dele ocupando `fracao` do lado."""
    escala = fracao * lado / max(marca.size)
    m = marca.resize((round(marca.width * escala), round(marca.height * escala)), Image.LANCZOS)
    im = Image.new("RGBA", (lado, lado), fundo)
    im.alpha_composite(m, ((lado - m.width) // 2, (lado - m.height) // 2))
    return im


def recortar(im: Image.Image, redondo: bool) -> Image.Image:
    """Recorte do ícone antigo: círculo, ou quadrado de cantos arredondados (com 4x de margem para suavizar)."""
    n = im.width * 4
    mascara = Image.new("L", (n, n), 0)
    d = ImageDraw.Draw(mascara)
    if redondo:
        d.ellipse((0, 0, n - 1, n - 1), fill=255)
    else:
        d.rounded_rectangle((0, 0, n - 1, n - 1), radius=n * 0.2, fill=255)
    out = im.copy()
    out.putalpha(mascara.resize(im.size, Image.LANCZOS))
    return out


def main() -> None:
    marca = logo()
    # silhueta branca: nos ícones temáticos o sistema usa só a transparência e pinta com a cor do tema
    mono = Image.new("RGBA", marca.size, (255, 255, 255, 0))
    mono.putalpha(marca.getchannel("A"))

    for nome, k in DENSIDADES.items():
        pasta = RES / f"mipmap-{nome}"
        pasta.mkdir(parents=True, exist_ok=True)
        camada = round(108 * k)  # camadas do ícone adaptativo: 108 dp
        # 0.48 de 108 dp ≈ 52 dp: com folga no círculo de 66 dp da área segura (os cantos do logo não encostam)
        no_centro(camada, marca, 0.48).save(pasta / "ic_launcher_foreground.png", optimize=True)
        no_centro(camada, mono, 0.48).save(pasta / "ic_launcher_monochrome.png", optimize=True)
        antigo = round(48 * k)  # ícone antigo: 48 dp, já com o fundo
        recortar(no_centro(antigo, marca, 0.66, FUNDO), redondo=False).save(pasta / "ic_launcher.png", optimize=True)
        recortar(no_centro(antigo, marca, 0.60, FUNDO), redondo=True).save(pasta / "ic_launcher_round.png", optimize=True)

    adaptativo = """<?xml version="1.0" encoding="utf-8"?>
<!-- gerado por tools/icones_android.py -->
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@color/ic_launcher_background" />
    <foreground android:drawable="@mipmap/ic_launcher_foreground" />
    <monochrome android:drawable="@mipmap/ic_launcher_monochrome" />
</adaptive-icon>
"""
    pasta = RES / "mipmap-anydpi-v26"
    pasta.mkdir(exist_ok=True)
    for nome in ("ic_launcher.xml", "ic_launcher_round.xml"):
        (pasta / nome).write_text(adaptativo, encoding="utf-8")
    cor = "#{:02X}{:02X}{:02X}".format(*FUNDO[:3])
    (RES / "values/ic_launcher_background.xml").write_text(
        f'<?xml version="1.0" encoding="utf-8"?>\n<resources>\n    <color name="ic_launcher_background">{cor}</color>\n</resources>\n',
        encoding="utf-8",
    )
    print(f"ícones gerados em {RES.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
