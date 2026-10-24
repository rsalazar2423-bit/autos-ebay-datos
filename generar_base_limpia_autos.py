"""Genera Base_limpia_Autos.csv a partir de autos.csv SIN descartar anuncios por rangos.

Principio: un valor dudoso se marca (indicador) y, si es imposible, se anula o se imputa;
la fila se conserva. Única excepción: duplicados exactos (se auditan en un archivo aparte).

Uso:  python3 generar_base_limpia_autos.py
Salidas:
    Base_limpia_Autos.csv             base de análisis (todas las filas, salvo duplicados exactos)
    Auditoria_eliminados_Autos.csv    filas eliminadas, con el motivo

TRAZABILIDAD DE FILAS (verificada por el código al final):
    autos (1).csv: 371.825 líneas de texto = 1 encabezado + 371.824 registros (1 por línea).
    Registros crudos:                                 371.824
    Duplicados exactos eliminados (auditados):              4
    Base_limpia_Autos.csv:                            371.820   <- cifra oficial de la base
        (371.821 líneas de texto = 1 encabezado + 371.820 registros)
"""
import csv

import numpy as np
import pandas as pd

CRUDA = "autos (1).csv"
SALIDA = "Base_limpia_Autos.csv"
AUDITORIA = "Auditoria_eliminados_Autos.csv"

PRECIO_MIN, PRECIO_MAX = 100, 200_000
ANIO_MIN, ANIO_MAX = 1950, 2016      # el scraping es de marzo-abril de 2016
POT_MIN, POT_MAX = 1, 800
MIN_GRUPO = 10                       # tamaño mínimo de un grupo para imputar con su mediana
FILAS_CRUDAS_ESPERADAS = 371_824     # registros de autos (1).csv (371.825 líneas - encabezado)
FILAS_FINALES_ESPERADAS = 371_820    # Base_limpia_Autos.csv = cruda - 4 duplicados exactos

# quoting=QUOTE_NONE es OBLIGATORIO: el archivo trae comillas sueltas dentro de los nombres
# (2.618 anuncios). Con la lectura por defecto, pandas las toma como inicio de un campo
# entrecomillado y se traga 296 registros. Verificado: las 371.824 líneas de datos tienen
# exactamente 20 campos y ninguna es continuación de otra.
df = pd.read_csv(CRUDA, encoding="latin-1", quoting=csv.QUOTE_NONE, dtype=str, keep_default_na=False)
for c in ["price", "yearOfRegistration", "powerPS", "kilometer", "monthOfRegistration", "nrOfPictures", "postalCode"]:
    df[c] = pd.to_numeric(df[c])
df = df.replace("", np.nan)
n_cruda = len(df)

# ---------------------------------------------------------------- 1. duplicados exactos
dup = df.duplicated(keep="first")
auditoria = df[dup].copy()
auditoria["motivo_eliminacion"] = "duplicado exacto (las 20 columnas idénticas a una fila anterior)"
df = df[~dup].copy()

# ---------------------------------------------------------------- 2. categóricas
mapa_dano = {"ja": "sí", "nein": "no"}
mapa_caja = {"manuell": "manual", "automatik": "automatica"}
mapa_comb = {"benzin": "gasolina", "diesel": "diesel", "lpg": "gas_lp", "cng": "gas_natural",
             "hybrid": "hibrido", "elektro": "electrico", "andere": "otro"}
df["notRepairedDamage"] = df["notRepairedDamage"].str.lower().map(mapa_dano).fillna("no especifica")
df["gearbox"] = df["gearbox"].str.lower().map(mapa_caja).fillna("no especifica")
df["fuelType"] = df["fuelType"].str.lower().map(mapa_comb).fillna("no especifica")
for c in ["vehicleType", "model"]:
    df[c] = df[c].fillna("no especifica")
for c in ["notRepairedDamage", "vehicleType", "fuelType", "gearbox", "model"]:
    df[f"{c}_imputado"] = df[c] == "no especifica"

# ---------------------------------------------------------------- 3. fechas
df["dateCreated"] = pd.to_datetime(df["dateCreated"], errors="coerce")
df["lastSeen"] = pd.to_datetime(df["lastSeen"], errors="coerce")
df["dias_en_mercado"] = (df["lastSeen"] - df["dateCreated"]).dt.days

# ---------------------------------------------------------------- 4. precio: se marca, no se toca
df["precio_atipico"] = ~df["price"].between(PRECIO_MIN, PRECIO_MAX)
df["precio_cero"] = df["price"] == 0

# ---------------------------------------------------------------- 5. año de registro
df["anio_invalido"] = ~df["yearOfRegistration"].between(ANIO_MIN, ANIO_MAX)
df["yearOfRegistration_original"] = df["yearOfRegistration"]
df.loc[df["anio_invalido"], "yearOfRegistration"] = np.nan
df["antiguedad_anios"] = 2016 - df["yearOfRegistration"]

# ---------------------------------------------------------------- 6. potencia: nula + imputación jerárquica
df["potencia_original"] = df["powerPS"]
df["potencia_invalida"] = ~df["powerPS"].between(POT_MIN, POT_MAX)
df.loc[df["potencia_invalida"], "powerPS"] = np.nan
df["bloque_anio"] = (df["yearOfRegistration"] // 5 * 5)   # NaN si el año es inválido

niveles = [["brand", "model", "bloque_anio"],
           ["brand", "model"],
           ["brand", "vehicleType", "bloque_anio"],
           ["brand", "vehicleType"],
           ["brand"]]
df["potencia_metodo"] = np.where(df["potencia_invalida"], "", "observada")
for llave in niveles:
    # 'no especifica' no identifica un modelo: no sirve como grupo
    ok = df["potencia_invalida"] & (df["potencia_metodo"] == "")
    for c in llave:
        ok &= df[c].notna() & (df[c] != "no especifica")
    g = df.groupby(llave, observed=True)["powerPS"]
    mediana, n = g.transform("median"), g.transform("count")
    usar = ok & df["powerPS"].isna() & (n >= MIN_GRUPO)
    df.loc[usar, "powerPS"] = mediana[usar]
    df.loc[usar, "potencia_metodo"] = "mediana por " + "+".join(llave)
resto = df["powerPS"].isna()
df.loc[resto, "powerPS"] = df["potencia_original"].where(~df["potencia_invalida"]).median()
df.loc[resto, "potencia_metodo"] = "mediana global"
df["powerPS_imputado"] = df["potencia_invalida"]

# ---------------------------------------------------------------- 7. columnas fuera
df = df.drop(columns=["offerType", "seller", "nrOfPictures", "abtest", "monthOfRegistration",
                      "dateCrawled", "postalCode", "bloque_anio"])
df = df.reset_index(drop=True)

df.to_csv(SALIDA, index=False)
auditoria.to_csv(AUDITORIA, index=False)

print(f"Cruda: {n_cruda:,}   eliminadas: {len(auditoria):,}   Base_limpia_Autos: {len(df):,}")
print(f"precio_atipico: {int(df.precio_atipico.sum()):,} (de ellos precio 0: {int(df.precio_cero.sum()):,})")
print(f"anio_invalido: {int(df.anio_invalido.sum()):,}")
print(f"potencia_invalida (imputada): {int(df.potencia_invalida.sum()):,}")
print(df.loc[df.potencia_invalida, "potencia_metodo"].value_counts())
print(f"dias_en_mercado < 0: {int((df.dias_en_mercado < 0).sum())}")

# ---------------------------------------------------------------- trazabilidad de filas
print("\n=== TRAZABILIDAD DE FILAS ===")
print(f"Registros crudos                      : {n_cruda:,}")
print(f"(-) Duplicados exactos eliminados     : {len(auditoria):,}  -> {AUDITORIA}")
print(f"(=) Base_limpia_Autos.csv             : {len(df):,}")
assert n_cruda == FILAS_CRUDAS_ESPERADAS, f"cruda={n_cruda:,}, se esperaban {FILAS_CRUDAS_ESPERADAS:,}"
assert len(df) == FILAS_FINALES_ESPERADAS, f"final={len(df):,}, se esperaban {FILAS_FINALES_ESPERADAS:,}"
assert n_cruda - len(auditoria) == len(df), "las filas no cuadran"
print("OK: las filas cuadran (371.824 - 4 = 371.820).")
