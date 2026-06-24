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
