# Montar la web paso a paso (sin saber nada de GitHub)

Todo se hace en el navegador. No hay que instalar nada ni usar la terminal. Al acabar tendrás una dirección web pública que se actualiza sola cada semana. Tiempo: unos 15 minutos la primera vez.

Vocabulario mínimo:
- **Repositorio ("repo")**: la carpeta de tu proyecto en GitHub.
- **Commit**: guardar un cambio. Cada vez que subes algo, haces un commit.
- **GitHub Pages**: el servicio que convierte tu repo en una web.
- **Action**: un robot que, al subir tú un archivo, reconstruye la portada y publica la web.

---

## Paso 1. Crear una cuenta

1. Entra en https://github.com
2. **Sign up**. Pon tu correo, una contraseña y un nombre de usuario (ese nombre saldrá en la dirección de la web, elígelo con calma; por ejemplo `infecciosas-hcuz`).
3. Confirma el correo que te llega.

## Paso 2. Crear el repositorio

1. Arriba a la derecha, pulsa el **+** → **New repository**.
2. **Repository name**: `resumenes-infecciosas`
3. Marca **Public**.
4. NO marques "Add a README file".
5. **Create repository**.

Quedas en una página con instrucciones para gente que usa terminal. Ignórala: vamos por el navegador.

## Paso 3. Encender GitHub Pages en modo automático

1. Arriba, pestaña **Settings**.
2. Menú izquierdo: **Pages**.
3. En **Source** (o "Build and deployment"), elige **GitHub Actions**.

No hay que guardar nada más ni tocar permisos. Esto es lo que evita el error más típico.

Si la opción "GitHub Actions" aparece en gris, sáltate este paso, haz el 4 y el 5, y vuelve aquí al terminar.

## Paso 4. Subir los archivos

1. Vuelve a la pestaña **Code** (arriba a la izquierda).
2. **Add file** → **Upload files**.
3. Arrastra estos archivos y la carpeta:
   - `build_index.py`
   - `README.md`
   - `GUIA-paso-a-paso.md`
   - la carpeta **semanas** entera (dentro va `resumen-2026-07-19.html`)
4. Abajo, pulsa **Commit changes**.

## Paso 5. Crear el archivo del robot

Este archivo vive en una carpeta con punto delante, que no se deja arrastrar. Se crea a mano, y es fácil:

1. **Add file** → **Create new file**.
2. En la casilla del nombre, escribe exactamente esto (las barras van creando las carpetas solas):

   ```
   .github/workflows/deploy.yml
   ```
3. En el cuadro grande de abajo, pega el contenido del archivo `deploy.yml` que te paso.
4. **Commit changes**.

Al guardar, el robot arranca solo.

## Paso 6. Comprobar que se ha publicado

1. Pestaña **Actions** (arriba). Verás una tarea llamada "Publicar web". Un círculo amarillo = trabajando; un tilde verde = hecho (tarda 1-2 minutos).
2. Cuando esté verde, ve a **Settings → Pages**. Arriba aparece la dirección:

   `https://TU-USUARIO.github.io/resumenes-infecciosas/`

Esa es tu web. Ábrela: verás la portada con la semana de ejemplo.

Si en el paso 3 la opción estaba en gris: entra ahora en **Settings → Pages**, elige **GitHub Actions**, luego ve a **Actions**, abre la última tarea y pulsa **Re-run all jobs**.

---

## Cada semana (esto es lo único que repetirás)

1. Genera el HTML con tu skill `seleccion-semanal-articulos`.
2. En GitHub, entra en la carpeta **semanas**.
3. **Add file** → **Upload files**. Arrastra el HTML nuevo, nombrado con su fecha: `resumen-AAAA-MM-DD.html` (por ejemplo `resumen-2026-07-26.html`). La fecha del nombre ordena la portada.
4. **Commit changes**.

En 1-2 minutos la web se actualiza y la semana nueva aparece arriba del todo. No toques la portada: se rehace sola.

## Si algo va mal

- **La tarea de Actions sale en rojo:** ábrela y mira el último paso. Casi siempre es que falta el paso 3 (Pages en modo GitHub Actions). Hazlo y pulsa **Re-run all jobs**.
- **La web da 404 al principio:** espera un par de minutos tras el primer tilde verde; la primera vez tarda algo más.
- **Una semana no aparece:** revisa que el archivo esté dentro de `semanas/` y que termine en `.html`.

## Aviso

Repositorio público: no subas datos de pacientes ni nada identificable.
