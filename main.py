-- ==========================================
-- AMPLIACIÓN DE EMPLEADOS + FAMILIARES
-- (basado en la Planilla de Datos Personales real)
-- ==========================================

-- 1) Separar nombre y apellido
ALTER TABLE empleados ADD COLUMN IF NOT EXISTS apellido TEXT;
-- (el campo "nombre" que ya existe pasa a usarse solo para el/los nombres de pila)

-- 2) Datos personales que faltaban
ALTER TABLE empleados ADD COLUMN IF NOT EXISTS tipo_documento TEXT;   -- DNI, LC, LE, Pasaporte
ALTER TABLE empleados ADD COLUMN IF NOT EXISTS nro_documento TEXT;
ALTER TABLE empleados ADD COLUMN IF NOT EXISTS nacionalidad TEXT;
ALTER TABLE empleados ADD COLUMN IF NOT EXISTS profesion TEXT;
ALTER TABLE empleados ADD COLUMN IF NOT EXISTS estado_civil TEXT;
ALTER TABLE empleados ADD COLUMN IF NOT EXISTS turno TEXT;

-- 3) Datos bancarios completos (CBU ya existía)
ALTER TABLE empleados ADD COLUMN IF NOT EXISTS banco TEXT;
ALTER TABLE empleados ADD COLUMN IF NOT EXISTS alias_cbu TEXT;

-- 4) Domicilio desglosado (para poder generar la DDJJ de domicilio como documento)
ALTER TABLE empleados ADD COLUMN IF NOT EXISTS dom_calle TEXT;
ALTER TABLE empleados ADD COLUMN IF NOT EXISTS dom_numero TEXT;
ALTER TABLE empleados ADD COLUMN IF NOT EXISTS dom_piso TEXT;
ALTER TABLE empleados ADD COLUMN IF NOT EXISTS dom_depto TEXT;
ALTER TABLE empleados ADD COLUMN IF NOT EXISTS dom_barrio TEXT;
ALTER TABLE empleados ADD COLUMN IF NOT EXISTS dom_localidad TEXT;
ALTER TABLE empleados ADD COLUMN IF NOT EXISTS dom_provincia TEXT;
ALTER TABLE empleados ADD COLUMN IF NOT EXISTS dom_codigo_postal TEXT;

-- 5) Familiares — tabla aparte (0 a N por empleado)
CREATE TABLE empleados_familiares (
    id SERIAL PRIMARY KEY,
    id_empleado INTEGER NOT NULL REFERENCES empleados(id) ON DELETE CASCADE,
    vinculo TEXT NOT NULL,        -- CONYUGE, CONVIVIENTE, PADRE, MADRE
    nombre_completo TEXT NOT NULL
);
