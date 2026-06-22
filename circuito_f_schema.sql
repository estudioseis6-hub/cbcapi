-- ============================================================================
--  CIRCUITO F  -  esquema de base de datos
--  Tablas aditivas (no modifican tablas existentes). Idempotente.
--  El ejercicio se identifica por su AÑO DE CIERRE (anio_ejercicio).
-- ============================================================================

-- Configuracion del modulo (una sola fila en uso).
CREATE TABLE IF NOT EXISTS circuito_f_config (
    id                    SERIAL PRIMARY KEY,
    mes_cierre            INTEGER NOT NULL DEFAULT 12,    -- 1..12, mes de cierre del ejercicio
    alicuota_iva_compras  NUMERIC NOT NULL DEFAULT 0.21,  -- para netear compras de IVA
    alicuota_iibb         NUMERIC NOT NULL DEFAULT 0.00,  -- IIBB sobre ventas netas
    actualizado_en        TIMESTAMP DEFAULT now()
);

-- Ventas netas por mes del ejercicio (carga manual del usuario).
CREATE TABLE IF NOT EXISTS circuito_f_ventas (
    id              SERIAL PRIMARY KEY,
    anio_ejercicio  INTEGER NOT NULL,
    mes             INTEGER NOT NULL,                     -- 1..12 (mes calendario)
    ventas_netas    NUMERIC NOT NULL DEFAULT 0,
    actualizado_en  TIMESTAMP DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_cf_ventas ON circuito_f_ventas (anio_ejercicio, mes);

-- Sueldos por mes (devengado, tomado del F.931).
CREATE TABLE IF NOT EXISTS circuito_f_sueldos (
    id                  SERIAL PRIMARY KEY,
    anio_ejercicio      INTEGER NOT NULL,
    mes                 INTEGER NOT NULL,                 -- 1..12 (mes calendario)
    sueldos             NUMERIC NOT NULL DEFAULT 0,
    cargas_sociales     NUMERIC NOT NULL DEFAULT 0,
    aportes_sindicales  NUMERIC NOT NULL DEFAULT 0,
    actualizado_en      TIMESTAMP DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_cf_sueldos ON circuito_f_sueldos (anio_ejercicio, mes);

-- Escala del impuesto a las ganancias (Ley 27.630). Editable por ejercicio.
-- impuesto = fijo + alicuota * (ganancia_neta - desde), para el tramo donde cae la ganancia.
CREATE TABLE IF NOT EXISTS circuito_f_escala (
    id              SERIAL PRIMARY KEY,
    anio_ejercicio  INTEGER NOT NULL,
    orden           INTEGER NOT NULL,                     -- orden ascendente del tramo
    desde           NUMERIC NOT NULL DEFAULT 0,
    hasta           NUMERIC,                              -- NULL = sin tope (ultimo tramo)
    fijo            NUMERIC NOT NULL DEFAULT 0,           -- monto fijo del tramo
    alicuota        NUMERIC NOT NULL DEFAULT 0,           -- alicuota marginal sobre el excedente
    actualizado_en  TIMESTAMP DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_cf_escala ON circuito_f_escala (anio_ejercicio, orden);
