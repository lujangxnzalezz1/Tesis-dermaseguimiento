from fastapi import FastAPI

app = FastAPI(title="Facial Traceability API")


@app.get("/")
def inicio():
    return {"mensaje": "Servidor funcionando correctamente"}


@app.get("/saludo/{nombre}")
def saludo(nombre: str):
    return {"mensaje": f"Hola {nombre}, bienvenida"}