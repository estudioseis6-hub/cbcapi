"""
Motor de extraccion de facturas con IA (Google Gemini - plan gratuito).

Usa un modelo Flash estable con cupo gratuito amplio (no el alias 'latest', que
apunta al modelo mas nuevo y con el cupo gratis mas bajo). Interfaz estable para
main.py:

    model = configurar()
    datos = analizar(ruta_archivo, model)   # -> {"cabecera": {...}, "items": [...]}
"""
import os
import json
import time
import google.generativeai as genai
from PIL import Image

# Modelo Flash estable con cupo gratuito amplio. Si algun dia se agota, probar
# otro: 'gemini-2.5-flash', 'gemini-2.0-flash-lite', etc.
MODELO = "gemini-2.5-flash"

PROMPT = """
Analiza este documento comercial argentino. Extrae datos en JSON puro.
REGLAS:
1. PROVEEDOR: Busca el logo o encabezado principal.
2. CUIT: Extrae el del EMISOR.
3. NUMERO COMPROBANTE: Extrae TODO el texto (ej: 0001-00001234).

Estructura JSON (claves minuscula):
{
    "cabecera": { "razon_social": "string", "fecha": "dd/mm/aaaa", "cuit": "string", "tipo_comprobante": "string", "numero_comprobante": "string", "subtotal": float, "impuestos_internos": float, "iva_21": float, "iva_10_5": float, "iva_27": float, "perc_iibb": float, "perc_iva": float, "perc_ganancias": float, "total": float },
    "items": [ { "producto": "string", "cantidad": float, "precio_unitario": float, "total_linea": float } ]
}
"""


def configurar(api_key=None):
    """Configura Gemini y devuelve el modelo listo para usar."""
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Falta GEMINI_API_KEY (variable de entorno).")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(MODELO)


def analizar(ruta_archivo, model):
    """
    Lee un PDF o imagen y devuelve {cabecera, items}.
    Lanza una excepcion con mensaje claro si no se pudo procesar.
    """
    extension = os.path.splitext(ruta_archivo)[1].lower()
    for intento in range(3):
        try:
            if extension == ".pdf":
                archivo_subido = genai.upload_file(ruta_archivo, mime_type="application/pdf")
                try:
                    for _ in range(40):
                        estado = genai.get_file(archivo_subido.name)
                        if estado.state.name == "ACTIVE":
                            break
                        if estado.state.name == "FAILED":
                            raise Exception("Gemini no pudo procesar el PDF.")
                        time.sleep(0.5)
                    response = model.generate_content([PROMPT, archivo_subido])
                finally:
                    try:
                        genai.delete_file(archivo_subido.name)
                    except Exception:
                        pass
            else:
                imagen = Image.open(ruta_archivo)
                if imagen.mode not in ("RGB", "L"):
                    imagen = imagen.convert("RGB")
                response = model.generate_content([PROMPT, imagen])

            texto_limpio = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(texto_limpio)

        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "quota" in error_str:
                time.sleep(20 * (2 ** intento))
            else:
                raise
    raise Exception("No se pudo leer la factura tras varios reintentos (cuota agotada).")
