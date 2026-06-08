from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB = "postgresql://neondb_owner:npg_0QazKFN8logm@ep-sweet-block-aq1035ng-pooler.c-8.us-east-1.aws.neon.tech/neondb?sslmode=require"

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
            cur.execute("SELECT id, nombre, tipo, moneda, saldo_inicial, activo, es_sistema FROM fondos WHERE activo=true ORDER BY id")
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/titulares")
def get_titulares():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nombre, nivel1 FROM titulares ORDER BY nombre")
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/cashflow")
def get_cashflow(mes: int = None, id_fondo: int = None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            where = []
            if mes:
                where.append(f"c.mes={mes}")
            if id_fondo:
                where.append(f"c.id_fondo={id_fondo}")
            sql = """
                SELECT c.fecha, t.nombre titular, f.nombre fondo, c.detalle, c.importe
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
