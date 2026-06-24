# ==========================================
# CIRCUITO F  (router en archivo propio)
# Seguimiento y proyeccion del ejercicio: ventas netas - compras - sueldos - IIBB
# -> resultado -> impuesto a las ganancias (escala Ley 27.630).
# El ejercicio se identifica por su anio de cierre (anio_ejercicio).
#
# IMPORTANTE: este modulo es self-contained (no depende de main.py) para que
# las ediciones de main.py no lo pisen. Se engancha con:
#     from circuito_f import router as circuito_f_router
#     app.include_router(circuito_f_router)
# ==========================================
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import date
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


def _conn():
    return psycopg2.connect(os.environ.get("DATABASE_URL"), cursor_factory=RealDictCursor)


# Tipos de comprobante de compra computados (Facturas + ND + Tique Factura).
# Las Notas de Credito (3,8,13) restan. Se excluyen recibos, remitos, tique
# simple, "Sin Factura" y "Varios".
_CF_TIPOS_COMPRA = (1, 2, 3, 6, 7, 8, 11, 12, 13, 82, 83)
_CF_TIPOS_NC = (3, 8, 13)

# Escala del impuesto a las ganancias por defecto (Ley 27.630, valores nominales
# base). Se ajustan por inflacion cada ejercicio: el usuario los edita desde el
# modulo. fijo + alicuota * (ganancia - desde).
_CF_ESCALA_DEFAULT = [
    (1, 0, 5000000, 0, 0.25),
    (2, 5000000, 50000000, 1250000, 0.30),
    (3, 50000000, None, 14750000, 0.35),
]

_CF_MESES_ABREV = ["", "ENE", "FEB", "MAR", "ABR", "MAY", "JUN",
                   "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]


def _cf_config(cur):
    """Devuelve la fila de configuracion, creandola con defaults si no existe."""
    cur.execute("""SELECT id, mes_cierre, alicuota_iva_compras, alicuota_iibb
                   FROM circuito_f_config ORDER BY id LIMIT 1""")
    row = cur.fetchone()
    if not row:
        cur.execute("""INSERT INTO circuito_f_config (mes_cierre, alicuota_iva_compras, alicuota_iibb)
                       VALUES (12, 0.21, 0.00)
                       RETURNING id, mes_cierre, alicuota_iva_compras, alicuota_iibb""")
        row = cur.fetchone()
    return row


def _cf_slots(anio_ejercicio, mes_cierre):
    """12 pares (anio, mes) ascendentes que terminan en el mes de cierre."""
    slots = []
    y, m = anio_ejercicio, mes_cierre
    for _ in range(12):
        slots.append((y, m))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    slots.reverse()
    return slots


def _cf_escala(cur, anio):
    """Tramos de la escala para el ejercicio; siembra los defaults si no hay."""
    cur.execute("""SELECT orden, desde, hasta, fijo, alicuota
                   FROM circuito_f_escala WHERE anio_ejercicio=%s ORDER BY orden""", (anio,))
    rows = cur.fetchall()
    if not rows:
        for (orden, desde, hasta, fijo, alic) in _CF_ESCALA_DEFAULT:
            cur.execute("""INSERT INTO circuito_f_escala (anio_ejercicio, orden, desde, hasta, fijo, alicuota)
                           VALUES (%s,%s,%s,%s,%s,%s)""", (anio, orden, desde, hasta, fijo, alic))
        cur.execute("""SELECT orden, desde, hasta, fijo, alicuota
                       FROM circuito_f_escala WHERE anio_ejercicio=%s ORDER BY orden""", (anio,))
        rows = cur.fetchall()
    return rows


def _cf_impuesto(ganancia, tramos):
    """Impuesto a las ganancias aplicando la escala (lista de dicts con
    desde/fijo/alicuota). Devuelve 0 si la ganancia no es positiva."""
    g = float(ganancia or 0)
    if g <= 0 or not tramos:
        return 0.0
    ordenados = sorted(tramos, key=lambda t: float(t["desde"]))
    elegido = ordenados[0]
    for t in ordenados:
        if g >= float(t["desde"]):
            elegido = t
        else:
            break
    return float(elegido["fijo"]) + float(elegido["alicuota"]) * (g - float(elegido["desde"]))


def _cf_anio_default(mes_cierre):
    """Anio de cierre del ejercicio en curso segun la fecha de hoy."""
    hoy = date.today()
    return hoy.year + 1 if hoy.month > mes_cierre else hoy.year


@router.get("/circuito_f/config")
def cf_get_config():
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cfg = _cf_config(cur)
        conn.commit()
        return {
            "mes_cierre": cfg["mes_cierre"],
            "alicuota_iva_compras": float(cfg["alicuota_iva_compras"]),
            "alicuota_iibb": float(cfg["alicuota_iibb"]),
        }
    finally:
        conn.close()


class CfConfigIn(BaseModel):
    mes_cierre: int = Field(ge=1, le=12)
    alicuota_iva_compras: float = Field(ge=0, le=1)
    alicuota_iibb: float = Field(ge=0, le=1)


@router.put("/circuito_f/config")
def cf_put_config(c: CfConfigIn):
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cfg = _cf_config(cur)
            cur.execute("""UPDATE circuito_f_config
                           SET mes_cierre=%s, alicuota_iva_compras=%s, alicuota_iibb=%s, actualizado_en=now()
                           WHERE id=%s""",
                        (c.mes_cierre, c.alicuota_iva_compras, c.alicuota_iibb, cfg["id"]))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.get("/circuito_f/ventas")
def cf_get_ventas(anio: int):
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT mes, ventas_netas FROM circuito_f_ventas
                           WHERE anio_ejercicio=%s ORDER BY mes""", (anio,))
            return [{"mes": r["mes"], "ventas_netas": float(r["ventas_netas"])} for r in cur.fetchall()]
    finally:
        conn.close()


class CfVentaIn(BaseModel):
    anio: int = Field(ge=2000, le=2100)
    mes: int = Field(ge=1, le=12)
    ventas_netas: float = Field(ge=0, le=1e15)


@router.put("/circuito_f/ventas")
def cf_put_venta(v: CfVentaIn):
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO circuito_f_ventas (anio_ejercicio, mes, ventas_netas)
                           VALUES (%s,%s,%s)
                           ON CONFLICT (anio_ejercicio, mes)
                           DO UPDATE SET ventas_netas=EXCLUDED.ventas_netas, actualizado_en=now()""",
                        (v.anio, v.mes, v.ventas_netas))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.get("/circuito_f/sueldos")
def cf_get_sueldos(anio: int):
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""SELECT mes, sueldos, cargas_sociales, aportes_sindicales
                           FROM circuito_f_sueldos WHERE anio_ejercicio=%s ORDER BY mes""", (anio,))
            return [{
                "mes": r["mes"],
                "sueldos": float(r["sueldos"]),
                "cargas_sociales": float(r["cargas_sociales"]),
                "aportes_sindicales": float(r["aportes_sindicales"]),
            } for r in cur.fetchall()]
    finally:
        conn.close()


class CfSueldoIn(BaseModel):
    anio: int = Field(ge=2000, le=2100)
    mes: int = Field(ge=1, le=12)
    sueldos: float = Field(ge=0, le=1e15)
    cargas_sociales: float = Field(ge=0, le=1e15)
    aportes_sindicales: float = Field(ge=0, le=1e15)


@router.put("/circuito_f/sueldos")
def cf_put_sueldo(s: CfSueldoIn):
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO circuito_f_sueldos
                              (anio_ejercicio, mes, sueldos, cargas_sociales, aportes_sindicales)
                           VALUES (%s,%s,%s,%s,%s)
                           ON CONFLICT (anio_ejercicio, mes)
                           DO UPDATE SET sueldos=EXCLUDED.sueldos,
                                         cargas_sociales=EXCLUDED.cargas_sociales,
                                         aportes_sindicales=EXCLUDED.aportes_sindicales,
                                         actualizado_en=now()""",
                        (s.anio, s.mes, s.sueldos, s.cargas_sociales, s.aportes_sindicales))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.get("/circuito_f/escala")
def cf_get_escala(anio: int):
    conn = _conn()
    try:
        with conn.cursor() as cur:
            rows = _cf_escala(cur, anio)
        conn.commit()
        return [{
            "orden": r["orden"],
            "desde": float(r["desde"]),
            "hasta": (float(r["hasta"]) if r["hasta"] is not None else None),
            "fijo": float(r["fijo"]),
            "alicuota": float(r["alicuota"]),
        } for r in rows]
    finally:
        conn.close()


class CfTramoIn(BaseModel):
    orden: int = Field(ge=1, le=20)
    desde: float = Field(ge=0, le=1e15)
    hasta: Optional[float] = Field(default=None, ge=0, le=1e15)
    fijo: float = Field(ge=0, le=1e15)
    alicuota: float = Field(ge=0, le=1)


class CfEscalaIn(BaseModel):
    anio: int = Field(ge=2000, le=2100)
    tramos: list[CfTramoIn]


@router.put("/circuito_f/escala")
def cf_put_escala(e: CfEscalaIn):
    if not e.tramos:
        raise HTTPException(status_code=400, detail="La escala debe tener al menos un tramo")
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM circuito_f_escala WHERE anio_ejercicio=%s", (e.anio,))
            for t in e.tramos:
                cur.execute("""INSERT INTO circuito_f_escala (anio_ejercicio, orden, desde, hasta, fijo, alicuota)
                               VALUES (%s,%s,%s,%s,%s,%s)""",
                            (e.anio, t.orden, t.desde, t.hasta, t.fijo, t.alicuota))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.get("/circuito_f/resumen")
def cf_resumen(anio: Optional[int] = None):
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cfg = _cf_config(cur)
            mes_cierre = cfg["mes_cierre"]
            alic_iva = float(cfg["alicuota_iva_compras"])
            alic_iibb = float(cfg["alicuota_iibb"])

            anio_ejercicio = anio if anio else _cf_anio_default(mes_cierre)
            slots = _cf_slots(anio_ejercicio, mes_cierre)

            desde = date(slots[0][0], slots[0][1], 1)
            if mes_cierre == 12:
                hasta = date(anio_ejercicio + 1, 1, 1)
            else:
                hasta = date(anio_ejercicio, mes_cierre + 1, 1)

            # compras netas formales por (anio, mes) desde operaciones
            cur.execute("""
                SELECT EXTRACT(YEAR FROM fecha)::int AS anio,
                       EXTRACT(MONTH FROM fecha)::int AS mes,
                       SUM(
                         (CASE WHEN id_tipo_comprobante IN %(nc)s THEN -1 ELSE 1 END)
                         *
                         (CASE WHEN subtotal IS NOT NULL
                               THEN COALESCE(subtotal,0) + COALESCE(exento,0)
                               ELSE COALESCE(importe,0) / (1 + %(alic)s) END)
                       ) AS compras_neto
                FROM operaciones
                WHERE COALESCE(sin_factura, 0) = 0
                  AND id_tipo_comprobante IN %(tipos)s
                  AND fecha >= %(desde)s AND fecha < %(hasta)s
                GROUP BY 1, 2
            """, {"nc": _CF_TIPOS_NC, "tipos": _CF_TIPOS_COMPRA, "alic": alic_iva,
                  "desde": desde, "hasta": hasta})
            compras_map = {(r["anio"], r["mes"]): float(r["compras_neto"] or 0) for r in cur.fetchall()}

            cur.execute("""SELECT mes, ventas_netas FROM circuito_f_ventas WHERE anio_ejercicio=%s""",
                        (anio_ejercicio,))
            ventas_map = {r["mes"]: float(r["ventas_netas"]) for r in cur.fetchall()}

            cur.execute("""SELECT mes, sueldos, cargas_sociales, aportes_sindicales
                           FROM circuito_f_sueldos WHERE anio_ejercicio=%s""", (anio_ejercicio,))
            sueldos_map = {r["mes"]: (float(r["sueldos"]) + float(r["cargas_sociales"]) + float(r["aportes_sindicales"]))
                           for r in cur.fetchall()}

            tramos = _cf_escala(cur, anio_ejercicio)
        conn.commit()

        meses = []
        acum = {"ventas_netas": 0.0, "compras": 0.0, "sueldos": 0.0, "iibb": 0.0, "resultado": 0.0}
        meses_con_datos = 0
        for (y, m) in slots:
            ventas = ventas_map.get(m, 0.0)
            compras = compras_map.get((y, m), 0.0)
            sueldos = sueldos_map.get(m, 0.0)
            iibb = ventas * alic_iibb
            resultado = ventas - compras - sueldos - iibb
            con_datos = bool(ventas or compras or sueldos)
            if con_datos:
                meses_con_datos += 1
                acum["ventas_netas"] += ventas
                acum["compras"] += compras
                acum["sueldos"] += sueldos
                acum["iibb"] += iibb
                acum["resultado"] += resultado
            meses.append({
                "mes": m,
                "anio_calendario": y,
                "etiqueta": _CF_MESES_ABREV[m],
                "ventas_netas": round(ventas, 2),
                "compras": round(compras, 2),
                "sueldos": round(sueldos, 2),
                "iibb": round(iibb, 2),
                "resultado": round(resultado, 2),
                "con_datos": con_datos,
            })

        factor = (12.0 / meses_con_datos) if meses_con_datos else 0.0
        proy = {k: round(v * factor, 2) for k, v in acum.items()}
        proy["meses_con_datos"] = meses_con_datos

        imp_acum = _cf_impuesto(acum["resultado"], tramos)
        imp_proy = _cf_impuesto(proy["resultado"], tramos)

        return {
            "anio_ejercicio": anio_ejercicio,
            "mes_cierre": mes_cierre,
            "alicuota_iva_compras": alic_iva,
            "alicuota_iibb": alic_iibb,
            "meses": meses,
            "totales": {k: round(v, 2) for k, v in acum.items()},
            "proyeccion": proy,
            "ganancias": {
                "resultado_acumulado": round(acum["resultado"], 2),
                "impuesto_acumulado": round(imp_acum, 2),
                "resultado_proyectado": proy["resultado"],
                "impuesto_proyectado": round(imp_proy, 2),
                "alicuota_efectiva_proy": round(imp_proy / proy["resultado"], 4) if proy["resultado"] > 0 else 0.0,
            },
        }
    finally:
        conn.close()
