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
            cur.execute("DELETE FROM cashflow WHERE id = %s", (id,))
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
