# MANUAL — CBC Sistema Contable

**Cómo se administra este documento:**
- Vive como archivo en GitHub, repo `cbcapi`, junto a `main.py`. Se edita ahí mismo (Ctrl+F, editar, commit) — igual que ya hacés con el código.
- Al empezar una sesión nueva con Claude: bajar este archivo de GitHub y subirlo antes de pedir cualquier cosa.
- Cuando algo cambia: se lo pedís a Claude ("actualizame el manual con esto") y te da el bloque de texto para pegar, o lo editás vos mismo directo.
- Estructura: **Parte 1 (arquitectura)** cambia poco, se toca solo cuando se agrega/rediseña algo grande. **Parte 2 (pendientes)** se actualiza seguido, es una lista viva.

---

# PARTE 1 — ARQUITECTURA Y CÓMO FUNCIONA CADA COSA

## 1. Qué es esto

Sistema contable y de sueldos hecho a medida para clientes gastronómicos (restaurantes), bajo convenios colectivos como UTHGRA. Reemplaza un sistema viejo en Excel/VBA usado 20 años por 80+ clientes. Rediseño desde cero, no un port directo.

**Dueño del proyecto:** Emi, contador con ~20 años de experiencia, no programador — trabaja pegando código en el editor de GitHub.
**Colaborador técnico:** Tomy — construye y mantiene **CircuitoF.js** y **CargaAutomatica.js** de forma independiente. Claude no debe tocar esos dos archivos salvo pedido explícito.

## 2. Arquitectura técnica

| Capa | Tecnología | Dónde vive |
|---|---|---|
| Frontend | React | repo `cbcfront`, Vercel (`cbcfront.vercel.app`) |
| Backend | FastAPI (Python) | repo `cbcapi`, Render (`cbcapi.onrender.com`) |
| Base de datos | PostgreSQL | Neon |

- `main.py`: se edita pegando directo en GitHub (Ctrl+F, buscar/reemplazar). No se descarga completo salvo que sea muy grande.
- Archivos `.js`/`.jsx` del frontend: se reemplazan completos.
- SQL: se corre a mano en la consola de Neon.
- **Para bajar TODO un repo de una vez:** botón verde "Code" → "Download ZIP" en la página principal del repo — no hace falta abrir archivo por archivo.
- Render no siempre redeploya solo — chequear que el commit coincida con el deploy activo.
- Vercel sí redeploya solo, pero el navegador cachea fuerte — ante "esto no cambió", probar Ctrl+Shift+R o incógnito antes de asumir que hay un bug.

**Formato de números en todo el sistema: separador de miles + 1 decimal, siempre**, incluso en campos editables (patrón "mostrar formateado, click para editar" — un `<input type="number">` no puede mostrar separador de miles mientras está enfocado, es límite de HTML).

## 3. Mapa completo de archivos del frontend (repo `cbcfront/src`)

| Archivo | Qué es | Escribe en (tablas/endpoints) |
|---|---|---|
| `App.js` | Layout general, navegación entre pantallas, bloqueo de pantallas si falta configuración | — |
| `Inicio.js` | Pantalla de bienvenida | — |
| `Configuracion.jsx` | Datos de la empresa, convenio, fecha de corte, checklist de configuración | `configuracion` |
| `RRHH.jsx` | Empleados, Escala Convenio, Sueldos por Categoría, Liquidaciones, Conceptos de Liquidación (ver Parte 1.5) | `empleados`, `cat_puestos*`, `escala_salarial*`, `conceptos_liquidacion`, `liquidaciones` |
| `Balance.js` | Cuadro de Resultados + Estado de Situación Patrimonial + carga de Saldos Iniciales + Cheques de Apertura | `saldos_iniciales` ✅ (con asientos), `cheques_apertura` (sin asientos todavía) |
| `Titulares.js` | Alta/edición de Proveedores y clientes (Titulares) | `titulares` (catálogo, no movimiento) |
| `PlanCuentas.js` | Asignar un "Fondo" a cada cuenta del Plan de Cuentas, para agilizar la carga diaria | `plan_cuentas` (metadata, no movimiento) |
| `Fondos.js` | Alta/edición de Fondos (cuentas de caja/banco) | `fondos` (catálogo, no movimiento) |
| `CargarMovimiento.js` | Pantalla real: **"Cargar Comprobante"** (`CargarComprobante`) — factura de un proveedor/titular | `operaciones` ❌ (sin asientos) |
| `CuentaCorriente.js` | Ver deuda por Titular, y **registrar el pago** de una factura | `operaciones`, `registrar_pago`, `registrar_pago_echeq` ❌ (sin asientos — el más delicado, doble efecto) |
| `GestionSaldos.js` | Vista de consulta/filtro de `operaciones` (impagas, por titular) | solo lectura |
| `Tesoreria.js` | Movimientos de caja/banco, transferencias entre fondos, confirmar vencimientos proyectados | `cashflow` ✅ (con asientos, movimiento manual y transferencia), `vencimientos/confirmar` ❌ (sin asientos) |
| `Admin.js` | Panel para gestionar el Plan de Cuentas directamente (alta/edición de cuentas, niveles) | `plan_cuentas`, `fondos_admin` (metadata estructural) |
| `CircuitoF.js` | **De Tomy — no tocar sin que él lo pida.** No documentado en detalle acá. | `circuito_f/*` |
| `CargaAutomatica.js` | **De Tomy — no tocar sin que él lo pida.** Parece lectura automática de facturas (con IA) → `operaciones`. | `facturas/*` |

## 4. Niveles del Plan de Cuentas (niv1 a niv5)

Confirmado directo en `Admin.js`:
- **Nivel 1** (`niv1`): la clasificación más gruesa de toda cuenta — solo 3 valores posibles en todo el sistema: **"Resultados"**, **"Patrimonial"**, **"Movimiento"**.
- **Nivel 2** (`niv2`): dentro de Resultados → Ventas, Deducciones Variables, Gastos. Dentro de Patrimonial → Activo, Pasivo, Patrimonio. Dentro de Movimiento → Mov. Fondos.
- **Nivel 3, 4**: subdivisiones cada vez más finas (ej. dentro de Gastos: Personal, Alquiler, Servicios...).
- **Nivel 5**: cuentas puntuales del Plan de Cuentas, la hoja final del árbol.

## 5. RRHH y Liquidaciones — reglas clave

- Jornada completa = **192 horas mensuales**. El sistema prorratea linealmente: básico, adicionales, todo escala con `horas/192`.
- **Obra Social** (uno de los 5 componentes de Aportes) es la excepción: se paga completa sin importar la jornada — se calcula escalando el Bruto entero por la proporción inversa de la jornada.
- **"Sueldo J. Completa"** es el campo editable (jornada completa, sin prorratear). **"Sueldo"** es de solo lectura, calculado = J.Completa × Horas ÷ 192.
- El "Sueldo Formal" declarado en el modal de alta de empleado es **solo una referencia** — Liquidaciones no lo usa para calcular. Prioridad real: 1° historial propio del empleado (si ya se liquidó ese mes), 2° Escala Convenio del mes que se está liquidando (con su propio arrastre de mes anterior).
- **Pendiente sin resolver:** algunas referencias (el aviso de "¿estás seguro?" del mínimo) comparan contra la Escala de **hoy**, no contra la del **mes que se está liquidando**.
- Conceptos de Liquidación (`conceptos_liquidacion`, campo `calculo`): `MANUAL` (se tipea a mano), `AUTOMATICO` (% del básico), `AUTOMATICO_BRUTO` (% del Bruto, segunda pasada — los 5 Aportes). Cualquier concepto tiene `activo` (se prende/apaga sin tocar código, desde la pantalla "Conceptos de Liquidación").
- Suma No Remunerativa: viene de Escala Convenio, se prorratea por jornada, se suma al Neto **después** de Aportes (no infla el Total Bruto ni la base de Aportes).
- **Borrador vs Liquidación real** (`liquidaciones.es_borrador`): "Guardar Cambios" = `true` (no bloquea nada). "Liquidar" = `false` (cierra el mes de verdad, bloquea Escala Convenio/Sueldos por Categoría para ese mes). Una vez `false`, no puede volver a `true` por accidente.
- **Liquidaciones hoy NO toca Balance en absoluto.** No devenga nada en Resultados, no genera "Sueldos a Pagar" en Pasivo. Es un pendiente de diseño de fondo (ver Parte 2).
- Feriados y Ausencias son campos independientes por circuito (Real vs Formal, no comparten número).
- El sistema recuerda el último Mes/Año visto en Liquidaciones (localStorage) — no vuelve a "hoy" cada vez.
- Hay un borrador local (localStorage, separado de `es_borrador` de la base) para no perder lo tipeado si se cambia de pantalla sin guardar.

## 6. Balance — cómo está armado

- **Dos componentes de React separados** dentro de `Balance.js`: `EstadoResultados` (Cuadro de Resultados) y `BloquePatrimonial` (Activo/Pasivo/PN). Cada uno con su propio estado de expandir/colapsar — un cambio de comportamiento hay que aplicarlo en los dos lugares.
- Framework "Causa vs Efecto" (terminología propia de Emi): PN-Causa = lo que generó el patrimonio con el tiempo; PN-Efecto = Activo menos Pasivo, la foto actual.
- **Fondos** (caja, bancos): saldo inicial + movimientos de `cashflow` — mecanismo ya correcto de punta a punta.
- **Pasivo por facturas** (Proveedores/Titulares): viene de `operaciones` impagas, separadas por fecha antes/después del corte.
- **`saldos_genericos`** (agregado en esta sesión): cualquier saldo inicial que NO sea de Fondos se suma tanto al Activo como al Pasivo según corresponda — resuelve el caso de deudas de apertura que no son factura de un proveedor puntual (ej. sueldos a pagar acumulados), y cuentas de Activo que tampoco son caja/banco (Bienes de Uso, Créditos Fiscales).
- Los nombres de cuenta patrimonial para Pasivo/Activo son listas de texto exactas, hardcodeadas en `Balance.js` (`pasivoProveedores`, `activoOtros`, etc.) — un nombre que no calce carácter por carácter no se toma.

## 7. El mecanismo de `asientos` (agregado en esta sesión)

**Por qué existe:** antes de esto, cada acción que tocaba el Balance escribía directo en su tabla (`cashflow`, `operaciones`, `saldos_iniciales`) sin ningún ID que las conectara ni forma de saber qué las generó — así que no había manera de anular algo con confianza si fue un error.

**Cómo funciona:** tabla `asientos` (id, tipo_origen, descripción, `anulado` boolean). Cada acción que toca el Balance primero crea un asiento, y la fila que genera en su tabla correspondiente (`saldos_iniciales`/`cashflow`/`operaciones`) queda con `id_asiento` apuntando a él. Anular = marcar el asiento (`PUT /asientos/{id}/anular`) — no se borra nada, y todas las consultas de Balance ya ignoran lo que tenga un asiento anulado.

**Ya conectado:** Saldos Iniciales (con botón "✕" para anular directo desde Balance), Movimiento manual de Tesorería, Transferencia entre fondos.

**Todavía NO conectado (ver Parte 2, es la prioridad #1):** Comprobantes (`operaciones`), Registrar Pago (el más delicado — mueve dos cosas a la vez), Cheques de Apertura, Vencimientos/confirmar.

---

# PARTE 2 — PENDIENTES (lista viva, actualizar seguido)

## Prioridad 1 — Terminar de conectar `asientos`
- [ ] **Comprobantes** (`CargarMovimiento.js` → `operaciones`): conectar creación al mecanismo de asientos.
- [ ] **Registrar Pago** (`CuentaCorriente.js` → `registrar_pago` / `registrar_pago_echeq`): el más delicado — un pago probablemente marca la factura como pagada Y mueve `cashflow` a la vez. Diseñar bien: ¿un solo asiento para las dos partes, o dos asientos relacionados? Pensar con calma antes de escribir código.
- [ ] **Cheques de Apertura** (`cheques_apertura`): conectar a asientos.
- [ ] **Vencimientos/confirmar** (`Tesoreria.js`): evaluar si necesita asiento propio o si hereda el del movimiento original.

## Prioridad 2 — Liquidaciones ↔ Balance (nunca se construyó)
- [ ] Diseñar qué pasa contablemente cuando se aprieta "Liquidar": ¿devenga en Resultados? ¿genera "Sueldos a Pagar" en Pasivo? ¿Con qué asiento?
- [ ] Módulo "Pagar Sueldos" (conectar el pago real de la liquidación a Tesorería).

## Otros pendientes conocidos, sin resolver
- [ ] Referencias de "hoy" vs "mes que se está liquidando" en algunos avisos de mínimo de Liquidaciones.
- [ ] Corrección de un mes ya liquidado (`es_borrador = false`) — sin diseñar.
- [ ] Unificar el mecanismo de expandir/colapsar entre `EstadoResultados` y `BloquePatrimonial` (se evaluó, no se hizo — por ahora los dos arrancan desplegados por default, alcanza).
- [ ] Impresión de recibos de sueldo (ícono placeholder sin funcionalidad en Liquidaciones).
- [ ] AFIP/ARCA — sin definir método (RPA vs certificado WSAA).
- [ ] Autenticación / multi-tenant — no implementado.

## Preguntas abiertas para Emi (antes de diseñar lo de arriba)
- [ ] ¿Qué son exactamente `CircuitoF.js` y `CargaAutomatica.js`? (De Tomy — confirmar antes de que Claude los toque alguna vez.)
