from dotenv import load_dotenv
import pathlib
load_dotenv(dotenv_path=pathlib.Path(__file__).parent / ".env")
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import date
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
                SELECT c.id, c.fecha, t.nombre titular, f.nombre fondo, c.detalle, c.importe, c.cod_cuenta
                FROM cashflow c
                LEFT JOIN titulares t ON c.id_titular = t.id
                LEFT JOIN fondos f ON c.id_fondo = f.id
            """
            if where:
                sql += " WHERE " + " AND ".join(where)
            sql += " ORDER BY c.fecha DESC LIMIT 500"
            cur.execute(sql)
            return cur.fetchall()
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
                INSERT INTO cashflow (mes, fecha, id_titular, cod_cuenta, detalle, importe, id_fondo)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
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

@app.post("/operaciones")
def crear_comprobante(c: ComprobanteIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            fecha = date.fromisoformat(c.fecha)
            cur.execute("""
                INSERT INTO operaciones (fecha, id_titular, id_tipo_comprobante, numero_comprobante, descripcion, importe, mes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (fecha, c.id_titular, c.id_tip
