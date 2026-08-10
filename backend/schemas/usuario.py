from pydantic import BaseModel


class UsuarioRegistro(BaseModel):
    email: str
    password: str
    nombre: str


class UsuarioRespuesta(BaseModel):
    id: int
    email: str
    nombre: str
    rol: str

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
