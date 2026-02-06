from fastapi import FastAPI
from pydantic import BaseModel
from pymongo import MongoClient
from datetime import datetime
from typing import Any, List, Optional
import pandas as pd
import numpy as np
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="pandas")

app = FastAPI(title="API Excel ↔ MongoDB v2", version="2.0")

# -------------------------------------------------------
#  Conexion con MongoDB
# -------------------------------------------------------
class MongoDBHandler:
    def __init__(self, uri="mongodb://localhost:27017/", db_name="exel3"):
        self.client = MongoClient(uri)
        self.db = self.client[db_name]

    def get_collection(self, collection_name):
        return self.db[collection_name]


# -------------------------------------------------------
#  Importar Excel a MongoDB
# -------------------------------------------------------
class ExcelToMongo:
    def __init__(self, mongo_handler, collection_name="tablas_exel"):
        self.collection = mongo_handler.get_collection(collection_name)

    def leer_excel(self, ruta, nombre_hoja=None):
        df = pd.read_excel(ruta, sheet_name=nombre_hoja, keep_default_na=False)
        return df

    def exportar_excel(self, ruta, nombre_hoja=None):
        df = self.leer_excel(ruta, nombre_hoja)
        if isinstance(df, dict):  # Varias hojas
            for hoja, df_hoja in df.items():
                datos = df_hoja.to_dict(orient="records")
                if datos:
                    self.collection.insert_many(datos)
            return {"mensaje": f"Archivo {ruta} exportado correctamente con varias hojas."}
        else:
            datos = df.to_dict(orient="records")
            if datos:
                self.collection.insert_many(datos)
            return {"mensaje": f"Archivo {ruta} exportado correctamente con {len(datos)} filas."}


# -------------------------------------------------------
#  Validacion con Pydantic
# -------------------------------------------------------
from pydantic import field_validator

class ValidadorCampo(BaseModel):
    valor: Any

    @field_validator("valor", mode="before")
    @classmethod
    def detectar_tipo(cls, v):
        if pd.isna(v) or v == "":
            return None
        try:
            float(v)
            return float(v)
        except:
            pass
        try:
            if isinstance(v, datetime):
                return v
            pd.to_datetime(v)
            return pd.to_datetime(v)
        except:
            pass
        return str(v)


# -------------------------------------------------------
#  Validacion, tabla dinamica y exportacion a Excel
# -------------------------------------------------------
class MongoToExcelValidator:
    def __init__(self, mongo_handler, collection_name):
        self.collection = mongo_handler.get_collection(collection_name)

    def obtener_datos(self):
        datos = list(self.collection.find({}, {"_id": 0}))
        return pd.DataFrame(datos)

    def detectar_tipo_predominante(self, serie):
        tipos = {"numero": 0, "fecha": 0, "texto": 0}
        for valor in serie:
            validado = ValidadorCampo(valor=valor).valor
            if isinstance(validado, (int, float)):
                tipos["numero"] += 1
            elif isinstance(validado, (datetime, pd.Timestamp)):
                tipos["fecha"] += 1
            elif isinstance(validado, str):
                tipos["texto"] += 1

        total = len(serie)
        if total == 0:
            return "texto"

        for tipo, cuenta in tipos.items():
            if cuenta / total >= 0.7:
                return tipo
        return "texto"

    def convertir_y_rellenar(self, df):
        df_resultado = df.copy()
        for columna in df.columns:
            tipo = self.detectar_tipo_predominante(df[columna])
            print(f"→ Columna '{columna}' detectada como tipo {tipo}")

            if tipo == "numero":
                df_resultado[columna] = pd.to_numeric(df[columna], errors="coerce").fillna(0)
            elif tipo == "fecha":
                df_resultado[columna] = pd.to_datetime(df[columna], errors="coerce").fillna("")
            else:
                df_resultado[columna] = df[columna].astype(str).replace(["nan", "NaT", "None"], "")
                df_resultado[columna] = df_resultado[columna].replace("", "sin datos")

        return df_resultado

    def crear_tabla_dinamica(self, df, columnas_indices, columnas_valores, funciones_agregacion):
        for col in columnas_indices + columnas_valores:
            if col not in df.columns:
                raise ValueError(f" Falta la columna requerida: {col}")

        for col in columnas_indices:
            df[col] = df[col].replace("", "sin datos")

        tabla_pivot = pd.pivot_table(
            df,
            index=columnas_indices,
            values=columnas_valores,
            aggfunc=funciones_agregacion,
            fill_value=0,
            margins=True,
            margins_name="Total General"
        )
        return tabla_pivot.sort_index()

    def exportar_excel(self, ruta_salida, columnas_indices, columnas_valores, funciones_agregacion):
        df = self.obtener_datos()
        df_validado = self.convertir_y_rellenar(df)
        try:
            tabla_pivot = self.crear_tabla_dinamica(df_validado, columnas_indices, columnas_valores, funciones_agregacion)
        except ValueError as e:
            tabla_pivot = pd.DataFrame({"Error": [str(e)]})

        with pd.ExcelWriter(ruta_salida, engine="openpyxl") as writer:
            df_validado.to_excel(writer, index=False, sheet_name="Datos_Validados")
            tabla_pivot.to_excel(writer, sheet_name="Tabla_Dinamica")

        return {"mensaje": f"Archivo Excel exportado correctamente a {ruta_salida}"}


# -------------------------------------------------------
#  Modelos de entrada para los endpoints
# -------------------------------------------------------
class ExcelImportRequest(BaseModel):
    ruta_excel: str
    hoja: Optional[str] = None
    collection_name: str = "tablas_exel"


class ExcelExportRequest(BaseModel):
    ruta_salida: str
    collection_name: str = "tablas_exel"
    columnas_indices: List[str]
    columnas_valores: List[str]
    funciones_agregacion: List[str]


# -------------------------------------------------------
#  Endpoints de la API
# -------------------------------------------------------

@app.post("/importar_excel/")
def importar_excel(request: ExcelImportRequest):
    mongo_handler = MongoDBHandler()
    exportador = ExcelToMongo(mongo_handler, collection_name=request.collection_name)
    resultado = exportador.exportar_excel(request.ruta_excel, request.hoja)
    return resultado


@app.post("/exportar_excel/")
def exportar_excel(request: ExcelExportRequest):
    mongo_handler = MongoDBHandler()
    validador = MongoToExcelValidator(mongo_handler, request.collection_name)
    resultado = validador.exportar_excel(
        ruta_salida=request.ruta_salida,
        columnas_indices=request.columnas_indices,
        columnas_valores=request.columnas_valores,
        funciones_agregacion=request.funciones_agregacion
    )
    return resultado

@app.get("/health")
def health():
    return {"status": "ok"}