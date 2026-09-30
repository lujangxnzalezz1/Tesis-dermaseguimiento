import re
from typing import Optional

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def limpiar_texto(valor: Optional[str], *, campo: str, max_len: int, obligatorio: bool = False) -> Optional[str]:
    """Sanitiza texto libre: recorta espacios, quita caracteres de control y
    rechaza marcado HTML/script (defensa contra inyección de código)."""
    if valor is None:
        if obligatorio:
            raise ValueError(f"El campo «{campo}» es obligatorio.")
        return None
    valor = _CONTROL.sub("", valor).strip()
    valor = re.sub(r"[ \t]+", " ", valor)
    if not valor:
        if obligatorio:
            raise ValueError(f"El campo «{campo}» no puede estar vacío.")
        return None
    if "<" in valor or ">" in valor:
        raise ValueError(f"El campo «{campo}» no puede contener los caracteres < o >.")
    if len(valor) > max_len:
        raise ValueError(f"El campo «{campo}» no puede superar los {max_len} caracteres.")
    return valor


class Pagina(dict):
    pass
