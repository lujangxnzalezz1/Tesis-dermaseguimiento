"""Importe en letras (en español) para el recibo."""
_UNIDADES = ["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez",
             "once", "doce", "trece", "catorce", "quince", "dieciséis", "diecisiete", "dieciocho", "diecinueve",
             "veinte", "veintiuno", "veintidós", "veintitrés", "veinticuatro", "veinticinco", "veintiséis",
             "veintisiete", "veintiocho", "veintinueve"]
_DECENAS = {30: "treinta", 40: "cuarenta", 50: "cincuenta", 60: "sesenta", 70: "setenta", 80: "ochenta", 90: "noventa"}
_CENTENAS = {100: "cien", 200: "doscientos", 300: "trescientos", 400: "cuatrocientos", 500: "quinientos",
             600: "seiscientos", 700: "setecientos", 800: "ochocientos", 900: "novecientos"}


def _menor_mil(n: int) -> str:
    if n < 30:
        return _UNIDADES[n]
    if n < 100:
        d, u = (n // 10) * 10, n % 10
        return _DECENAS[d] if u == 0 else f"{_DECENAS[d]} y {_UNIDADES[u]}"
    c, resto = (n // 100) * 100, n % 100
    if resto == 0:
        return _CENTENAS[c]
    base = "ciento" if c == 100 else _CENTENAS[c]
    return f"{base} {_menor_mil(resto)}"


def entero_en_letras(n: int) -> str:
    if n < 1000:
        return _menor_mil(n)
    if n < 1_000_000:
        miles, resto = divmod(n, 1000)
        pref = "mil" if miles == 1 else f"{_menor_mil(miles).replace('uno', 'un')} mil"
        return pref if resto == 0 else f"{pref} {_menor_mil(resto)}"
    millones, resto = divmod(n, 1_000_000)
    pref = "un millón" if millones == 1 else f"{entero_en_letras(millones).replace(' uno', ' un')} millones"
    return pref if resto == 0 else f"{pref} {entero_en_letras(resto)}"


def monto_en_letras(monto, moneda: str = "USD") -> str:
    entero = int(monto)
    centavos = int(round((float(monto) - entero) * 100))
    nombre = {"USD": "dólares estadounidenses", "PYG": "guaraníes"}.get(moneda, moneda)
    if moneda == "USD" and entero == 1:
        nombre = "dólar estadounidense"
    letras = entero_en_letras(entero)
    if entero % 10 == 1 and entero != 1 and entero % 100 != 11 and letras.endswith("uno"):
        letras = letras[:-3] + "ún"
    return f"{letras.capitalize()} {nombre} con {centavos:02d}/100"
