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

## Dependencias pendientes de la entrega pública

No se ha publicado ni verificado una URL de GitHub Pages. La CLI de GitHub necesita reautenticación y el navegador muestra login. El conector disponible lee el perfil, pero no permite crear repositorios. `scripts/publish.ps1` prepara la creación/subida tras reconectar.

Tampoco se ha acreditado una licencia de redistribución pública para los históricos Yahoo. El workflow de Pages queda condicionado a documentar esa evidencia; CI puede ejecutarse sin datos. Los workflows están implementados, pero aún no han sido ejecutados en GitHub. Las actualizaciones automáticas no están activas en un remoto.
