# Datos: precios de autos usados (eBay Kleinanzeigen, 2016)

- `autos.csv`: crudo, 371.825 líneas = 1 encabezado + 371.824 registros. Leer con `quoting=csv.QUOTE_NONE`.
- `Base_limpia_Autos.csv`: 371.820 registros (crudo menos 4 duplicados exactos). Sin descartes por rango; valores dudosos marcados con indicadores.
- `Auditoria_eliminados_Autos.csv`: los 4 duplicados eliminados.
- `generar_base_limpia_autos.py`: script que genera la base limpia desde el crudo.
