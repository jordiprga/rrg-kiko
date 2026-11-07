# Inframarinos para WordPress

Tema a medida y plugin de gestión, conservando el diseño de cartel de taberna, la postal, el ticket y el banner de Instagram. No requiere Elementor, ACF ni licencias de pago.

## Descargar e instalar

Los ZIP se generan con `python3 wordpress/package.py` desde la raíz del repositorio. También están publicados en la carpeta `public/inframarinos/descargas/`:

- `inframarinos-tema.zip`: se instala en **Apariencia → Temas → Añadir nuevo → Subir tema**. Activar **Inframarinos**.
- `inframarinos-gestion.zip`: se instala en **Plugins → Añadir nuevo → Subir plugin**. Activar **Inframarinos · Gestión del bar**.
- `inframarinos-wordpress.zip`: paquete de entrega con los dos ZIP anteriores y esta guía. Descomprimir primero; este paquete completo no se sube directamente como tema.

Requisitos: WordPress 6.5 o superior, PHP 7.4 o superior (recomendado PHP 8.3 o superior) y MySQL/MariaDB. En WordPress.com se necesita un plan que permita instalar temas y plugins propios.

Tras activar ambos, **Inframarinos → La web** permite editar la portada. El tema utiliza `front-page.php`, por lo que la dirección principal del WordPress muestra la taberna sin necesidad de crear una página especial.

La web pública de GitHub Pages sigue siendo una demostración estática. El panel de WordPress funciona en el alojamiento donde se instalen estos paquetes; GitHub Pages no ejecuta PHP ni almacena contenidos de WordPress.

## Entregarlo al cliente

1. En **Inframarinos → Cómo se usa**, pulsa **Cargar la carta de ejemplo** si quieres comenzar con los diez productos ficticios. La importación es opcional y no sobrescribe los cambios de los productos ya importados. No recupera productos de ejemplo que se hayan enviado a la papelera: restáuralos desde ella.
2. En **La web**, cambia nombre, titulares, textos, fotografía, dirección, horarios, aviso temporal y cuenta de Instagram. Los campos de texto no permiten modificar la estructura del diseño.
3. En **Platos y bebidas**, edita o añade productos. Usa **Publicar** para hacerlos visibles. Un borrador no se muestra. Para incluir un producto en la web hay que asignarle una categoría.
4. Escribe el precio con coma o punto, sin `€`. Si lo dejas vacío se muestra **Consultar**. Un precio inválido conserva el anterior y muestra un aviso.
5. Usa **Atributos → Orden** para ordenar productos, y **Categorías de la carta → Posición** para ordenar pestañas. Los números más bajos aparecen primero.
6. Desmarca **Disponible** para mostrar **Agotado por hoy**. Marca **Puede salir como tapa de la marea** para incluirlo en el botón de tapas: solo se sortean productos publicados y disponibles.
7. En **Usuarios → Añadir nuevo**, crea la cuenta del cliente con el perfil **Encargado de Inframarinos**. Puede gestionar esta web y subir imágenes, sin instalar plugins, cambiar temas ni administrar usuarios. El perfil de administrador se reserva para quien mantenga WordPress.

Instagram se guarda como nombre de usuario, con o sin `@`. El banner completo y el enlace del menú se actualizan juntos. Dejar la cuenta vacía oculta ambos enlaces. El usuario inicial es `@yordiprga`.

Los horarios permiten añadir y eliminar franjas. El aviso temporal solo aparece al activar su casilla y escribir un texto. Los cambios se publican al guardar; si el alojamiento utiliza caché, puede ser necesario vaciarla.

## Separación de datos y diseño

- `inframarinos/`: tema PHP, plantillas y recursos locales. Incluye las tipografías, sus licencias y la fotografía original.
- `inframarinos-gestion/`: plugin que registra productos, categorías, ajustes y permisos. No hace llamadas a servicios externos.
- Los productos y ajustes se guardan en la base de datos de WordPress. Cambiar el tema no elimina datos ni el panel de gestión. Desactivar el plugin no elimina datos; reactívalo para volver a editarlos. No hay una rutina de desinstalación que borre la carta.
- La portada mantiene su estructura para proteger el diseño. Los productos usan el editor nativo de WordPress y campos de precio y disponibilidad. Las páginas adicionales admiten el editor nativo.
- Imágenes propias se gestionan con la Biblioteca de medios; admite fotos de portada y de productos.

Las actualizaciones del código se realizan en GitHub y se instalan como nuevas versiones del tema o plugin. Los contenidos del cliente permanecen en WordPress. Incluye la base de datos y `wp-content/uploads` en las copias de seguridad del alojamiento.

## Probar en tu ordenador con Docker

Descarga el código del repositorio y, desde su carpeta `wordpress/`:

```sh
cp .env.example .env
# Edita .env y establece WORDPRESS_DB_PASSWORD con una contraseña propia.
docker compose up -d
```

Abre `http://localhost:8080`, completa el instalador de WordPress y activa tema y plugin. El puerto solo se abre en el ordenador local. Los datos persisten en volúmenes; `docker compose down` detiene el entorno y los conserva. No uses `down -v` si quieres conservarlos.

Esta configuración es para desarrollo local. Para usar el panel en Internet, instala el paquete en tu alojamiento WordPress y configura su dominio y HTTPS.

## Verificación

Se ha probado con WordPress 7.1.4 sobre PHP 8.3.36 y MariaDB 11, incluyendo renderizado, importación sin duplicados, orden de categorías y platos, borradores, agotados, precios, cambios de Instagram, sanitización y permisos. Las pruebas HTTP realizan subidas de fotos y guardados por los formularios reales de WordPress con el perfil de encargado, y comprueban los rechazos por falta de permisos o nonce.

Los scripts de `tests/` solo se ejecutan en una instalación de prueba aislada; modifican su contenido y comprueban el dominio interno antes de ejecutarse. No deben ejecutarse en un sitio de un cliente. No se ha realizado revisión visual con navegador en esta sesión.

## Contenido y licencias

El código se distribuye bajo GPL-2.0-or-later. DM Sans y Playfair Display se incluyen con sus licencias SIL Open Font License en `assets/`. La fotografía procede de [Unsplash](https://images.unsplash.com/photo-1514933651103-005eec06c04b).

Inframarinos es una ficción, sin relación con ningún establecimiento real. Los textos, horarios y precios iniciales son imaginarios y deben revisarse antes de ponerlos en la web de un negocio real.
