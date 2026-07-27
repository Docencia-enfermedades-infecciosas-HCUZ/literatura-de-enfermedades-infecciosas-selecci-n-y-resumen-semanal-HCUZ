#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera index.html (la portada) a partir de los HTML que haya en semanas/.
Lee de cada archivo el <title>, el subtitulo (.sub), el conteo (.count)
y la fecha (de su nombre de archivo) y monta un listado ordenado, lo mas
reciente arriba.

Uso: python build_index.py
No necesita instalar nada (solo libreria estandar de Python).
"""
import os
import re
import glob
import html

SEMANAS_DIR = "semanas"
SALIDA = "index.html"

MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio",
         "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def extraer(patron, texto):
    m = re.search(patron, texto, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else ""


def fecha_de_nombre(nombre):
    """Devuelve (a, m, d) a partir del nombre; None si no encuentra fecha."""
    m = re.search(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})", nombre)
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def leer_semana(ruta):
    with open(ruta, encoding="utf-8") as f:
        s = f.read()
    nombre = os.path.basename(ruta)
    titulo = extraer(r"<title>(.*?)</title>", s) or "Resumen semanal"
    sub = extraer(r'class="sub"[^>]*>(.*?)<', s)
    # linea secundaria opcional: .variant (skill actual) o .count (formato viejo)
    variant = extraer(r'class="variant"[^>]*>(.*?)<', s)
    count = extraer(r'class="count"[^>]*>(.*?)<', s)
    fecha = fecha_de_nombre(nombre)
    return {
        "archivo": nombre,
        "titulo": titulo,
        "sub": sub,
        "variant": variant,
        "count": count,
        "fecha": fecha,
    }


def etiqueta_fecha(item):
    """Texto principal de la tarjeta: usa .sub si existe; si no, la fecha."""
    if item["sub"]:
        return item["sub"]
    f = item["fecha"]
    if f:
        return "Semana del %d de %s de %d" % (f[2], MESES[f[1]], f[0])
    return item["titulo"]


def limpio(t):
    """Deshace entidades del origen y reescapa solo lo imprescindible.
    Evita el doble escapado (&middot; -> &amp;middot;)."""
    return html.escape(html.unescape(t or ""), quote=True)


def tarjeta(item):
    principal = limpio(etiqueta_fecha(item))
    # linea secundaria: variante si existe; si no, el conteo del formato viejo
    extra = limpio(item["variant"] or item["count"])
    href = "semanas/" + item["archivo"]
    extra_html = ('<p class="wtitle">%s</p>' % extra) if extra else ""
    return """  <a class="week" href="{href}">
   <div class="wtop">
    <span class="wdate">{principal}</span>
    <span class="go">Abrir &rarr;</span>
   </div>
   {extra_html}
  </a>""".format(href=href, principal=principal, extra_html=extra_html)


def construir():
    rutas = [p for p in glob.glob(os.path.join(SEMANAS_DIR, "*.html"))]
    items = [leer_semana(p) for p in rutas]
    # orden: por fecha descendente; los sin fecha, al final por nombre
    items.sort(key=lambda it: (it["fecha"] is not None, it["fecha"] or (0, 0, 0),
                               it["archivo"]), reverse=True)
    tarjetas = "\n".join(tarjeta(it) for it in items) or \
        '  <p class="empty">Aun no hay resumenes. Sube un HTML a la carpeta semanas/.</p>'
    n = len(items)
    frase = "1 resumen publicado" if n == 1 else ("%d resumenes publicados" % n)
    return PLANTILLA.format(frase=frase, tarjetas=tarjetas)


PLANTILLA = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Resumenes semanales &middot; Infecciosas HCU Zaragoza</title>
<style>
:root{{
 --bg:#FBF6EC; --card:#FFFFFF; --ink:#403829; --muted:#8F856F; --line:#E7DCC6;
 --terra:#C77E5D; --terra-soft:#F4DDD0; --terra-deep:#A85F40;
 --sage:#8FA875; --sage-soft:#E6ECD8; --sage-deep:#4D5B3A;
 --blue:#7E9DBE; --blue-soft:#DEE8F0; --blue-deep:#3F5D77;
}}
*{{box-sizing:border-box;}}
html,body{{margin:0;padding:0;}}
body{{font-family:"Avenir Next Condensed","Avenir Next","Avenir","Segoe UI",system-ui,sans-serif;
 background:var(--bg); color:var(--ink); line-height:1.5; font-size:20px; -webkit-font-smoothing:antialiased;}}
.wrap{{max-width:900px;margin:0 auto;padding:0 20px 80px;}}
header{{text-align:center;padding:44px 18px 6px;}}
header h1{{margin:0;font-size:38px;font-weight:700;letter-spacing:.3px;color:var(--terra-deep);line-height:1.1;}}
header .sub{{margin:9px 0 0;color:var(--muted);font-size:18px;}}
.lead{{color:var(--muted);font-size:17px;margin:22px 2px 6px;}}
a.week{{display:block;text-decoration:none;color:inherit;background:var(--card);
 border:1px solid var(--line);border-radius:18px;padding:18px 22px;margin:14px 0;
 box-shadow:0 1px 4px rgba(80,60,40,.06);transition:.15s;}}
a.week:hover{{border-color:var(--terra-soft);box-shadow:0 5px 16px rgba(199,126,93,.18);transform:translateY(-1px);}}
.wtop{{display:flex;align-items:baseline;justify-content:space-between;gap:12px;}}
.wdate{{font-size:22px;font-weight:700;color:var(--terra-deep);}}
.go{{font-size:15px;font-weight:700;color:var(--blue-deep);white-space:nowrap;}}
.wtitle{{margin:4px 0 0;font-size:16px;color:var(--ink);}}
.count{{margin:6px 0 0;font-size:14.5px;color:var(--muted);}}
.empty{{color:var(--muted);background:var(--card);border:1px dashed var(--line);
 border-radius:14px;padding:22px;text-align:center;}}
footer{{text-align:center;color:var(--muted);font-size:13px;padding:34px 0 0;}}
@media(max-width:560px){{ body{{font-size:18px;}} header h1{{font-size:29px;}} .wdate{{font-size:19px;}} }}
</style>
</head>
<body>
<header>
 <h1>Resumenes semanales</h1>
 <p class="sub">Enfermedades Infecciosas &middot; HCU Zaragoza</p>
</header>
<div class="wrap">
 <p class="lead">{frase}. El mas reciente, arriba.</p>

{tarjetas}

 <footer>Portada generada automaticamente. Material docente orientativo.</footer>
</div>
</body>
</html>
"""


if __name__ == "__main__":
    salida = construir()
    with open(SALIDA, "w", encoding="utf-8") as f:
        f.write(salida)
    print("index.html generado.")
