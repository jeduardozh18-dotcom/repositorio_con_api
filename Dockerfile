FROM python:3.11-slim

WORKDIR /app

COPY . /app

# Instalar dependencias necesarias
RUN pip install fastapi uvicorn pymongo pandas openpyxl

# Exponer puerto 9000 para evitar conflicto con el 8000
EXPOSE 9000

# Ejecutar la API
CMD ["uvicorn", "app2:app", "--host", "0.0.0.0", "--port", "9000"]
