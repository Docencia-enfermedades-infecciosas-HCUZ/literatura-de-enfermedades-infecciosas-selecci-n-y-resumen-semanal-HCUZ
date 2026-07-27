# Selección semanal de artículos · Infecciosas HCU Zaragoza

Web con la selección y síntesis semanal de artículos del Servicio de Enfermedades Infecciosas. Cada semana es un HTML autocontenido (lo genera la skill `seleccion-semanal-articulos`). La portada, con el listado de todas las semanas, se construye y publica sola.

## Qué hay aquí

- `semanas/` — un HTML por semana. Nombre con fecha: `resumen-AAAA-MM-DD.html`.
- `build_index.py` — construye la portada leyendo la carpeta `semanas/`. No hay que ejecutarlo a mano.
- `.github/workflows/deploy.yml` — automatización: al subir algo, reconstruye la portada y publica la web.

`index.html` (la portada) no está en el repositorio a propósito: se genera en cada publicación. No se edita a mano.

## Rutina de cada semana

1. Genera el HTML con la skill `seleccion-semanal-articulos`.
2. Súbelo a `semanas/` con el nombre `resumen-AAAA-MM-DD.html`.
3. Nada más. En 1-2 minutos la web se actualiza y la semana aparece arriba.

Puesta en marcha (una sola vez): ver `GUIA-paso-a-paso.md`.

## Aviso

Repositorio público: no subas datos de pacientes.
