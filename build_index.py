#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera index.html (la portada) y catalogo.json a partir de los HTML de semanas/.

La portada tiene dos partes:
  1. Un buscador de articulos con filtros (tema, tipo de estudio, revista,
     periodo y destacados). Los articulos se leen de las fichas de cada
     semana: no hay que mantener ninguna lista a mano.
  2. El listado de todas las semanas, lo mas reciente arriba.

Si una semana no se puede leer, sale en el listado igualmente y el resto de la
portada se construye: un archivo raro nunca impide publicar la web.

Uso: python build_index.py
No necesita instalar nada (solo libreria estandar de Python).
"""
import os
import re
import glob
import html
import json
import datetime
import unicodedata

SEMANAS_DIR = "semanas"
SALIDA = "index.html"
CATALOGO = "catalogo.json"
INDICE = "indice.json"  # texto completo de cada ficha, lo carga el buscador

MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio",
         "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

# Vocabulario: categorias, tipos de articulo y palabras clave. Es copia del de
# la skill html-articulos-semanal (reference/vocabulario.json): si cambia alli,
# se copia aqui. El orden de las listas es el orden en pantalla.
VOCABULARIO = "vocabulario.json"
# Reclasificacion a mano de fichas ya publicadas, por "archivo#id". Manda
# sobre lo que diga el HTML de la semana. Sirve para las semanas anteriores
# al vocabulario actual y para corregir una ficha sin rehacer su semana.
CLASIFICACION = "clasificacion.json"


def cargar_json(ruta, defecto):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return defecto


VOC = cargar_json(VOCABULARIO, {"areas": [], "tipos": [], "claves": []})
AREAS = [(a[0], a[1]) for a in VOC["areas"]]
TIPOS = [(t[0], t[1]) for t in VOC["tipos"]]
CLAVES = [(grupo, [(k, n) for k, n in lista]) for grupo, lista in VOC["claves"]]
IDS_CLAVE = {k for _, lista in CLAVES for k, _ in lista}

# Areas del vocabulario anterior que pasan a una del actual cuando la ficha
# no esta en clasificacion.json. Solo es el ultimo recurso.
AREA_ANTIGUA = {"vihits": "vih", "vih-its": "vih", "huesped": "sindromes"}

TIPO_ALIAS = {"comentario": "editorial", "carta": "editorial"}
REVISTA_ALIAS = {"CMI Communications": "CMI Commun"}

# Semanas antiguas: el tipo no venia marcado y se deduce del diseno escrito.
# Se aplica de arriba abajo; gana la primera regla que encaja.
REGLAS_TIPO = [
    (r"emulaci|anidad", "cohorte"),
    (r"posici|position|consenso|statement|gu[ií]a|delphi", "guia"),
    (r"editorial|coment|commentary|perspectiv|correspondencia|carta|opini", "editorial"),
    (r"revisi|review|metaan|meta-an", "revision"),
    (r"caso|casos", "caso"),
    (r"ensayo|eca\b|ecas\b|aleatoriz", "ensayo"),
    (r"diagn|precisi|concordancia", "diagnostico"),
    (r"modeliz|simulaci", "modelizacion"),
    (r"brote", "brote"),
    (r"gen[oó]mic|inmunol|wgs|in vitro", "microbiologico"),
    (r"cohorte|observacional|retrospectiv|prospectiv|registro|longitudinal", "cohorte"),
]


# ---------------------------------------------------------------- utilidades

def texto(fragmento):
    """HTML a texto plano de una linea."""
    t = re.sub(r"<(script|style)\b.*?</\1>", " ", fragmento or "", flags=re.S | re.I)
    t = re.sub(r"<br\s*/?>|</p>|</li>|</span>\s*<span>|<ul[^>]*>", " ", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = html.unescape(t).replace(" ", " ")
    return re.sub(r"\s+", " ", t).strip()


def primero(patron, s, grupo=1, flags=re.S | re.I):
    m = re.search(patron, s or "", flags)
    return m.group(grupo) if m else ""


def recorta(t, n=260):
    """Recorta en el ultimo final de frase antes de n caracteres."""
    if len(t) <= n:
        return t
    corte = t[:n]
    p = corte.rfind(". ")
    if p > n * 0.5:
        return corte[:p + 1]
    return corte[:corte.rfind(" ")].rstrip(",;:") + "…"


def palabras(t):
    """Palabras unicas, sin tildes y en minusculas, para el buscador."""
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    vistas, out = set(), []
    for w in re.findall(r"[a-z0-9]{3,}", t):
        if w not in vistas:
            vistas.add(w)
            out.append(w)
    return " ".join(out)


def fecha_de_nombre(nombre):
    m = re.search(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})", nombre)
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def tipo_de_diseno(diseno):
    d = (diseno or "").lower()
    for patron, tipo in REGLAS_TIPO:
        if re.search(patron, d):
            return tipo
    return "estudio"


def tipo_de_ficha(raw, diseno):
    raw = (raw or "").strip().lower()
    raw = TIPO_ALIAS.get(raw, raw)
    if raw in dict(TIPOS):
        return raw
    if raw:
        return "estudio"
    return tipo_de_diseno(diseno)


# ---------------------------------------------------------------- lectura

def leer_cita(bloque):
    cita = primero(r'<span class="cite">(.*?)</span>\s*(?:</span>\s*)?(?:<span class="(?:lead|smeta|verficha)"|</summary>)', bloque)
    if not cita:
        cita = primero(r'<span class="cite">(.*)', bloque)
    revista = texto(primero(r'<span class="jr">(.*?)</span>', cita))
    autor = texto(primero(r'<span class="au">(.*?)</span>', cita))
    if not autor:
        antes = cita.split('<span class="jr">')[0]
        autor = texto(re.sub(r"<a\b.*?</a>", "", antes, flags=re.S))
    despues = cita.split("</span>", 1)[1] if '<span class="jr">' in cita else ""
    despues = cita[cita.find('<span class="jr">'):] if '<span class="jr">' in cita else cita
    despues = re.sub(r'^<span class="jr">.*?</span>', "", despues, flags=re.S)
    despues = texto(re.sub(r"<a\b.*?</a>", "", despues, flags=re.S))
    ref = primero(r"^(.*?\.)(?:\s|$)", despues) or despues
    titulo = texto(primero(r"<b>(.*?)</b>", cita)).strip("«» ")
    if not titulo:
        titulo = html.unescape(primero(r'<a [^>]*title="([^"]*)"', cita))
    doi = primero(r'href="https?://(?:dx\.)?doi\.org/([^"]+)"', cita)
    anio = primero(r"\b(20\d{2}|19\d{2})\b", ref) or primero(r"\b(20\d{2})\b", texto(cita))
    autores = [x.strip() for x in autor.rstrip(" .").split(",") if x.strip()]
    if len(autores) > 3 and not any("et al" in x for x in autores):
        autor = autores[0] + ", et al"
    # en la portada basta con ano, volumen y paginas; el resto vive en la ficha
    vol = primero(r"\b((?:19|20)\d{2}\s*;\s*[^\s,(]+(?:\([^)]*\))?[^\s,]*)", ref)
    ref = vol.rstrip(".") if vol else (primero(r"\b((?:19|20)\d{2})\b", ref) or ref)
    if "no consta" in titulo.lower():
        titulo = ""
    revista = REVISTA_ALIAS.get(revista, revista)
    return {
        "autor": autor.rstrip(" ."),
        "revista": revista,
        "ref": ref.strip(),
        "titulo": titulo,
        "doi": html.unescape(doi),
        "anio": int(anio) if anio else None,
    }


def leer_fichas(s, archivo):
    """Devuelve (areas, fichas) de una semana."""
    marcas = []
    for m in re.finditer(r'<h2 class="area" id="([^"]+)"[^>]*>(.*?)</h2>', s, re.S):
        marcas.append((m.start(), "area", m))
    for m in re.finditer(r'<details class="ficha"([^>]*)>', s):
        marcas.append((m.start(), "ficha", m))
    marcas.sort(key=lambda x: x[0])

    areas, fichas = [], []
    area_id, orden = "", 0
    for i, (pos, clase, m) in enumerate(marcas):
        if clase == "area":
            area_id = m.group(1)
            titular = texto(re.sub(r'<span class="n">.*?</span>', "", m.group(2), flags=re.S))
            areas.append({"id": area_id, "titular": titular, "n": 0})
            continue
        fin = marcas[i + 1][0] if i + 1 < len(marcas) else len(s)
        bloque = s[pos:fin]
        attrs = m.group(1)
        fid = primero(r'\bid="([^"]+)"', attrs)
        resumen_html = bloque.split("</summary>", 1)[0]
        destacada = ('data-star="1"' in attrs) or ('class="star"' in resumen_html)
        resumen_html = re.sub(r'<span class="star"[^>]*>.*?</span>', "", resumen_html, flags=re.S)
        pregunta = texto(primero(r'<span class="(?:stitle )?q">(.*?)</span>\s*<span class="cite">', resumen_html)) \
            or texto(primero(r'class="(?:stitle q|q)">(.*?)</span>', resumen_html))
        diseno = texto(primero(r'<span class="mtxt">(.*?)</span>', bloque)).split("·")[0].strip()
        cierre = primero(r'data-sec="cierre"[^>]*>.*?<div class="secbody">\s*<p>(.*?)</p>', bloque)
        if not cierre:
            cierre = primero(r'data-sec="cierre"[^>]*>.*?<div class="secbody">(.*?)</div>', bloque)
        if not cierre:
            cierre = primero(r'<div class="close">\s*<span class="lbl">.*?</span>(.*?)</div>', bloque)
        if not cierre:
            cierre = primero(r'<span class="lead">(.*?)<span class="smeta"', bloque) \
                or primero(r'<span class="lead">(.*?)</summary>', bloque)
        cita = leer_cita(resumen_html)
        if not pregunta:
            continue
        orden += 1
        if areas:
            areas[-1]["n"] += 1
        fichas.append({
            "id": fid,
            "semana": archivo,
            "orden": orden,
            "area": area_id or "otros",
            "tipo": tipo_de_ficha(primero(r'data-tipo="([^"]*)"', attrs), diseno),
            "claves": [k for k in primero(r'data-claves="([^"]*)"', attrs).split() if k in IDS_CLAVE],
            "diseno": diseno,
            "pregunta": pregunta,
            "autor": cita["autor"],
            "revista": cita["revista"],
            "ref": cita["ref"],
            "titulo": cita["titulo"],
            "doi": cita["doi"],
            "anio": cita["anio"],
            "destacada": destacada,
            "quedarse": recorta(texto(cierre)),
            "_texto": palabras(texto(re.sub(r"<svg\b.*?</svg>", " ", bloque, flags=re.S))),
        })
    return areas, fichas


def leer_semana(ruta):
    with open(ruta, encoding="utf-8") as f:
        s = f.read()
    nombre = os.path.basename(ruta)
    item = {
        "archivo": nombre,
        "titulo": texto(primero(r"<title>(.*?)</title>", s)) or "Resumen semanal",
        "sub": texto(primero(r'<p class="sub"[^>]*>(.*?)</p>', s)),
        "fecha": fecha_de_nombre(nombre),
        "areas": [],
        "fichas": [],
        "error": "",
    }
    try:
        item["areas"], item["fichas"] = leer_fichas(s, nombre)
    except Exception as e:  # una semana rara no impide publicar
        item["error"] = str(e)
    return item


# ---------------------------------------------------------------- portada

def esc(t):
    return html.escape(t or "", quote=True)


def etiqueta_fecha(item):
    if item["sub"]:
        return item["sub"]
    f = item["fecha"]
    if f:
        return "Semana del %d de %s de %d" % (f[2], MESES[f[1]], f[0])
    return item["titulo"]


def nombre_area(aid, titulares):
    corto = dict(AREAS)
    corto["otros"] = "Sin clasificar"
    return corto.get(aid) or titulares.get(aid) or aid


def tarjeta_semana(item, titulares, ultima=False):
    n = len(item["fichas"])
    dest = sum(1 for f in item["fichas"] if f["destacada"])
    partes = []
    if n:
        partes.append("%d artículo%s" % (n, "" if n == 1 else "s"))
    if dest:
        partes.append("%d destacado%s" % (dest, "" if dest == 1 else "s"))
    meta = " · ".join(partes)
    chips = "".join(
        '<span class="chip">%s <b>%d</b></span>' % (esc(nombre_area(a["id"], titulares)), a["n"])
        for a in item["areas"] if a["n"])
    return (
        '<a class="card top week%s" href="semanas/%s">'
        '%s<span class="wdate">%s</span>'
        '<span class="wmeta">%s</span>'
        '<span class="chips">%s</span>'
        '<span class="go">Abrir la semana</span></a>'
        % (" last" if ultima else "", esc(item["archivo"]),
           '<span class="lbl">Última semana</span>' if ultima else "",
           esc(etiqueta_fecha(item)), esc(meta), chips))


def construir():
    rutas = glob.glob(os.path.join(SEMANAS_DIR, "*.html"))
    items = [leer_semana(p) for p in rutas]
    items.sort(key=lambda it: (it["fecha"] is not None, it["fecha"] or (0, 0, 0),
                               it["archivo"]), reverse=True)

    titulares = {}
    for it in reversed(items):  # el titular mas reciente manda
        for a in it["areas"]:
            titulares[a["id"]] = a["titular"]

    semanas, articulos, indice = [], [], {}
    clasif = cargar_json(CLASIFICACION, {})
    ids_area = {a for a, _ in AREAS}
    for k, it in enumerate(items):
        f = it["fecha"]
        iso = "%04d-%02d-%02d" % f if f else ""
        semanas.append({"archivo": it["archivo"], "etiqueta": etiqueta_fecha(it),
                        "fecha": iso, "n": len(it["fichas"])})
        for fi in it["fichas"]:
            fi = dict(fi)
            clave = fi["semana"] + "#" + fi["id"]
            indice[clave] = fi.pop("_texto")
            manual = clasif.get(clave)
            if manual:
                fi["area"] = manual.get("area", fi["area"])
                fi["tipo"] = manual.get("tipo", fi["tipo"])
                fi["claves"] = [k for k in manual.get("claves", []) if k in IDS_CLAVE]
            fi["area"] = AREA_ANTIGUA.get(fi["area"], fi["area"])
            if fi["area"] not in ids_area:
                fi["area"] = "otros"
            fi["fecha"] = iso
            fi["k"] = k
            articulos.append(fi)

    presentes = {a["area"] for a in articulos}
    areas = [{"id": aid, "nombre": nom} for aid, nom in AREAS if aid in presentes]
    if "otros" in presentes:
        areas.append({"id": "otros", "nombre": "Sin clasificar"})
    usadas = {k for a in articulos for k in a["claves"]}
    claves = [{"grupo": g, "claves": [{"id": k, "nombre": n} for k, n in lista if k in usadas]}
              for g, lista in CLAVES]
    claves = [g for g in claves if g["claves"]]
    # recuento por area de cada semana con la clasificacion vigente
    por_semana = {}
    for a in articulos:
        por_semana.setdefault(a["semana"], {}).setdefault(a["area"], 0)
        por_semana[a["semana"]][a["area"]] += 1
    orden = [a["id"] for a in areas]
    for it in items:
        c = por_semana.get(it["archivo"], {})
        it["areas"] = [{"id": k, "n": c[k]} for k in orden if c.get(k)]
    tipos_presentes = {a["tipo"] for a in articulos}
    tipos = [{"id": t, "nombre": n} for t, n in TIPOS if t in tipos_presentes]

    datos = {
        "generado": datetime.date.today().isoformat(),
        "semanas": semanas,
        "areas": areas,
        "tipos": tipos,
        "claves": claves,
        "articulos": articulos,
    }

    ultima = tarjeta_semana(items[0], titulares, ultima=True) if items else \
        '<p class="empty">Aún no hay resúmenes. Sube un HTML a la carpeta semanas/.</p>'
    tarjetas = "\n".join(tarjeta_semana(it, titulares) for it in items[1:])

    n_sem, n_art = len(items), len(articulos)
    frase = "%d semana%s · %d artículo%s" % (
        n_sem, "" if n_sem == 1 else "s", n_art, "" if n_art == 1 else "s")

    json_txt = json.dumps(datos, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    pagina = (PLANTILLA
              .replace("{{FRASE}}", esc(frase))
              .replace("{{N_ART}}", str(n_art))
              .replace("{{ULTIMA}}", ultima)
              .replace("{{TARJETAS}}", tarjetas)
              .replace("{{LOGO}}", LOGO)
              .replace("{{DATA}}", json_txt))
    return pagina, datos, indice


LOGO = ("data:image/png;base64,"
        "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")

PLANTILLA = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Selección semanal de artículos de enfermedades infecciosas &middot; HCUZ</title>
<meta name="description" content="Selección y resumen semanal de artículos de enfermedades infecciosas del Servicio de EE.II. del HCU Lozano Blesa, con buscador por tema, tipo de estudio, revista y fecha.">
<link rel="icon" type="image/png" href="{{LOGO}}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Roboto+Condensed:wght@400;500;700&family=Source+Sans+3:ital,wght@0,400;0,600;0,700;1,400&display=swap" rel="stylesheet">
<style>
:root{
  --page:#f6f6f6; --card:#fff; --sunken:#eceeef; --line:#e1e4e3; --hair:#eef0ef;
  --ink-strong:#1f2524; --ink:#3b4140; --muted:#636b6a;
  --brand:#028174; --brand-solid:#028174; --brand-ink:#01665b; --brand-deep:#0f433c; --brand-tint:#e2f0ee;
  --on-brand:#fff;
  --accent:#f8772b; --accent-tint:#feeadd; --accent-ink:#a8460a;
  --mark:#ffe3c7;
  --focus:#12a594; --r:8px;
  --shadow:0 1px 2px rgba(15,23,25,.06),0 2px 8px rgba(15,23,25,.05);
  --f-head:"Roboto Condensed","Arial Narrow",Arial,sans-serif;
  --f-body:"Source Sans 3","Segoe UI",Roboto,Arial,sans-serif;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --page:#16181a; --card:#1f2224; --sunken:#26292c; --line:#34393c; --hair:#2b2f31;
  --ink-strong:#f2f3f3; --ink:#d9dcdc; --muted:#a2a9ab;
  --brand:#34c9b5; --brand-solid:#00756a; --brand-ink:#5fd8c8; --brand-deep:#0c2a26; --brand-tint:#123a34;
  --accent:#f0854a; --accent-tint:#3a2a18; --accent-ink:#f3ad78; --mark:#5a3d1c;
  --shadow:0 1px 2px rgba(0,0,0,.3);
}}
:root[data-theme="dark"]{
  --page:#16181a; --card:#1f2224; --sunken:#26292c; --line:#34393c; --hair:#2b2f31;
  --ink-strong:#f2f3f3; --ink:#d9dcdc; --muted:#a2a9ab;
  --brand:#34c9b5; --brand-solid:#00756a; --brand-ink:#5fd8c8; --brand-deep:#0c2a26; --brand-tint:#123a34;
  --accent:#f0854a; --accent-tint:#3a2a18; --accent-ink:#f3ad78; --mark:#5a3d1c;
  --shadow:0 1px 2px rgba(0,0,0,.3);
}
*{box-sizing:border-box}
[hidden]{display:none!important}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}
body{margin:0;background:var(--page);color:var(--ink);font:17px/1.55 var(--f-body)}
h1,h2,h3,button,select,.lbl,.chip,.pill{font-family:var(--f-head)}
a{color:var(--brand-ink)}
.in{max-width:1100px;margin:0 auto;padding:0 24px}

/* cabecera */
.band{background:var(--brand-solid);color:#fff;padding:26px 0 30px}
.band .in{display:grid;grid-template-columns:auto 1fr auto;gap:18px 22px;align-items:center}
.logo{width:76px;height:76px;border-radius:50%;background:#fff;padding:4px;box-shadow:0 0 0 2px rgba(255,255,255,.35)}
.logo img{width:100%;height:100%;display:block}
.band .lbl{color:rgba(255,255,255,.8)}
.band h1{margin:4px 0 4px;font-size:32px;line-height:1.12;color:#fff;font-weight:700}
.band .scope{margin:0;color:rgba(255,255,255,.88);font-size:16px}
.band .scope b{font-weight:700;color:#fff}
.theme{align-self:start;background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.35);color:#fff;border-radius:999px;min-height:40px;padding:6px 14px;font:600 14px var(--f-head);cursor:pointer}
.theme:hover{background:rgba(255,255,255,.24)}

.lbl{font-size:12px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--brand-ink)}
.nota{margin:22px 0 0;font-size:15px;color:var(--muted);line-height:1.5}
.nota p{margin:0 0 6px}
.nota b{color:var(--accent-ink)}

.sec-h{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 12px;margin:36px 0 14px}
.sec-h .n{font:600 12px var(--f-head);color:var(--muted)}
.sec-h h2{margin:0;font-size:20px;letter-spacing:.08em;text-transform:uppercase;color:var(--brand-ink)}
.sec-h .scope{margin-left:auto;font-size:14px;color:var(--muted)}

.card{background:var(--card);border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--shadow)}
.card.top{border-top:3px solid var(--brand)}

/* buscador */
.panel{padding:18px 20px 16px}
.qbox{position:relative}
.qbox svg{position:absolute;left:14px;top:50%;width:20px;height:20px;margin-top:-10px;fill:none;stroke:var(--muted);stroke-width:2}
#q{width:100%;min-height:52px;border:2px solid var(--line);border-radius:999px;background:var(--card);color:var(--ink-strong);font:18px var(--f-body);padding:10px 18px 10px 44px}
#q:focus{outline:none;border-color:var(--brand)}
.frow{display:grid;grid-template-columns:96px 1fr;gap:6px 12px;align-items:start;margin-top:14px}
.frow>.lbl{padding-top:9px;color:var(--muted)}
.pills{display:flex;flex-wrap:wrap;gap:6px}
.pill{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);background:var(--card);color:var(--ink-strong);border-radius:999px;min-height:36px;padding:5px 13px;font-size:14.5px;font-weight:500;cursor:pointer}
.pill .c{font-weight:700;color:var(--muted);font-variant-numeric:tabular-nums}
.pill[aria-pressed="true"]{background:var(--brand-solid);border-color:var(--brand-solid);color:#fff}
.pill[aria-pressed="true"] .c{color:rgba(255,255,255,.85)}
.pill:disabled{opacity:.4;cursor:default}
.pill.star-t[aria-pressed="true"]{background:var(--accent);border-color:var(--accent);color:#1f1206}
.pill.star-t svg{width:14px;height:14px;fill:var(--accent)}
.pill.star-t[aria-pressed="true"] svg{fill:#1f1206}
.sels{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
select{min-height:36px;border:1px solid var(--line);border-radius:999px;background:var(--card);color:var(--ink-strong);font-size:14.5px;padding:5px 30px 5px 13px;max-width:100%;appearance:none;-webkit-appearance:none;
 background-image:linear-gradient(45deg,transparent 50%,var(--muted) 50%),linear-gradient(135deg,var(--muted) 50%,transparent 50%);background-position:calc(100% - 17px) 55%,calc(100% - 12px) 55%;background-size:5px 5px;background-repeat:no-repeat;cursor:pointer}
select.on{border-color:var(--brand);color:var(--brand-ink);font-weight:700}
.resumen{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center;justify-content:space-between;margin-top:16px;padding-top:12px;border-top:1px solid var(--hair)}
.resumen .vivo{font:600 15px var(--f-head);color:var(--ink-strong)}
.lnk{background:none;border:0;color:var(--brand-ink);font:700 14px var(--f-head);text-decoration:underline;cursor:pointer;padding:8px 0}
.hint{font-size:13.5px;color:var(--muted)}

/* resultados */
.res{margin-top:14px;padding:4px 20px}
.art{display:block;padding:16px 0;border-bottom:1px solid var(--hair)}
.art:last-child{border-bottom:0}
.art h3{margin:0 0 4px;font:600 18px/1.35 var(--f-body);color:var(--ink-strong)}
.art h3 a{color:inherit;text-decoration:none}
.art h3 a:hover{color:var(--brand-ink);text-decoration:underline}
.art .st{display:inline-block;width:16px;height:16px;margin-right:5px;vertical-align:-2px;fill:var(--accent)}
.art .cite{font-size:14.5px;color:var(--muted)}
.art .cite i{font-style:italic}
.art .kq{margin:8px 0 0;font-size:15.5px;color:var(--ink);padding-left:12px;border-left:3px solid var(--brand-tint)}
.art .kq .k{font:700 12px var(--f-head);letter-spacing:.08em;text-transform:uppercase;color:var(--brand-ink);margin-right:6px}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px;align-items:center}
.chip{display:inline-flex;align-items:center;gap:4px;border-radius:999px;padding:2px 10px;font-size:13px;font-weight:500;background:var(--sunken);color:var(--ink)}
.chip.a{background:var(--brand-tint);color:var(--brand-ink);font-weight:700}
.chip b{font-weight:700}
.chip.ft{background:var(--mark);color:var(--ink-strong)}
.art .wk{font-size:13px;color:var(--muted);text-decoration:none;margin-left:auto}
.art .wk:hover{text-decoration:underline;color:var(--brand-ink)}
/* revista: desplegable con casillas */
.dd{position:relative}
.dd>summary{list-style:none;display:inline-flex;align-items:center;gap:6px;min-height:36px;border:1px solid var(--line);border-radius:999px;background:var(--card);color:var(--ink-strong);font:500 14.5px var(--f-head);padding:5px 30px 5px 13px;cursor:pointer;
 background-image:linear-gradient(45deg,transparent 50%,var(--muted) 50%),linear-gradient(135deg,var(--muted) 50%,transparent 50%);background-position:calc(100% - 17px) 55%,calc(100% - 12px) 55%;background-size:5px 5px;background-repeat:no-repeat}
.dd>summary::-webkit-details-marker{display:none}
.dd.on>summary{border-color:var(--brand);color:var(--brand-ink);font-weight:700}
.ddp{position:absolute;z-index:20;top:calc(100% + 6px);left:0;width:min(340px,86vw);max-height:340px;overflow:auto;background:var(--card);border:1px solid var(--line);border-radius:var(--r);box-shadow:0 8px 24px rgba(0,0,0,.14);padding:6px 6px 2px}
.opt{display:flex;align-items:center;gap:10px;min-height:40px;padding:4px 8px;border-radius:6px;cursor:pointer;font-size:14.5px;color:var(--ink-strong)}
.opt:hover{background:var(--sunken)}
.opt input{width:18px;height:18px;accent-color:var(--brand-solid);margin:0}
.opt .c{margin-left:auto;font-weight:700;color:var(--muted);font-variant-numeric:tabular-nums}
.opt.off{opacity:.45;cursor:default}
.ddp .lnk{padding:8px}
/* palabras clave */
.kwbox{position:relative}
.kwin{display:flex;flex-wrap:wrap;gap:6px;align-items:center;min-height:42px;border:1px solid var(--line);border-radius:22px;background:var(--card);padding:4px 6px}
.kwin:focus-within{border-color:var(--brand);box-shadow:0 0 0 1px var(--brand)}
#kw{flex:1 1 200px;min-width:160px;border:0;outline:0;background:transparent;color:var(--ink-strong);font:15.5px var(--f-body);padding:6px 8px}
.kwsel{display:contents}
.tag{display:inline-flex;align-items:center;gap:6px;border:0;border-radius:999px;background:var(--brand-solid);color:#fff;font:600 14px var(--f-head);min-height:32px;padding:4px 8px 4px 12px;cursor:pointer}
.tag span{font-size:17px;line-height:1;opacity:.85}
.kwsug{position:absolute;z-index:20;left:0;right:0;top:calc(100% + 4px);max-width:520px;background:var(--card);border:1px solid var(--line);border-radius:var(--r);box-shadow:0 8px 24px rgba(0,0,0,.14);padding:4px}
.sug{display:flex;align-items:baseline;gap:8px;width:100%;min-height:40px;border:0;background:none;text-align:left;padding:8px 10px;border-radius:6px;font:15px var(--f-body);color:var(--ink-strong);cursor:pointer}
.sug.act,.sug:hover{background:var(--brand-tint)}
.sug .c{font-weight:700;color:var(--muted)}
.sug .g{margin-left:auto;font-size:12.5px;color:var(--muted)}
.sug:disabled{opacity:.45;cursor:default}
.kwsug .nada{padding:10px;font-size:14px;color:var(--muted)}
.kwall{margin-top:8px}
.kwall>summary{list-style:none;cursor:pointer;font:700 14px var(--f-head);color:var(--brand-ink);text-decoration:underline;padding:4px 0}
.kwall>summary::-webkit-details-marker{display:none}
.kg{margin-top:10px}.kg .lbl{display:block;margin-bottom:6px;color:var(--muted);font-size:11px}
.pill.sm{min-height:32px;font-size:13.5px;padding:3px 11px}
.chip.k{border:1px solid var(--line);background:var(--card);cursor:pointer;font-family:var(--f-head)}
.chip.k:hover{border-color:var(--brand);color:var(--brand-ink)}
mark{background:var(--mark);color:inherit;padding:0 2px;border-radius:3px}
.mas{display:flex;justify-content:center;padding:14px 0 18px}
.btn{border:1px solid var(--brand);background:var(--card);color:var(--brand-ink);border-radius:999px;min-height:44px;padding:8px 22px;font:700 15px var(--f-head);cursor:pointer}
.btn:hover{background:var(--brand-tint)}
.vacio{padding:26px 0;text-align:center;color:var(--muted)}

/* semanas */
.weeks{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(min(100%,320px),1fr))}
.week{display:flex;flex-direction:column;gap:6px;padding:16px 18px;text-decoration:none;color:inherit;transition:box-shadow .15s,transform .15s}
.week:hover{box-shadow:0 6px 18px rgba(2,129,116,.16);transform:translateY(-1px)}
.week.last{border-top-color:var(--accent);padding:18px 22px}
.week.last .lbl{color:var(--accent-ink)}
.wdate{font:700 20px/1.2 var(--f-head);color:var(--ink-strong)}
.week.last .wdate{font-size:24px}
.wmeta{font-size:14.5px;color:var(--muted)}
.week .chips{display:flex;flex-wrap:wrap;gap:5px;margin-top:2px}
.week .chip{font-size:12.5px}
.go{margin-top:auto;padding-top:6px;font:700 14.5px var(--f-head);color:var(--brand-ink)}
.go::after{content:" \203A"}
.empty{color:var(--muted);background:var(--card);border:1px dashed var(--line);border-radius:var(--r);padding:22px;text-align:center}

footer{margin:44px 0 0;padding:22px 0 40px;border-top:1px solid var(--line);font-size:14px;color:var(--muted)}
footer p{margin:0 0 6px}
:focus-visible{outline:2px solid var(--focus);outline-offset:2px}

@media (max-width:720px){
  .in{padding:0 16px}
  .band{padding:18px 0 22px}
  .band .in{grid-template-columns:auto 1fr;gap:12px 14px}
  .logo{width:56px;height:56px;padding:3px}
  .band h1{font-size:24px}
  .band .scope{grid-column:1/-1;font-size:15px}
  .theme{grid-column:2;justify-self:end;grid-row:1}
  .band .tit{grid-column:1/-1}
  .frow{grid-template-columns:1fr;gap:6px}
  .pills{flex-wrap:nowrap;overflow-x:auto;margin:0 -14px;padding:0 14px 4px;scrollbar-width:none}
  .pills::-webkit-scrollbar{display:none}
  .pill{flex:none}
  .kg .pills{flex-wrap:wrap;margin:0;padding:0}
  .frow>.lbl{padding-top:0}
  .panel,.res{padding-left:14px;padding-right:14px}
  .art h3{font-size:17px}
  .art .wk{margin-left:0;flex-basis:100%}
  .sec-h .scope{margin-left:0;flex-basis:100%}
}
@media print{
  .theme,#buscar,.nota{display:none!important}
  body{background:#fff}.band{background:#fff;color:#000}.band h1,.band .lbl,.band .scope{color:#000}
  .card{box-shadow:none;break-inside:avoid}
}
</style>
</head>
<body>
<header class="band">
 <div class="in">
  <div class="logo"><img src="{{LOGO}}" alt="Hospital Clínico Universitario Lozano Blesa" width="68" height="68"></div>
  <div class="tit">
   <div class="lbl">EE.II. · HCUZ · Formación continuada</div>
   <h1>Selección semanal de artículos de enfermedades infecciosas</h1>
   <p class="scope">Servicio de Enfermedades Infecciosas · <b>{{FRASE}}</b></p>
  </div>
  <button class="theme" type="button" id="tema" hidden>Modo oscuro</button>
 </div>
</header>

<main class="in">
 <div class="nota">
  <p>Revisamos la tabla de contenidos y los artículos en prensa de algunas de las principales revistas de enfermedades infecciosas y seleccionamos lo que nos parece interesante. La síntesis y los resúmenes se elaboran con inteligencia artificial (Claude); nosotros supervisamos y corregimos.</p>
  <p>No nos responsabilizamos si los artículos no te resultan interesantes o los resúmenes contienen errores. <b>¡Es gratis!</b></p>
 </div>

 <section id="ultima">
  <div class="sec-h"><span class="n">01</span><h2>Esta semana</h2><span class="scope">El último resumen publicado</span></div>
  {{ULTIMA}}
 </section>

 <section id="buscar" hidden>
  <div class="sec-h"><span class="n">02</span><h2>Buscar artículos</h2><span class="scope">Entre los {{N_ART}} artículos de todas las semanas</span></div>
  <div class="card top panel">
   <div class="qbox">
    <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg>
    <input id="q" type="search" placeholder="Palabra, fármaco, microorganismo, autor…" aria-label="Buscar en los artículos" autocomplete="off">
   </div>
   <div class="frow"><span class="lbl" id="l-area">Categoría</span><div class="pills" id="f-area" role="group" aria-labelledby="l-area"></div></div>
   <div class="frow"><span class="lbl" id="l-kw">Palabra clave</span><div class="kwbox">
     <div class="kwin"><div id="kw-sel" class="kwsel"></div><input id="kw" type="text" placeholder="Escribe: neumonía, inmunodeprimido, S. aureus…" aria-labelledby="l-kw" autocomplete="off" role="combobox" aria-controls="kw-sug" aria-autocomplete="list"></div>
     <div id="kw-sug" class="kwsug" role="listbox" hidden></div>
     <details class="kwall"><summary>Ver todas las palabras clave</summary><div id="kw-todas"></div></details>
   </div></div>
   <div class="frow"><span class="lbl" id="l-tipo">Tipo</span><div class="pills" id="f-tipo" role="group" aria-labelledby="l-tipo"></div></div>
   <div class="frow"><span class="lbl">Más</span><div class="sels">
     <details class="dd" id="dd-rev"><summary>Revista <span id="rev-n"></span></summary><div class="ddp"><div id="rev-lista"></div><button class="lnk" type="button" id="rev-borrar">Todas las revistas</button></div></details>
     <select id="f-per" aria-label="Periodo"></select>
     <button class="pill star-t" type="button" id="f-est" aria-pressed="false"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 1.7l3.1 6.6 7.2.9-5.3 4.9 1.4 7.2-6.4-3.6-6.4 3.6 1.4-7.2L1.7 9.2l7.2-.9z"/></svg>Solo destacados</button>
   </div></div>
   <div class="resumen"><span class="vivo" id="vivo" aria-live="polite"></span><span><button class="lnk" type="button" id="copiar">Copiar enlace a esta búsqueda</button><span id="limpiar-w"> · <button class="lnk" type="button" id="limpiar">Limpiar</button></span></span></div>
  </div>
  <div class="card res" id="res"></div>
  <p class="hint">En categoría, tipo y revista puedes marcar varias: salen los artículos de cualquiera de ellas. Las palabras clave se suman: neumonía e inmunodeprimido no VIH trae los que tienen las dos. Toca una palabra clave de un resultado para filtrar por ella. Cada resultado abre la ficha dentro de su semana.</p>
 </section>

 <section id="semanas">
  <div class="sec-h"><span class="n" id="n-sem">02</span><h2>Semanas anteriores</h2><span class="scope">La más reciente, arriba</span></div>
  <div class="weeks">
{{TARJETAS}}
  </div>
 </section>

 <footer>
  <p>Los artículos provienen del cribado de las tablas de contenido y los artículos en prensa de las revistas de la especialidad y generalistas, de redes sociales y de lo que comparten los miembros del servicio. Un facultativo del servicio hace la selección; Claude redacta los resúmenes a partir del texto completo.</p>
  <p><b>Todo lo que empuje a cambiar la práctica debe revisarse en la fuente original.</b> Material docente orientativo. Portada generada automáticamente.</p>
 </footer>
</main>

<script type="application/json" id="data">{{DATA}}</script>
<script>
(function(){
"use strict";
var DATA; try{ DATA=JSON.parse(document.getElementById('data').textContent); }catch(e){ return; }
var $=function(s,r){return (r||document).querySelector(s)};
var ART=DATA.articulos||[];
if(!ART.length) return;

var store=(function(){try{localStorage.setItem('__p','1');localStorage.removeItem('__p');return{
 get:function(k){try{return localStorage.getItem(k)}catch(e){return null}},
 set:function(k,v){try{localStorage.setItem(k,v)}catch(e){}}};}catch(e){return{get:function(){return null},set:function(){}}}})();

/* tema claro u oscuro */
var root=document.documentElement, bt=$('#tema');
var th=store.get('hcuz-portada-tema'); if(th) root.dataset.theme=th;
function esOscuro(){return root.dataset.theme? root.dataset.theme==='dark' : matchMedia('(prefers-color-scheme:dark)').matches;}
function rotulo(){bt.textContent=esOscuro()?'Modo claro':'Modo oscuro';}
bt.hidden=false; rotulo();
bt.addEventListener('click',function(){root.dataset.theme=esOscuro()?'light':'dark';store.set('hcuz-portada-tema',root.dataset.theme);rotulo();});

/* utilidades */
var norm=function(s){return (s||'').normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase();};
var esc=function(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});};
var MES=['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre'];
var AREA={},TIPO={},SEM={},CLAVE={};
DATA.areas.forEach(function(a){AREA[a.id]=a.nombre;});
DATA.tipos.forEach(function(t){TIPO[t.id]=t.nombre;});
DATA.semanas.forEach(function(s){SEM[s.archivo]=s;});
(DATA.claves||[]).forEach(function(g){g.claves.forEach(function(k){CLAVE[k.id]={nombre:k.nombre,grupo:g.grupo};});});
var STAR='<svg class="st" viewBox="0 0 24 24" aria-label="Destacado" role="img"><path d="M12 1.7l3.1 6.6 7.2.9-5.3 4.9 1.4 7.2-6.4-3.6-6.4 3.6 1.4-7.2L1.7 9.2l7.2-.9z"/></svg>';

ART.forEach(function(a){
 a.claves=a.claves||[];
 a._h=norm([a.pregunta,a.titulo,a.autor,a.revista,a.diseno,a.quedarse,AREA[a.area],TIPO[a.tipo],a.doi].concat(a.claves.map(function(k){return CLAVE[k]?CLAVE[k].nombre:k;})).join(' '));
 a._mes=(a.fecha||'').slice(0,7);
});

/* periodos, por mes de la seleccion */
var ultima=DATA.semanas.length?DATA.semanas[0].fecha:'';
function menosDias(iso,d){var t=new Date(iso+'T12:00:00');t.setDate(t.getDate()-d);return t.toISOString().slice(0,10);}
var PER=[{id:'',n:'Cualquier fecha'}];
if(ultima){PER.push({id:'1m',n:'Último mes',desde:menosDias(ultima,31)});PER.push({id:'3m',n:'Últimos 3 meses',desde:menosDias(ultima,92)});}
var meses=[];ART.forEach(function(a){if(a._mes&&meses.indexOf(a._mes)<0)meses.push(a._mes);});
meses.sort().reverse().forEach(function(m){PER.push({id:m,n:MES[+m.slice(5,7)-1].replace(/^./,function(c){return c.toUpperCase()})+' '+m.slice(0,4),mes:m});});
$('#f-per').innerHTML=PER.map(function(p){return '<option value="'+p.id+'">'+esc(p.n)+'</option>';}).join('');

/* revistas por frecuencia */
var rc={};ART.forEach(function(a){if(a.revista)rc[a.revista]=(rc[a.revista]||0)+1;});
var REV=Object.keys(rc).sort(function(x,y){return rc[y]-rc[x]||x.localeCompare(y);});

/* estado: dentro de tema, tipo y revista vale cualquiera de las marcadas;
   las palabras clave se suman (neumonia y ademas inmunodeprimido) */
var PASO=10;
function vacio(){return{q:'',area:[],tipo:[],rev:[],clave:[],per:'',est:false,ver:PASO};}
var state=vacio();
function lista(v,validos){return (v||'').split(',').filter(function(x){return x&&validos(x);});}
function leerHash(){var p=new URLSearchParams(location.hash.slice(1));state=vacio();
 state.q=p.get('q')||'';
 state.area=lista(p.get('tema'),function(x){return AREA[x];});
 state.tipo=lista(p.get('tipo'),function(x){return TIPO[x];});
 state.clave=lista(p.get('clave'),function(x){return CLAVE[x];});
 state.rev=(p.get('revista')||'').split('|').filter(function(x){return rc[x];});
 state.per=p.get('periodo')||'';if(!PER.some(function(x){return x.id===state.per}))state.per='';
 state.est=p.get('destacados')==='1';}
function escribirHash(){var p=new URLSearchParams();
 if(state.q)p.set('q',state.q);if(state.area.length)p.set('tema',state.area.join(','));
 if(state.tipo.length)p.set('tipo',state.tipo.join(','));if(state.clave.length)p.set('clave',state.clave.join(','));
 if(state.rev.length)p.set('revista',state.rev.join('|'));if(state.per)p.set('periodo',state.per);if(state.est)p.set('destacados','1');
 var h=p.toString();history.replaceState(null,'',h?'#'+h:location.pathname+location.search);}

function pasa(a,salvo){
 var terms=norm(state.q).split(/\s+/).filter(Boolean);
 for(var i=0;i<terms.length;i++) if(a._h.indexOf(terms[i])<0) return false;
 if(salvo!=='area'&&state.area.length&&state.area.indexOf(a.area)<0) return false;
 if(salvo!=='tipo'&&state.tipo.length&&state.tipo.indexOf(a.tipo)<0) return false;
 if(salvo!=='rev'&&state.rev.length&&state.rev.indexOf(a.revista)<0) return false;
 for(var j=0;j<state.clave.length;j++) if(a.claves.indexOf(state.clave[j])<0) return false;
 if(state.est&&!a.destacada) return false;
 if(state.per){var p=PER.filter(function(x){return x.id===state.per})[0];
  if(p&&p.mes&&a._mes!==p.mes) return false;
  if(p&&p.desde&&a.fecha<p.desde) return false;}
 return true;
}
function contar(campo,fn){var c={};ART.forEach(function(a){if(pasa(a,campo))(fn?fn(a):[a[campo]]).forEach(function(k){c[k]=(c[k]||0)+1;});});return c;}
function quita(arr,v){var i=arr.indexOf(v);if(i>=0)arr.splice(i,1);else arr.push(v);}

function pills(el,items,campo){
 var c=contar(campo),tot=0;Object.keys(c).forEach(function(k){tot+=c[k];});
 var h='<button class="pill" type="button" data-v="" aria-pressed="'+(!state[campo].length)+'">Todos <span class="c">'+tot+'</span></button>';
 items.forEach(function(x){var n=c[x.id]||0,on=state[campo].indexOf(x.id)>=0;
  h+='<button class="pill" type="button" data-v="'+x.id+'" aria-pressed="'+on+'"'+(!n&&!on?' disabled':'')+'>'+esc(x.nombre)+' <span class="c">'+n+'</span></button>';});
 el.innerHTML=h;
}

function revistas(){
 var c=contar('rev',function(a){return [a.revista];});
 $('#rev-lista').innerHTML=REV.map(function(r){var on=state.rev.indexOf(r)>=0,n=c[r]||0;
  return '<label class="opt'+(!n&&!on?' off':'')+'"><input type="checkbox" value="'+esc(r)+'"'+(on?' checked':'')+(!n&&!on?' disabled':'')+'><span>'+esc(r)+'</span><span class="c">'+n+'</span></label>';}).join('');
 $('#rev-n').textContent=state.rev.length?'('+state.rev.length+')':'';
 $('#dd-rev').classList.toggle('on',!!state.rev.length);
}

/* palabras clave: autocompletado y lista completa */
function sugerir(){
 var t=norm($('#kw').value.trim()),box=$('#kw-sug');
 if(!t){box.hidden=true;box.innerHTML='';return;}
 var c=contar('clave',function(a){return a.claves;});
 var r=Object.keys(CLAVE).filter(function(k){return state.clave.indexOf(k)<0&&norm(CLAVE[k].nombre).indexOf(t)>=0;})
  .sort(function(x,y){return (c[y]||0)-(c[x]||0);}).slice(0,8);
 box.innerHTML=r.length?r.map(function(k,i){var n=c[k]||0;
  return '<button type="button" role="option" class="sug'+(i===0?' act':'')+'" data-k="'+k+'"'+(n?'':' disabled')+'>'+esc(CLAVE[k].nombre)+' <span class="c">'+n+'</span><span class="g">'+esc(CLAVE[k].grupo)+'</span></button>';}).join('')
  :'<div class="nada">Ninguna palabra clave contiene «'+esc($('#kw').value)+'». Prueba el buscador de texto de arriba.</div>';
 box.hidden=false;
}
function addClave(k){if(k&&CLAVE[k]&&state.clave.indexOf(k)<0){state.clave.push(k);}$('#kw').value='';sugerir();cambia();}
function claves(){
 $('#kw-sel').innerHTML=state.clave.map(function(k){return '<button type="button" class="tag" data-k="'+k+'" aria-label="Quitar '+esc(CLAVE[k].nombre)+'">'+esc(CLAVE[k].nombre)+'<span aria-hidden="true">×</span></button>';}).join('');
 var c=contar('clave',function(a){return a.claves;});
 $('#kw-todas').innerHTML=(DATA.claves||[]).map(function(g){
  return '<div class="kg"><span class="lbl">'+esc(g.grupo)+'</span><div class="pills">'+g.claves.map(function(k){var n=c[k.id]||0,on=state.clave.indexOf(k.id)>=0;
   return '<button class="pill sm" type="button" data-k="'+k.id+'" aria-pressed="'+on+'"'+(!n&&!on?' disabled':'')+'>'+esc(k.nombre)+' <span class="c">'+n+'</span></button>';}).join('')+'</div></div>';}).join('');
}

function marca(t){
 var terms=norm(state.q).split(/\s+/).filter(function(x){return x.length>1;});
 var s=esc(t); if(!terms.length) return s;
 var n=norm(s), out='', i=0;
 if(n.length!==s.length) return s;
 var re=new RegExp(terms.map(function(x){return x.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');}).join('|'),'g'),m;
 while((m=re.exec(n))){ if(m[0].length===0){re.lastIndex++;continue;}
  var a=m.index,b=a+m[0].length;
  if(s.slice(a,b).indexOf('&')>=0) continue;
  out+=s.slice(i,a)+'<mark>'+s.slice(a,b)+'</mark>'; i=b; }
 return out+s.slice(i);
}
function fuera(a){
 var terms=norm(state.q).split(/\s+/).filter(Boolean); if(!terms.length) return false;
 var v=norm([a.pregunta,a.autor,a.revista,a.quedarse].join(' '));
 return terms.some(function(x){return v.indexOf(x)<0;});
}
function tarjeta(a){
 var sem=SEM[a.semana]||{};
 var href='semanas/'+encodeURIComponent(a.semana)+(a.id?'#'+encodeURIComponent(a.id):'');
 var cita=(a.autor?esc(a.autor)+'. ':'')+(a.revista?'<i>'+esc(a.revista)+'</i> ':'')+esc(a.ref||(a.anio||''));
 return '<article class="art"><h3>'+(a.destacada?STAR:'')+'<a href="'+href+'">'+marca(a.pregunta)+'</a></h3>'+
  '<div class="cite">'+cita+(a.doi?' · <a href="https://doi.org/'+esc(a.doi)+'" target="_blank" rel="noopener">DOI</a>':'')+'</div>'+
  (a.quedarse?'<p class="kq"><span class="k">Con qué quedarse</span>'+marca(a.quedarse)+'</p>':'')+
  '<div class="tags">'+(fuera(a)?'<span class="chip ft">En el texto de la ficha</span>':'')+
  '<span class="chip a">'+esc(AREA[a.area]||a.area)+'</span><span class="chip">'+esc(TIPO[a.tipo]||a.tipo)+'</span>'+
  a.claves.map(function(k){return CLAVE[k]?'<button type="button" class="chip k" data-k="'+k+'" title="Filtrar por esta palabra clave">'+esc(CLAVE[k].nombre)+'</button>':'';}).join('')+
  '<a class="wk" href="semanas/'+encodeURIComponent(a.semana)+'">Semana: '+esc(sem.etiqueta||a.semana)+'</a></div></article>';
}

function render(){
 pills($('#f-area'),DATA.areas,'area');
 pills($('#f-tipo'),DATA.tipos,'tipo');
 revistas(); claves();
 if($('#q').value!==state.q) $('#q').value=state.q;
 $('#f-per').value=state.per;$('#f-per').classList.toggle('on',!!state.per);
 $('#f-est').setAttribute('aria-pressed',state.est);
 var r=ART.filter(function(a){return pasa(a);});
 r.sort(function(x,y){return x.k-y.k||x.orden-y.orden;});
 var partes=[];
 if(state.area.length)partes.push(state.area.map(function(x){return AREA[x];}).join(' o '));
 if(state.tipo.length)partes.push(state.tipo.map(function(x){return TIPO[x].toLowerCase();}).join(' o '));
 if(state.clave.length)partes.push(state.clave.map(function(x){return CLAVE[x].nombre;}).join(' y '));
 if(state.rev.length)partes.push(state.rev.join(' o '));
 if(state.per)partes.push(PER.filter(function(x){return x.id===state.per})[0].n.toLowerCase());
 if(state.est)partes.push('destacados');
 if(state.q)partes.push('«'+state.q+'»');
 $('#vivo').textContent=r.length+(r.length===1?' artículo':' artículos')+(partes.length?' · '+partes.join(' · '):' · los más recientes primero');
 $('#limpiar-w').hidden=!partes.length;
 var el=$('#res');
 if(!r.length){el.innerHTML='<div class="vacio">Ningún artículo cumple todo a la vez. Prueba a quitar un filtro o una palabra clave.</div>';return;}
 el.innerHTML=r.slice(0,state.ver).map(tarjeta).join('')+
  (r.length>state.ver?'<div class="mas"><button class="btn" type="button" id="mas">Ver '+Math.min(PASO,r.length-state.ver)+' más (quedan '+(r.length-state.ver)+')</button></div>':'');
 var m=$('#mas'); if(m) m.addEventListener('click',function(){state.ver+=PASO;render();});
}
function cambia(){state.ver=PASO;escribirHash();render();}

function botonera(sel,campo){$(sel).addEventListener('click',function(e){var b=e.target.closest('button');if(!b||b.disabled)return;
 if(!b.dataset.v)state[campo]=[];else quita(state[campo],b.dataset.v);cambia();});}
botonera('#f-area','area');botonera('#f-tipo','tipo');
$('#rev-lista').addEventListener('change',function(e){if(e.target.type==='checkbox'){quita(state.rev,e.target.value);cambia();}});
$('#rev-borrar').addEventListener('click',function(){state.rev=[];cambia();});
document.addEventListener('click',function(e){var d=$('#dd-rev');if(d.open&&!d.contains(e.target))d.open=false;
 var s=$('#kw-sug');if(!s.hidden&&!e.target.closest('.kwbox'))s.hidden=true;});
$('#f-per').addEventListener('change',function(){state.per=this.value;cambia();});
$('#f-est').addEventListener('click',function(){state.est=!state.est;cambia();});
var t;$('#q').addEventListener('input',function(){var v=this.value;clearTimeout(t);t=setTimeout(function(){state.q=v.trim();cambia();},150);});
$('#kw').addEventListener('input',sugerir);
$('#kw').addEventListener('focus',sugerir);
$('#kw').addEventListener('keydown',function(e){
 var bs=[].slice.call($('#kw-sug').querySelectorAll('.sug:not([disabled])')),i=bs.findIndex(function(b){return b.classList.contains('act');});
 if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();if(!bs.length)return;if(i>=0)bs[i].classList.remove('act');i=(i+(e.key==='ArrowDown'?1:-1)+bs.length)%bs.length;bs[i].classList.add('act');}
 else if(e.key==='Enter'){e.preventDefault();if(bs.length)addClave((bs[i>=0?i:0]).dataset.k);}
 else if(e.key==='Escape'){$('#kw-sug').hidden=true;}
 else if(e.key==='Backspace'&&!this.value&&state.clave.length){state.clave.pop();cambia();}});
$('#kw-sug').addEventListener('click',function(e){var b=e.target.closest('.sug');if(b&&!b.disabled)addClave(b.dataset.k);});
$('#kw-sel').addEventListener('click',function(e){var b=e.target.closest('.tag');if(b){quita(state.clave,b.dataset.k);cambia();}});
$('#kw-todas').addEventListener('click',function(e){var b=e.target.closest('.pill');if(b&&!b.disabled){quita(state.clave,b.dataset.k);cambia();}});
$('#res').addEventListener('click',function(e){var b=e.target.closest('.chip.k');if(b){if(state.clave.indexOf(b.dataset.k)<0)state.clave.push(b.dataset.k);cambia();$('#buscar').scrollIntoView({behavior:'smooth'});}});
$('#limpiar').addEventListener('click',function(){state=vacio();cambia();$('#q').focus();});
$('#copiar').addEventListener('click',function(){var b=this,u=location.href,ok=function(){var o=b.textContent;b.textContent='Enlace copiado';setTimeout(function(){b.textContent=o;},1600);};
 var fb=function(){var a=document.createElement('textarea');a.value=u;a.style.position='fixed';a.style.opacity='0';document.body.appendChild(a);a.select();try{document.execCommand('copy');ok();}catch(e){}a.remove();};
 navigator.clipboard?navigator.clipboard.writeText(u).then(ok,fb):fb();});
window.addEventListener('hashchange',function(){leerHash();render();});

leerHash();
if(window.fetch&&location.protocol!=='file:'){
 fetch('indice.json').then(function(r){return r.ok?r.json():null;}).then(function(ix){
  if(!ix) return; ART.forEach(function(a){var t=ix[a.semana+'#'+a.id]; if(t) a._h+=' '+t;}); render();
 }).catch(function(){});
}
$('#buscar').hidden=false;$('#n-sem').textContent='03';
render();
})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    pagina, datos, indice = construir()
    with open(INDICE, "w", encoding="utf-8") as f:
        json.dump(indice, f, ensure_ascii=False, separators=(",", ":"))
    with open(SALIDA, "w", encoding="utf-8") as f:
        f.write(pagina)
    with open(CATALOGO, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
    print("index.html generado: %d semanas, %d artículos." % (
        len(datos["semanas"]), len(datos["articulos"])))
