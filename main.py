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

@app.get("/fondos")
def get_fondos():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT f.id, f.nombre, f.tipo, f.moneda, f.activo, f.es_sistema,
                       f.saldo_inicial, COALESCE(SUM(c.importe),0) as movimientos
                FROM fondos f
                LEFT JOIN cashflow c ON c.id_fondo = f.id
                WHERE f.activo = true
                GROUP BY f.id, f.nombre, f.tipo, f.moneda, f.activo, f.es_sistema, f.saldo_inicial
                ORDER BY f.id
            """)
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/fondos_admin")
def get_fondos_admin():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nombre, tipo, moneda, saldo_inicial, activo, es_sistema FROM fondos ORDER BY id")
            return cur.fetchall()
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
                SELECT id, nombre, nivel1,
                       COALESCE(tipo_titular, 'PROVEEDOR') tipo_titular,
                       COALESCE(plazo_pago, 0) plazo_pago
                FROM titulares
                ORDER BY CASE WHEN nivel1='SISTEMA' THEN 0 ELSE 1 END, nombre
            """)
            return cur.fetchall()
    finally:
        conn.close()

class TitularIn(BaseModel):
    nombre: str
    nivel1: str
    tipo_titular: str
    plazo_pago: int

@app.post("/titulares")
def crear_titular(t: TitularIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO titulares (nombre, nivel1, tipo_titular, plazo_pago)
                VALUES (%s, %s, %s, %s)
            """, (t.nombre, t.nivel1, t.tipo_titular, t.plazo_pago))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@app.put("/titulares/{id}")
def actualizar_titular(id: int, t: TitularIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE titulares SET nombre=%s, nivel1=%s, tipo_titular=%s, plazo_pago=%s
                WHERE id=%s
            """, (t.nombre, t.nivel1, t.tipo_titular, t.plazo_pago, id))
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
                       c.detalle, c.importe, c.cod_cuenta,
                       c.confirmado
                FROM cashflow c
                LEFT JOIN titulares t ON c.id_titular = t.id
                LEFT JOIN fondos f ON c.id_fondo = f.id
            """
            if where:
                sql += " WHERE " + " AND ".join(where)
            sql += " ORDER BY c.fecha DESC, c.confirmado ASC LIMIT 500"
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
                SELECT c.id, c.fecha, t.nombre titular, f.nombre fondo,
                       c.detalle, c.importe
                FROM cashflow c
                LEFT JOIN titulares t ON c.id_titular = t.id
                LEFT JOIN fondos f ON c.id_fondo = f.id
                WHERE c.confirmado = false AND c.fecha <= CURRENT_DATE
                ORDER BY c.fecha ASC
            """)
            return cur.fetchall()
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
            cur.execute("""
                INSERT INTO cashflow (mes, fecha, id_titular, cod_cuenta, detalle, importe, id_fondo, confirmado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, true)
            """, (fecha.month, fecha, m.id_titular, m.cod_cuenta, m.detalle, m.importe, m.id_fondo))
        conn.commit()
        return {"ok": True}
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
            if id_titular:
                where.append(f"o.id_titular = {id_titular}")
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
            cur.execute(sql)
            return cur.fetchall()
    finally:
        conn.close()

class ComprobanteIn(BaseModel):
    fecha: str
    id_titular: int
    id_tipo_comprobante: int
    numero_comprobante: str
    descripcion: str
    importe: float
    id_fondo: Optional[int] = None
    fecha_vencimiento: Optional[str] = None

@app.post("/operaciones")
def crear_comprobante(c: ComprobanteIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            fecha = date.fromisoformat(c.fecha)

            cur.execute("""
                INSERT INTO operaciones (fecha, id_titular, id_tipo_comprobante, numero_comprobante, descripcion, importe, mes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (fecha, str(c.id_titular), c.id_tipo_comprobante, c.numero_comprobante, c.descripcion, c.importe, fecha.month))
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
                    """, (fecha_vto.month, fecha_vto, str(c.id_titular), c.descripcion, -abs(c.importe), id_fondo, id_operacion))

                conn.commit()
                return {
                    "ok": True,
                    "id_operacion": id_operacion,
                    "proyectado": True,
                    "fecha_vencimiento": str(fecha_vto)
                }
            else:
                conn.commit()
                return {
                    "ok": True,
                    "id_operacion": id_operacion,
                    "proyectado": False,
                    "sin_plazo": True
                }
    finally:
        conn.close()

@app.get("/plan_cuentas")
def get_plan_cuentas():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT niv1_desc, niv2_desc, nombre, signo FROM plan_de_cuentas ORDER BY niv1,niv2,niv3,niv4,niv5")
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/balance")
def get_balance(mes: Optional[int] = None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            where_mes = f"AND EXTRACT(MONTH FROM c.fecha)={mes}" if mes else ""
            cur.execute(f"""
                SELECT p.niv2_desc subtipo, p.nombre cuenta, COALESCE(SUM(c.importe),0) importe
                FROM plan_de_cuentas p
                LEFT JOIN cashflow c ON c.cod_cuenta = p.nombre {where_mes}
                WHERE p.niv1=1
                GROUP BY p.niv2_desc, p.nombre, p.niv1, p.niv2, p.niv3, p.niv4, p.niv5
                HAVING COALESCE(SUM(c.importe),0) <> 0
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
