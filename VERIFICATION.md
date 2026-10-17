# Verificación de la V1 · 17/10/2026

## Datos reales

- Descarga de Yahoo Finance completada para los 18 instrumentos del catálogo, con 1.255 sesiones válidas por instrumento. Última sesión diaria y semanal: 16/10/2026.
- Dataset validado por el script de publicación: fechas ordenadas y únicas, valores positivos finitos, referencias y activos iniciales completos, histórico suficiente y antigüedad dentro del límite.
- Datos y caché conservados sólo en local; no forman parte del commit público.

## Pruebas automáticas

- Python: 15 pruebas de cálculo, intersección de fechas, invariancia, causalidad, calendario, semana con viernes festivo, cierre reducido, fallo de proveedor y escritura atómica.
- TypeScript: 13 pruebas de URL, restauración, selección vacía, parámetros inválidos, recorrido temporal, cuadrantes y escala.
- TypeScript sin errores de tipos y build de producción correcto.

## Navegador

- Inicio con cuatro índices reales, semanal y cola de 17.
- Cambio a sectores y diario; seis activos preseleccionados, valores distintos de los semanales.
- Campo numérico de cola a 30 sincronizado con slider y URL.
- Retroceso de una sesión actualiza benchmark, fecha explorada y tabla.
- Desde el jueves 15/10 en diario, pasar a semanal muestra el viernes 09/10, sin anticipar el 16/10.
- Ocultar XLK, resaltar XLE y copiar enlace; confirmación visible de copia.
- Abrir ese enlace en otra pestaña restaura conjunto, frecuencia, cola y ocultación, y vuelve a la fecha más reciente, según lo previsto.
- Pulsar el benchmark navega al histórico; reproducción avanza hasta el último periodo y se detiene.
- Producción servida bajo `/rrg-kiko/`: carga de JavaScript/CSS/datos, dos gráficos y cuatro filas; recarga directa con parámetros.
- Revisión visual de escritorio y de layout estrecho: configuración plegable, gráficos y tabla disponibles. El navegador integrado limitó el ancho efectivo a aproximadamente 748 px; no se afirma una prueba en un teléfono físico ni una captura real a 390 px.
- Consola revisada sin errores ni advertencias durante las interacciones comprobadas.

## Estado previo al despliegue

Las pruebas anteriores se realizaron en local antes del despliegue. Posteriormente se verificó la sesión de GitHub CLI con acceso de red: conectada como `jordiprga`. Las comprobaciones sin acceso de red podían indicar un token inválido de forma errónea.

Tras la instrucción posterior del usuario de subir y generar la página para su prototipo personal, se habilita el workflow de Pages. Esto no se presenta como acreditación de una licencia de redistribución de los datos. Los resultados de ejecución y la URL verificada se añadirán tras finalizar la publicación.
