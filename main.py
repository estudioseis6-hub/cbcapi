# ============================================================
# MAIN.PY — CBC Sistema Contable EMI— Backend FastAPI
# ============================================================
from dotenv import load_dotenv
import pathlib
import json
load_dotenv(dotenv_path=pathlib.Path(__file__).parent / ".env")
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import date, timedelta
from typing import Optional, List
from pydantic import BaseModel
from collections import defaultdict
import uuid

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from circuito_f import router as circuito_f_router
app.include_router(circuito_f_router)

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
            cur.execute("SELECT valor FROM configuracion WHERE clave = 'fecha_inicio_sistema'")
            fila_corte = cur.fetchone()
            fecha_corte = fila_corte["valor"] if fila_corte else None
            cur.execute("""
                SELECT f.id, f.nombre, f.tipo, f.moneda, f.activo, f.es_sistema,
                       COALESCE(si.importe, 0) AS saldo_inicial,
                       f.slot, f.abrev, f.grupo,
                       COALESCE(SUM(CASE WHEN c.confirmado = true AND c.fecha <= (CURRENT_TIMESTAMP AT TIME ZONE 'America/Argentina/Buenos_Aires')::date THEN c.importe ELSE 0 END), 0) AS movimientos,
                       COALESCE(SUM(CASE WHEN c.fecha > (CURRENT_TIMESTAMP AT TIME ZONE 'America/Argentina/Buenos_Aires')::date THEN c.importe ELSE 0 END), 0) AS proyectado
                FROM fondos f
                LEFT JOIN cashflow c ON c.id_fondo = f.id
                LEFT JOIN saldos_iniciales si ON si.cuenta_patrimonial = f.cuenta_patrimonial
                    AND si.fecha = %s
                WHERE f.slot IS NOT NULL
                GROUP BY f.id, f.nombre, f.tipo, f.moneda, f.activo, f.es_sistema, si.importe, f.slot, f.abrev, f.grupo
                ORDER BY f.orden
            """, (fecha_corte,))
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/fondos_admin")
def get_fondos_admin():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nombre, abrev, tipo, moneda, saldo_inicial, activo, es_sistema, cuenta_patrimonial FROM fondos ORDER BY id")
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
    cuenta_patrimonial: Optional[str] = None

@app.put("/fondos/{id}")
def actualizar_fondo(id: int, f: FondoUpdateIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE fondos SET nombre=%s, abrev=%s, tipo=%s, moneda=%s, saldo_inicial=%s, activo=%s, cuenta_patrimonial=%s
                WHERE id=%s
            """, (f.nombre, f.abrev, f.tipo, f.moneda, f.saldo_inicial, f.activo, f.cuenta_patrimonial, id))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

class FondoIn(BaseModel):
    nombre: str
    abrev: str
    tipo: str
    moneda: str
    grupo: str  # "CORRIENTE" (día a día) o "NO_CORRIENTE" (reserva)
    saldo_inicial: float
    nombre_cuenta_contable: str

@app.post("/fondos")
def crear_fondo(f: FondoIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Efectivo va dentro de "Efectivo Circulante" (niv5=1); cualquier otro tipo (Banco,
            # Billetera, etc.) va dentro de "Cuentas Bancarias y Otras" (niv5=2) — mismos
            # niveles 1-4 ya fijos para toda cuenta de Disponibilidades.
            niv5 = 1 if f.tipo == "Efectivo" else 2
            niv5_desc = "Efectivo Circulante" if niv5 == 1 else "Cuentas Bancarias y Otras"
            cur.execute("""
                SELECT COALESCE(MAX(niv6), 0) AS maximo FROM plan_de_cuentas
                WHERE niv1 = 2 AND niv2 = 1 AND niv3 = 1 AND niv4 = 1 AND niv5 = %s
            """, (niv5,))
            siguiente_niv6 = cur.fetchone()["maximo"] + 1
            id_codigo = f"2.1.1.1.{niv5}.{siguiente_niv6}."
            cur.execute("""
                INSERT INTO plan_de_cuentas
                    (niv1, niv1_desc, niv2, niv2_desc, niv3, niv3_desc, niv4, niv4_desc, niv5, niv5_desc, niv6, niv6_desc, nombre, id_codigo, activo)
                VALUES (2, 'Patrimonial', 1, 'Activo', 1, 'Activos Corrientes', 1, 'Disponibilidades', %s, %s, %s, %s, %s, %s, true)
            """, (niv5, niv5_desc, siguiente_niv6, f.nombre_cuenta_contable, f.nombre_cuenta_contable, id_codigo))
            # "slot" solo marca que el Fondo está activo/visible (no es una posición fija de
            # columna) y "orden" define en qué lugar aparece — el siguiente disponible.
            cur.execute("SELECT COALESCE(MAX(slot), 0) AS s, COALESCE(MAX(orden), 0) AS o FROM fondos")
            fila = cur.fetchone()
            siguiente_slot, siguiente_orden = fila["s"] + 1, fila["o"] + 1
            cur.execute("""
                INSERT INTO fondos (nombre, abrev, tipo, moneda, grupo, saldo_inicial, es_sistema, cuenta_patrimonial, slot, orden, activo)
                VALUES (%s, %s, %s, %s, %s, %s, false, %s, %s, %s, true)
            """, (f.nombre, f.abrev, f.tipo, f.moneda, f.grupo, f.saldo_inicial, f.nombre_cuenta_contable, siguiente_slot, siguiente_orden))
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
                       cod1, cod2, cod3, cod4, cod5, cod6, cod7, cod8, cod9, cod10,
                       fondo_def, razon_social, cuit, cond_fiscal,
                       genera_cc, activo, iva_default, cuenta_patrimonial
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
    cod6: Optional[str] = None
    cod7: Optional[str] = None
    cod8: Optional[str] = None
    cod9: Optional[str] = None
    cod10: Optional[str] = None
    fondo_def: Optional[str] = None
    genera_cc: Optional[bool] = True
    activo: Optional[bool] = True
    iva_default: Optional[float] = None
    cuenta_patrimonial: Optional[str] = None

@app.post("/titulares")
def crear_titular(t: TitularIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO titulares (nombre, nivel1, nivel2, nivel3, nivel4, tipo_titular, plazo_pago,
                       razon_social, cuit, cond_fiscal,
                       cod1, cod2, cod3, cod4, cod5, cod6, cod7, cod8, cod9, cod10,
                       fondo_def, genera_cc, activo, iva_default, cuenta_patrimonial)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (t.nombre, t.nivel1, t.nivel2, t.nivel3, t.nivel4, t.tipo_titular, t.plazo_pago,
                  t.razon_social, t.cuit, t.cond_fiscal,
                  t.cod1, t.cod2, t.cod3, t.cod4, t.cod5, t.cod6, t.cod7, t.cod8, t.cod9, t.cod10,
                  t.fondo_def, t.genera_cc, t.activo, t.iva_default, t.cuenta_patrimonial))
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
                       cod6=%s, cod7=%s, cod8=%s, cod9=%s, cod10=%s,
                       fondo_def=%s, genera_cc=%s, activo=%s, iva_default=%s, cuenta_patrimonial=%s
                WHERE id=%s
            """, (t.nombre, t.nivel1, t.nivel2, t.nivel3, t.nivel4, t.tipo_titular, t.plazo_pago,
                  t.razon_social, t.cuit, t.cond_fiscal,
                  t.cod1, t.cod2, t.cod3, t.cod4, t.cod5,
                  t.cod6, t.cod7, t.cod8, t.cod9, t.cod10,
                  t.fondo_def, t.genera_cc, t.activo, t.iva_default, t.cuenta_patrimonial, id))
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
                       c.confirmado, c.id_operacion, c.id_titular,
                       ch.nro_cheque, ch.fecha_emision, ch.fecha_vencimiento,
                       ch.estado AS estado_cheque,
                       EXISTS(SELECT 1 FROM operaciones o WHERE o.id_pago = c.id) AS cancela_cc,
                       c.id_transferencia
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
                SET fecha = (CURRENT_TIMESTAMP AT TIME ZONE 'America/Argentina/Buenos_Aires')::date,
                    mes = EXTRACT(MONTH FROM (CURRENT_TIMESTAMP AT TIME ZONE 'America/Argentina/Buenos_Aires'))::integer
                WHERE confirmado = false
                AND fecha < (CURRENT_TIMESTAMP AT TIME ZONE 'America/Argentina/Buenos_Aires')::date
                AND id NOT IN (SELECT id_cashflow FROM cheques_emitidos WHERE id_cashflow IS NOT NULL)
            """)
            movidos = cur.rowcount
            conn.commit()
            cur.execute("""
                SELECT c.id, c.fecha, t.nombre titular, f.nombre fondo,
                       c.detalle, c.importe, c.id_operacion, c.id_titular
                FROM cashflow c
                LEFT JOIN titulares t ON c.id_titular = t.id
                LEFT JOIN fondos f ON c.id_fondo = f.id
                WHERE c.confirmado = false AND c.fecha <= (CURRENT_TIMESTAMP AT TIME ZONE 'America/Argentina/Buenos_Aires')::date
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
            # Si es un cheque de apertura, marcarlo como debitado y generar el asiento que
            # cancela el Pasivo pendiente y baja el Fondo real — mismo criterio que si se
            # marcara Debitado directo desde la solapa de Cheques de Apertura en Balance.
            cur.execute("SELECT id_cheque_apertura, id_fondo FROM cashflow WHERE id=%s", (id,))
            row = cur.fetchone()
            if row and row["id_cheque_apertura"]:
                cur.execute("SELECT debitado, numero, importe, id_asiento_debito FROM cheques_apertura WHERE id = %s", (row["id_cheque_apertura"],))
                cheque = cur.fetchone()
                cur.execute("UPDATE cheques_apertura SET debitado=true WHERE id=%s", (row["id_cheque_apertura"],))
                if cheque and not cheque["debitado"] and not cheque["id_asiento_debito"] and row["id_fondo"]:
                    cur.execute("SELECT cuenta_patrimonial, nombre FROM fondos WHERE id = %s", (row["id_fondo"],))
                    fila_fondo = cur.fetchone()
                    cuenta_fondo = (fila_fondo["cuenta_patrimonial"] if fila_fondo else None) or (fila_fondo["nombre"] if fila_fondo else None)
                    if cuenta_fondo:
                        nuevo_asiento = _crear_asiento(cur, "CHEQUE_APERTURA_DEBITO", f"Débito de cheque apertura #{cheque['numero'] or ''}", fecha)
                        _agregar_lineas_asiento(cur, nuevo_asiento, [
                            ("Valores Emitidos — Cheques Pendientes", cheque["importe"], 0, "Débito de cheque"),
                            (cuenta_fondo, 0, cheque["importe"], "Débito de cheque"),
                        ])
                        cur.execute("UPDATE cheques_apertura SET id_asiento_debito = %s WHERE id = %s", (nuevo_asiento, row["id_cheque_apertura"]))
                        # Si se revierte este asiento: NO se borra el cheque, vuelve a Pendiente
                        # y su proyección en Tesorería se des-confirma (no se borra).
                        _set_reversion(cur, nuevo_asiento, [
                            {"tabla": "cheques_apertura", "where_columna": "id", "where_valor": row["id_cheque_apertura"], "tipo": "UPDATE",
                             "campos": {"debitado": False, "id_asiento_debito": None}},
                            {"tabla": "cashflow", "where_columna": "id_cheque_apertura", "where_valor": row["id_cheque_apertura"], "tipo": "UPDATE",
                             "campos": {"confirmado": False}},
                        ])

            # Si es un ECheq emitido para pagar una factura (registrar_pago_echeq), el mismo
            # criterio que un cheque de apertura: al confirmarse el débito, se cancela la deuda
            # de "Valores Emitidos" y baja el Fondo real.
            cur.execute("SELECT id, id_asiento_debito FROM cheques_emitidos WHERE id_cashflow = %s", (id,))
            cheque_emitido = cur.fetchone()
            if cheque_emitido and not cheque_emitido["id_asiento_debito"] and row and row["id_fondo"]:
                cur.execute("SELECT importe FROM cashflow WHERE id = %s", (id,))
                fila_cf = cur.fetchone()
                importe_echeq = abs(fila_cf["importe"]) if fila_cf else 0
                cur.execute("SELECT cuenta_patrimonial, nombre FROM fondos WHERE id = %s", (row["id_fondo"],))
                fila_fondo = cur.fetchone()
                cuenta_fondo = (fila_fondo["cuenta_patrimonial"] if fila_fondo else None) or (fila_fondo["nombre"] if fila_fondo else None)
                if cuenta_fondo and importe_echeq:
                    nuevo_asiento = _crear_asiento(cur, "PAGO_ECHEQ_DEBITO", "Débito de ECheq emitido", fecha)
                    _agregar_lineas_asiento(cur, nuevo_asiento, [
                        ("Valores Emitidos — Cheques Pendientes", importe_echeq, 0, "Débito de ECheq"),
                        (cuenta_fondo, 0, importe_echeq, "Débito de ECheq"),
                    ])
                    cur.execute("UPDATE cheques_emitidos SET id_asiento_debito = %s WHERE id_cashflow = %s", (nuevo_asiento, id))
                    _set_reversion(cur, nuevo_asiento, [
                        {"tabla": "cheques_emitidos", "where_columna": "id_cashflow", "where_valor": id, "tipo": "UPDATE",
                         "campos": {"id_asiento_debito": None, "estado": "EMITIDO"}},
                        {"tabla": "cashflow", "where_columna": "id", "where_valor": id, "tipo": "UPDATE",
                         "campos": {"confirmado": False}},
                    ])
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
            id_asiento = _crear_asiento(cur, "MOVIMIENTO_MANUAL", m.detalle, fecha)
            # Líneas reales del asiento: si es un egreso, el Fondo se acredita (sale plata) y la
            # cuenta de gasto se debita. Si es un ingreso, al revés.
            cur.execute("SELECT nombre, cuenta_patrimonial FROM fondos WHERE id = %s", (m.id_fondo,))
            fila_fondo = cur.fetchone()
            cuenta_fondo = (fila_fondo["cuenta_patrimonial"] if fila_fondo else None) or (fila_fondo["nombre"] if fila_fondo else f"Fondo #{m.id_fondo}")
            monto = abs(m.importe)
            if m.importe < 0:
                lineas = [(m.cod_cuenta, monto, 0, m.detalle), (cuenta_fondo, 0, monto, m.detalle)]
            else:
                lineas = [(cuenta_fondo, monto, 0, m.detalle), (m.cod_cuenta, 0, monto, m.detalle)]
            _agregar_lineas_asiento(cur, id_asiento, lineas)
            cur.execute("""
                INSERT INTO cashflow (mes, fecha, id_titular, cod_cuenta, detalle, importe, id_fondo, confirmado, id_asiento)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (fecha.month, fecha, m.id_titular, m.cod_cuenta, m.detalle, m.importe, m.id_fondo, confirmado, id_asiento))
            _set_reversion(cur, id_asiento, [
                {"tabla": "cashflow", "where_columna": "id_asiento", "where_valor": id_asiento, "tipo": "DELETE"},
            ])
        conn.commit()
        return {"ok": True, "id_asiento": id_asiento}
    finally:
        conn.close()

class AcreditacionTarjetasIn(BaseModel):
    fecha: str
    id_fondo: int
    importe: float

@app.post("/acreditacion_tarjetas")
def crear_acreditacion_tarjetas(a: AcreditacionTarjetasIn):
    """Carga rápida: solo pide Fecha, Fondo e Importe — la cuenta contable
    ('Tarj. Credit. Pend. Acreditacion') ya se sabe de antemano, no hace falta elegirla."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            fecha = date.fromisoformat(a.fecha)
            confirmado = fecha <= date.today()
            monto = abs(a.importe)
            detalle = f"Acreditación de tarjetas (${monto:,.1f})"
            id_asiento = _crear_asiento(cur, "MOVIMIENTO_MANUAL", detalle, fecha)
            cur.execute("SELECT nombre, cuenta_patrimonial FROM fondos WHERE id = %s", (a.id_fondo,))
            fila_fondo = cur.fetchone()
            cuenta_fondo = (fila_fondo["cuenta_patrimonial"] if fila_fondo else None) or (fila_fondo["nombre"] if fila_fondo else f"Fondo #{a.id_fondo}")
            cur.execute("SELECT id FROM titulares WHERE nombre = 'Ingresos Generales' LIMIT 1")
            fila_titular = cur.fetchone()
            id_titular_generico = fila_titular["id"] if fila_titular else None
            # Entra plata al banco (Debe) / se cancela el crédito pendiente (Haber).
            _agregar_lineas_asiento(cur, id_asiento, [
                (cuenta_fondo, monto, 0, detalle),
                ("Tarj. Credit. Pend. Acreditacion", 0, monto, detalle),
            ])
            cur.execute("""
                INSERT INTO cashflow (mes, fecha, id_titular, cod_cuenta, detalle, importe, id_fondo, confirmado, id_asiento)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (fecha.month, fecha, id_titular_generico, "Tarj. Credit. Pend. Acreditacion", detalle, monto, a.id_fondo, confirmado, id_asiento))
            _set_reversion(cur, id_asiento, [
                {"tabla": "cashflow", "where_columna": "id_asiento", "where_valor": id_asiento, "tipo": "DELETE"},
            ])
        conn.commit()
        return {"ok": True, "id_asiento": id_asiento}
    finally:
        conn.close()

class TransferenciaIn(BaseModel):
    fecha: str
    id_fondo_origen: int
    id_fondo_destino: int
    importe: float
    detalle: str = ""

@app.post("/transferencia_fondos")
def crear_transferencia(t: TransferenciaIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            fecha = date.fromisoformat(t.fecha)
            confirmado = fecha <= date.today()
            id_transf = str(uuid.uuid4())
            # Nombres reales de los fondos, para que la descripción del asiento diga
            # "Banco Santander → Efectivo Caja" en vez de un texto genérico.
            cur.execute("SELECT id, nombre, cuenta_patrimonial FROM fondos WHERE id IN (%s, %s)", (t.id_fondo_origen, t.id_fondo_destino))
            filas_fondo = {r["id"]: r for r in cur.fetchall()}
            nombre_origen = filas_fondo.get(t.id_fondo_origen, {}).get("nombre", f"Fondo #{t.id_fondo_origen}")
            nombre_destino = filas_fondo.get(t.id_fondo_destino, {}).get("nombre", f"Fondo #{t.id_fondo_destino}")
            cuenta_origen = filas_fondo.get(t.id_fondo_origen, {}).get("cuenta_patrimonial") or nombre_origen
            cuenta_destino = filas_fondo.get(t.id_fondo_destino, {}).get("cuenta_patrimonial") or nombre_destino
            monto_fmt = f"{abs(t.importe):,.1f}"
            detalle_base = t.detalle or f"Transferencia: {nombre_origen} → {nombre_destino} (${monto_fmt})"
            detalle = detalle_base
            # Un solo asiento para las dos patas — anular una, anula la otra junto con ella.
            id_asiento = _crear_asiento(cur, "TRANSFERENCIA", detalle_base, fecha)
            # Líneas reales del asiento: entra plata al destino (debe), sale del origen (haber).
            _agregar_lineas_asiento(cur, id_asiento, [
                (cuenta_destino, abs(t.importe), 0, f"Ingresa a {nombre_destino}"),
                (cuenta_origen, 0, abs(t.importe), f"Sale de {nombre_origen}"),
            ])
            cur.execute("""
                INSERT INTO cashflow (mes, fecha, id_titular, cod_cuenta, detalle, importe, id_fondo, confirmado, id_transferencia, id_asiento)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (fecha.month, fecha, 717, "Transferencias", detalle, -abs(t.importe), t.id_fondo_origen, confirmado, id_transf, id_asiento))
            cur.execute("""
                INSERT INTO cashflow (mes, fecha, id_titular, cod_cuenta, detalle, importe, id_fondo, confirmado, id_transferencia, id_asiento)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (fecha.month, fecha, 716, "Transferencias", detalle, abs(t.importe), t.id_fondo_destino, confirmado, id_transf, id_asiento))
            _set_reversion(cur, id_asiento, [
                {"tabla": "cashflow", "where_columna": "id_asiento", "where_valor": id_asiento, "tipo": "DELETE"},
            ])
        conn.commit()
        return {"ok": True, "id_transferencia": id_transf, "id_asiento": id_asiento}
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
                       o.es_informal,
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
            es_informal = (c.id_tipo_comprobante == 995) or ((c.sin_factura or 0) > 0)
            num_norm = _solo_digitos(c.numero_comprobante)
            if num_norm:
                cur.execute("""
                    SELECT id FROM operaciones
                    WHERE id_titular = %s
                      AND regexp_replace(COALESCE(numero_comprobante,''),'\\D','','g') = %s
                    LIMIT 1
                """, (str(c.id_titular), num_norm))
                existe = cur.fetchone()
                if existe:
                    return {"ok": False, "duplicado": True, "id_existente": existe["id"]}
            importe = (
                (c.subtotal or 0) + (c.exento or 0)
                + (c.iva_105 or 0) + (c.iva_21 or 0) + (c.iva_27 or 0)
                + (c.perc_iva or 0) + (c.perc_iibb or 0) + (c.perc_otras or 0)
                + (c.sin_factura or 0)
            )

            # Buscamos las cuentas del Titular: cuenta_patrimonial (el Pasivo, va al Haber)
            # y nivel4 (la cuenta de Gasto/Resultado, va al Debe) — nada de esto se tipea a mano
            # en el formulario, ya está configurado una sola vez en Titulares.
            cur.execute("SELECT cuenta_patrimonial, nivel4 FROM titulares WHERE id = %s", (str(c.id_titular),))
            row_titular = cur.fetchone() or {}
            cuenta_pasivo = row_titular.get("cuenta_patrimonial")
            cuenta_gasto = row_titular.get("nivel4")

            lineas_asiento = []
            monto_gasto = (c.subtotal or 0) + (c.exento or 0) + (c.sin_factura or 0)
            if cuenta_gasto and monto_gasto:
                lineas_asiento.append((cuenta_gasto, monto_gasto, 0, c.descripcion))
            monto_iva = (c.iva_105 or 0) + (c.iva_21 or 0) + (c.iva_27 or 0)
            if monto_iva:
                lineas_asiento.append(("IVA Crédito Fiscal", monto_iva, 0, c.descripcion))
            if c.perc_iva:
                lineas_asiento.append(("Percepción IVA a Cuenta", c.perc_iva, 0, c.descripcion))
            if c.perc_iibb:
                lineas_asiento.append(("Percepción IIBB a Cuenta", c.perc_iibb, 0, c.descripcion))
            if c.perc_otras:
                lineas_asiento.append(("Otras Percepciones a Cuenta", c.perc_otras, 0, c.descripcion))
            if cuenta_pasivo and importe:
                lineas_asiento.append((cuenta_pasivo, 0, importe, c.descripcion))

            id_asiento = _crear_asiento(cur, "COMPROBANTE", f"Factura {c.numero_comprobante} — {c.descripcion}", fecha_compra)
            if lineas_asiento:
                _agregar_lineas_asiento(cur, id_asiento, lineas_asiento)

            cur.execute("""
                INSERT INTO operaciones
                    (fecha, fecha_compra, id_titular, id_tipo_comprobante, numero_comprobante, descripcion, importe, mes,
                     subtotal, exento, iva_105, iva_21, iva_27, perc_iva, perc_iibb, perc_otras, sin_factura, es_informal, id_asiento)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (fecha, fecha_compra, str(c.id_titular), c.id_tipo_comprobante, c.numero_comprobante, c.descripcion, importe, fecha.month,
                  c.subtotal, c.exento, c.iva_105, c.iva_21, c.iva_27, c.perc_iva, c.perc_iibb, c.perc_otras, c.sin_factura, es_informal, id_asiento))
            id_operacion = cur.fetchone()["id"]
            id_fondo = c.id_fondo
            if id_fondo:
                cur.execute("SELECT tipo FROM fondos WHERE id = %s", (id_fondo,))
                fondo_row = cur.fetchone()
                if es_informal and fondo_row and fondo_row["tipo"] != "Efectivo":
                    conn.commit()
                    return {"ok": False, "error_fondo_informal": True}
            else:
                if es_informal:
                    cur.execute("SELECT id FROM fondos WHERE tipo = 'Efectivo' AND moneda = 'ARS' AND activo = true ORDER BY id LIMIT 1")
                    r = cur.fetchone()
                    id_fondo = r["id"] if r else None
                else:
                    cur.execute("SELECT fondo_def FROM titulares WHERE id = %s", (str(c.id_titular),))
                    r = cur.fetchone()
                    id_fondo = r["fondo_def"] if r and r["fondo_def"] else None
            if not id_fondo:
                conn.commit()
                return {"ok": False, "sin_fondo": True}
            plazo = None
            if not c.fecha_vencimiento:
                cur.execute("SELECT plazo_pago FROM titulares WHERE id = %s", (str(c.id_titular),))
                row = cur.fetchone()
                if row and row["plazo_pago"] and row["plazo_pago"] > 0:
                    plazo = row["plazo_pago"]
            if c.fecha_vencimiento:
                fecha_vto = date.fromisoformat(c.fecha_vencimiento)
                sin_plazo = False
            elif plazo:
                fecha_vto = fecha + timedelta(days=plazo)
                sin_plazo = False
            else:
                fecha_vto = fecha + timedelta(days=30)
                sin_plazo = True
            cur.execute("""
                INSERT INTO cashflow (mes, fecha, id_titular, detalle, importe, id_fondo, id_operacion, confirmado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, false)
            """, (fecha_vto.month, fecha_vto, str(c.id_titular), c.descripcion, -abs(importe), id_fondo, id_operacion))
            _set_reversion(cur, id_asiento, [
                {"tabla": "cashflow", "where_columna": "id_operacion", "where_valor": id_operacion, "tipo": "DELETE"},
                {"tabla": "operaciones", "where_columna": "id", "where_valor": id_operacion, "tipo": "DELETE"},
            ])
            conn.commit()
            return {"ok": True, "id_operacion": id_operacion, "proyectado": True, "fecha_vencimiento": str(fecha_vto), "sin_plazo": sin_plazo, "es_informal": es_informal}
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
                WHERE p.niv1 = 1
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
            cur.execute("SELECT es_informal FROM operaciones WHERE id = ANY(%s) AND es_informal = true LIMIT 1", (p.ids_operaciones,))
            if cur.fetchone():
                cur.execute("SELECT tipo FROM fondos WHERE id = %s", (p.id_fondo,))
                fondo_row = cur.fetchone()
                if fondo_row and fondo_row["tipo"] != "Efectivo":
                    return {"ok": False, "error_fondo_informal": True}
            cur.execute("SELECT COALESCE(SUM(importe),0) FROM operaciones WHERE id = ANY(%s)", (p.ids_operaciones,))
            total = cur.fetchone()["coalesce"]
            fecha = date.fromisoformat(p.fecha)
            cur.execute("SELECT id FROM cashflow WHERE id_operacion = ANY(%s) AND confirmado = false", (p.ids_operaciones,))
            proyectados = [r["id"] for r in cur.fetchall()]
            if proyectados:
                cur.execute("DELETE FROM cashflow WHERE id = ANY(%s)", (proyectados,))
            # El asiento del pago: se cancela la deuda (Debe, el Pasivo baja) y baja el Fondo
            # real (Haber) — sin esto, Balance nunca se enteraba de que la factura se pagó.
            cur.execute("SELECT cuenta_patrimonial, nombre FROM fondos WHERE id = %s", (p.id_fondo,))
            fila_fondo = cur.fetchone()
            cuenta_fondo = (fila_fondo["cuenta_patrimonial"] if fila_fondo else None) or (fila_fondo["nombre"] if fila_fondo else f"Fondo #{p.id_fondo}")
            monto = abs(total)
            id_asiento = _crear_asiento(cur, "PAGO", p.detalle or f"Pago a Titular #{p.id_titular}", fecha)
            _agregar_lineas_asiento(cur, id_asiento, [
                (p.cod_cuenta, monto, 0, p.detalle),
                (cuenta_fondo, 0, monto, p.detalle),
            ])
            cur.execute("""
                INSERT INTO cashflow (mes, fecha, id_titular, cod_cuenta, detalle, importe, id_fondo, confirmado, id_asiento)
                VALUES (%s, %s, %s, %s, %s, %s, %s, true, %s)
                RETURNING id
            """, (fecha.month, fecha, str(p.id_titular), p.cod_cuenta, p.detalle, -abs(total), p.id_fondo, id_asiento))
            id_pago = cur.fetchone()["id"]
            cur.execute("UPDATE operaciones SET id_pago = %s WHERE id = ANY(%s)", (id_pago, p.ids_operaciones))
            # Si se revierte: se deshace el pago (vuelve a deberse) y se desvincula la factura,
            # que vuelve a quedar impaga — no se borra la factura en sí, solo el pago.
            _set_reversion(cur, id_asiento, [
                {"tabla": "operaciones", "where_columna": "id_pago", "where_valor": id_pago, "tipo": "UPDATE",
                 "campos": {"id_pago": None}},
                {"tabla": "cashflow", "where_columna": "id_asiento", "where_valor": id_asiento, "tipo": "DELETE"},
            ])
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
            cur.execute("SELECT es_informal FROM operaciones WHERE id = ANY(%s) AND es_informal = true LIMIT 1", (p.ids_operaciones,))
            if cur.fetchone():
                return {"ok": False, "error_fondo_informal": True}
            cur.execute("SELECT COALESCE(SUM(importe),0) FROM operaciones WHERE id = ANY(%s)", (p.ids_operaciones,))
            total = cur.fetchone()["coalesce"]
            fecha_emision = date.fromisoformat(p.fecha_emision)
            fecha_vto = date.fromisoformat(p.fecha_vencimiento)
            cur.execute("SELECT id FROM cashflow WHERE id_operacion = ANY(%s) AND confirmado = false", (p.ids_operaciones,))
            proyectados = [r["id"] for r in cur.fetchall()]
            if proyectados:
                cur.execute("DELETE FROM cashflow WHERE id = ANY(%s)", (proyectados,))
            monto = abs(total)
            # Al emitir el cheque, se cancela la deuda con el Titular (Debe) y aparece una
            # deuda nueva: "Valores Emitidos — Cheques Pendientes" (Haber) — el cheque todavía
            # no salió del banco de verdad, eso pasa después, cuando se confirme el débito.
            id_asiento = _crear_asiento(cur, "PAGO_ECHEQ", p.detalle or f"Cheque emitido #{p.nro_cheque}", fecha_emision)
            _agregar_lineas_asiento(cur, id_asiento, [
                (p.cod_cuenta, monto, 0, p.detalle),
                ("Valores Emitidos — Cheques Pendientes", 0, monto, p.detalle),
            ])
            cur.execute("""
                INSERT INTO cashflow (mes, fecha, id_titular, cod_cuenta, detalle, importe, id_fondo, confirmado, id_asiento)
                VALUES (%s, %s, %s, %s, %s, %s, %s, false, %s)
                RETURNING id
            """, (fecha_vto.month, fecha_vto, str(p.id_titular), p.cod_cuenta, p.detalle, -abs(total), p.id_fondo, id_asiento))
            id_cashflow = cur.fetchone()["id"]
            cur.execute("""
                INSERT INTO cheques_emitidos (nro_cheque, fecha_emision, fecha_vencimiento, estado, id_cashflow, id_asiento)
                VALUES (%s, %s, %s, 'EMITIDO', %s, %s)
            """, (p.nro_cheque, fecha_emision, fecha_vto, id_cashflow, id_asiento))
            cur.execute("UPDATE operaciones SET id_pago = %s WHERE id = ANY(%s)", (id_cashflow, p.ids_operaciones))
            # Si se revierte: el cheque nunca se emitió, la factura vuelve a quedar impaga.
            _set_reversion(cur, id_asiento, [
                {"tabla": "operaciones", "where_columna": "id_pago", "where_valor": id_cashflow, "tipo": "UPDATE",
                 "campos": {"id_pago": None}},
                {"tabla": "cheques_emitidos", "where_columna": "id_cashflow", "where_valor": id_cashflow, "tipo": "DELETE"},
                {"tabla": "cashflow", "where_columna": "id_asiento", "where_valor": id_asiento, "tipo": "DELETE"},
            ])
        conn.commit()
        return {"ok": True, "id_cashflow": id_cashflow, "total": total}
    finally:
        conn.close()

@app.delete("/operaciones/{id}")
def eliminar_operacion(id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id_pago, id_asiento FROM operaciones WHERE id = %s", (id,))
            row = cur.fetchone()
            if not row:
                return {"ok": False, "error": "Operación no encontrada"}
            if row["id_pago"] is not None:
                return {"ok": False, "error_paga": True}
            cur.execute("DELETE FROM cashflow WHERE id_operacion = %s AND confirmado = false", (id,))
            cur.execute("DELETE FROM operaciones WHERE id = %s", (id,))
            # El paso que faltaba: si esta factura tenía un asiento (Gasto, IVA Crédito Fiscal,
            # Percepciones, deuda al Proveedor), hay que anularlo — sino Balance lo sigue contando
            # aunque la factura ya no exista en ningún otro lado.
            if row["id_asiento"] is not None:
                cur.execute("""
                    UPDATE asientos SET anulado = true,
                        fecha_anulacion = (CURRENT_TIMESTAMP AT TIME ZONE 'America/Argentina/Buenos_Aires'),
                        motivo_anulacion = 'Factura eliminada desde Cuenta Corriente'
                    WHERE id = %s
                """, (row["id_asiento"],))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

class OperacionUpdateIn(BaseModel):
    fecha: str
    fecha_compra: Optional[str] = None
    descripcion: str
    id_fondo: int
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

@app.put("/operaciones/{id}")
def actualizar_operacion(id: int, o: OperacionUpdateIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id_pago, es_informal FROM operaciones WHERE id = %s", (id,))
            row = cur.fetchone()
            if not row:
                return {"ok": False, "error": "Operación no encontrada"}
            if row["id_pago"] is not None:
                return {"ok": False, "error_paga": True}
            es_informal = row["es_informal"]
            if es_informal:
                cur.execute("SELECT tipo FROM fondos WHERE id = %s", (o.id_fondo,))
                fondo_row = cur.fetchone()
                if fondo_row and fondo_row["tipo"] != "Efectivo":
                    return {"ok": False, "error_fondo_informal": True}
            fecha = date.fromisoformat(o.fecha)
            fecha_compra = date.fromisoformat(o.fecha_compra) if o.fecha_compra else fecha
            importe = (
                (o.subtotal or 0) + (o.exento or 0)
                + (o.iva_105 or 0) + (o.iva_21 or 0) + (o.iva_27 or 0)
                + (o.perc_iva or 0) + (o.perc_iibb or 0) + (o.perc_otras or 0)
                + (o.sin_factura or 0)
            )
            cur.execute("""
                UPDATE operaciones SET
                    fecha=%s, fecha_compra=%s, descripcion=%s, importe=%s, mes=%s,
                    subtotal=%s, exento=%s, iva_105=%s, iva_21=%s, iva_27=%s,
                    perc_iva=%s, perc_iibb=%s, perc_otras=%s, sin_factura=%s
                WHERE id=%s
            """, (fecha, fecha_compra, o.descripcion, importe, fecha.month,
                  o.subtotal, o.exento, o.iva_105, o.iva_21, o.iva_27,
                  o.perc_iva, o.perc_iibb, o.perc_otras, o.sin_factura, id))
            if o.fecha_vencimiento:
                fecha_vto = date.fromisoformat(o.fecha_vencimiento)
            else:
                cur.execute("SELECT plazo_pago FROM titulares WHERE id = (SELECT id_titular FROM operaciones WHERE id = %s)", (id,))
                t_row = cur.fetchone()
                plazo = t_row["plazo_pago"] if t_row and t_row["plazo_pago"] else 0
                fecha_vto = fecha + timedelta(days=plazo if plazo > 0 else 30)
            cur.execute("""
                UPDATE cashflow SET fecha=%s, mes=%s, importe=%s, id_fondo=%s, detalle=%s
                WHERE id_operacion=%s AND confirmado=false
            """, (fecha_vto, fecha_vto.month, -abs(importe), o.id_fondo, o.descripcion, id))
        conn.commit()
        return {"ok": True, "fecha_vencimiento": str(fecha_vto), "importe": importe}
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
    t = re.sub(r"[\"'\u201c\u201d\u00ab\u00bb]", " ", t)
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
            cur.execute("SELECT COUNT(*) AS n FROM operaciones WHERE id_titular = %s", (id,))
            n_operaciones = cur.fetchone()["n"]
            cur.execute("SELECT COUNT(*) AS n FROM cashflow WHERE id_titular = %s", (id,))
            n_cashflow = cur.fetchone()["n"]
            if n_operaciones > 0 or n_cashflow > 0:
                partes = []
                if n_operaciones > 0:
                    partes.append(f"{n_operaciones} comprobante(s) en Cuenta Corriente")
                if n_cashflow > 0:
                    partes.append(f"{n_cashflow} movimiento(s) en Tesorería")
                return {
                    "ok": False,
                    "error": "No se puede eliminar: tiene " + " y ".join(partes) + " asociado(s)."
                }
            cur.execute("DELETE FROM titulares WHERE id = %s", (id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# ==========================================
# EMPLEADOS (separado de titulares)
# ==========================================
class EmpleadoIn(BaseModel):
    nombre: str
    apellido: Optional[str] = None
    cuil: Optional[str] = None
    tipo_documento: Optional[str] = None
    nro_documento: Optional[str] = None
    nacionalidad: Optional[str] = None
    profesion: Optional[str] = None
    estado_civil: Optional[str] = None
    categoria: Optional[str] = None
    convenio: Optional[str] = None
    sector: Optional[str] = None
    sector_detalle: Optional[str] = None
    turno: Optional[str] = None
    fecha_nacimiento: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    banco: Optional[str] = None
    cbu: Optional[str] = None
    alias_cbu: Optional[str] = None
    legajo: Optional[str] = None
    fecha_ingreso_afip: Optional[str] = None
    alta_afip: Optional[bool] = False
    fecha_ingreso_real: Optional[str] = None
    jornada_real: Optional[float] = 192
    jornada_formal: Optional[float] = 192
    sueldo_basico: Optional[float] = None
    sueldo_basico_formal_alta: Optional[float] = None
    forma_pago: Optional[str] = None
    obra_social: Optional[str] = None
    sindicato: Optional[str] = None
    direccion: Optional[str] = None
    dom_calle: Optional[str] = None
    dom_numero: Optional[str] = None
    dom_piso: Optional[str] = None
    dom_depto: Optional[str] = None
    dom_barrio: Optional[str] = None
    dom_localidad: Optional[str] = None
    dom_provincia: Optional[str] = None
    dom_codigo_postal: Optional[str] = None
    cuenta_patrimonial: Optional[str] = "Remuneraciones a Pagar — Sueldos"
    id_puesto_formal_declarado: Optional[int] = None
    id_puesto_real_declarado: Optional[int] = None
    activo: Optional[bool] = True

# ==========================================
# CATÁLOGO DE PUESTOS (Nivel → Sector → Posición)
# ==========================================
class PuestoIn(BaseModel):
    convenio: str
    nivel: str
    sector: Optional[str] = None
    posicion: str
    categoria_convenio: Optional[int] = None
    activo: Optional[bool] = True

@app.get("/cat_puestos")
def get_cat_puestos(convenio: Optional[str] = None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if convenio:
                cur.execute("""
                    SELECT * FROM cat_puestos
                    WHERE (convenio = %s OR convenio = 'GENERAL') AND activo = true
                    ORDER BY categoria_convenio NULLS LAST, nivel, sector NULLS FIRST, posicion
                """, (convenio,))
            else:
                cur.execute("SELECT * FROM cat_puestos ORDER BY convenio, categoria_convenio NULLS LAST, nivel, sector NULLS FIRST, posicion")
            return cur.fetchall()
    finally:
        conn.close()

@app.post("/cat_puestos")
def crear_puesto(p: PuestoIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute("""
                    INSERT INTO cat_puestos (convenio, nivel, sector, posicion, categoria_convenio, activo)
                    VALUES (%s,%s,%s,%s,%s,%s)
                """, (p.convenio, p.nivel, p.sector, p.posicion, p.categoria_convenio, p.activo))
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
                return {"ok": False, "error": "Ese puesto ya existe para ese convenio/nivel/sector."}
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@app.put("/cat_puestos/{id}")
def actualizar_puesto(id: int, p: PuestoIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE cat_puestos SET convenio=%s, nivel=%s, sector=%s, posicion=%s, categoria_convenio=%s, activo=%s
                WHERE id=%s
            """, (p.convenio, p.nivel, p.sector, p.posicion, p.categoria_convenio, p.activo, id))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@app.delete("/cat_puestos/{id}")
def eliminar_puesto(id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM empleados WHERE categoria = (SELECT posicion FROM cat_puestos WHERE id = %s)", (id,))
            if cur.fetchone()["n"] > 0:
                return {"ok": False, "error": "No se puede eliminar: hay empleados con esta posición asignada."}
            cur.execute("DELETE FROM cat_puestos WHERE id = %s", (id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# ==========================================
# ESCALA SALARIAL FORMAL — sueldo mínimo de convenio, por categoría x tenedores x mes
# ==========================================
class EscalaSalarialIn(BaseModel):
    convenio: str
    categoria_convenio: int
    tenedores: int
    mes: int
    anio: int
    basico: float
    suma_no_remunerativa: Optional[float] = None

@app.get("/escala_salarial")
def get_escala_salarial(mes: int, anio: int, convenio: Optional[str] = None):
    """Para cada combinación categoría x tenedores ya cargada alguna vez, trae el valor de
    este mes si existe, o si no, el último anterior (mismo criterio que escala_salarial_real)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            where = "WHERE convenio = %s" if convenio else "WHERE 1=1"
            params = [convenio] if convenio else []
            cur.execute(f"SELECT DISTINCT convenio, categoria_convenio, tenedores FROM escala_salarial {where}", params)
            combinaciones = cur.fetchall()
            out = []
            for c in combinaciones:
                cur.execute("""
                    SELECT basico, suma_no_remunerativa, mes AS mes_origen, anio AS anio_origen FROM escala_salarial
                    WHERE convenio = %s AND categoria_convenio = %s AND tenedores = %s
                      AND (anio < %s OR (anio = %s AND mes <= %s))
                    ORDER BY anio DESC, mes DESC LIMIT 1
                """, (c["convenio"], c["categoria_convenio"], c["tenedores"], anio, anio, mes))
                row = cur.fetchone()
                if row:
                    out.append({
                        "convenio": c["convenio"], "categoria_convenio": c["categoria_convenio"], "tenedores": c["tenedores"],
                        "basico": float(row["basico"]), "suma_no_remunerativa": float(row["suma_no_remunerativa"]) if row["suma_no_remunerativa"] is not None else None,
                        "mes": mes, "anio": anio,
                    })
            return out
    finally:
        conn.close()

@app.post("/escala_salarial")
def guardar_escala_salarial(e: EscalaSalarialIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM liquidaciones WHERE mes = %s AND anio = %s AND es_borrador = false", (e.mes, e.anio))
            if cur.fetchone()["n"] > 0:
                return {"ok": False, "error": "Ese mes ya tiene liquidaciones guardadas — no se puede modificar la escala de convenio de un mes ya liquidado."}
            cur.execute("""
                INSERT INTO escala_salarial (convenio, categoria_convenio, tenedores, mes, anio, basico, suma_no_remunerativa)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (convenio, categoria_convenio, tenedores, mes, anio)
                DO UPDATE SET basico = EXCLUDED.basico, suma_no_remunerativa = EXCLUDED.suma_no_remunerativa
            """, (e.convenio, e.categoria_convenio, e.tenedores, e.mes, e.anio, e.basico, e.suma_no_remunerativa))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

class AumentoFormalIn(BaseModel):
    convenio: str
    mes: int
    anio: int
    porcentaje: float

@app.post("/escala_salarial/aumento")
def aplicar_aumento_formal(a: AumentoFormalIn):
    """Aplica un % de aumento a toda la escala Formal de un convenio, tomando como base
    la última combinación categoría x tenedores cargada (mismo mes o el más reciente anterior)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM liquidaciones WHERE mes = %s AND anio = %s AND es_borrador = false", (a.mes, a.anio))
            if cur.fetchone()["n"] > 0:
                return {"ok": False, "error": "Ese mes ya tiene liquidaciones guardadas — no se puede aplicar un aumento sobre un mes ya liquidado."}
            cur.execute("""
                SELECT DISTINCT categoria_convenio, tenedores FROM escala_salarial
                WHERE convenio = %s AND (anio < %s OR (anio = %s AND mes <= %s))
            """, (a.convenio, a.anio, a.anio, a.mes))
            combinaciones = cur.fetchall()
            actualizadas = 0
            for c in combinaciones:
                cur.execute("""
                    SELECT basico, suma_no_remunerativa FROM escala_salarial
                    WHERE convenio = %s AND categoria_convenio = %s AND tenedores = %s
                      AND (anio < %s OR (anio = %s AND mes <= %s))
                    ORDER BY anio DESC, mes DESC LIMIT 1
                """, (a.convenio, c["categoria_convenio"], c["tenedores"], a.anio, a.anio, a.mes))
                row = cur.fetchone()
                if not row:
                    continue
                nuevo_basico = round(float(row["basico"]) * (1 + a.porcentaje / 100), 2)
                nueva_suma = round(float(row["suma_no_remunerativa"]) * (1 + a.porcentaje / 100), 2) if row["suma_no_remunerativa"] is not None else None
                cur.execute("""
                    INSERT INTO escala_salarial (convenio, categoria_convenio, tenedores, mes, anio, basico, suma_no_remunerativa)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (convenio, categoria_convenio, tenedores, mes, anio)
                    DO UPDATE SET basico = EXCLUDED.basico, suma_no_remunerativa = EXCLUDED.suma_no_remunerativa
                """, (a.convenio, c["categoria_convenio"], c["tenedores"], a.mes, a.anio, nuevo_basico, nueva_suma))
                actualizadas += 1
        conn.commit()
        return {"ok": True, "actualizadas": actualizadas}
    finally:
        conn.close()


# ==========================================
# CATÁLOGO DE POSICIONES REALES (Nivel → Sector → Posición Real)
# ==========================================
class PuestoRealIn(BaseModel):
    convenio: str
    nivel: str
    sector: Optional[str] = None
    posicion_real: str
    activo: Optional[bool] = True

@app.get("/convenios")
def get_convenios():
    """Lista los convenios que ya tienen posiciones reales cargadas."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT convenio FROM cat_puestos_reales ORDER BY convenio")
            return [r["convenio"] for r in cur.fetchall()]
    finally:
        conn.close()

@app.get("/cat_puestos_reales")
def get_cat_puestos_reales(convenio: Optional[str] = None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if convenio:
                cur.execute("""
                    SELECT * FROM cat_puestos_reales
                    WHERE convenio = %s AND activo = true
                    ORDER BY nivel, sector NULLS FIRST, posicion_real
                """, (convenio,))
            else:
                cur.execute("SELECT * FROM cat_puestos_reales ORDER BY convenio, nivel, sector NULLS FIRST, posicion_real")
            return cur.fetchall()
    finally:
        conn.close()

@app.post("/cat_puestos_reales")
def crear_puesto_real(p: PuestoRealIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute("""
                    INSERT INTO cat_puestos_reales (convenio, nivel, sector, posicion_real, activo)
                    VALUES (%s,%s,%s,%s,%s)
                """, (p.convenio, p.nivel, p.sector, p.posicion_real, p.activo))
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
                return {"ok": False, "error": "Esa posición real ya existe para ese convenio/nivel/sector."}
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@app.put("/cat_puestos_reales/{id}")
def actualizar_puesto_real(id: int, p: PuestoRealIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE cat_puestos_reales SET convenio=%s, nivel=%s, sector=%s, posicion_real=%s, activo=%s
                WHERE id=%s
            """, (p.convenio, p.nivel, p.sector, p.posicion_real, p.activo, id))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# ==========================================
# ESCALA SALARIAL REAL — sueldo estándar por posición Real, versionado por mes
# (mismo criterio que escala_salarial para el lado Formal)
# ==========================================
class EscalaSalarialRealIn(BaseModel):
    id_real: int
    mes: int
    anio: int
    sueldo_estandar: float

@app.get("/escala_salarial_real")
def get_escala_salarial_real(mes: int, anio: int, convenio: Optional[str] = None):
    """Para cada posición Real (de un convenio), trae el sueldo estándar de ese mes,
    o si no está cargado, el último valor anterior (mismo criterio que básicos_anteriores)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if convenio:
                cur.execute("SELECT id, posicion_real, nivel, sector FROM cat_puestos_reales WHERE convenio = %s AND activo = true ORDER BY nivel, sector NULLS FIRST, posicion_real", (convenio,))
            else:
                cur.execute("SELECT id, posicion_real, nivel, sector FROM cat_puestos_reales WHERE activo = true ORDER BY convenio, nivel, sector NULLS FIRST, posicion_real")
            posiciones = cur.fetchall()
            out = []
            for p in posiciones:
                cur.execute("""
                    SELECT sueldo_estandar FROM escala_salarial_real
                    WHERE id_real = %s AND (anio < %s OR (anio = %s AND mes <= %s))
                    ORDER BY anio DESC, mes DESC LIMIT 1
                """, (p["id"], anio, anio, mes))
                row = cur.fetchone()
                out.append({
                    "id_real": p["id"], "posicion_real": p["posicion_real"], "nivel": p["nivel"], "sector": p["sector"],
                    "sueldo_estandar": float(row["sueldo_estandar"]) if row else None,
                })
            return out
    finally:
        conn.close()

@app.post("/escala_salarial_real")
def guardar_escala_salarial_real(e: EscalaSalarialRealIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM liquidaciones WHERE mes = %s AND anio = %s AND es_borrador = false", (e.mes, e.anio))
            if cur.fetchone()["n"] > 0:
                return {"ok": False, "error": "Ese mes ya tiene liquidaciones guardadas — no se puede modificar la escala salarial de un mes ya liquidado."}
            cur.execute("""
                INSERT INTO escala_salarial_real (id_real, mes, anio, sueldo_estandar)
                VALUES (%s,%s,%s,%s)
                ON CONFLICT (id_real, mes, anio) DO UPDATE SET sueldo_estandar = EXCLUDED.sueldo_estandar
            """, (e.id_real, e.mes, e.anio, e.sueldo_estandar))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@app.get("/escala_salarial_real/mes_cerrado")
def get_mes_cerrado(mes: int, anio: int):
    """Indica si ya existen liquidaciones guardadas para ese mes (bloquea edición de la escala)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM liquidaciones WHERE mes = %s AND anio = %s AND es_borrador = false", (mes, anio))
            return {"cerrado": cur.fetchone()["n"] > 0}
    finally:
        conn.close()

class AumentoIn(BaseModel):
    mes: int
    anio: int
    porcentaje: float
    convenio: Optional[str] = None

@app.post("/escala_salarial_real/aumento")
def aplicar_aumento_real(a: AumentoIn):
    """Aplica un % de aumento a TODAS las posiciones, tomando como base el valor vigente
    (el de este mes si ya hay algo cargado, o el arrastrado del último mes anterior)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM liquidaciones WHERE mes = %s AND anio = %s AND es_borrador = false", (a.mes, a.anio))
            if cur.fetchone()["n"] > 0:
                return {"ok": False, "error": "Ese mes ya tiene liquidaciones guardadas — no se puede aplicar un aumento sobre un mes ya liquidado."}
            if a.convenio:
                cur.execute("SELECT id FROM cat_puestos_reales WHERE convenio = %s AND activo = true", (a.convenio,))
            else:
                cur.execute("SELECT id FROM cat_puestos_reales WHERE activo = true")
            posiciones = cur.fetchall()
            actualizadas = 0
            for p in posiciones:
                cur.execute("""
                    SELECT sueldo_estandar FROM escala_salarial_real
                    WHERE id_real = %s AND (anio < %s OR (anio = %s AND mes <= %s))
                    ORDER BY anio DESC, mes DESC LIMIT 1
                """, (p["id"], a.anio, a.anio, a.mes))
                row = cur.fetchone()
                if not row:
                    continue
                nuevo_valor = round(float(row["sueldo_estandar"]) * (1 + a.porcentaje / 100), 2)
                cur.execute("""
                    INSERT INTO escala_salarial_real (id_real, mes, anio, sueldo_estandar)
                    VALUES (%s,%s,%s,%s)
                    ON CONFLICT (id_real, mes, anio) DO UPDATE SET sueldo_estandar = EXCLUDED.sueldo_estandar
                """, (p["id"], a.mes, a.anio, nuevo_valor))
                actualizadas += 1
        conn.commit()
        return {"ok": True, "actualizadas": actualizadas}
    finally:
        conn.close()

@app.get("/escala_salarial_real/comparativo")
def get_comparativo_real(anio: int, convenio: Optional[str] = None):
    """Devuelve, para cada posición, el sueldo estándar de cada uno de los 12 meses del año —
    para poder comparar de un vistazo cómo evolucionó, estilo planilla Excel."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if convenio:
                cur.execute("SELECT id, posicion_real, nivel, sector FROM cat_puestos_reales WHERE convenio = %s AND activo = true ORDER BY nivel, sector NULLS FIRST, posicion_real", (convenio,))
            else:
                cur.execute("SELECT id, posicion_real, nivel, sector FROM cat_puestos_reales WHERE activo = true ORDER BY convenio, nivel, sector NULLS FIRST, posicion_real")
            posiciones = cur.fetchall()
            out = []
            for p in posiciones:
                cur.execute("SELECT mes, sueldo_estandar FROM escala_salarial_real WHERE id_real = %s AND anio = %s", (p["id"], anio))
                valores = {r["mes"]: float(r["sueldo_estandar"]) for r in cur.fetchall()}
                out.append({
                    "id_real": p["id"], "posicion_real": p["posicion_real"], "nivel": p["nivel"], "sector": p["sector"],
                    "meses": [valores.get(m) for m in range(1, 13)],
                })
            return out
    finally:
        conn.close()

@app.get("/cat_puestos_reales/{id}/sueldo_actual")
def get_sueldo_actual_real(id: int):
    """Último sueldo estándar cargado para esta posición, sin importar el mes (para autocompletar en el alta de empleados)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT sueldo_estandar, mes, anio FROM escala_salarial_real
                WHERE id_real = %s ORDER BY anio DESC, mes DESC LIMIT 1
            """, (id,))
            row = cur.fetchone()
            return {"sueldo_estandar": float(row["sueldo_estandar"]) if row else None, "mes": row["mes"] if row else None, "anio": row["anio"] if row else None}
    finally:
        conn.close()

@app.get("/cat_puestos/{id}/minimo_actual")
def get_minimo_actual_formal(id: int):
    """Mínimo de convenio vigente hoy para esta Categoría Formal, según los Tenedores configurados
    (para autocompletar y validar en el alta de empleados)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT valor FROM configuracion WHERE clave = 'tenedores_establecimiento'")
            row = cur.fetchone()
            tenedores = int(row["valor"]) if row and row["valor"] else None
            if not tenedores:
                return {"basico": None}
            cur.execute("SELECT convenio, categoria_convenio FROM cat_puestos WHERE id = %s", (id,))
            p = cur.fetchone()
            if not p or p["categoria_convenio"] is None:
                return {"basico": None}
            from datetime import date as _date
            hoy = _date.today()
            cur.execute("""
                SELECT basico FROM escala_salarial
                WHERE convenio = %s AND categoria_convenio = %s AND tenedores = %s
                  AND (anio < %s OR (anio = %s AND mes <= %s))
                ORDER BY anio DESC, mes DESC LIMIT 1
            """, (p["convenio"], p["categoria_convenio"], tenedores, hoy.year, hoy.year, hoy.month))
            esc = cur.fetchone()
            return {"basico": float(esc["basico"]) if esc else None}
    finally:
        conn.close()

@app.get("/cat_puestos_reales/{id}/formales")
def get_formales_de_real(id: int):
    """Devuelve las posiciones Formales permitidas para una posición Real, ordenadas de mayor a menor jerarquía."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT f.id, f.posicion, f.categoria_convenio
                FROM cat_puestos_reales_formal rf
                JOIN cat_puestos f ON f.id = rf.id_formal
                WHERE rf.id_real = %s
                ORDER BY f.categoria_convenio DESC, f.posicion
            """, (id,))
            return cur.fetchall()
    finally:
        conn.close()

class RelacionRealFormalIn(BaseModel):
    id_real: int
    id_formal: int

@app.post("/cat_puestos_reales_formal")
def agregar_relacion_real_formal(r: RelacionRealFormalIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute("INSERT INTO cat_puestos_reales_formal (id_real, id_formal) VALUES (%s,%s)", (r.id_real, r.id_formal))
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
                return {"ok": False, "error": "Esa relación ya existe."}
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@app.delete("/cat_puestos_reales_formal")
def eliminar_relacion_real_formal(id_real: int, id_formal: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM cat_puestos_reales_formal WHERE id_real = %s AND id_formal = %s", (id_real, id_formal))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@app.get("/empleados")
def get_empleados():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM empleados
                ORDER BY apellido NULLS LAST, nombre
            """)
            return cur.fetchall()
    finally:
        conn.close()

def _validar_sueldo_formal_minimo(cur, e):
    """Si el empleado tiene Categoría Formal y sueldo declarado, chequea que no sea menor
    al mínimo de convenio vigente. Devuelve un mensaje de error si lo viola, o None si está OK."""
    if e.sueldo_basico_formal_alta is None or not e.id_puesto_formal_declarado:
        return None
    cur.execute("SELECT valor FROM configuracion WHERE clave = 'tenedores_establecimiento'")
    row = cur.fetchone()
    tenedores = int(row["valor"]) if row and row["valor"] else None
    if not tenedores:
        return None
    cur.execute("SELECT categoria_convenio FROM cat_puestos WHERE id = %s", (e.id_puesto_formal_declarado,))
    fp = cur.fetchone()
    if not fp or fp["categoria_convenio"] is None:
        return None
    from datetime import date as _date
    hoy = _date.today()
    cur.execute("""
        SELECT basico FROM escala_salarial
        WHERE convenio = %s AND categoria_convenio = %s AND tenedores = %s
          AND (anio < %s OR (anio = %s AND mes <= %s))
        ORDER BY anio DESC, mes DESC LIMIT 1
    """, (e.convenio, fp["categoria_convenio"], tenedores, hoy.year, hoy.year, hoy.month))
    esc = cur.fetchone()
    if esc and e.sueldo_basico_formal_alta < float(esc["basico"]):
        return f"No se puede declarar un sueldo Formal menor al mínimo de convenio (${esc['basico']})."
    return None

@app.post("/empleados")
def crear_empleado(e: EmpleadoIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            error_minimo = _validar_sueldo_formal_minimo(cur, e)
            if error_minimo:
                return {"ok": False, "error": error_minimo}
            cur.execute("""
                INSERT INTO empleados
                    (nombre, apellido, cuil, tipo_documento, nro_documento, nacionalidad, profesion, estado_civil,
                     categoria, convenio, sector, sector_detalle, turno, fecha_nacimiento, telefono, email,
                     banco, cbu, alias_cbu, legajo,
                     fecha_ingreso_afip, fecha_ingreso_real, jornada_real, jornada_formal, alta_afip,
                     sueldo_basico, sueldo_basico_formal_alta, forma_pago, obra_social, sindicato, direccion,
                     dom_calle, dom_numero, dom_piso, dom_depto, dom_barrio, dom_localidad, dom_provincia, dom_codigo_postal,
                     id_puesto_formal_declarado, id_puesto_real_declarado, cuenta_patrimonial, activo)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (e.nombre, e.apellido, e.cuil, e.tipo_documento, e.nro_documento, e.nacionalidad, e.profesion, e.estado_civil,
                  e.categoria, e.convenio, e.sector, e.sector_detalle, e.turno, e.fecha_nacimiento, e.telefono, e.email,
                  e.banco, e.cbu, e.alias_cbu, e.legajo,
                  e.fecha_ingreso_afip, e.fecha_ingreso_real, e.jornada_real, e.jornada_formal, e.alta_afip,
                  e.sueldo_basico, e.sueldo_basico_formal_alta, e.forma_pago, e.obra_social, e.sindicato, e.direccion,
                  e.dom_calle, e.dom_numero, e.dom_piso, e.dom_depto, e.dom_barrio, e.dom_localidad, e.dom_provincia, e.dom_codigo_postal,
                  e.id_puesto_formal_declarado, e.id_puesto_real_declarado, e.cuenta_patrimonial, e.activo))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@app.put("/empleados/{id}")
def actualizar_empleado(id: int, e: EmpleadoIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            error_minimo = _validar_sueldo_formal_minimo(cur, e)
            if error_minimo:
                return {"ok": False, "error": error_minimo}
            cur.execute("""
                UPDATE empleados SET
                    nombre=%s, apellido=%s, cuil=%s, tipo_documento=%s, nro_documento=%s, nacionalidad=%s, profesion=%s, estado_civil=%s,
                    categoria=%s, convenio=%s, sector=%s, sector_detalle=%s, turno=%s, fecha_nacimiento=%s, telefono=%s, email=%s,
                    banco=%s, cbu=%s, alias_cbu=%s, legajo=%s,
                    fecha_ingreso_afip=%s, fecha_ingreso_real=%s, jornada_real=%s, jornada_formal=%s, alta_afip=%s, sueldo_basico=%s, sueldo_basico_formal_alta=%s,
                    forma_pago=%s, obra_social=%s, sindicato=%s, direccion=%s,
                    dom_calle=%s, dom_numero=%s, dom_piso=%s, dom_depto=%s, dom_barrio=%s, dom_localidad=%s, dom_provincia=%s, dom_codigo_postal=%s,
                    id_puesto_formal_declarado=%s, id_puesto_real_declarado=%s, cuenta_patrimonial=%s, activo=%s
                WHERE id=%s
            """, (e.nombre, e.apellido, e.cuil, e.tipo_documento, e.nro_documento, e.nacionalidad, e.profesion, e.estado_civil,
                  e.categoria, e.convenio, e.sector, e.sector_detalle, e.turno, e.fecha_nacimiento, e.telefono, e.email,
                  e.banco, e.cbu, e.alias_cbu, e.legajo,
                  e.fecha_ingreso_afip, e.fecha_ingreso_real, e.jornada_real, e.jornada_formal, e.alta_afip,
                  e.sueldo_basico, e.sueldo_basico_formal_alta, e.forma_pago, e.obra_social, e.sindicato, e.direccion,
                  e.dom_calle, e.dom_numero, e.dom_piso, e.dom_depto, e.dom_barrio, e.dom_localidad, e.dom_provincia, e.dom_codigo_postal,
                  e.id_puesto_formal_declarado, e.id_puesto_real_declarado, e.cuenta_patrimonial, e.activo, id))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@app.delete("/empleados/{id}")
def eliminar_empleado(id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM liquidaciones WHERE id_empleado = %s AND es_borrador = false", (id,))
            n_liq = cur.fetchone()["n"]
            cur.execute("SELECT COUNT(*) AS n FROM cashflow WHERE id_empleado = %s", (id,))
            n_cash = cur.fetchone()["n"]
            if n_liq > 0 or n_cash > 0:
                partes = []
                if n_liq > 0:
                    partes.append(f"{n_liq} liquidación(es)")
                if n_cash > 0:
                    partes.append(f"{n_cash} movimiento(s) de pago")
                return {"ok": False, "error": "No se puede eliminar: este empleado ya generó " + " y ".join(partes) + " — eso afectó el Balance. Si ya no trabaja más acá, marcalo como \"Inactivo\" en vez de eliminarlo."}
            cur.execute("DELETE FROM empleados_familiares WHERE id_empleado = %s", (id,))
            cur.execute("DELETE FROM empleados WHERE id = %s", (id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# ==========================================
# FAMILIARES DEL EMPLEADO (Cónyuge, Conviviente, Padre, Madre)
# ==========================================
class FamiliarIn(BaseModel):
    id_empleado: int
    vinculo: str
    nombre_completo: str

@app.get("/empleados_familiares")
def get_familiares(id_empleado: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM empleados_familiares WHERE id_empleado = %s ORDER BY id", (id_empleado,))
            return cur.fetchall()
    finally:
        conn.close()

@app.post("/empleados_familiares")
def crear_familiar(f: FamiliarIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO empleados_familiares (id_empleado, vinculo, nombre_completo)
                VALUES (%s,%s,%s)
            """, (f.id_empleado, f.vinculo, f.nombre_completo))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@app.delete("/empleados_familiares/{id}")
def eliminar_familiar(id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM empleados_familiares WHERE id = %s", (id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# ==========================================
# CONCEPTOS DE LIQUIDACIÓN (catálogo por convenio)
# ==========================================
class ConceptoLiquidacionIn(BaseModel):
    convenio: str
    nombre: str
    tipo: str            # 'HABER' o 'DESCUENTO'
    calculo: str         # 'MANUAL' o 'AUTOMATICO'
    track: str           # 'FORMAL', 'REAL' o 'AMBOS'
    porcentaje: Optional[float] = None
    orden: Optional[int] = 0
    activo: Optional[bool] = True

@app.get("/conceptos_liquidacion")
def get_conceptos_liquidacion(convenio: Optional[str] = None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if convenio:
                cur.execute("""
                    SELECT * FROM conceptos_liquidacion
                    WHERE convenio = %s OR convenio = 'GENERAL'
                    ORDER BY orden, id
                """, (convenio,))
            else:
                cur.execute("SELECT * FROM conceptos_liquidacion ORDER BY convenio, orden, id")
            return cur.fetchall()
    finally:
        conn.close()

@app.post("/conceptos_liquidacion")
def crear_concepto_liquidacion(c: ConceptoLiquidacionIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO conceptos_liquidacion (convenio, nombre, tipo, calculo, track, porcentaje, orden, activo)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (c.convenio, c.nombre, c.tipo, c.calculo, c.track, c.porcentaje, c.orden, c.activo))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@app.put("/conceptos_liquidacion/{id}")
def actualizar_concepto_liquidacion(id: int, c: ConceptoLiquidacionIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE conceptos_liquidacion SET
                    convenio=%s, nombre=%s, tipo=%s, calculo=%s, track=%s, porcentaje=%s, orden=%s, activo=%s
                WHERE id=%s
            """, (c.convenio, c.nombre, c.tipo, c.calculo, c.track, c.porcentaje, c.orden, c.activo, id))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@app.delete("/conceptos_liquidacion/{id}")
def eliminar_concepto_liquidacion(id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM liquidacion_detalle WHERE id_concepto = %s", (id,))
            if cur.fetchone()["n"] > 0:
                return {"ok": False, "error": "No se puede eliminar: ya fue usado en liquidaciones existentes."}
            cur.execute("DELETE FROM conceptos_liquidacion WHERE id = %s", (id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


# ==========================================
# LIQUIDACIONES — motor de cálculo (dos tracks: FORMAL / REAL)
# ==========================================
def _get_config_num(cur, clave, default):
    cur.execute("SELECT valor FROM configuracion WHERE clave = %s", (clave,))
    row = cur.fetchone()
    return float(row["valor"]) if row else default

def _calcular_track(conceptos, track, sueldo_basico, feriados, aus_just, aus_no_just, manuales, divisor_feriado, divisor_dia, es_caba=False, suma_no_remunerativa=0.0, basico_jornada_completa=None):
    """Devuelve lista de detalle [(id_concepto, nombre, tipo, monto)] y el neto de ese track.
    Los conceptos marcados 'AUTOMATICO_BRUTO' (los Aportes) se calculan aparte, en una segunda
    pasada, porque van sobre el Bruto ya armado (sueldo + adicionales), no sobre el básico solo.
    "Obra Social (Aportes)" es la excepción: por acuerdo paritario se paga completa sin importar
    la jornada, así que se calcula sobre un Bruto "hipotético" armado con el básico de jornada
    completa (no el prorrateado) + los mismos adicionales ya calculados.
    La Suma No Remunerativa se suma DESPUÉS de los Aportes — no forma parte de la base sobre la
    que se calculan, tal como corresponde legalmente."""
    detalle = []
    total_haberes = 0.0
    total_descuentos = 0.0
    conceptos_sobre_bruto = []
    for c in conceptos:
        if c["track"] not in (track, "AMBOS"):
            continue
        nombre = c["nombre"]
        if c["calculo"] == "AUTOMATICO_BRUTO":
            conceptos_sobre_bruto.append(c)  # se procesan después, sobre el Bruto
            continue
        if c["calculo"] == "MANUAL":
            monto = float(manuales.get((track, c["id"]), 0) or 0)
        elif nombre == "Presentismo":
            monto = 0.0 if (aus_just + aus_no_just) > 0 else sueldo_basico * float(c["porcentaje"] or 0)
        elif nombre == "Feriados":
            monto = (sueldo_basico / divisor_feriado) * feriados if divisor_feriado else 0.0
        elif nombre == "Ausencias No Justificadas":
            monto = (sueldo_basico / divisor_dia) * aus_no_just if divisor_dia else 0.0
        elif nombre == "Plus CABA":
            monto = sueldo_basico * float(c["porcentaje"] or 0) if es_caba else 0.0
        elif c["calculo"] == "AUTOMATICO" and c["porcentaje"] is not None:
            monto = sueldo_basico * float(c["porcentaje"])
        else:
            monto = 0.0
        monto = round(monto, 2)
        detalle.append({"id_concepto": c["id"], "nombre": nombre, "tipo": c["tipo"], "track": track, "monto": monto})
        if c["tipo"] == "HABER":
            total_haberes += monto
        else:
            total_descuentos += monto
    bruto = round(sueldo_basico + total_haberes, 2)
    # Bruto "hipotético" de jornada completa, solo para la Obra Social (básico completo + los mismos adicionales)
    # Bruto "hipotético" de jornada completa, para Obra Social: se escala TODO el Bruto ya armado
    # (básico + adicionales) por la proporción inversa de la jornada — no solo el básico.
    # Así funciona igual para media jornada, un tercio, o cualquier fracción.
    if basico_jornada_completa and sueldo_basico:
        proporcion_jornada = sueldo_basico / basico_jornada_completa
        bruto_obra_social = round(bruto / proporcion_jornada, 2) if proporcion_jornada else bruto
    else:
        bruto_obra_social = bruto

    # Conceptos sobre el Bruto (los Aportes) — cada uno con su propio %, todos visibles por separado.
    # Se calculan ANTES de sumar la Suma No Remunerativa, porque esa suma no forma parte de la base.
    for c in conceptos_sobre_bruto:
        base = bruto_obra_social if c["nombre"] == "Obra Social (Aportes)" else bruto
        monto = round(base * float(c["porcentaje"] or 0), 2)
        detalle.append({"id_concepto": c["id"], "nombre": c["nombre"], "tipo": c["tipo"], "track": track, "monto": monto})
        total_descuentos += monto

    # Suma No Remunerativa: no forma parte del Bruto ni de la base de Aportes — se suma
    # directo al Neto, como una línea aparte (al mismo nivel que iría un Adelanto).
    extra_no_remunerativo = 0.0
    if track == "FORMAL" and suma_no_remunerativa:
        detalle.append({"id_concepto": None, "nombre": "Suma No Remunerativa", "tipo": "HABER", "track": track, "monto": round(suma_no_remunerativa, 2)})
        extra_no_remunerativo = suma_no_remunerativa

    neto = round(bruto - total_descuentos + extra_no_remunerativo, 2)
    return detalle, bruto, neto

class LiquidacionCalcularIn(BaseModel):
    convenio: str
    sueldo_basico_formal: float
    sueldo_basico_real: Optional[float] = None
    horas_formal: Optional[float] = 192
    horas_real: Optional[float] = 192
    feriados_trabajados: int = 0  # feriados del circuito Real
    feriados_trabajados_formal: int = 0  # feriados del circuito Formal — independiente del Real
    ausencias_justificadas: int = 0
    ausencias_no_justificadas: int = 0
    manuales: dict = {}   # { "FORMAL:3": 23000, "REAL:7": 100000 }
    suma_no_remunerativa_formal: float = 0  # de la Escala Convenio, ya prorrateada por jornada — no cuenta para Aportes
    basico_jornada_completa_formal: Optional[float] = None  # sin prorratear — la Obra Social de Aportes se calcula siempre sobre esto

def _parse_manuales(manuales_in):
    out = {}
    for k, v in (manuales_in or {}).items():
        track, id_concepto = k.split(":")
        out[(track, int(id_concepto))] = v
    return out

@app.post("/liquidaciones/calcular")
def calcular_liquidacion(l: LiquidacionCalcularIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM conceptos_liquidacion
                WHERE (convenio = %s OR convenio = 'GENERAL') AND activo = true
                ORDER BY orden, id
            """, (l.convenio,))
            conceptos = cur.fetchall()
            divisor_feriado = _get_config_num(cur, "divisor_feriado", 25)
            divisor_dia = _get_config_num(cur, "divisor_dia_normal", 30)
            cur.execute("SELECT valor FROM configuracion WHERE clave = 'caba'")
            row_caba = cur.fetchone()
            es_caba = bool(row_caba and row_caba["valor"] == "SI")

        manuales = _parse_manuales(l.manuales)

        detalle_formal, bruto_formal, neto_formal = _calcular_track(
            conceptos, "FORMAL", l.sueldo_basico_formal, l.feriados_trabajados_formal,
            l.ausencias_justificadas, l.ausencias_no_justificadas, manuales, divisor_feriado, divisor_dia,
            es_caba, l.suma_no_remunerativa_formal, l.basico_jornada_completa_formal
        )

        detalle_real, bruto_real, neto_real = None, None, None
        pago_efectivo = 0.0
        if l.sueldo_basico_real is not None:
            detalle_real, bruto_real, neto_real = _calcular_track(
                conceptos, "REAL", l.sueldo_basico_real, l.feriados_trabajados,
                l.ausencias_justificadas, l.ausencias_no_justificadas, manuales, divisor_feriado, divisor_dia,
                es_caba
            )
            pago_efectivo = round(neto_real - neto_formal, 2)

        neto_total = round(neto_formal + pago_efectivo, 2)

        return {
            "detalle_formal": detalle_formal,
            "detalle_real": detalle_real,
            "total_bruto_formal": bruto_formal,
            "neto_formal": neto_formal,
            "total_bruto_real": bruto_real,
            "neto_real": neto_real,
            "pago_efectivo": pago_efectivo,
            "neto_total_a_pagar": neto_total,
        }
    finally:
        conn.close()


class LiquidacionIn(LiquidacionCalcularIn):
    id_empleado: int
    mes: int
    anio: int
    fecha: str
    es_borrador: bool = True  # True = "Guardar Cambios" (sin consecuencias), False = "Liquidar" (cierra el mes)

@app.get("/liquidaciones")
def get_liquidaciones(mes: Optional[int] = None, anio: Optional[int] = None, id_empleado: Optional[int] = None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            query = """
                SELECT l.*, e.nombre AS empleado_nombre
                FROM liquidaciones l
                JOIN empleados e ON e.id = l.id_empleado
                WHERE 1=1
            """
            params = []
            if mes is not None:
                query += " AND l.mes = %s"; params.append(mes)
            if anio is not None:
                query += " AND l.anio = %s"; params.append(anio)
            if id_empleado is not None:
                query += " AND l.id_empleado = %s"; params.append(id_empleado)
            query += " ORDER BY e.nombre"
            cur.execute(query, params)
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/liquidaciones/basicos_anteriores")
def get_basicos_anteriores(mes: int, anio: int):
    """Para cada empleado activo, intenta traer el Básico Formal/Real desde las escalas
    (según su Categoría/Posición declarada). Si no hay dato en la escala para ese empleado,
    cae al criterio viejo: el último Básico que usó en una liquidación anterior, o el de alta."""
    mes_prev, anio_prev = (12, anio - 1) if mes == 1 else (mes - 1, anio)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT valor FROM configuracion WHERE clave = 'tenedores_establecimiento'")
            row = cur.fetchone()
            tenedores = int(row["valor"]) if row and row["valor"] else None

            cur.execute("""
                SELECT id, nombre, apellido, convenio, sueldo_basico, sueldo_basico_formal_alta, id_puesto_formal_declarado, id_puesto_real_declarado,
                       fecha_ingreso_afip, fecha_ingreso_real, jornada_real, jornada_formal
                FROM empleados WHERE activo = true ORDER BY apellido NULLS LAST, nombre
            """)
            empleados = cur.fetchall()
            from datetime import date as _date
            fecha_periodo = _date(anio, mes, 1)
            out = []
            for e in empleados:
                # Si el período que se está liquidando es ANTERIOR a la fecha de ingreso de cada circuito,
                # ese circuito todavía no corresponde — ni historial ni Escala, directamente $0.
                fecha_ingreso_formal = e["fecha_ingreso_afip"]
                fecha_ingreso_real_emp = e["fecha_ingreso_real"]
                no_corresponde_formal = fecha_ingreso_formal and _date(fecha_ingreso_formal.year, fecha_ingreso_formal.month, 1) > fecha_periodo
                no_corresponde_real = fecha_ingreso_real_emp and _date(fecha_ingreso_real_emp.year, fecha_ingreso_real_emp.month, 1) > fecha_periodo

                # Si en NINGUNO de los dos circuitos había ingresado todavía, directamente no aparece este mes.
                if no_corresponde_formal and no_corresponde_real:
                    continue

                cur.execute("""
                    SELECT sueldo_basico_formal, sueldo_basico_real, horas_formal, horas_real FROM liquidaciones
                    WHERE id_empleado = %s AND es_borrador = false AND (anio < %s OR (anio = %s AND mes <= %s))
                    ORDER BY anio DESC, mes DESC LIMIT 1
                """, (e["id"], anio_prev, anio_prev, mes_prev))
                prev = cur.fetchone()

                # Jornada sugerida: 1° la que venía usando en liquidaciones, 2° la declarada al alta, 3° 192hs (completa)
                horas_formal = float(prev["horas_formal"]) if (prev and prev["horas_formal"] is not None) else float(e["jornada_formal"] or 192)
                horas_real = float(prev["horas_real"]) if (prev and prev["horas_real"] is not None) else float(e["jornada_real"] or 192)
                proporcion_formal = horas_formal / 192
                proporcion_real = horas_real / 192

                # --- Referencia de Escala Formal (siempre se calcula, para poder avisar si el usuario se aparta) ---
                escala_formal_ref = None
                suma_no_remunerativa_ref = None
                if e["id_puesto_formal_declarado"] and tenedores:
                    cur.execute("SELECT categoria_convenio FROM cat_puestos WHERE id = %s", (e["id_puesto_formal_declarado"],))
                    fp = cur.fetchone()
                    if fp and fp["categoria_convenio"] is not None:
                        cur.execute("""
                            SELECT basico, suma_no_remunerativa FROM escala_salarial
                            WHERE convenio = %s AND categoria_convenio = %s AND tenedores = %s
                              AND (anio < %s OR (anio = %s AND mes <= %s))
                            ORDER BY anio DESC, mes DESC LIMIT 1
                        """, (e["convenio"], fp["categoria_convenio"], tenedores, anio, anio, mes))
                        esc = cur.fetchone()
                        if esc:
                            escala_formal_ref = float(esc["basico"])
                            if esc["suma_no_remunerativa"] is not None:
                                suma_no_remunerativa_ref = float(esc["suma_no_remunerativa"])

                # --- Básico FORMAL sugerido: 1° su propio historial, 2° la Escala Convenio del mes (ya trae su propio arrastre) ---
                if no_corresponde_formal:
                    basico_formal = 0
                elif prev and prev["sueldo_basico_formal"] is not None:
                    basico_formal = float(prev["sueldo_basico_formal"])
                elif escala_formal_ref is not None:
                    basico_formal = round(escala_formal_ref * proporcion_formal, 2)
                else:
                    basico_formal = 0

                # --- Referencia de Escala Real (siempre se calcula) ---
                escala_real_ref = None
                if e["id_puesto_real_declarado"]:
                    cur.execute("""
                        SELECT sueldo_estandar FROM escala_salarial_real
                        WHERE id_real = %s AND (anio < %s OR (anio = %s AND mes <= %s))
                        ORDER BY anio DESC, mes DESC LIMIT 1
                    """, (e["id_puesto_real_declarado"], anio, anio, mes))
                    esc_r = cur.fetchone()
                    if esc_r:
                        escala_real_ref = float(esc_r["sueldo_estandar"])

                # --- Básico REAL sugerido: 1° su propio historial, 2° lo pactado al alta, 3° la Escala ---
                if no_corresponde_real:
                    basico_real = 0
                elif prev and prev["sueldo_basico_real"] is not None:
                    basico_real = float(prev["sueldo_basico_real"])
                elif e["sueldo_basico"] is not None:
                    basico_real = round(float(e["sueldo_basico"]) * proporcion_real, 2)
                elif prev:
                    basico_real = float(prev["sueldo_basico_formal"])
                elif escala_real_ref is not None:
                    basico_real = round(escala_real_ref * proporcion_real, 2)
                else:
                    basico_real = 0

                # La referencia de "jornada completa" prioriza lo declarado específicamente para
                # este empleado (el campo del modal es el que manda) — la Escala es solo el respaldo
                # si nunca se declaró nada puntual.
                referencia_formal_jornada_completa = escala_formal_ref
                referencia_real_jornada_completa = float(e["sueldo_basico"]) if e["sueldo_basico"] is not None else escala_real_ref

                out.append({
                    "id_empleado": e["id"],
                    "nombre": f"{e['apellido']}, {e['nombre']}" if e["apellido"] else e["nombre"],
                    "convenio": e["convenio"],
                    "sueldo_basico_formal": basico_formal,
                    "sueldo_basico_real": basico_real,
                    "escala_formal_ref": round(referencia_formal_jornada_completa * proporcion_formal, 2) if referencia_formal_jornada_completa is not None else None,
                    "escala_real_ref": round(referencia_real_jornada_completa * proporcion_real, 2) if referencia_real_jornada_completa is not None else None,
                    "escala_formal_ref_jornada_completa": referencia_formal_jornada_completa,
                    "escala_real_ref_jornada_completa": referencia_real_jornada_completa,
                    "no_corresponde_formal": bool(no_corresponde_formal),
                    "no_corresponde_real": bool(no_corresponde_real),
                    "horas_formal": horas_formal,
                    "horas_real": horas_real,
                    "suma_no_remunerativa_formal": round(suma_no_remunerativa_ref * proporcion_formal, 2) if suma_no_remunerativa_ref is not None else 0,
                    "suma_no_remunerativa_jornada_completa": suma_no_remunerativa_ref if suma_no_remunerativa_ref is not None else 0,
                })
            return out
    finally:
        conn.close()

@app.post("/liquidaciones/calcular_lote")
def calcular_liquidaciones_lote(items: List[LiquidacionCalcularIn]):
    return [calcular_liquidacion(item) for item in items]

@app.post("/liquidaciones/guardar_lote")
def guardar_liquidaciones_lote(items: List[LiquidacionIn]):
    resultados = []
    for item in items:
        try:
            resultados.append({"id_empleado": item.id_empleado, **crear_liquidacion(item)})
        except Exception as ex:
            resultados.append({"id_empleado": item.id_empleado, "ok": False, "error": str(ex)})
    return resultados

@app.get("/liquidaciones/{id}")
def get_liquidacion(id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM liquidaciones WHERE id = %s", (id,))
            liq = cur.fetchone()
            if not liq:
                return {"ok": False, "error": "No encontrada"}
            cur.execute("SELECT ld.*, c.nombre, c.tipo FROM liquidacion_detalle ld JOIN conceptos_liquidacion c ON c.id = ld.id_concepto WHERE id_liquidacion = %s", (id,))
            liq["detalle"] = cur.fetchall()
            return liq
    finally:
        conn.close()

@app.post("/liquidaciones")
def crear_liquidacion(l: LiquidacionIn):
    conn = get_conn()
    try:
        calculo = calcular_liquidacion(l)
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO liquidaciones
                    (id_empleado, mes, anio, fecha, sueldo_basico_formal, sueldo_basico_real,
                     horas_formal, horas_real,
                     feriados_trabajados, feriados_trabajados_formal, ausencias_justificadas, ausencias_no_justificadas,
                     total_bruto_formal, neto_formal, total_bruto_real, neto_real,
                     pago_efectivo, neto_total_a_pagar, saldo_pendiente, es_borrador)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id_empleado, mes, anio) DO UPDATE SET
                    fecha=EXCLUDED.fecha, sueldo_basico_formal=EXCLUDED.sueldo_basico_formal,
                    sueldo_basico_real=EXCLUDED.sueldo_basico_real,
                    horas_formal=EXCLUDED.horas_formal, horas_real=EXCLUDED.horas_real,
                    feriados_trabajados=EXCLUDED.feriados_trabajados,
                    feriados_trabajados_formal=EXCLUDED.feriados_trabajados_formal,
                    ausencias_justificadas=EXCLUDED.ausencias_justificadas,
                    ausencias_no_justificadas=EXCLUDED.ausencias_no_justificadas,
                    total_bruto_formal=EXCLUDED.total_bruto_formal, neto_formal=EXCLUDED.neto_formal,
                    total_bruto_real=EXCLUDED.total_bruto_real, neto_real=EXCLUDED.neto_real,
                    pago_efectivo=EXCLUDED.pago_efectivo, neto_total_a_pagar=EXCLUDED.neto_total_a_pagar,
                    saldo_pendiente = liquidaciones.saldo_pendiente + (EXCLUDED.neto_total_a_pagar - liquidaciones.neto_total_a_pagar),
                    es_borrador = liquidaciones.es_borrador AND EXCLUDED.es_borrador
                RETURNING id
            """, (l.id_empleado, l.mes, l.anio, l.fecha, l.sueldo_basico_formal, l.sueldo_basico_real,
                  l.horas_formal, l.horas_real,
                  l.feriados_trabajados, l.feriados_trabajados_formal, l.ausencias_justificadas, l.ausencias_no_justificadas,
                  calculo["total_bruto_formal"], calculo["neto_formal"], calculo["total_bruto_real"], calculo["neto_real"],
                  calculo["pago_efectivo"], calculo["neto_total_a_pagar"], calculo["neto_total_a_pagar"], l.es_borrador))
            id_liq = cur.fetchone()["id"]

            cur.execute("DELETE FROM liquidacion_detalle WHERE id_liquidacion = %s", (id_liq,))
            detalle_completo = calculo["detalle_formal"] + (calculo["detalle_real"] or [])
            for d in detalle_completo:
                cur.execute("""
                    INSERT INTO liquidacion_detalle (id_liquidacion, track, id_concepto, monto)
                    VALUES (%s,%s,%s,%s)
                """, (id_liq, d["track"], d["id_concepto"], d["monto"]))
        conn.commit()
        return {"ok": True, "id": id_liq, **calculo}
    finally:
        conn.close()

@app.delete("/liquidaciones/{id}")
def eliminar_liquidacion(id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT saldo_pendiente, neto_total_a_pagar FROM liquidaciones WHERE id = %s", (id,))
            row = cur.fetchone()
            if not row:
                return {"ok": False, "error": "No encontrada"}
            if row["saldo_pendiente"] != row["neto_total_a_pagar"]:
                return {"ok": False, "error": "No se puede eliminar: ya tiene pagos registrados contra esta liquidación."}
            cur.execute("DELETE FROM liquidaciones WHERE id = %s", (id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@app.post("/cashflow/{id}/anular_echeq")
def anular_echeq(id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, id_asiento FROM cheques_emitidos WHERE id_cashflow = %s", (id,))
            cheque = cur.fetchone()
            if not cheque:
                return {"ok": False, "error": "No es un ECheq"}
            cur.execute("UPDATE cheques_emitidos SET estado='ANULADO' WHERE id_cashflow = %s", (id,))
            cur.execute("UPDATE operaciones SET id_pago = NULL WHERE id_pago = %s", (id,))
            cur.execute("UPDATE cashflow SET confirmado=true, importe=0 WHERE id = %s", (id,))
            # El paso que faltaba: anular el asiento de emisión (cancela la deuda al Titular,
            # sube "Valores Emitidos") — sino Balance sigue contando un cheque que se anuló.
            if cheque["id_asiento"]:
                cur.execute("""
                    UPDATE asientos SET anulado = true,
                        fecha_anulacion = (CURRENT_TIMESTAMP AT TIME ZONE 'America/Argentina/Buenos_Aires'),
                        motivo_anulacion = 'ECheq anulado desde Tesorería'
                    WHERE id = %s
                """, (cheque["id_asiento"],))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@app.put("/cashflow/{id}/postergar_echeq")
def postergar_echeq(id: int, body: ReprogramarIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM cheques_emitidos WHERE id_cashflow = %s", (id,))
            if not cur.fetchone():
                return {"ok": False, "error": "No es un ECheq"}
            fecha = date.fromisoformat(body.fecha)
            cur.execute("UPDATE cashflow SET fecha=%s, mes=%s WHERE id=%s", (fecha, fecha.month, id))
            cur.execute("UPDATE cheques_emitidos SET fecha_vencimiento=%s WHERE id_cashflow=%s", (fecha, id))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@app.delete("/cashflow/{id}")
def eliminar_cashflow(id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM cheques_emitidos WHERE id_cashflow = %s", (id,))
            if cur.fetchone():
                return {"ok": False, "error": "Los ECheqs no se pueden eliminar."}
            cur.execute("SELECT id_transferencia, id_asiento FROM cashflow WHERE id = %s", (id,))
            row = cur.fetchone()
            id_transf = row["id_transferencia"] if row else None
            id_asiento = row["id_asiento"] if row else None
            if id_transf:
                cur.execute("UPDATE operaciones SET id_pago = NULL WHERE id_pago IN (SELECT id FROM cashflow WHERE id_transferencia = %s)", (id_transf,))
                cur.execute("DELETE FROM cashflow WHERE id_transferencia = %s", (id_transf,))
            else:
                cur.execute("UPDATE operaciones SET id_pago = NULL WHERE id_pago = %s", (id,))
                cur.execute("DELETE FROM cashflow WHERE id = %s", (id,))
            # El paso que faltaba: anular el asiento vinculado (mismo para las dos patas de una
            # transferencia, ya que comparten un solo id_asiento) — sino Balance lo sigue contando.
            if id_asiento is not None:
                cur.execute("""
                    UPDATE asientos SET anulado = true,
                        fecha_anulacion = (CURRENT_TIMESTAMP AT TIME ZONE 'America/Argentina/Buenos_Aires'),
                        motivo_anulacion = 'Movimiento eliminado desde Tesorería'
                    WHERE id = %s
                """, (id_asiento,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

class CashflowUpdateIn(BaseModel):
    importe: Optional[float] = None
    fecha: Optional[str] = None
    detalle: Optional[str] = None

@app.put("/cashflow/{id}")
def actualizar_cashflow(id: int, c: CashflowUpdateIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if c.importe is not None:
                cur.execute("UPDATE cashflow SET importe=%s WHERE id=%s", (c.importe, id))
            if c.fecha is not None:
                fecha = date.fromisoformat(c.fecha)
                cur.execute("UPDATE cashflow SET fecha=%s, mes=%s WHERE id=%s", (fecha, fecha.month, id))
            if c.detalle is not None:
                cur.execute("UPDATE cashflow SET detalle=%s WHERE id=%s", (c.detalle, id))
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

@app.get("/manual")
def get_manual():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT contenido, actualizado_en FROM manual_cbc ORDER BY id LIMIT 1")
            row = cur.fetchone()
            return row if row else {"contenido": "", "actualizado_en": None}
    finally:
        conn.close()

class ManualIn(BaseModel):
    contenido: str

@app.put("/manual")
def guardar_manual(m: ManualIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM manual_cbc LIMIT 1")
            row = cur.fetchone()
            if row:
                cur.execute("UPDATE manual_cbc SET contenido=%s, actualizado_en=now() WHERE id=%s", (m.contenido, row["id"]))
            else:
                cur.execute("INSERT INTO manual_cbc (contenido) VALUES (%s)", (m.contenido,))
        conn.commit()
        return {"ok": True}
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
                       COALESCE(SUM(CASE WHEN c.confirmado = true AND c.fecha <= (CURRENT_TIMESTAMP AT TIME ZONE 'America/Argentina/Buenos_Aires')::date
                                          AND (c.id_asiento IS NULL OR c.id_asiento NOT IN (SELECT id FROM asientos WHERE anulado = true))
                                     THEN c.importe ELSE 0 END), 0)
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
                WHERE c.fecha > (CURRENT_TIMESTAMP AT TIME ZONE 'America/Argentina/Buenos_Aires')::date
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
                    primer_rojo_por_fondo[f["id"]] = {"fecha": str(m["fecha"]), "saldo": round(saldo, 1)}
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
                primer_rojo_total = {"fecha": fecha, "saldo": round(saldo_total, 1)}
                break

        return {"primer_rojo_total": primer_rojo_total, "primer_rojo_por_fondo": primer_rojo_por_fondo}
    finally:
        conn.close()

@app.get("/balance_patrimonial")
def get_balance_patrimonial(mes: Optional[int] = None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Leer fecha de corte desde configuracion
            cur.execute("SELECT valor FROM configuracion WHERE clave = 'fecha_inicio_sistema'")
            row = cur.fetchone()
            fecha_corte = row["valor"] if row else "2026-05-31"

            # Saldos de fondos por cuenta_patrimonial
            cur.execute("""
                SELECT f.cuenta_patrimonial,
                       COALESCE(si.importe, 0) +
                       COALESCE(SUM(CASE WHEN c.confirmado = true AND c.fecha <= (CURRENT_TIMESTAMP AT TIME ZONE 'America/Argentina/Buenos_Aires')::date
                                          AND (c.id_asiento IS NULL OR c.id_asiento NOT IN (SELECT id FROM asientos WHERE anulado = true))
                                     THEN c.importe ELSE 0 END), 0) AS saldo_actual
                FROM fondos f
                LEFT JOIN cashflow c ON c.id_fondo = f.id
                LEFT JOIN saldos_iniciales si ON si.cuenta_patrimonial = f.cuenta_patrimonial
                    AND si.fecha = %s
                    AND (si.id_asiento IS NULL OR si.id_asiento NOT IN (SELECT id FROM asientos WHERE anulado = true))
                WHERE f.cuenta_patrimonial IS NOT NULL AND f.activo = true
                GROUP BY f.cuenta_patrimonial, si.importe
            """, (fecha_corte,))
            fondos = {r["cuenta_patrimonial"]: float(r["saldo_actual"]) for r in cur.fetchall()}

            # Saldos "genéricos" para cualquier cuenta que NO sea un Fondo de tesorería — sirven
            # tanto para Pasivo (deudas de apertura que no son factura de un proveedor puntual,
            # ej. Sueldos a Pagar) como para Activo (Bienes de Uso, Créditos Fiscales, etc.).
            # Es un historial real: la carga original de apertura NUNCA se toca — cada pago o ajuste
            # posterior es una fila NUEVA, con su propia fecha y su propio asiento (mismo mecanismo
            # que ya usa Fondos con cashflow). El total es la suma de todo lo que tenga fecha hasta
            # hoy, exactamente como ya funciona con Fondos.
            cur.execute("""
                SELECT cuenta_patrimonial, COALESCE(SUM(importe), 0) AS total
                FROM saldos_iniciales
                WHERE fecha <= (CURRENT_TIMESTAMP AT TIME ZONE 'America/Argentina/Buenos_Aires')::date
                AND cuenta_patrimonial NOT IN (
                    SELECT cuenta_patrimonial FROM fondos WHERE cuenta_patrimonial IS NOT NULL
                )
                AND (id_asiento IS NULL OR id_asiento NOT IN (SELECT id FROM asientos WHERE anulado = true))
                GROUP BY cuenta_patrimonial
            """)
            saldos_genericos = {r["cuenta_patrimonial"]: float(r["total"]) for r in cur.fetchall()}

            # Cualquier movimiento registrado en asientos (ej. IVA Crédito Fiscal y Percepciones de
            # una factura de compra) también cuenta para el saldo genérico de esa cuenta —
            # así una cuenta nueva, agregada en Admin, ya empieza a mostrar su saldo apenas tenga
            # su primer asiento, sin que haga falta ningún otro cambio.
            cur.execute("""
                SELECT al.cuenta_patrimonial, COALESCE(SUM(al.debe - al.haber), 0) AS total
                FROM asiento_lineas al
                JOIN asientos a ON a.id = al.id_asiento
                WHERE a.anulado = false
                AND al.cuenta_patrimonial NOT IN (
                    SELECT cuenta_patrimonial FROM fondos WHERE cuenta_patrimonial IS NOT NULL
                )
                AND al.cuenta_patrimonial NOT IN (
                    SELECT cuenta_patrimonial FROM titulares WHERE cuenta_patrimonial IS NOT NULL
                )
                AND al.cuenta_patrimonial IN (
                    SELECT nombre FROM plan_de_cuentas WHERE niv1_desc = 'Patrimonial'
                )
                GROUP BY al.cuenta_patrimonial
            """)
            for r in cur.fetchall():
                cuenta = r["cuenta_patrimonial"]
                saldos_genericos[cuenta] = saldos_genericos.get(cuenta, 0) + float(r["total"])

            # Pasivo inicio: facturas impagas con fecha <= fecha_corte
            cur.execute("""
                SELECT t.cuenta_patrimonial, COALESCE(SUM(o.importe), 0) AS total
                FROM operaciones o
                JOIN titulares t ON o.id_titular = t.id
                WHERE o.id_pago IS NULL AND t.cuenta_patrimonial IS NOT NULL
                AND o.fecha <= %s
                GROUP BY t.cuenta_patrimonial
            """, (fecha_corte,))
            pasivo_cc_inicio = {r["cuenta_patrimonial"]: float(r["total"]) for r in cur.fetchall()}
            # Sumamos los saldos genéricos de apertura (ej. Sueldos a Pagar declarado a mano) —
            # así una deuda de apertura que no es factura de proveedor también cuenta.
            for cuenta, importe in saldos_genericos.items():
                pasivo_cc_inicio[cuenta] = pasivo_cc_inicio.get(cuenta, 0) + importe

            # Pasivo actual: facturas impagas con fecha > fecha_corte
            cur.execute("""
                SELECT t.cuenta_patrimonial, COALESCE(SUM(o.importe), 0) AS total
                FROM operaciones o
                JOIN titulares t ON o.id_titular = t.id
                WHERE o.id_pago IS NULL AND t.cuenta_patrimonial IS NOT NULL
                AND o.fecha > %s
                GROUP BY t.cuenta_patrimonial
            """, (fecha_corte,))
            pasivo_cc_actual = {r["cuenta_patrimonial"]: float(r["total"]) for r in cur.fetchall()}

            # ECheqs emitidos pendientes (operativos)
            cur.execute("""
                SELECT COALESCE(SUM(c.importe), 0) AS total
                FROM cashflow c
                JOIN cheques_emitidos ch ON ch.id_cashflow = c.id
                WHERE c.confirmado = false
            """)
            echeqs = float(cur.fetchone()["total"])

            # Cheques de apertura (pasivo inicial) — todos los emitidos antes del corte, debitados o no
            cur.execute("""
                SELECT COALESCE(SUM(importe), 0) AS total
                FROM cheques_apertura
                WHERE fecha_emision <= %s
            """, (fecha_corte,))
            cheques_apertura_total = float(cur.fetchone()["total"])

            # Cheques de apertura ya debitados (para restar del pasivo actual)
            cur.execute("""
                SELECT COALESCE(SUM(importe), 0) AS total
                FROM cheques_apertura
                WHERE debitado = true AND fecha_emision <= %s
            """, (fecha_corte,))
            cheques_apertura_debitados = float(cur.fetchone()["total"])
            where_mes = f"AND EXTRACT(MONTH FROM c.fecha) = {mes}" if mes else ""
            cur.execute(f"""
                SELECT COALESCE(SUM(c.importe), 0) AS total
                FROM cashflow c
                WHERE c.cod_cuenta = 'Tarj. Credit. Pend. Acreditacion' {where_mes}
            """)
            tarjetas = float(cur.fetchone()["total"])

        return {
            "fondos": fondos,
            "saldos_genericos": saldos_genericos,
            "pasivo_cc_inicio": pasivo_cc_inicio,
            "pasivo_cc_actual": pasivo_cc_actual,
            "pasivo_cc": pasivo_cc_actual,
            "echeqs_pendientes": echeqs,
            "cheques_apertura": cheques_apertura_total,
            "cheques_apertura_debitados": cheques_apertura_debitados,
            "tarjetas_pendientes": tarjetas,
            "fecha_corte": fecha_corte,
        }
    finally:
        conn.close()


class AsientoIn(BaseModel):
    tipo_origen: str
    descripcion: Optional[str] = None

class AnularAsientoIn(BaseModel):
    motivo: Optional[str] = None

def _crear_asiento(cur, tipo_origen, descripcion=None, fecha=None):
    """Crea un asiento y devuelve su id. Se usa DESDE ADENTRO de otros endpoints
    (saldos_iniciales, comprobantes, movimientos, liquidaciones) — no es para llamar solo,
    siempre como parte de la misma transacción de lo que genera.
    'fecha' es la fecha REAL de la operación (la de la factura, la del movimiento) — si no se
    pasa, se usa hoy como mejor aproximación."""
    cur.execute(
        "INSERT INTO asientos (tipo_origen, descripcion, fecha) VALUES (%s, %s, %s) RETURNING id",
        (tipo_origen, descripcion, fecha or date.today())
    )
    return cur.fetchone()["id"]

def _agregar_lineas_asiento(cur, id_asiento, lineas):
    """lineas: lista de tuplas (cuenta_patrimonial, debe, haber, descripcion_opcional).
    Todo asiento tiene que quedar balanceado: suma de debe == suma de haber."""
    for linea in lineas:
        cuenta, debe, haber = linea[0], linea[1], linea[2]
        desc = linea[3] if len(linea) > 3 else None
        cur.execute(
            "INSERT INTO asiento_lineas (id_asiento, cuenta_patrimonial, debe, haber, descripcion) VALUES (%s, %s, %s, %s, %s)",
            (id_asiento, cuenta, debe, haber, desc)
        )

def _set_reversion(cur, id_asiento, acciones):
    """PRINCIPIO GENERAL: cada asiento tiene que dejar anotado, en el momento en que se crea,
    exactamente qué hay que deshacer si algún día se lo revierte — así 'revertir_todo_asiento'
    nunca necesita saber a mano qué es un cheque, una transferencia, o cualquier cosa nueva que
    se agregue en el futuro; el asiento ya lo trae escrito.

    'acciones' es una lista de diccionarios, cada uno describe UNA acción a ejecutar:
      - Para borrar una fila (o varias que compartan un valor): 
          {"tabla": "operaciones", "where_columna": "id_asiento", "where_valor": id_asiento, "tipo": "DELETE"}
      - Para actualizar campos en vez de borrar (ej. "volver a Pendiente" sin borrar el registro):
          {"tabla": "cheques_apertura", "where_columna": "id", "where_valor": 7, "tipo": "UPDATE",
           "campos": {"debitado": False, "id_asiento_debito": None}}
    'where_valor' casi siempre es el propio id_asiento, salvo que la acción tenga que apuntar a
    un id específico de otra tabla (ej. el id de la fila de cheques_apertura)."""
    cur.execute("UPDATE asientos SET reversion_acciones = %s WHERE id = %s", (json.dumps(acciones), id_asiento))

@app.post("/asientos")
def crear_asiento(a: AsientoIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            id_nuevo = _crear_asiento(cur, a.tipo_origen, a.descripcion)
        conn.commit()
        return {"ok": True, "id": id_nuevo}
    finally:
        conn.close()

@app.get("/asientos_con_lineas")
def get_asientos_con_lineas(tipo_origen: Optional[str] = None, incluir_anulados: bool = True):
    """Igual que /asientos, pero cada uno ya trae sus líneas adentro — para no tener que
    pedirlas una por una desde el frontend."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if tipo_origen:
                where = "WHERE tipo_origen = %s" + ("" if incluir_anulados else " AND anulado = false")
                cur.execute(f"SELECT * FROM asientos {where} ORDER BY fecha_creacion DESC", (tipo_origen,))
            else:
                where = "" if incluir_anulados else "WHERE anulado = false"
                cur.execute(f"SELECT * FROM asientos {where} ORDER BY fecha_creacion DESC")
            asientos = cur.fetchall()
            ids = [a["id"] for a in asientos]
            lineas_por_asiento = {}
            if ids:
                cur.execute("SELECT * FROM asiento_lineas WHERE id_asiento = ANY(%s) ORDER BY (haber > 0), id", (ids,))
                for l in cur.fetchall():
                    lineas_por_asiento.setdefault(l["id_asiento"], []).append(l)
            for a in asientos:
                a["lineas"] = lineas_por_asiento.get(a["id"], [])
            return asientos
    finally:
        conn.close()

@app.get("/asientos")
def get_asientos(tipo_origen: Optional[str] = None, incluir_anulados: bool = True):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if tipo_origen:
                where = "WHERE tipo_origen = %s" + ("" if incluir_anulados else " AND anulado = false")
                cur.execute(f"SELECT * FROM asientos {where} ORDER BY fecha_creacion DESC", (tipo_origen,))
            else:
                where = "" if incluir_anulados else "WHERE anulado = false"
                cur.execute(f"SELECT * FROM asientos {where} ORDER BY fecha_creacion DESC")
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/asientos/{id}/lineas")
def get_lineas_asiento(id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM asiento_lineas WHERE id_asiento = %s ORDER BY id", (id,))
            return cur.fetchall()
    finally:
        conn.close()

@app.get("/balance_unificado")
def get_balance_unificado(mes: Optional[int] = None, anio: Optional[int] = None):
    """Reemplaza /balance y /balance_patrimonial — una sola fuente de verdad (asiento_lineas)
    para TODO el Balance (Resultados y Patrimonial), sin mezclar cashflow/operaciones/fondos
    por separado. Cada cuenta del Plan de Cuentas trae:
      - 'periodo': el movimiento SOLO del mes elegido (lo que importa para Resultados).
      - 'acumulado': el saldo de siempre hasta el fin de ese mes (lo que importa para Patrimonial).
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            hoy = date.today()
            anio = anio or hoy.year
            if mes:
                fecha_inicio_periodo = date(anio, mes, 1)
                fecha_fin_periodo = date(anio + 1, 1, 1) - timedelta(days=1) if mes == 12 else date(anio, mes + 1, 1) - timedelta(days=1)
            else:
                fecha_inicio_periodo = date(anio, 1, 1)
                fecha_fin_periodo = hoy

            cur.execute("""
                SELECT id, niv1, niv2, niv3, niv4, niv5, niv6, niv1_desc, niv2_desc, niv3_desc, niv4_desc, niv6_desc, nombre, id_codigo
                FROM plan_de_cuentas WHERE activo = true
                ORDER BY niv1, niv2, niv3, niv4, niv5, niv6
            """)
            cuentas = cur.fetchall()

            # Movimiento del período (para Resultados): solo asientos con fecha DENTRO del mes elegido.
            cur.execute("""
                SELECT al.cuenta_patrimonial, COALESCE(SUM(al.debe - al.haber), 0) AS total
                FROM asiento_lineas al
                JOIN asientos a ON a.id = al.id_asiento
                WHERE a.anulado = false AND a.fecha BETWEEN %s AND %s
                GROUP BY al.cuenta_patrimonial
            """, (fecha_inicio_periodo, fecha_fin_periodo))
            movimiento_periodo = {r["cuenta_patrimonial"]: float(r["total"]) for r in cur.fetchall()}

            # Saldo acumulado (para Patrimonial): todo lo que tenga fecha <= fin del mes elegido.
            cur.execute("""
                SELECT al.cuenta_patrimonial, COALESCE(SUM(al.debe - al.haber), 0) AS total
                FROM asiento_lineas al
                JOIN asientos a ON a.id = al.id_asiento
                WHERE a.anulado = false AND a.fecha <= %s
                GROUP BY al.cuenta_patrimonial
            """, (fecha_fin_periodo,))
            saldo_acumulado = {r["cuenta_patrimonial"]: float(r["total"]) for r in cur.fetchall()}

            resultado = []
            for c in cuentas:
                nombre = c["nombre"]
                resultado.append({
                    **c,
                    "periodo": movimiento_periodo.get(nombre, 0),
                    "acumulado": saldo_acumulado.get(nombre, 0),
                })
            return resultado
    finally:
        conn.close()

@app.put("/asientos/{id}/anular")
def anular_asiento(id: int, a: AnularAsientoIn):
    """Anula un asiento. No borra ninguna fila de las tablas que dependen de él — las queries de
    Balance ya filtran por 'asiento no anulado', así que esto alcanza para que deje de contar."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE asientos SET anulado = true,
                    fecha_anulacion = (CURRENT_TIMESTAMP AT TIME ZONE 'America/Argentina/Buenos_Aires'),
                    motivo_anulacion = %s
                WHERE id = %s
            """, (a.motivo, id))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

def _ejecutar_reversion(cur, id):
    """Ejecuta lo que el asiento dejó anotado en 'reversion_acciones' (o la red de seguridad
    genérica si no tiene nada anotado) — sin tocar el asiento en sí. Lo que se hace DESPUÉS con
    el asiento (anularlo, dejando rastro, o borrarlo del todo) lo decide quien llama a esto."""
    cur.execute("SELECT reversion_acciones FROM asientos WHERE id = %s", (id,))
    fila = cur.fetchone()
    acciones = fila["reversion_acciones"] if fila and fila["reversion_acciones"] else []

    for accion in acciones:
        tabla, where_col, where_val = accion["tabla"], accion["where_columna"], accion["where_valor"]
        if accion["tipo"] == "DELETE":
            cur.execute(f"DELETE FROM {tabla} WHERE {where_col} = %s", (where_val,))
        elif accion["tipo"] == "UPDATE":
            campos = accion["campos"]
            sets = ", ".join(f"{k} = %s" for k in campos)
            cur.execute(f"UPDATE {tabla} SET {sets} WHERE {where_col} = %s", (*campos.values(), where_val))

    # Red de seguridad para asientos viejos, creados antes de que existiera
    # 'reversion_acciones' — mismo comportamiento genérico de siempre (borrar todo lo
    # que apunte directo a este asiento), por si 'acciones' vino vacío.
    if not acciones:
        cur.execute("UPDATE operaciones SET id_pago = NULL WHERE id_pago IN (SELECT id FROM cashflow WHERE id_asiento = %s)", (id,))
        cur.execute("DELETE FROM cashflow WHERE id_asiento = %s", (id,))
        cur.execute("DELETE FROM operaciones WHERE id_asiento = %s", (id,))
        cur.execute("DELETE FROM saldos_iniciales WHERE id_asiento = %s", (id,))

@app.put("/asientos/{id}/revertir_todo")
def revertir_todo_asiento(id: int, a: AnularAsientoIn):
    """Uso restringido (Emi/Tomy) — a diferencia de 'anular' (que solo marca el asiento), esto
    ANULA el asiento Y ejecuta lo que ese mismo asiento haya dejado anotado en
    'reversion_acciones' al momento de crearse (ver _set_reversion) — sin importar las reglas
    propias de cada pantalla. Genérico: agregar un tipo de asiento nuevo en el futuro NUNCA
    requiere tocar esta función — alcanza con que, al crearlo, llame a _set_reversion().
    Deja rastro (anulado=true), no borra el asiento en sí — para uso normal, día a día."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            _ejecutar_reversion(cur, id)
            cur.execute("""
                UPDATE asientos SET anulado = true,
                    fecha_anulacion = (CURRENT_TIMESTAMP AT TIME ZONE 'America/Argentina/Buenos_Aires'),
                    motivo_anulacion = %s
                WHERE id = %s
            """, (a.motivo or "Revertido por completo desde Libro Diario", id))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@app.put("/asientos/revertir_todos_los_activos")
def revertir_todos_los_asientos_activos():
    """Botón sensible (Libro Diario, uso restringido) — revierte los asientos activos (con el
    mismo mecanismo genérico de arriba) Y borra TODOS los asientos, estén anulados o no —
    Libro Diario queda completamente en cero, sin ningún asiento fantasma de pruebas
    anteriores. Vacía toda la actividad del sistema (facturas, pagos, movimientos, saldos
    iniciales, cheques) dejando intactos los datos NO patrimoniales (Titulares, Plan de
    Cuentas, Fondos, Configuración, Empleados) — pensado para arrancar de cero después de
    cargar datos de prueba."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, anulado FROM asientos ORDER BY id")
            filas = cur.fetchall()
            ids = [r["id"] for r in filas]
            ids_activos = [r["id"] for r in filas if not r["anulado"]]
            for id_asiento in ids_activos:
                _ejecutar_reversion(cur, id_asiento)
            if ids:
                cur.execute("DELETE FROM asiento_lineas WHERE id_asiento = ANY(%s)", (ids,))
                cur.execute("DELETE FROM asientos WHERE id = ANY(%s)", (ids,))
        conn.commit()
        return {"ok": True, "cantidad": len(ids)}
    finally:
        conn.close()

@app.put("/asientos/{id}/reactivar")
def reactivar_asiento(id: int):
    """Por si se anuló por error — vuelve a contar como si nunca se hubiera anulado."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE asientos SET anulado = false, fecha_anulacion = NULL, motivo_anulacion = NULL WHERE id = %s", (id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


class SaldoInicialIn(BaseModel):
    fecha: str
    cuenta_patrimonial: str
    importe: float
    descripcion: Optional[str] = None


# ==========================================
# CHEQUES DE APERTURA
# ==========================================
class ChequeAperturaIn(BaseModel):
    fecha_emision: str
    fecha_cheque: str
    numero: Optional[str] = None
    id_titular: Optional[int] = None
    id_fondo: Optional[int] = None
    importe: float
    descripcion: Optional[str] = None
    debitado: Optional[bool] = False

@app.get("/cheques_apertura")
def get_cheques_apertura():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ca.*, t.nombre as titular_nombre
                FROM cheques_apertura ca
                LEFT JOIN titulares t ON t.id::integer = ca.id_titular
                ORDER BY ca.fecha_cheque, ca.id
            """)
            return cur.fetchall()
    finally:
        conn.close()

@app.post("/cheques_apertura")
def crear_cheque_apertura(c: ChequeAperturaIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # El cheque, mientras está Pendiente, es una deuda (Pasivo) — misma lógica que
            # cualquier saldo de apertura: contrapartida contra "Saldo Patrimonial de Apertura".
            id_asiento = _crear_asiento(cur, "CHEQUE_APERTURA", f"Cheque apertura #{c.numero or ''}", date.fromisoformat(c.fecha_emision))
            _agregar_lineas_asiento(cur, id_asiento, [
                ("Saldo Patrimonial de Apertura", c.importe, 0, "Apertura de cheque"),
                ("Valores Emitidos — Cheques Pendientes", 0, c.importe, "Apertura de cheque"),
            ])
            cur.execute("""
                INSERT INTO cheques_apertura (fecha_emision, fecha_cheque, numero, id_titular, importe, descripcion, debitado, id_asiento)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
            """, (c.fecha_emision, c.fecha_cheque, c.numero, c.id_titular, c.importe, c.descripcion, c.debitado, id_asiento))
            id_nuevo = cur.fetchone()["id"]
            # Crear movimiento proyectado en cashflow si tiene fondo y no está debitado
            if c.id_fondo and not c.debitado:
                fecha = date.fromisoformat(c.fecha_cheque)
                cur.execute("""
                    INSERT INTO cashflow (mes, fecha, id_titular, cod_cuenta, detalle, importe, id_fondo, confirmado, id_cheque_apertura, id_asiento)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, false, %s, %s)
                """, (fecha.month, fecha, c.id_titular, 'Valores Emitidos — Cheques Pendientes',
                      f"Cheque apertura #{c.numero or ''} - {c.descripcion or ''}", 
                      -abs(c.importe), c.id_fondo, id_nuevo, id_asiento))
            # Si algún día se revierte este asiento: el cheque nunca existió, se borra entero
            # (y su cashflow, si tenía uno).
            _set_reversion(cur, id_asiento, [
                {"tabla": "cashflow", "where_columna": "id_cheque_apertura", "where_valor": id_nuevo, "tipo": "DELETE"},
                {"tabla": "cheques_apertura", "where_columna": "id", "where_valor": id_nuevo, "tipo": "DELETE"},
            ])
        conn.commit()
        return {"ok": True, "id": id_nuevo}
    finally:
        conn.close()

@app.put("/cheques_apertura/{id}")
def actualizar_cheque_apertura(id: int, c: ChequeAperturaIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT debitado, id_asiento_debito, id_asiento FROM cheques_apertura WHERE id = %s", (id,))
            existente = cur.fetchone()
            ya_debitado = existente["debitado"] if existente else False
            id_asiento_debito = existente["id_asiento_debito"] if existente else None
            id_asiento = existente["id_asiento"] if existente else None

            cur.execute("""
                UPDATE cheques_apertura SET fecha_emision=%s, fecha_cheque=%s, numero=%s,
                id_titular=%s, id_fondo=%s, importe=%s, descripcion=%s, debitado=%s
                WHERE id=%s
            """, (c.fecha_emision, c.fecha_cheque, c.numero, c.id_titular, c.id_fondo, c.importe, c.descripcion, c.debitado, id))

            # Se editó el cheque (importe y/o fecha) — el asiento original tiene que reflejar
            # los mismos datos nuevos, no quedarse con los viejos. Se actualizan sus líneas y
            # su fecha, en vez de crear un asiento nuevo.
            if id_asiento is not None:
                cur.execute("""
                    UPDATE asientos SET fecha = %s, descripcion = %s WHERE id = %s
                """, (date.fromisoformat(c.fecha_emision), f"Cheque apertura #{c.numero or ''}", id_asiento))
                cur.execute("""
                    UPDATE asiento_lineas SET debe = %s WHERE id_asiento = %s AND cuenta_patrimonial = 'Saldo Patrimonial de Apertura'
                """, (c.importe, id_asiento))
                cur.execute("""
                    UPDATE asiento_lineas SET haber = %s WHERE id_asiento = %s AND cuenta_patrimonial = 'Valores Emitidos — Cheques Pendientes'
                """, (c.importe, id_asiento))

            # Recién se marca Debitado (antes no lo estaba): la plata sale de verdad del banco.
            # Segundo asiento: se cancela el Pasivo pendiente, y baja el Fondo real.
            if c.debitado and not ya_debitado and c.id_fondo:
                cur.execute("SELECT cuenta_patrimonial, nombre FROM fondos WHERE id = %s", (c.id_fondo,))
                fila_fondo = cur.fetchone()
                cuenta_fondo = (fila_fondo["cuenta_patrimonial"] if fila_fondo else None) or (fila_fondo["nombre"] if fila_fondo else None)
                if cuenta_fondo:
                    nuevo_asiento = _crear_asiento(cur, "CHEQUE_APERTURA_DEBITO", f"Débito de cheque apertura #{c.numero or ''}", date.today())
                    _agregar_lineas_asiento(cur, nuevo_asiento, [
                        ("Valores Emitidos — Cheques Pendientes", c.importe, 0, "Débito de cheque"),
                        (cuenta_fondo, 0, c.importe, "Débito de cheque"),
                    ])
                    cur.execute("UPDATE cheques_apertura SET id_asiento_debito = %s WHERE id = %s", (nuevo_asiento, id))
                    _set_reversion(cur, nuevo_asiento, [
                        {"tabla": "cheques_apertura", "where_columna": "id", "where_valor": id, "tipo": "UPDATE",
                         "campos": {"debitado": False, "id_asiento_debito": None}},
                        {"tabla": "cashflow", "where_columna": "id_cheque_apertura", "where_valor": id, "tipo": "UPDATE",
                         "campos": {"confirmado": False}},
                    ])
            # Se destilda Debitado (antes sí lo estaba): se revierte el segundo asiento.
            elif not c.debitado and ya_debitado and id_asiento_debito:
                cur.execute("""
                    UPDATE asientos SET anulado = true,
                        fecha_anulacion = (CURRENT_TIMESTAMP AT TIME ZONE 'America/Argentina/Buenos_Aires'),
                        motivo_anulacion = 'Vuelto a Pendiente'
                    WHERE id = %s
                """, (id_asiento_debito,))
            elif c.debitado and ya_debitado and id_asiento_debito:
                # Ya estaba Debitado y se edita el importe/fondo — el segundo asiento también
                # tiene que reflejar el dato nuevo, no quedarse con el viejo.
                if c.id_fondo:
                    cur.execute("SELECT cuenta_patrimonial, nombre FROM fondos WHERE id = %s", (c.id_fondo,))
                    fila_fondo = cur.fetchone()
                    cuenta_fondo = (fila_fondo["cuenta_patrimonial"] if fila_fondo else None) or (fila_fondo["nombre"] if fila_fondo else None)
                    if cuenta_fondo:
                        cur.execute("""
                            UPDATE asiento_lineas SET debe = %s WHERE id_asiento = %s AND cuenta_patrimonial = 'Valores Emitidos — Cheques Pendientes'
                        """, (c.importe, id_asiento_debito))
                        cur.execute("""
                            DELETE FROM asiento_lineas WHERE id_asiento = %s AND haber > 0
                        """, (id_asiento_debito,))
                        _agregar_lineas_asiento(cur, id_asiento_debito, [(cuenta_fondo, 0, c.importe, "Débito de cheque (editado)")])

            # Actualizar cashflow proyectado (como ya hacía)
            fecha = date.fromisoformat(c.fecha_cheque)
            if c.debitado:
                cur.execute("UPDATE cashflow SET confirmado=true WHERE id_cheque_apertura=%s", (id,))
            else:
                cur.execute("""
                    UPDATE cashflow SET fecha=%s, mes=%s, importe=%s, id_fondo=%s, confirmado=false
                    WHERE id_cheque_apertura=%s
                """, (fecha, fecha.month, -abs(c.importe), c.id_fondo, id))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@app.delete("/cheques_apertura/{id}")
def eliminar_cheque_apertura(id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id_asiento, id_asiento_debito FROM cheques_apertura WHERE id = %s", (id,))
            row = cur.fetchone()
            cur.execute("DELETE FROM cashflow WHERE id_cheque_apertura = %s", (id,))
            cur.execute("DELETE FROM cheques_apertura WHERE id=%s", (id,))
            if row:
                for id_asiento in [row["id_asiento"], row["id_asiento_debito"]]:
                    if id_asiento is not None:
                        cur.execute("""
                            UPDATE asientos SET anulado = true,
                                fecha_anulacion = (CURRENT_TIMESTAMP AT TIME ZONE 'America/Argentina/Buenos_Aires'),
                                motivo_anulacion = 'Cheque de apertura eliminado'
                            WHERE id = %s
                        """, (id_asiento,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@app.get("/cheques_apertura/total")
def get_total_cheques_apertura():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(SUM(importe), 0) as total FROM cheques_apertura WHERE debitado = false")
            return cur.fetchone()
    finally:
        conn.close()

@app.get("/estado_configuracion")
def get_estado_configuracion():
    """Para cada paso del checklist, chequea si el sistema realmente tiene datos cargados ahí —
    no se le pregunta al usuario, se va a mirar la base directamente."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM saldos_iniciales")
            saldos_iniciales = cur.fetchone()["n"] > 0
            cur.execute("SELECT COUNT(*) AS n FROM titulares")
            titulares = cur.fetchone()["n"] > 0
            cur.execute("SELECT COUNT(*) AS n FROM fondos WHERE es_sistema = false")
            fondos = cur.fetchone()["n"] > 0
            cur.execute("SELECT COUNT(*) AS n FROM empleados")
            empleados = cur.fetchone()["n"] > 0
            cur.execute("SELECT COUNT(*) AS n FROM conceptos_liquidacion WHERE convenio != 'GENERAL'")
            conceptos_liquidacion = cur.fetchone()["n"] > 0
            return {
                "saldos_iniciales": saldos_iniciales,
                "titulares": titulares,
                "fondos": fondos,
                "empleados": empleados,
                "conceptos_liquidacion": conceptos_liquidacion,
            }
    finally:
        conn.close()

@app.get("/configuracion")
def get_configuracion():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT clave, valor, descripcion FROM configuracion ORDER BY clave")
            rows = cur.fetchall()
            return {r["clave"]: {"valor": r["valor"], "descripcion": r["descripcion"]} for r in rows}
    finally:
        conn.close()

@app.put("/configuracion/{clave}")
def actualizar_configuracion(clave: str, body: dict):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO configuracion (clave, valor, descripcion)
                VALUES (%s, %s, %s)
                ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor
            """, (clave, body.get("valor"), body.get("descripcion")))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@app.get("/saldos_iniciales")
def get_saldos_iniciales(fecha: Optional[str] = None, incluir_anulados: bool = False):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            filtro_anulados = "" if incluir_anulados else "AND (id_asiento IS NULL OR id_asiento NOT IN (SELECT id FROM asientos WHERE anulado = true))"
            if fecha:
                cur.execute(f"SELECT * FROM saldos_iniciales WHERE fecha = %s {filtro_anulados} ORDER BY cuenta_patrimonial", (fecha,))
            else:
                cur.execute(f"SELECT * FROM saldos_iniciales WHERE true {filtro_anulados} ORDER BY fecha, cuenta_patrimonial")
            return cur.fetchall()
    finally:
        conn.close()

def _lineas_apertura(cur, cuenta_patrimonial, importe):
    """Arma las 2 líneas de un asiento de apertura: la cuenta en sí, y la contrapartida
    contra 'Saldo Patrimonial de Apertura' — Activo al Debe, Pasivo al Haber."""
    cur.execute("SELECT niv2_desc FROM plan_de_cuentas WHERE nombre = %s LIMIT 1", (cuenta_patrimonial,))
    fila = cur.fetchone()
    lado = fila["niv2_desc"] if fila else None
    monto = abs(importe)
    if lado == "Pasivos":
        return [
            (cuenta_patrimonial, 0, monto, "Apertura"),
            ("Saldo Patrimonial de Apertura", monto, 0, "Apertura"),
        ]
    else:
        return [
            (cuenta_patrimonial, monto, 0, "Apertura"),
            ("Saldo Patrimonial de Apertura", 0, monto, "Apertura"),
        ]

@app.post("/saldos_iniciales")
def crear_saldo_inicial(s: SaldoInicialIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Si ya existe un saldo inicial cargado para esta misma cuenta, se reemplaza
            # (mismo criterio que el PUT) — así "editar" no suma un asiento nuevo arriba del
            # anterior, sino que corrige el que ya estaba.
            cur.execute("SELECT id, id_asiento FROM saldos_iniciales WHERE cuenta_patrimonial = %s ORDER BY id LIMIT 1", (s.cuenta_patrimonial,))
            existente = cur.fetchone()
            if existente:
                id_asiento = existente["id_asiento"]
                if id_asiento is not None:
                    cur.execute("DELETE FROM asiento_lineas WHERE id_asiento = %s", (id_asiento,))
                else:
                    id_asiento = _crear_asiento(cur, "APERTURA", f"Apertura: {s.cuenta_patrimonial}", date.fromisoformat(s.fecha))
                _agregar_lineas_asiento(cur, id_asiento, _lineas_apertura(cur, s.cuenta_patrimonial, s.importe))
                cur.execute("""
                    UPDATE saldos_iniciales SET fecha=%s, importe=%s, descripcion=%s, id_asiento=%s
                    WHERE id = %s
                """, (s.fecha, s.importe, s.descripcion, id_asiento, existente["id"]))
                _set_reversion(cur, id_asiento, [
                    {"tabla": "saldos_iniciales", "where_columna": "id", "where_valor": existente["id"], "tipo": "DELETE"},
                ])
                conn.commit()
                return {"ok": True, "id": existente["id"], "id_asiento": id_asiento}

            id_asiento = _crear_asiento(cur, "APERTURA", f"Apertura: {s.cuenta_patrimonial}", date.fromisoformat(s.fecha))
            _agregar_lineas_asiento(cur, id_asiento, _lineas_apertura(cur, s.cuenta_patrimonial, s.importe))
            cur.execute("""
                INSERT INTO saldos_iniciales (fecha, cuenta_patrimonial, importe, descripcion, id_asiento)
                VALUES (%s, %s, %s, %s, %s) RETURNING id
            """, (s.fecha, s.cuenta_patrimonial, s.importe, s.descripcion, id_asiento))
            id_nuevo = cur.fetchone()["id"]
            _set_reversion(cur, id_asiento, [
                {"tabla": "saldos_iniciales", "where_columna": "id", "where_valor": id_nuevo, "tipo": "DELETE"},
            ])
        conn.commit()
        return {"ok": True, "id": id_nuevo, "id_asiento": id_asiento}
    finally:
        conn.close()

@app.put("/saldos_iniciales/{id}")
def actualizar_saldo_inicial(id: int, s: SaldoInicialIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id_asiento FROM saldos_iniciales WHERE id = %s", (id,))
            existente = cur.fetchone()
            id_asiento = existente["id_asiento"] if existente else None
            if id_asiento is None:
                id_asiento = _crear_asiento(cur, "APERTURA", f"Apertura: {s.cuenta_patrimonial}", date.fromisoformat(s.fecha))
            else:
                # Ya tenía asiento — se reemplazan sus líneas por las nuevas, en vez de duplicar.
                cur.execute("DELETE FROM asiento_lineas WHERE id_asiento = %s", (id_asiento,))
            _agregar_lineas_asiento(cur, id_asiento, _lineas_apertura(cur, s.cuenta_patrimonial, s.importe))
            cur.execute("""
                UPDATE saldos_iniciales SET fecha=%s, cuenta_patrimonial=%s, importe=%s, descripcion=%s, id_asiento=%s
                WHERE id=%s
            """, (s.fecha, s.cuenta_patrimonial, s.importe, s.descripcion, id_asiento, id))
            _set_reversion(cur, id_asiento, [
                {"tabla": "saldos_iniciales", "where_columna": "id", "where_valor": id, "tipo": "DELETE"},
            ])
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()

@app.delete("/saldos_iniciales/{id}")
def eliminar_saldo_inicial(id: int):
    """No borra la fila si tiene un asiento — anula el asiento en su lugar, para dejar rastro
    de que existió y se dio de baja, en vez de que desaparezca sin dejar huella."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id_asiento FROM saldos_iniciales WHERE id = %s", (id,))
            row = cur.fetchone()
            if row and row["id_asiento"]:
                cur.execute("""
                    UPDATE asientos SET anulado = true,
                        fecha_anulacion = (CURRENT_TIMESTAMP AT TIME ZONE 'America/Argentina/Buenos_Aires'),
                        motivo_anulacion = 'Eliminado desde Balance Inicial'
                    WHERE id = %s
                """, (row["id_asiento"],))
            else:
                cur.execute("DELETE FROM saldos_iniciales WHERE id=%s", (id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()
