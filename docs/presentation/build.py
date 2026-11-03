"""Собрать презентацию из исходников (deck.json + slides/*.html) в один HTML-файл.

Запуск: python docs/presentation/build.py
Результат: docs/presentation/idea.html и docs/presentation/defense.html — открываются в браузере
без сервера; листание стрелками ← → или пробелом, F — полный экран.
"""

import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DECKS = ("idea", "defense")

TEMPLATE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="{fonts}">
<style>
  html, body {{ margin: 0; height: 100%; background: #0d0e13; overflow: hidden; }}
  #stage {{ position: absolute; left: 50%; top: 50%; width: 1920px; height: 1080px; transform-origin: 0 0; }}
  section {{ position: absolute; inset: 0; box-sizing: border-box; }}
  /* у слайдов display задан в style, поэтому скрывать неактивные можно только через !important */
  section:not(.active) {{ display: none !important; }}
  section aside {{ display: none; }}
  section h1, section h2, section h3, section p, section ul, section ol {{ margin: 0; }}
  section table {{ border-collapse: collapse; }}
  section th, section td {{ text-align: left; border-bottom: 1px solid rgba(128, 128, 128, .3); }}
  #counter {{ position: fixed; right: 16px; bottom: 12px; color: #8a90a0; font: 14px sans-serif; }}
</style>
</head>
<body>
<div id="stage">
{slides}
</div>
<div id="counter"></div>
<script>
  const slides = [...document.querySelectorAll("#stage > section")];
  const stage = document.getElementById("stage");
  let current = 0;
  function fit() {{
    const scale = Math.min(innerWidth / 1920, innerHeight / 1080);
    stage.style.transform = `scale(${{scale}}) translate(-50%, -50%)`;
  }}
  function show(i) {{
    current = Math.max(0, Math.min(slides.length - 1, i));
    slides.forEach((s, n) => s.classList.toggle("active", n === current));
    document.getElementById("counter").textContent = `${{current + 1}} / ${{slides.length}}`;
    location.hash = current + 1;
  }}
  addEventListener("resize", fit);
  addEventListener("keydown", (e) => {{
    if (["ArrowRight", "PageDown", " "].includes(e.key)) show(current + 1);
    if (["ArrowLeft", "PageUp"].includes(e.key)) show(current - 1);
    if (e.key === "f") document.documentElement.requestFullscreen?.();
  }});
  addEventListener("click", (e) => show(current + (e.clientX > innerWidth / 2 ? 1 : -1)));
  fit();
  show((parseInt(location.hash.slice(1), 10) || 1) - 1);
</script>
</body>
</html>
"""


def build(name: str) -> Path:
    folder = HERE / name
    deck = json.loads((folder / "deck.json").read_text(encoding="utf-8"))
    slides = "\n".join(
        (folder / "slides" / f"{slide_id}.html").read_text(encoding="utf-8") for slide_id in deck["order"]
    )
    fonts = next(iter(deck["faces"].values()))["href"]
    out = HERE / f"{name}.html"
    out.write_text(TEMPLATE.format(title=html.escape(deck["title"]), fonts=fonts, slides=slides), encoding="utf-8")
    return out


if __name__ == "__main__":
    for deck_name in DECKS:
        print(build(deck_name))
