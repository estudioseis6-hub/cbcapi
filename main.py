class TitularIn(BaseModel):
    nombre: str
    nivel1: str
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

@app.post("/titulares")
def crear_titular(t: TitularIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO titulares (nombre, nivel1, tipo_titular, plazo_pago, razon_social, cuit, cond_fiscal, cod1, cod2, cod3, cod4, cod5, fondo_def, genera_cc, activo)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (t.nombre, t.nivel1, t.tipo_titular, t.plazo_pago, t.razon_social, t.cuit, t.cond_fiscal, t.cod1, t.cod2, t.cod3, t.cod4, t.cod5, t.fondo_def, t.genera_cc, t.activo))
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
                UPDATE titulares SET nombre=%s, nivel1=%s, tipo_titular=%s, plazo_pago=%s,
                       razon_social=%s, cuit=%s, cond_fiscal=%s,
                       cod1=%s, cod2=%s, cod3=%s, cod4=%s, cod5=%s,
                       fondo_def=%s, genera_cc=%s, activo=%s
                WHERE id=%s
            """, (t.nombre, t.nivel1, t.tipo_titular, t.plazo_pago,
                  t.razon_social, t.cuit, t.cond_fiscal,
                  t.cod1, t.cod2, t.cod3, t.cod4, t.cod5,
                  t.fondo_def, t.genera_cc, t.activo, id))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()
