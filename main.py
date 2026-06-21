from dotenv import load_dotenv
import pathlib
load_dotenv(dotenv_path=pathlib.Path(__file__).parent / ".env")
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import date, timedelta
from typing import Optional
from pydantic import BaseModel
from collections import defaultdict

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

import os
DB = os.environ.get("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DB, cursor_factory=RealDictCursor)

@app.get("/")
def root():
    return {"status": "ok"}

@app.get("/ping")
def ping():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return {"status": "ok"}
    finally:
        conn.close()

@app.get("/fondos")
def get_fondos():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT f.id, f.nombre, f.tipo, f.moneda, f.activo, f.es_sistema,
                       f.saldo_inicial, f.slot, f.abrev, f.grupo,
                       COALESCE(SUM(CASE WHEN c.confirmado = true AND c.fecha <= CURRENT_DATE THEN c.importe ELSE 0 END), 0) AS movimientos,
                       COALESCE(SUM(CASE WHEN c.fecha > CURRENT_DATE THEN c.importe ELSE 0 END), 0) AS proyectado
                FROM fondos f
                LEFT JOIN cashflow c ON c.id_fondo = f.id
                WHERE f.slot IS NOT NULL
                GROUP BY f.id, f.nombre, f.tipo, f.moneda, f.activo, f.es_sistema, f.saldo_inicial, f.slot, f.abrev, f.grupo
                ORDER BY f.orden
            """)
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/fondos_admin")
def get_fondos_admin():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nombre, abrev, tipo, moneda, saldo_inicial, activo, es_sistema FROM fondos ORDER BY id")
            return cur.fetchall()
    finally:
        conn.close()

class FondoUpdateIn(BaseModel):
    nombre: str
    abrev: Optional[str] = None
    tipo: str
    moneda: str
    saldo_inicial: float
    activo: bool

@app.put("/fondos/{id}")
def actualizar_fondo(id: int, f: FondoUpdateIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE fondos SET nombre=%s, abrev=%s, tipo=%s, moneda=%s, saldo_inicial=%s, activo=%s
                WHERE id=%s
            """, (f.nombre, f.abrev, f.tipo, f.moneda, f.saldo_inicial, f.activo, id))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

class FondoIn(BaseModel):
    nombre: str
    tipo: str
    moneda: str
    saldo_inicial: float

@app.post("/fondos")
def crear_fondo(f: FondoIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO fondos (nombre, tipo, moneda, saldo_inicial, es_sistema) VALUES (%s, %s, %s, %s, false)",
                       (f.nombre, f.tipo, f.moneda, f.saldo_inicial))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@app.get("/titulares")
def get_titulares():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, nombre, nivel1, nivel2, nivel3, nivel4,
                       COALESCE(tipo_titular, 'PROVEEDOR') tipo_titular,
                       COALESCE(plazo_pago, 0) plazo_pago,
                       cod1, cod2, cod3, cod4, cod5,
                       fondo_def, razon_social, cuit, cond_fiscal,
                       genera_cc, activo, iva_default
                FROM titulares
                ORDER BY CASE WHEN nivel1='SISTEMA' THEN 0 ELSE 1 END, nombre
            """)
            return cur.fetchall()
    finally:
        conn.close()

class TitularIn(BaseModel):
    nombre: str
    nivel1: str
    nivel2: Optional[str] = None
    nivel3: Optional[str] = None
    nivel4: Optional[str] = None
    tipo_titular: str
    plazo_pago: int
    razon_social: Optional[str] = None
    cuit: Optional[str] = None
    cond_fiscal: Optional[str] = None
    cod1: Optional[str] = None
    cod2: Optional[str] = None
    cod3: Optional[str] = None
    cod4: Optional[str] = None
    cod5: Optional[str] = None
    fondo_def: Optional[str] = None
    genera_cc: Optional[bool] = True
    activo: Optional[bool] = True
    iva_default: Optional[float] = None

@app.post("/titulares")
def crear_titular(t: TitularIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO titulares (nombre, nivel1, nivel2, nivel3, nivel4, tipo_titular, plazo_pago, razon_social, cuit, cond_fiscal, cod1, cod2, cod3, cod4, cod5, fondo_def, genera_cc, activo, iva_default)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (t.nombre, t.nivel1, t.nivel2, t.nivel3, t.nivel4, t.tipo_titular, t.plazo_pago, t.razon_social, t.cuit, t.cond_fiscal, t.cod1, t.cod2, t.cod3, t.cod4, t.cod5, t.fondo_def, t.genera_cc, t.activo, t.iva_default))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@app.put("/titulares/{id}")
def actualizar_titular(id: str, t: TitularIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE titulares SET nombre=%s, nivel1=%s, nivel2=%s, nivel3=%s, nivel4=%s, tipo_titular=%s, plazo_pago=%s,
                       razon_social=%s, cuit=%s, cond_fiscal=%s,
                       cod1=%s, cod2=%s, cod3=%s, cod4=%s, cod5=%s,
                       fondo_def=%s, genera_cc=%s, activo=%s, iva_default=%s
                WHERE id=%s
            """, (t.nombre, t.nivel1, t.nivel2, t.nivel3, t.nivel4, t.tipo_titular, t.plazo_pago,
                  t.razon_social, t.cuit, t.cond_fiscal,
                  t.cod1, t.cod2, t.cod3, t.cod4, t.cod5,
                  t.fondo_def, t.genera_cc, t.activo, t.iva_default, id))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@app.get("/cuentas")
def get_cuentas():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT nombre FROM plan_de_cuentas ORDER BY niv1,niv2,niv3,niv4,niv5")
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/cashflow")
def get_cashflow(mes: Optional[int] = None, id_fondo: Optional[int] = None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            where = []
            if mes:
                where.append(f"c.mes={mes}")
            if id_fondo:
                where.append(f"c.id_fondo={id_fondo}")
            sql = """
                SELECT c.id, c.fecha, t.nombre titular, f.nombre fondo,
                       c.detalle, c.importe, c.cod_cuenta, c.id_fondo,
                       c.confirmado,
                       ch.nro_cheque, ch.fecha_emision, ch.fecha_vencimiento,
                       ch.estado AS estado_cheque
                FROM cashflow c
                LEFT JOIN titulares t ON c.id_titular = t.id
                LEFT JOIN fondos f ON c.id_fondo = f.id
                LEFT JOIN cheques_emitidos ch ON ch.id_cashflow = c.id
            """
            if where:
                sql += " WHERE " + " AND ".join(where)
            sql += " ORDER BY c.fecha ASC LIMIT 500"
            cur.execute(sql)
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/vencimientos")
def get_vencimientos():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE cashflow
                SET fecha = CURRENT_DATE, mes = EXTRACT(MONTH FROM CURRENT_DATE)::integer
                WHERE confirmado = false AND fecha < CURRENT_DATE
                AND id NOT IN (SELECT id_cashflow FROM cheques_emitidos WHERE id_cashflow IS NOT NULL)
            """)
            movidos = cur.rowcount
            conn.commit()
            cur.execute("""
                SELECT c.id, c.fecha, t.nombre titular, f.nombre fondo,
                       c.detalle, c.importe
                FROM cashflow c
                LEFT JOIN titulares t ON c.id_titular = t.id
                LEFT JOIN fondos f ON c.id_fondo = f.id
                WHERE c.confirmado = false AND c.fecha <= CURRENT_DATE
                ORDER BY c.fecha ASC
            """)
            return {"vencimientos": cur.fetchall(), "movidos": movidos}
    finally:
        conn.close()

class ConfirmarPagoIn(BaseModel):
    fecha: Optional[str] = None

@app.post("/vencimientos/{id}/confirmar")
def confirmar_vencimiento(id: int, body: ConfirmarPagoIn = None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            fecha = date.fromisoformat(body.fecha) if body and body.fecha else date.today()
            cur.execute("UPDATE cashflow SET confirmado=true, fecha=%s, mes=%s WHERE id=%s",
                        (fecha, fecha.month, id))
            cur.execute("UPDATE cheques_emitidos SET estado='DEBITADO' WHERE id_cashflow=%s", (id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

class ReprogramarIn(BaseModel):
    fecha: str

@app.post("/vencimientos/{id}/reprogramar")
def reprogramar_vencimiento(id: int, body: ReprogramarIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            fecha = date.fromisoformat(body.fecha)
            cur.execute("UPDATE cashflow SET fecha=%s, mes=%s WHERE id=%s",
                        (fecha, fecha.month, id))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

class MovimientoIn(BaseModel):
    fecha: str
    id_titular: int
    id_fondo: int
    cod_cuenta: str
    detalle: str
    importe: float

@app.post("/cashflow")
def crear_movimiento(m: MovimientoIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            fecha = date.fromisoformat(m.fecha)
            confirmado = fecha <= date.today()
            cur.execute("""
                INSERT INTO cashflow (mes, fecha, id_titular, cod_cuenta, detalle, importe, id_fondo, confirmado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (fecha.month, fecha, m.id_titular, m.cod_cuenta, m.detalle, m.importe, m.id_fondo, confirmado))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

class ECheqIn(BaseModel):
    fecha_emision: str
    fecha_vencimiento: str
    nro_cheque: str
    id_titular: int
    id_fondo: int
    cod_cuenta: str
    detalle: str
    importe: float

@app.post("/cheques_emitidos")
def crear_echeq(c: ECheqIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            fecha_emision = date.fromisoformat(c.fecha_emision)
            fecha_vto = date.fromisoformat(c.fecha_vencimiento)
            cur.execute("""
                INSERT INTO cashflow (mes, fecha, id_titular, cod_cuenta, detalle, importe, id_fondo, confirmado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, false)
                RETURNING id
            """, (fecha_vto.month, fecha_vto, c.id_titular, c.cod_cuenta, c.detalle, -abs(c.importe), c.id_fondo))
            id_cashflow = cur.fetchone()["id"]
            cur.execute("""
                INSERT INTO cheques_emitidos (nro_cheque, fecha_emision, fecha_vencimiento, estado, id_cashflow)
                VALUES (%s, %s, %s, 'EMITIDO', %s)
            """, (c.nro_cheque, fecha_emision, fecha_vto, id_cashflow))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@app.get("/cheques_emitidos")
def get_cheques_emitidos():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ch.id, ch.nro_cheque, ch.fecha_emision, ch.fecha_vencimiento, ch.estado,
                       t.nombre titular, f.nombre fondo, c.importe, c.detalle, c.confirmado
                FROM cheques_emitidos ch
                JOIN cashflow c ON ch.id_cashflow = c.id
                JOIN titulares t ON c.id_titular = t.id
                JOIN fondos f ON c.id_fondo = f.id
                ORDER BY ch.fecha_vencimiento ASC
            """)
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/tipos_comprobante")
def get_tipos_comprobante():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, descripcion FROM tipos_comprobante WHERE activo=true ORDER BY id")
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/operaciones")
def get_operaciones(id_titular: Optional[int] = None, estado: Optional[str] = None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            where = []
            params = []
            if id_titular:
                where.append("o.id_titular = %s")
                params.append(str(id_titular))
            if estado == "IMPAGO":
                where.append("o.id_pago IS NULL")
            elif estado == "PAGO":
                where.append("o.id_pago IS NOT NULL")
            sql = """
                SELECT o.id, o.fecha, o.id_titular, t.nombre titular, tc.descripcion tipo,
                       o.numero_comprobante numero, o.descripcion concepto, o.importe,
                       CASE WHEN o.id_pago IS NULL THEN 'IMPAGO' ELSE 'PAGO' END estado
                FROM operaciones o
                LEFT JOIN titulares t ON o.id_titular = t.id
                LEFT JOIN tipos_comprobante tc ON o.id_tipo_comprobante = tc.id
            """
            if where:
                sql += " WHERE " + " AND ".join(where)
            sql += " ORDER BY o.fecha DESC LIMIT 200"
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()

class ComprobanteIn(BaseModel):
    fecha: str
    fecha_compra: Optional[str] = None
    id_titular: int
    id_tipo_comprobante: int
    numero_comprobante: str
    descripcion: str
    id_fondo: Optional[int] = None
    fecha_vencimiento: Optional[str] = None
    subtotal: Optional[float] = 0
    exento: Optional[float] = 0
    iva_105: Optional[float] = 0
    iva_21: Optional[float] = 0
    iva_27: Optional[float] = 0
    perc_iva: Optional[float] = 0
    perc_iibb: Optional[float] = 0
    perc_otras: Optional[float] = 0
    sin_factura: Optional[float] = 0

@app.post("/operaciones")
def crear_comprobante(c: ComprobanteIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            fecha = date.fromisoformat(c.fecha)
            fecha_compra = date.fromisoformat(c.fecha_compra) if c.fecha_compra else fecha
            importe = (
                (c.subtotal or 0) + (c.exento or 0)
                + (c.iva_105 or 0) + (c.iva_21 or 0) + (c.iva_27 or 0)
                + (c.perc_iva or 0) + (c.perc_iibb or 0) + (c.perc_otras or 0)
                + (c.sin_factura or 0)
            )
            cur.execute("""
                INSERT INTO operaciones
                    (fecha, fecha_compra, id_titular, id_tipo_comprobante, numero_comprobante, descripcion, importe, mes,
                     subtotal, exento, iva_105, iva_21, iva_27, perc_iva, perc_iibb, perc_otras, sin_factura)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (fecha, fecha_compra, str(c.id_titular), c.id_tipo_comprobante, c.numero_comprobante, c.descripcion, importe, fecha.month,
                  c.subtotal, c.exento, c.iva_105, c.iva_21, c.iva_27, c.perc_iva, c.perc_iibb, c.perc_otras, c.sin_factura))
            id_operacion = cur.fetchone()["id"]

            plazo = None
            if not c.fecha_vencimiento:
                cur.execute("SELECT plazo_pago FROM titulares WHERE id = %s", (str(c.id_titular),))
                row = cur.fetchone()
                if row and row["plazo_pago"] and row["plazo_pago"] > 0:
                    plazo = row["plazo_pago"]

            if c.fecha_vencimiento or plazo:
                if c.fecha_vencimiento:
                    fecha_vto = date.fromisoformat(c.fecha_vencimiento)
                else:
                    fecha_vto = fecha + timedelta(days=plazo)

                id_fondo = c.id_fondo
                if not id_fondo:
                    cur.execute("SELECT fondo_def FROM titulares WHERE id = %s", (str(c.id_titular),))
                    r = cur.fetchone()
                    if r and r["fondo_def"]:
                        id_fondo = r["fondo_def"]

                if id_fondo:
                    cur.execute("""
                        INSERT INTO cashflow (mes, fecha, id_titular, detalle, importe, id_fondo, id_operacion, confirmado)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, false)
                    """, (fecha_vto.month, fecha_vto, str(c.id_titular), c.descripcion, -abs(importe), id_fondo, id_operacion))

                conn.commit()
                return {"ok": True, "id_operacion": id_operacion, "proyectado": True, "fecha_vencimiento": str(fecha_vto)}
            else:
                conn.commit()
                return {"ok": True, "id_operacion": id_operacion, "proyectado": False, "sin_plazo": True}
    finally:
        conn.close()

@app.get("/plan_cuentas")
def get_plan_cuentas():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, niv1, niv2, niv3, niv4, niv5, niv1_desc, niv2_desc, niv3_desc, niv4_desc, nombre, signo, fondo, dd, activo, cod_cbc, moneda
                FROM plan_de_cuentas
                ORDER BY niv1,niv2,niv3,niv4,niv5
            """)
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/plan_cuentas_grupos")
def get_plan_cuentas_grupos(niv1: Optional[int] = None, niv2: Optional[int] = None, niv3: Optional[int] = None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            where = ["activo = true"]
            params = []
            if niv1: where.append("niv1 = %s"); params.append(niv1)
            if niv2: where.append("niv2 = %s"); params.append(niv2)
            if niv3: where.append("niv3 = %s"); params.append(niv3)
            cur.execute(f"""
                SELECT DISTINCT niv1, niv2, niv3, niv3_desc, niv4, niv4_desc
                FROM plan_cuentas_grupos
                WHERE {" AND ".join(where)}
                ORDER BY niv1, niv2, niv3, niv4
            """, params)
            return cur.fetchall()
    finally:
        conn.close()

class CuentaIn(BaseModel):
    niv1: int
    niv1_desc: str
    niv2: int
    niv2_desc: str
    niv3: Optional[int] = 1
    niv3_desc: Optional[str] = None
    niv4: Optional[int] = 1
    niv4_desc: Optional[str] = None
    niv5: Optional[int] = None
    nombre: str
    cod_cbc: Optional[str] = None
    signo: Optional[str] = None
    fondo: Optional[str] = None
    moneda: Optional[str] = "ARS"
    dd: Optional[bool] = False
    activo: Optional[bool] = True

@app.post("/plan_cuentas")
def crear_cuenta(c: CuentaIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if c.niv5 is None:
                cur.execute("""
                    SELECT COALESCE(MAX(niv5), 0) + 1 AS siguiente
                    FROM plan_de_cuentas
                    WHERE niv1=%s AND niv2=%s AND niv3=%s AND niv4=%s
                """, (c.niv1, c.niv2, c.niv3, c.niv4))
                niv5 = cur.fetchone()["siguiente"]
            else:
                niv5 = c.niv5
            cur.execute("""
                INSERT INTO plan_de_cuentas
                    (niv1, niv2, niv3, niv4, niv5, niv1_desc, niv2_desc, niv3_desc, niv4_desc,
                     nombre, cod_cbc, signo, fondo, moneda, dd, activo)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (c.niv1, c.niv2, c.niv3, c.niv4, niv5,
                  c.niv1_desc, c.niv2_desc, c.niv3_desc, c.niv4_desc,
                  c.nombre, c.cod_cbc, c.signo, c.fondo or None,
                  c.moneda, c.dd, c.activo))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@app.put("/plan_cuentas/{id}")
def actualizar_cuenta(id: int, c: CuentaIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE plan_de_cuentas
                SET niv1=%s, niv1_desc=%s, niv2=%s, niv2_desc=%s,
                    niv3=%s, niv3_desc=%s, niv4=%s, niv4_desc=%s,
                    nombre=%s, cod_cbc=%s, signo=%s, fondo=%s,
                    moneda=%s, dd=%s, activo=%s
                WHERE id=%s
            """, (c.niv1, c.niv1_desc, c.niv2, c.niv2_desc,
                  c.niv3, c.niv3_desc, c.niv4, c.niv4_desc,
                  c.nombre, c.cod_cbc, c.signo, c.fondo or None,
                  c.moneda, c.dd, c.activo, id))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@app.delete("/plan_cuentas/{id}")
def eliminar_cuenta(id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM plan_de_cuentas WHERE id=%s", (id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@app.get("/balance")
def get_balance(mes: Optional[int] = None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            where_mes = f"AND EXTRACT(MONTH FROM c.fecha)={mes}" if mes else ""
            cur.execute(f"""
                SELECT p.niv1, p.niv1_desc, p.niv2, p.niv2_desc, 
                       p.niv3, p.niv3_desc, p.niv4, p.niv4_desc,
                       p.niv5, p.nombre, 
                       COALESCE(SUM(c.importe),0) importe
                FROM plan_de_cuentas p
                LEFT JOIN cashflow c ON c.cod_cuenta = p.nombre {where_mes}
                GROUP BY p.niv1, p.niv1_desc, p.niv2, p.niv2_desc,
                         p.niv3, p.niv3_desc, p.niv4, p.niv4_desc,
                         p.niv5, p.nombre
                ORDER BY p.niv1, p.niv2, p.niv3, p.niv4, p.niv5
            """)
            return cur.fetchall()
    finally:
        conn.close()

class PagoIn(BaseModel):
    fecha: str
    id_titular: int
    id_fondo: int
    cod_cuenta: str
    detalle: str
    ids_operaciones: list[int]
    medio_pago: str = "TD"

@app.post("/registrar_pago")
def registrar_pago(p: PagoIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(SUM(importe),0) FROM operaciones WHERE id = ANY(%s)", (p.ids_operaciones,))
            total = cur.fetchone()["coalesce"]
            fecha = date.fromisoformat(p.fecha)
            cur.execute("""
                INSERT INTO cashflow (mes, fecha, id_titular, cod_cuenta, detalle, importe, id_fondo, confirmado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, true)
                RETURNING id
            """, (fecha.month, fecha, str(p.id_titular), p.cod_cuenta, p.detalle, -abs(total), p.id_fondo))
            id_pago = cur.fetchone()["id"]
            cur.execute("UPDATE operaciones SET id_pago = %s WHERE id = ANY(%s)", (id_pago, p.ids_operaciones))
        conn.commit()
        return {"ok": True, "id_pago": id_pago, "total": total}
    finally:
        conn.close()

class PagoECheqIn(BaseModel):
    fecha_emision: str
    fecha_vencimiento: str
    nro_cheque: str
    id_titular: int
    id_fondo: int
    cod_cuenta: str
    detalle: str
    ids_operaciones: list[int]

@app.post("/registrar_pago_echeq")
def registrar_pago_echeq(p: PagoECheqIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(SUM(importe),0) FROM operaciones WHERE id = ANY(%s)", (p.ids_operaciones,))
            total = cur.fetchone()["coalesce"]
            fecha_emision = date.fromisoformat(p.fecha_emision)
            fecha_vto = date.fromisoformat(p.fecha_vencimiento)
            cur.execute("""
                INSERT INTO cashflow (mes, fecha, id_titular, cod_cuenta, detalle, importe, id_fondo, confirmado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, false)
                RETURNING id
            """, (fecha_vto.month, fecha_vto, str(p.id_titular), p.cod_cuenta, p.detalle, -abs(total), p.id_fondo))
            id_cashflow = cur.fetchone()["id"]
            cur.execute("""
                INSERT INTO cheques_emitidos (nro_cheque, fecha_emision, fecha_vencimiento, estado, id_cashflow)
                VALUES (%s, %s, %s, 'EMITIDO', %s)
            """, (p.nro_cheque, fecha_emision, fecha_vto, id_cashflow))
            cur.execute("UPDATE operaciones SET id_pago = %s WHERE id = ANY(%s)", (id_cashflow, p.ids_operaciones))
        conn.commit()
        return {"ok": True, "id_cashflow": id_cashflow, "total": total}
    finally:
        conn.close()

# ==========================================
# CARGA AUTOMATICA DE COMPROBANTES (FACTUR.IA)
# ==========================================
import re
import tempfile
import unicodedata
from datetime import datetime
from fastapi import UploadFile, File
import factura_ia

_modelo_ia = None
def _get_modelo_ia():
    global _modelo_ia
    if _modelo_ia is None:
        _modelo_ia = factura_ia.configurar()
    return _modelo_ia

def _solo_digitos(texto):
    return re.sub(r"\D", "", str(texto or ""))

def _norm(texto):
    t = str(texto or "").strip().lower()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[\"'""«»]", " ", t)
    return re.sub(r"\s+", " ", t).strip()

def _norm_fuerte(texto):
    return re.sub(r"[^a-z0-9]", "", _norm(texto))

def _sugerir_titulares(razon_social, titulares, limite=5):
    objetivo = _norm_fuerte(razon_social)
    if len(objetivo) < 4:
        return []
    out = []
    for t in titulares:
        for campo in (t.get("nombre"), t.get("razon_social")):
            nm = _norm_fuerte(campo)
            if nm and (nm == objetivo or (len(nm) >= 5 and (nm in objetivo or objetivo in nm))):
                out.append({"id": t["id"], "nombre": t["nombre"],
                            "cuit": t.get("cuit_norm"), "plazo_pago": t["plazo_pago"]})
                break
        if len(out) >= limite:
            break
    return out

def _match_titular(cuit, titulares):
    cuit_norm = _solo_digitos(cuit)
    if not cuit_norm:
        return None
    for t in titulares:
        if t["cuit_norm"] and t["cuit_norm"] == cuit_norm:
            return t
    return None

def _match_tipo(descripcion, tipos):
    d = _norm(descripcion)
    if not d:
        return None
    for t in tipos:
        if _norm(t["descripcion"]) == d:
            return t["id"]
    for t in tipos:
        td = _norm(t["descripcion"])
        if td and (td in d or d in td):
            return t["id"]
    letra_m = re.search(r"\b([abcm])\b", d)
    letra = letra_m.group(1) if letra_m else None
    if "credito" in d:
        clase = "nota de credito"
    elif "debito" in d:
        clase = "nota de debito"
    elif "recibo" in d:
        clase = "recibo"
    elif "factura" in d:
        clase = "factura"
    elif "tique" in d or "ticket" in d:
        clase = "tique"
    elif "remito" in d:
        clase = "remito"
    else:
        return None
    objetivo = f"{clase} {letra}" if letra else clase
    for t in tipos:
        if _norm(t["descripcion"]) == objetivo:
            return t["id"]
    for t in tipos:
        if _norm(t["descripcion"]).startswith(clase):
            return t["id"]
    return None

def _imputar_items(items, id_titular, reglas):
    salida = []
    for it in items or []:
        prod = _norm(it.get("producto"))
        cuenta = None
        if id_titular:
            for r in reglas:
                if r["patron"] == prod and r["id_titular"] == str(id_titular):
                    cuenta = r["cod_cuenta"]; break
        if cuenta is None:
            for r in reglas:
                if r["patron"] == prod and not r["id_titular"]:
                    cuenta = r["cod_cuenta"]; break
        salida.append({
            "producto": it.get("producto"),
            "cantidad": it.get("cantidad"),
            "precio_unitario": it.get("precio_unitario"),
            "total_linea": it.get("total_linea"),
            "cod_cuenta": cuenta,
        })
    return salida

def _convertir_fecha_iso(fecha_str):
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y", "%d.%m.%Y"):
        try:
            return datetime.strptime(str(fecha_str).strip(), fmt).date().isoformat()
        except (ValueError, AttributeError):
            pass
    return None

@app.post("/facturas/analizar")
async def analizar_facturas(archivos: list[UploadFile] = File(...)):
    model = _get_modelo_ia()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, regexp_replace(COALESCE(cuit,''), '\\D', '', 'g') AS cuit_norm,
                       nombre, razon_social, plazo_pago, fondo_def
                FROM titulares
            """)
            titulares = cur.fetchall()
            cur.execute("SELECT id, descripcion FROM tipos_comprobante WHERE activo = true")
            tipos = cur.fetchall()
            cur.execute("SELECT lower(patron_producto) AS patron, id_titular, cod_cuenta FROM imputacion_producto")
            reglas = cur.fetchall()

        resultados = []
        vistos = set()
        for archivo in archivos:
            contenido = await archivo.read()
            suf = os.path.splitext(archivo.filename or "")[1] or ".pdf"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suf) as tmp:
                tmp.write(contenido)
                ruta_tmp = tmp.name
            try:
                datos = factura_ia.analizar(ruta_tmp, model)
            except Exception as e:
                resultados.append({"archivo": archivo.filename, "estado": "ERROR_LECTURA", "error": str(e)[:200]})
                continue
            finally:
                try: os.unlink(ruta_tmp)
                except Exception: pass

            cab = datos.get("cabecera", {}) or {}
            titular = _match_titular(cab.get("cuit"), titulares)
            id_titular = titular["id"] if titular else None
            id_tipo = _match_tipo(cab.get("tipo_comprobante"), tipos)
            numero = str(cab.get("numero_comprobante", "") or "")
            num_norm = _solo_digitos(numero)
            sugerencias = _sugerir_titulares(cab.get("razon_social"), titulares) if id_titular is None else []

            duplicado = False
            candidatos = [id_titular] if id_titular else [s["id"] for s in sugerencias]
            if num_norm and candidatos:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT 1 FROM operaciones
                        WHERE id_titular = ANY(%s)
                          AND regexp_replace(COALESCE(numero_comprobante,''),'\\D','','g') = %s
                        LIMIT 1
                    """, (candidatos, num_norm))
                    duplicado = cur.fetchone() is not None

            items = _imputar_items(datos.get("items", []), id_titular, reglas)

            proveedor_key = _solo_digitos(cab.get("cuit")) or _norm_fuerte(cab.get("razon_social"))
            clave_lote = (proveedor_key, num_norm)
            dup_en_lote = bool(num_norm) and clave_lote in vistos
            if num_norm:
                vistos.add(clave_lote)

            if duplicado or dup_en_lote:
                estado = "DUPLICADO"
            elif id_titular is None:
                estado = "FALTA_TITULAR"
            else:
                estado = "LISTO"

            resultados.append({
                "archivo": archivo.filename,
                "estado": estado,
                "razon_social": cab.get("razon_social"),
                "cuit": cab.get("cuit"),
                "fecha": _convertir_fecha_iso(cab.get("fecha")),
                "tipo_comprobante": cab.get("tipo_comprobante"),
                "id_tipo_comprobante": id_tipo,
                "numero_comprobante": numero,
                "total": cab.get("total"),
                "id_titular": id_titular,
                "titular_nombre": titular["nombre"] if titular else None,
                "plazo_pago": titular["plazo_pago"] if titular else None,
                "sugerencias": sugerencias,
                "items": items,
            })
        return resultados
    finally:
        conn.close()


class TitularNuevoIn(BaseModel):
    nombre: str
    cuit: str
    razon_social: Optional[str] = None
    plazo_pago: int
    nivel1: str = "Proveedores"
    tipo_titular: str = "PROVEEDOR"

@app.post("/facturas/titular")
def crear_titular_factura(t: TitularNuevoIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO titulares (nombre, razon_social, cuit, nivel1, tipo_titular, plazo_pago, activo)
                VALUES (%s, %s, %s, %s, %s, %s, true)
                RETURNING id
            """, (t.nombre, t.razon_social or t.nombre, _solo_digitos(t.cuit),
                  t.nivel1, t.tipo_titular, t.plazo_pago))
            nuevo_id = cur.fetchone()["id"]
        conn.commit()
        return {"ok": True, "id": nuevo_id, "nombre": t.nombre, "plazo_pago": t.plazo_pago}
    finally:
        conn.close()

class VincularTitularIn(BaseModel):
    cuit: str
    razon_social: Optional[str] = None
    plazo_pago: Optional[int] = None

@app.post("/facturas/titular/{id}/vincular")
def vincular_titular_factura(id: str, v: VincularTitularIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if v.plazo_pago is not None:
                cur.execute("""
                    UPDATE titulares
                    SET cuit=%s,
                        razon_social=COALESCE(NULLIF(razon_social,''), %s),
                        plazo_pago=%s
                    WHERE id=%s
                    RETURNING id, nombre, plazo_pago
                """, (_solo_digitos(v.cuit), v.razon_social, v.plazo_pago, id))
            else:
                cur.execute("""
                    UPDATE titulares
                    SET cuit=%s,
                        razon_social=COALESCE(NULLIF(razon_social,''), %s)
                    WHERE id=%s
                    RETURNING id, nombre, plazo_pago
                """, (_solo_digitos(v.cuit), v.razon_social, id))
            row = cur.fetchone()
        conn.commit()
        if not row:
            return {"ok": False, "error": "Titular no encontrado"}
        return {"ok": True, "id": row["id"], "nombre": row["nombre"], "plazo_pago": row["plazo_pago"]}
    finally:
        conn.close()

@app.delete("/titulares/{id}")
def eliminar_titular(id: str):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM titulares WHERE id = %s", (id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@app.delete("/cashflow/{id}")
def eliminar_cashflow(id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE operaciones SET id_pago = NULL WHERE id_pago = %s", (id,))
            cur.execute("DELETE FROM cheques_emitidos WHERE id_cashflow = %s", (id,))
            cur.execute("DELETE FROM cashflow WHERE id = %s", (id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

class CashflowUpdateIn(BaseModel):
    importe: float

@app.put("/cashflow/{id}")
def actualizar_cashflow(id: int, c: CashflowUpdateIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE cashflow SET importe=%s WHERE id=%s", (c.importe, id))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@app.delete("/operaciones/{id}")
def eliminar_operacion(id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM operaciones WHERE id = %s", (id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

class ItemFacturaIn(BaseModel):
    producto: Optional[str] = None
    cantidad: Optional[float] = None
    precio_unitario: Optional[float] = None
    total_linea: Optional[float] = None
    cod_cuenta: Optional[str] = None

class FacturaGuardarIn(BaseModel):
    fecha: str
    id_titular: str
    id_tipo_comprobante: Optional[int] = None
    numero_comprobante: str = ""
    descripcion: str = ""
    importe: float
    id_fondo: Optional[int] = None
    fecha_vencimiento: Optional[str] = None
    items: list[ItemFacturaIn] = []

@app.post("/facturas/guardar")
def guardar_factura(c: FacturaGuardarIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            fecha = date.fromisoformat(c.fecha)
            id_tipo = c.id_tipo_comprobante or 999
            id_titular = str(c.id_titular)

            num_norm = _solo_digitos(c.numero_comprobante)
            if num_norm:
                cur.execute("""
                    SELECT id FROM operaciones
                    WHERE id_titular = %s
                      AND regexp_replace(COALESCE(numero_comprobante,''),'\\D','','g') = %s
                    LIMIT 1
                """, (id_titular, num_norm))
                existe = cur.fetchone()
                if existe:
                    return {"ok": False, "duplicado": True, "id_existente": existe["id"]}

            cur.execute("""
                INSERT INTO operaciones (fecha, id_titular, id_tipo_comprobante, numero_comprobante, descripcion, importe, mes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (fecha, id_titular, id_tipo, c.numero_comprobante, c.descripcion, c.importe, fecha.month))
            id_operacion = cur.fetchone()["id"]

            plazo = None
            if not c.fecha_vencimiento:
                cur.execute("SELECT plazo_pago FROM titulares WHERE id = %s", (id_titular,))
                row = cur.fetchone()
                if row and row["plazo_pago"] and row["plazo_pago"] > 0:
                    plazo = row["plazo_pago"]
            fecha_vto = None
            if c.fecha_vencimiento or plazo:
                fecha_vto = date.fromisoformat(c.fecha_vencimiento) if c.fecha_vencimiento else fecha + timedelta(days=plazo)
                id_fondo = c.id_fondo
                if not id_fondo:
                    cur.execute("SELECT fondo_def FROM titulares WHERE id = %s", (id_titular,))
                    r = cur.fetchone()
                    if r and r["fondo_def"]:
                        id_fondo = r["fondo_def"]
                if id_fondo:
                    cur.execute("""
                        INSERT INTO cashflow (mes, fecha, id_titular, detalle, importe, id_fondo, id_operacion, confirmado)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, false)
                    """, (fecha_vto.month, fecha_vto, id_titular, c.descripcion, -abs(c.importe), id_fondo, id_operacion))

            for it in c.items:
                cur.execute("""
                    INSERT INTO operaciones_items (id_operacion, producto, cantidad, precio_unitario, total_linea, cod_cuenta)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (id_operacion, it.producto, it.cantidad, it.precio_unitario, it.total_linea, it.cod_cuenta))

                if it.cod_cuenta and it.producto:
                    cur.execute("""
                        INSERT INTO imputacion_producto (patron_producto, id_titular, cod_cuenta)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (lower(patron_producto), COALESCE(id_titular, ''))
                        DO UPDATE SET cod_cuenta = EXCLUDED.cod_cuenta, creado_en = now()
                    """, (it.producto, id_titular, it.cod_cuenta))

        conn.commit()
        return {
            "ok": True,
            "id_operacion": id_operacion,
            "items_guardados": len(c.items),
            "fecha_vencimiento": str(fecha_vto) if fecha_vto else None,
        }
    finally:
        conn.close()

@app.get("/proyeccion_alerta")
def get_proyeccion_alerta():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT f.id, f.nombre, f.abrev, f.slot, f.moneda,
                       f.saldo_inicial +
                       COALESCE(SUM(CASE WHEN c.confirmado = true AND c.fecha <= CURRENT_DATE THEN c.importe ELSE 0 END), 0)
                       AS saldo_actual
                FROM fondos f
                LEFT JOIN cashflow c ON c.id_fondo = f.id
                WHERE f.slot IS NOT NULL AND f.activo = true AND f.moneda = 'ARS'
                GROUP BY f.id, f.nombre, f.abrev, f.slot, f.moneda, f.saldo_inicial
                ORDER BY f.orden
            """)
            fondos = cur.fetchall()

            cur.execute("""
                SELECT c.id_fondo, c.fecha, SUM(c.importe) as total
                FROM cashflow c
                JOIN fondos f ON c.id_fondo = f.id
                WHERE c.fecha > CURRENT_DATE
                  AND f.moneda = 'ARS'
                  AND f.slot IS NOT NULL
                GROUP BY c.id_fondo, c.fecha
                ORDER BY c.fecha ASC
            """)
            movimientos = cur.fetchall()

        mov_por_fondo = defaultdict(list)
        for m in movimientos:
            mov_por_fondo[m["id_fondo"]].append(m)

        primer_rojo_por_fondo = {}
        for f in fondos:
            saldo = float(f["saldo_actual"])
            for m in mov_por_fondo[f["id"]]:
                saldo += float(m["total"])
                if saldo < 0:
                    primer_rojo_por_fondo[f["id"]] = {
                        "fecha": str(m["fecha"]),
                        "saldo": round(saldo, 1)
                    }
                    break

        saldo_total = sum(float(f["saldo_actual"]) for f in fondos)
        todas_fechas = sorted(set(str(m["fecha"]) for m in movimientos))
        primer_rojo_total = None
        for fecha in todas_fechas:
            for f in fondos:
                for m in mov_por_fondo[f["id"]]:
                    if str(m["fecha"]) == fecha:
                        saldo_total += float(m["total"])
            if saldo_total < 0 and primer_rojo_total is None:
                primer_rojo_total = {
                    "fecha": fecha,
                    "saldo": round(saldo_total, 1)
                }
                break

        return {
            "primer_rojo_total": primer_rojo_total,
            "primer_rojo_por_fondo": primer_rojo_por_fondo
        }
    finally:
        conn.close()
