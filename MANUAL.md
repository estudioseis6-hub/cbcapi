# MANUAL — CBC Sistema Contable
**Cómo se administra este documento:** vive en GitHub, repo `cbcapi`, en la raíz (al lado de `main.py`). Se edita ahí mismo. Al empezar una sesión nueva con Claude, se sube este archivo antes de pedir cualquier cosa.

---

# PARTE 1 — GUÍA FUNCIONAL (paso a paso, qué hace cada cosa)

## Recorrido general del sistema
El sistema arranca en la pantalla **Inicio**, que tiene los links a todo lo demás. Lo primero que
hay que hacer, siempre, es ir a **Configuración** y completar lo que el sistema pida ahí (datos de
la empresa, convenio laboral, fecha de corte patrimonial, etc.) — varias pantallas no dejan
avanzar hasta que esto esté completo.

Después de Configuración, el orden natural de uso es:
1. **RRHH** — cargar empleados y liquidar sueldos.
2. **Tesorería** — el día a día de ingresos y egresos de plata.
3. **Cuenta Corriente** — la deuda con Proveedores/Titulares, y el pago de facturas.
4. **Balance** — la foto contable completa: Resultados y Situación Patrimonial, más la carga inicial (Saldos Iniciales, Cheques de Apertura).
5. **Dashboard** (nuevo, 19-8-2026) — panorama visual rápido, arranca chico.

---

## TESORERÍA — cómo funciona, paso a paso
En Tesorería se cargan y se ven todos los ingresos y egresos de plata, organizados por **Fondo**
(cada caja, cada cuenta bancaria es un Fondo separado). Todo lo que cargás acá modifica el saldo
del Fondo que elegiste — nunca "la plata en general", siempre un fondo puntual.

Cada movimiento que ves en la lista tiene un **Estado**:
- **Histórico**: ya pasó, está confirmado.
- **Hoy**: pasa hoy.
- **Proyectado**: todavía no pasó, es una fecha futura.

Y dentro de "Proyectado", hay 3 **tipos distintos** de registro — esto es importante porque cada
uno se maneja diferente:

### 1. Movimiento Directo
Lo cargás vos a mano, sin que venga de ninguna factura. Puede ser algo que ya pasó (Histórico/Hoy)
o algo que planeás que pase en el futuro (Proyectado).
- **Qué le hace al Balance:** apenas queda **confirmado** (o si lo cargaste como ya ocurrido),
  suma o resta directo al saldo del Fondo elegido — y por lo tanto al Activo (Caja/Banco) del Balance.
- **Se puede eliminar directo** desde Tesorería. Si eliminás un movimiento directo, listo, desaparece.
- **Se puede reprogramar:** sí, cambiarle la fecha con "Reprogramar".
- **Ojo con esto:** si ese movimiento directo en realidad había sido un pago que cancelaba facturas
  en Cuenta Corriente, al eliminarlo esas facturas **vuelven a estado IMPAGO** — es decir, revive la deuda.

### 2. Obligación Proyectada
Esta NO la cargás en Tesorería — aparece sola porque viene de una **factura cargada en Cuenta
Corriente**. Es la proyección de "esto vamos a tener que pagar tal fecha".
- **Qué le hace al Balance:** mientras está proyectada, no movió nada todavía — es solo una
  advertencia de lo que se viene. El Pasivo real ya lo generó la factura en sí (en Cuenta Corriente),
  no esta proyección.
- **NO se puede eliminar desde Tesorería.** Si querés sacarla, tenés que ir a Cuenta Corriente y
  eliminar la factura de origen ahí.
- **Sí se puede reprogramar** la fecha desde Tesorería (por ejemplo, si sabés que vas a pagar más tarde).

### 3. Estimación Proyectada
Una proyección manual tuya de "esto va a pasar", pero sin que exista todavía una factura real
detrás — un cálculo o expectativa que cargaste a mano.
- **Qué le hace al Balance:** nada todavía, es solo informativa hasta que se confirme.
- **Se puede eliminar y reprogramar libremente** — es tuya, no depende de nada más.

### Confirmar un Proyectado
Cualquiera de los tres, cuando llega el momento, se puede **Confirmar** (botón "✓ Confirmar") —
eso lo pasa de "Proyectado" a real, y ahí sí impacta el saldo del Fondo.

### Transferencia entre Fondos
Mover plata de un Fondo a otro (ej. de Caja a Banco). Genera **dos movimientos ligados** (uno de
egreso en el fondo de origen, uno de ingreso en el de destino) — si eliminás uno, **se eliminan los
dos juntos**, para que nunca quede una transferencia con solo una mitad registrada.

---

## CUENTA CORRIENTE — cómo funciona, paso a paso
Acá vive la deuda con Proveedores y otros Titulares — y es donde se registra el pago. Hay una
distinción importante que separa todo el circuito en dos caminos, según el Titular:
- **Titular con "genera cuenta corriente" activado** (proveedores habituales, con seguimiento de
  deuda en el tiempo): la factura se carga **acá, en Cuenta Corriente**, con percepciones
  impositivas (IVA, IIBB, otras) si corresponde.
- **Titular SIN "genera cuenta corriente"** (algo puntual, un gasto suelto): la factura se carga
  desde **"Cargar Comprobante"** (pantalla aparte), más simple, sin percepciones. Si se intenta
  cargar ahí una factura de un titular que sí maneja cuenta corriente, el sistema frena y manda para acá.

### Tipos de registro en Cuenta Corriente

**1. Factura (Comprobante)** — se carga con Titular, Tipo de Comprobante, Número, Importe, y las
percepciones si corresponde.
- **Qué le hace al Balance:** genera una deuda — el Pasivo del Titular sube. Queda en estado **IMPAGO**.
- No mueve ninguna Caja/Banco todavía — es solo el reconocimiento de que se debe.

**1.b. Nota de Crédito / Ajuste — el mismo comprobante, la deuda va al revés (nuevo, 19-8-2026)**
Cualquier tipo de comprobante puede marcarse en Admin → Tipos de Comprobante con dos casilleros
independientes:
- **"Es Nota de Crédito"**: invierte el asiento entero — baja la deuda y baja el gasto, en vez de
  subirlos. Se usa para Notas de Crédito formales (proveedor te devuelve algo).
- **"Admite montos negativos"**: solo el tipo **"Ajuste"** (creado hoy, id 1001) lo tiene tildado.
  Con este tipo, cargás **cualquier importe** (subtotal, "Sin Factura", lo que sea) en **positivo
  para subir** la deuda del Titular, o en **negativo para bajarla** — sin necesitar un segundo tipo
  de comprobante separado. Para cualquier OTRO tipo (Factura A, S/F, etc.), un monto negativo se
  **rechaza con un error claro** ("Este tipo de comprobante no admite montos negativos... Usá el
  tipo 'Ajuste' para eso") — antes de esto, un negativo colado por error (tipeo, o un "-" pegado de
  Excel) podía romper el asiento en silencio.
- **"S/F" (Sin Factura, tipo 995) queda reservado** para compras/ventas informales reales — no se
  usa más para ajustes de saldo (eso es trabajo de "Ajuste" ahora).
- **Gastos exentos que no son compras** (ej. Cargas Sociales, algo sin IVA): usar un tipo de
  comprobante nuevo tipo "Exento" (id 1000, ya existía), sin "Exige IVA" tildado.

**2. Registrar Pago** — se eligen una o varias facturas IMPAGAS de un Titular y se marcan como
pagadas, junto con el medio de pago:
- **TD (Transferencia Directa):** el pago sale ya, de un Fondo elegido (Caja o Banco).
  - **Qué le hace al Balance:** dos cosas a la vez — **resta** de la Caja/Banco elegido (Activo) y
    **cancela** la deuda de esas facturas puntuales (baja el Pasivo). Las facturas pasan de IMPAGO a **PAGO**.
- **ECHEQ:** el pago se hace con un cheque electrónico, con fecha de vencimiento futura.
  - **Qué le hace al Balance:** la deuda con el Proveedor se cancela (pasa a PAGO) pero se
    **reemplaza** por una deuda de "Valores Emitidos — Cheques Pendientes" hasta la fecha de
    vencimiento del cheque, donde recién ahí sale la plata de verdad del Fondo.
- **Pago Parcial:** si seleccionás UNA sola factura, podés pagar menos del total — el saldo restante
  queda proyectado en Tesorería, listo para completarse con otro pago después. Funciona tanto para
  TD como para ECheq. Cada aplicación queda en la tabla `aplicaciones_pago` (factura + pago + cuánto cubrió).
- **Ojo:** las operaciones marcadas como "informales" (sin factura) solo se pueden pagar en
  efectivo, no con ECheq.

**3. Eliminar un Titular (nuevo, 19-8-2026)** — desde la pantalla propia de Titulares, botón
"Eliminar" en cada fila, con confirmación. El sistema **bloquea el borrado** si ese Titular tiene
comprobantes en Cuenta Corriente o movimientos en Tesorería asociados — para no romper el
historial. Solo se puede eliminar un Titular que nunca se usó.

### "Saldo a fecha" en Saldos Pendientes (nuevo, 19-8-2026)
Además del filtro por Estado, hay un campo **"Saldo a fecha"** (vacío = hoy) — si le ponés una
fecha, te muestra el saldo pendiente **tal como estaba ese día**: solo cuenta facturas que ya
existían y pagos que ya se habían aplicado hasta esa fecha, ignorando lo posterior. Sirve para
comparar ese número directo contra el Balance de un mes puntual.

### Si un pago se elimina desde Tesorería
Si en Tesorería se elimina un movimiento que había sido un pago TD, las facturas que ese pago
había cancelado **vuelven a estado IMPAGO** — la deuda revive. Por eso, para deshacer un pago, es
más prolijo hacerlo desde Cuenta Corriente si se puede, para no perder de vista qué facturas se
ven afectadas.

---

## RRHH y LIQUIDACIONES — cómo funciona, paso a paso
### Escala Convenio y Sueldos por Categoría
Acá se cargan los mínimos y estándares salariales, mes a mes, por Categoría (convenio) o Posición
(real). Si un mes no tiene carga propia, el sistema **arrastra automáticamente** el último mes
anterior que sí tenga algo cargado — no hace falta cargar todos los meses si no cambió nada.

### Alta de Empleado
El "Sueldo Formal" y "Sueldo Real" que se cargan acá son **solo de referencia** — no son lo que
Liquidaciones termina usando para calcular (ver abajo). Jornada se declara en horas mensuales
(192 = completa, 96 = media jornada).

### Liquidaciones — el corazón de RRHH
Por cada empleado, cada mes, hay dos "circuitos" (Formal y Real) que se calculan por separado.
- **De dónde sale el Sueldo Formal:** 1° si ya se liquidó ese empleado antes, se respeta lo que
  ya quedó guardado ese mes. 2° si es la primera vez, va directo a la Escala Convenio **del mes
  que se está liquidando** (no la de "hoy").
- **Jornada:** todo se prorratea según las horas declaradas (básico, adicionales) — **excepto la
  Obra Social** (uno de los Aportes), que por acuerdo paritario se paga completa sin importar la
  jornada.
- **Presentismo:** se anula automáticamente si el empleado tuvo alguna ausencia (justificada o no)
  ese mes.
- **Aportes:** se desglosan en 5 líneas separadas (Jubilación, Ley 19.032, Obra Social, Sindicato,
  Seguro de Vida y Sepelio), cada uno auditable por separado, no solo un total.
- **Guardar Cambios vs Liquidar:** "Guardar Cambios" guarda el trabajo en progreso, sin
  consecuencias — se puede seguir editando después. "Liquidar" (con confirmación) cierra el mes
  de verdad — a partir de ahí, ya no se puede tocar la Escala Convenio de ese mes.
- **Importante, todavía no resuelto:** apretar "Liquidar" hoy **no genera ningún efecto en
  Balance** — no devenga sueldos en Resultados, no crea "Sueldos a Pagar" en el Pasivo. Es un
  pendiente de diseño grande (ver Parte 3).

---

## BALANCE — cómo funciona, paso a paso
Balance tiene dos partes que se ven juntas pero son independientes: el **Cuadro de Resultados**
(Ventas, Gastos, Ganancia/Pérdida del período) y el **Estado de Situación Patrimonial** (Activo,
Pasivo, Patrimonio Neto). Además, acá vive la carga de **Saldos Iniciales** y **Cheques de
Apertura** — la foto de "cómo empezaba todo" el día del corte.

Balance ahora tiene varias pestañas (arriba, junto a "Balance"):

### Cheques de Apertura / Cheques Pendientes
Como ya estaba — cheques emitidos antes del corte (Apertura) o que salieron de Tesorería/Cuenta
Corriente y todavía no se debitaron (Pendientes).

### Mayor por Fondo (traído de un archivo aparte, 19-8-2026)
Planilla de Ingresos y Egresos agrupada por Cuenta contable, repartida en 4 columnas de Fondo
(EFVO $, Cuentas $, EFVO USD, Cuentas USD) — vivía en un archivo separado (`MayorPorFondo.js`,
también en el menú principal), ahora está también acá para tener todo junto.

### Mayor por Cuenta (nuevo, 19-8-2026) — "asiento sintetizado"
Buscás una cuenta puntual (con autocompletado), y te arma el **asiento sintetizado**: todas las
líneas de todos los asientos que tocaron esa cuenta, agrupadas por la cuenta del otro lado (Debe
o Haber según corresponda) — como si fuera un único asiento resumen de toda la historia de esa
cuenta. Arriba, un cartel confirma que Total Debe = Total Haber (si no coincide, hay algo mal
conectado en esa cuenta puntual).
- **Limitación importante, para no confundirse:** solo muestra movimientos donde una cuenta de
  **Resultados** (un gasto) participó directamente. Un **pago** (Patrimonial contra Patrimonial —
  ej. Efectivo cancelando una deuda vieja) **no aparece acá**, porque en ese asiento no participa
  ninguna cuenta de Resultados. No es un error, es el alcance de la herramienta. Debajo de cada
  columna hay un número chico "hoy: $X" — el saldo **actual real** de esa cuenta patrimonial
  (incluye pagos posteriores), aclarando que es el saldo de la cuenta en general, no exclusivo de
  esa fila (varios gastos distintos pueden compartir la misma cuenta patrimonial).
- Tiene un buscador de rango de fechas, con persistencia (se acuerda de lo último elegido).

### Saldos Iniciales
Cada cuenta del Balance (Activo o Pasivo) tiene una celda donde se carga su valor de apertura con
un click — un campo que dice "Cargue aquí" si está vacío.
- **Para qué sirve:** declarar cuánto había (o se debía) de esa cuenta el día del corte, antes de
  que el sistema empezara a registrar movimientos día a día.
- **Qué le hace al Balance:** ese valor se mantiene igual mes a mes (no tiene movimientos propios)
  hasta que alguien lo edite o lo anule — si se carga una deuda de apertura, va a seguir
  apareciendo en Junio, Julio, etc., no solo en el mes del corte.
- **Para anularlo:** click en la "✕" al lado del valor. No se borra el registro — queda anotado
  que existió y se anuló, con un ID propio (ver "Asientos" abajo), así que si fue un error se puede
  rastrear y revertir con confianza.
- **Cuentas de Fondos (Caja/Banco):** estas sí tienen su propio movimiento (lo que entra y sale
  por Tesorería) además del saldo de apertura — el saldo inicial es solo el punto de partida.

### Cheques de Apertura
Cheques que la empresa ya había emitido antes del corte, y que todavía no se debitaron del banco.
- **Estado Pendiente:** todavía no salió la plata — cuenta como deuda ("Valores Emitidos —
  Cheques Pendientes") en el Pasivo.
- **Estado Debitado:** ya salió la plata del banco — deja de contar como deuda pendiente.

### El mecanismo de "Asiento"
Cada vez que se carga algo que afecta el Balance, el sistema crea por adentro un **Asiento** — un
recibo con su propio número, que dice qué tipo de carga fue y cuándo se hizo. Si después hace
falta deshacer esa carga porque fue un error, el sistema anula el Asiento completo (no borra nada
a lo bruto) — queda constancia de que existió y se dio de baja, en vez de desaparecer sin dejar
rastro.

---

## DASHBOARD — nuevo, 19-8-2026, primer ensayo
Pantalla nueva, fondo oscuro (misma paleta que Balance: #0D1B2A / #132436 / #1B263B), pensada
para arrancar chica e ir creciendo. Por ahora tiene:
- 3 tarjetas: Ventas del mes, Gastos del mes, Resultado neto.
- Un gráfico de barras horizontal (hecho con `div`s simples, **sin ninguna librería externa de
  gráficos** — a propósito, para no arriesgar que el build falle si esa librería no está
  instalada en el proyecto real) — cada rubro del Cuadro de Resultados, verde apagado los
  ingresos, terracota apagado los gastos.
- Selector Mes/Rango, mismo patrón que Balance y Mayor por Fondo, con persistencia.
- Fuente de datos: mismo endpoint que usa Balance (`/balance_unificado`).

---

# PARTE 2 — REFERENCIA TÉCNICA (arquitectura, para Claude y para ir aprendiendo)

## Arquitectura
| Capa | Tecnología | Dónde vive |
|---|---|---|
| Frontend | React | repo `cbcfront`, Vercel |
| Backend | FastAPI (Python) | repo `cbcapi`, Render |
| Base de datos | PostgreSQL | Neon |

- `main.py` se edita pegando directo en GitHub. Archivos `.js`/`.jsx` se reemplazan completos. SQL se corre a mano en Neon.
- Para bajar TODO un repo de una vez: botón verde "Code" → "Download ZIP".
- Render no siempre redeploya solo. Vercel sí, pero el navegador cachea fuerte (Ctrl+Shift+R antes de asumir un bug).
- Números: separador de miles + 1 decimal, siempre, en todo el sistema.
- **Regla nueva de hoy:** ninguna pantalla nueva debería sumar una librería npm que no se confirmó
  que ya esté instalada en el proyecto real — un `import` de algo no instalado rompe el build
  entero en Vercel, y el síntoma es confuso (la pantalla nueva no aparece, todo lo demás sigue
  andando con la versión vieja cacheada). Preferir siempre `div`s/CSS puro para gráficos simples,
  salvo que se confirme antes que la librería ya está en `package.json`.

## Mapa de archivos del frontend (`cbcfront/src`)
| Archivo | Qué es |
|---|---|
| `App.js` | Layout, navegación, bloqueo de pantallas si falta configuración |
| `Inicio.js` | Pantalla de bienvenida |
| `Dashboard.js` | **Nuevo (19-8-2026).** Panorama visual, fondo oscuro, arranca con Cuadro de Resultados |
| `Configuracion.jsx` | Datos de empresa, convenio, corte, checklist |
| `RRHH.jsx` | Empleados, Escala Convenio, Sueldos por Categoría, Liquidaciones, Conceptos de Liquidación |
| `Balance.js` | Cuadro de Resultados + Situación Patrimonial + Saldos Iniciales + Cheques de Apertura + Mayor por Fondo + Mayor por Cuenta |
| `Titulares.jsx` | Alta/edición/eliminación de Proveedores y clientes — pantalla completa, única fuente (ya no hay una copia reducida en ningún otro lado) |
| `PlanCuentas.js` | Asignar un Fondo a cada cuenta del Plan de Cuentas |
| `Fondos.js` | Alta/edición de Fondos (caja/banco) |
| `CargarMovimiento.js` | "Cargar Comprobante" — factura simple, para titulares sin cuenta corriente |
| `CuentaCorriente.js` | Deuda por Titular, carga de facturas con percepciones, Registrar Pago (TD/ECheq/Parcial), Saldo a fecha |
| `GestionSaldos.js` | Vista de consulta de operaciones (solo lectura) |
| `Tesoreria.js` | Movimientos de caja/banco, transferencias, confirmar vencimientos |
| `Admin.js` | Gestión del Plan de Cuentas (con filtros por los 6 niveles), Tipos de Comprobante (con Exige IVA / Es Nota de Crédito / Admite Negativos), Cheques Pendientes, Manual. Ya NO tiene pestaña de Titulares (era una copia redundante e inferior a la pantalla propia). |
| `CargaMasiva.js` | Carga masiva de facturas/movimientos pegados desde Excel — `normalizarImporte` corregida (ver Parte 2, bugs de hoy) |
| `MayorPorFondo.js` | Archivo original (ahora también incluido dentro de `Balance.js`) |
| `CircuitoF.js` | **De Tomy — no tocar sin que él lo pida.** |
| `CargaAutomatica.js` | **De Tomy — no tocar sin que él lo pida.** Lectura automática de facturas. |

## Niveles del Plan de Cuentas
- **Nivel 1**: 3 valores en todo el sistema — "Resultados", "Patrimonial", "Movimiento".
- **Nivel 2**: dentro de Resultados → Ventas, Deducciones Variables, Gastos. Dentro de Patrimonial → Activo, Pasivo, Patrimonio. Dentro de Movimiento → Mov. Fondos.
- **Nivel 3, 4, 5**: subdivisiones cada vez más finas.
- **Nivel 6**: la cuenta puntual, la hoja final del árbol — coincide siempre con el campo `nombre` (confirmado por SQL, 197 de 201 cuentas exactas, las otras 4 eran inconsistencias de tipeo ya corregidas). No cumple ninguna función propia distinta del nombre — se mantiene por si algún día se usa para diferenciar de verdad.

## Admin → Plan de Cuentas: filtros por los 6 niveles (19-8-2026)
Fila de 6 desplegables (Nivel 1 a 6), en cascada — cada uno solo muestra las opciones que existen
dentro de lo ya elegido arriba. Ancho fijo (150px cada uno) con scroll horizontal si hace falta,
para que nunca se rompa el ancho general de la pantalla (ver bug de `minWidth: 0` en Parte 2 más
abajo).

## Detalles técnicos de Liquidaciones
- Jornada completa = 192 horas mensuales. Todo prorratea linealmente salvo Obra Social (excepción explicada en Parte 1).
- `conceptos_liquidacion.calculo`: `MANUAL` / `AUTOMATICO` (% del básico) / `AUTOMATICO_BRUTO` (% del Bruto, segunda pasada — los 5 Aportes). Campo `activo` prende/apaga sin tocar código.
- `liquidaciones.es_borrador`: `true` = "Guardar Cambios" (sin bloqueos). `false` = "Liquidar" (cierra el mes). No puede volver a `true` por accidente una vez `false`.
- Suma No Remunerativa: de Escala Convenio, prorrateada, se suma al Neto después de Aportes (no infla Bruto ni la base de Aportes).

## Detalles técnicos de Balance
- **Una sola fuente de verdad: `asiento_lineas`.** El Balance lee un único endpoint,
  `/balance_unificado?mes=X&anio=Y` (o `fecha_desde`/`fecha_hasta` para rangos largos), que suma
  `debe - haber` de `asiento_lineas` (uniendo con `asientos` para descartar los anulados),
  agrupado por `id_cuenta` (no por nombre de texto).
- Devuelve, por cada cuenta: `periodo` (movimiento solo de ese mes — Resultados) y `acumulado`
  (saldo de siempre hasta el fin de ese mes — Patrimonial).
- **`EstadoUnificado`** es el componente genérico que arma la tabla jerárquica, ordenando por los
  números reales de Nivel 2/3/4/5 (no alfabético, no hardcodeado).
- **Signo de PN Origen:** se muestran invertidas (`-1 * acumulado`) porque son cuentas "espejo".
- **PN Efecto = Activo + Pasivo. PN Causa = PN Origen (invertido) + Resultado Acumulado (invertido).**
- **"Diagnosticar diferencia"** (visible solo si la ecuación no cierra) corre 4 chequeos
  automáticos (asientos no balanceados, cuentas puente sin cerrar, cuentas huérfanas) — evita
  tener que correr SQL a mano cada vez.

## El mecanismo de `asientos` y `asiento_lineas`
- **`asientos`**: cabecera (id, tipo_origen, descripción, `fecha` real, `anulado`).
- **`asiento_lineas`**: el detalle real de débito/crédito (`cuenta_patrimonial` texto, `id_cuenta`
  numérico, `debe`, `haber`) — desde la migración a ID (6-8-2026) cada línea nueva guarda ambos.
- Anular = `PUT /asientos/{id}/anular`. Revertir todo = `PUT /asientos/{id}/revertir_todo` (ejecuta
  `reversion_acciones`, ver regla obligatoria en Parte 3).

## Tipos de Comprobante — 3 columnas de configuración (nuevo, 19-8-2026)
Tabla `tipos_comprobante`, gestionable 100% desde Admin, sin tocar código:
- **`exige_iva`** (bool): obligación fiscal real de discriminar IVA (Factura/ND/NC A, Tique
  Factura A). Si está tildado y el IVA queda en $0, la carga se bloquea con aviso.
- **`es_nota_credito`** (bool): invierte Debe/Haber del asiento entero (baja deuda y gasto).
- **`admite_negativos`** (bool): permite montos negativos en cualquier campo — el signo decide la
  dirección (XOR con `es_nota_credito`). Solo el tipo "Ajuste" (id 1001) lo tiene tildado hoy.
  Cualquier otro tipo con un negativo se bloquea con error claro en el backend
  (`_crear_comprobante`, `main.py`).

## Cuentas especiales por "código interno" (`_cuenta(cur, codigo)`)
Mecanismo para resolver cuentas fijas del sistema (Valores Emitidos, IVA Crédito Fiscal,
Percepciones, Saldo de Apertura, Resultado por Tenencia ME, Tarjetas Pend. Acreditación) por un
código interno estable (`plan_de_cuentas.codigo_interno`), nunca por nombre de texto ni ID fijo en
código — así renombrar la cuenta en Admin no rompe nada.
- **Si el código interno no está sembrado**, la función devuelve un texto placeholder
  (`[FALTA CONFIGURAR: CODIGO]`) en vez de romper — pero ese texto queda **sin `id_cuenta`
  asociado**, invisible para Balance, rompiendo la ecuación en silencio hasta que alguien lo nota.
  **Encontrado hoy (19-8-2026):** `PERCEPCION_IVA` y `PERCEPCION_IIBB` nunca habían sido sembradas
  — 19 líneas de asiento históricas quedaron con este placeholder. Se crearon 2 cuentas nuevas
  (`Crédito Fiscal — Percepciones de IVA/IIBB Sufridas`, clasificadas correctamente como **Activo**,
  no Pasivo como estaban las cuentas de "percepciones bancarias" viejas) con su `codigo_interno`
  correspondiente, y se corrigieron las 19 líneas rotas por SQL. **Antes de dar por sembrado
  cualquier código interno nuevo, confirmarlo con SQL** (`SELECT ... WHERE codigo_interno = 'X'`),
  no asumir.

## Bugs reales encontrados y corregidos hoy (19-8-2026) — para no repetirlos

### 1. `normalizarImporte` (CargaMasiva.js) no manejaba números de miles sin coma decimal
Un valor como `"968.269"` (novecientos sesenta y ocho mil, sin centavos, sin coma) se interpretaba
como `968.269` (novecientos sesenta y ocho **coma** dos sesenta y nueve) — mil veces menos. La
función solo convertía bien cuando había una coma presente. **Arreglada:** ahora también detecta
el patrón `\d{1,3}(\.\d{3})+` (punto de miles sin coma) y lo trata como tal. Un número real casi
nunca tiene 3+ dígitos decimales exactos sin coma, así que el patrón es seguro.

### 2. Backend no serializaba tipos de PostgreSQL al guardar `reversion_acciones`
En `registrar_pago_parcial`, cuando un pago parcial terminaba de cancelar la factura completa, se
guardaba la fila de `cashflow` (la proyección vieja) directo en `reversion_acciones` para poder
recrearla si algún día se revierte el pago — pero esa fila viene de la base con tipos Python que
`json.dumps()` no puede convertir solo (`date`, `Decimal`), rompiendo el guardado con un error real
de servidor. El frontend, al no chequear `r.ok` antes de leer la respuesta, mostraba "Error de
conexión" genérico, tapando la causa real. **Arreglado:** se normalizan los valores (`.isoformat()`
para fechas, `float()` para Decimal) antes de guardarlos.

### 3. Barrida de manejo de errores frontend (37 casos, en Admin.js/Balance.js/CuentaCorriente.js/Titulares.jsx)
Patrón repetido: leer `r.json()` sin chequear `r.ok` primero, o descartar `data.detail`/`data.error`
del backend y mostrar un mensaje genérico ("Error al guardar.", "Error de conexión.") que tapaba
la causa real. Corregido en los 37 casos encontrados — de acá en más, cualquier error real del
servidor se va a ver en pantalla tal cual, no un mensaje inútil. **Al escribir código nuevo:
siempre `if (!r.ok) { leer detail } else { leer data }`, nunca asumir que la respuesta es JSON
válido sin chequear el status primero.**

### 4. Modal atajo de Titulares (CuentaCorriente.js) era una copia reducida e incompleta
`ModalEditarTitularRapido` (un modal aparte, solo con Plazo e IVA) se abría desde los links
"Configurar ahora →" en Nueva Factura — pero le faltaban todas las cuentas adicionales (`cod1`-
`cod10`) y otros campos que sí tiene el modal real. **Arreglado:** se sacó el modal reducido, y
ahora esos links abren el `ModalTitular` real (importado de `Titulares.jsx`, el mismo que usa la
pantalla de Titulares) — una sola fuente de verdad para editar un Titular, en cualquier pantalla.

### 5. Fondo default para facturas formales sin respaldo final
Si un Titular no tenía Fondo propio Y la configuración general (`fondo_default_facturas`) tampoco
estaba cargada, la factura se creaba pero sin ningún Fondo — bloqueando 19 de 22 facturas en una
carga masiva real. El camino **informal** ya tenía un tercer nivel de respaldo ("agarrá cualquier
Efectivo activo"), el camino **formal** no. **Arreglado:** se agregó el mismo respaldo final
("cualquier Banco activo") al camino formal.

### 6. `sugerirCuentaPatrimonial` (Titulares.jsx) comparaba por nombre de texto
La sugerencia automática de cuenta patrimonial al elegir la clasificación de un Titular comparaba
contra nombres de cuenta escritos fijos en el código — si esa cuenta se renombraba, la sugerencia
quedaba rota en silencio (2 de 7 casos ya estaban rotos). **Arreglado:** ahora resuelve por **ID**
contra la lista de cuentas vigente — si la cuenta sugerida ya no existe, no sugiere nada roto,
queda vacío para elegir a mano. Además, se detectó que "Estado - Nacional - Impuestos y Tasas"
mezclaba IVA y Ganancias bajo una sola sugerencia (ambigua, un impuesto no tiene una sola cuenta
patrimonial) — se partió en dos clasificaciones separadas ("Estado - Nacional - IVA" / "Estado -
Nacional - Ganancias"), cada una con su propia cuenta.

## Bug de layout — tabla ancha rompía todo el ancho de la página (19-8-2026)
Una tabla con muchas columnas (Admin → Plan de Cuentas, filtros por Nivel 1-6) hacía que **toda la
pantalla** se estirara horizontalmente, en vez de quedar con scroll propio contenido. Causa: el
contenedor principal de `App.js` (`<div style={{flex:1, ...}}>`, dentro de un flex en columna) no
tenía `minWidth: 0` — por una regla de CSS poco conocida, un item de flex **no se achica** por
debajo del tamaño de su contenido aunque tenga `overflow: auto`, salvo que se le ponga
`minWidth: 0` explícito. **Arreglado en `App.js`** — cualquier tabla ancha futura, en cualquier
pantalla, ya no puede volver a romper el layout general por este motivo.

## `id_codigo` — chequeo de unicidad
Se encontró (19-8-2026) que dos cuentas ("IVA Crédito por Gastos Bancarios" e "Iva Debito Fiscal")
compartían el mismo `id_codigo` — un typo del Nivel 6 numérico al cargar una de las dos.
Corregido a mano. **No hay validación automática de unicidad todavía** — si se carga una cuenta
nueva con Nivel 6 repetido dentro del mismo grupo, no hay aviso. Pendiente considerar agregar esa
validación al backend.

---

# PARTE 3 — PENDIENTES (lista viva, actualizar seguido)

## Criterio de diseño: guardado explícito, no automático
Ningún campo editable debería guardar solo al perder el foco (`onBlur`) — regla: **solo Enter
guarda**; perder el foco sin Enter **cancela** (no guarda nada).

## MAPA — Registros patrimoniales vs no patrimoniales (base para saber qué necesita asiento)
**Principio:** un asiento se registra cuando cambia un Activo o un Pasivo.

**No patrimoniales (nunca generan asiento):** Titulares, Plan de Cuentas (alta), Fondos (alta),
Configuración, Empleados (alta), catálogos.

**Patrimoniales (tienen que generar asiento):**
| Pantalla de origen | Registro / Acción | ¿Genera asiento hoy? | ¿Eliminar revierte? |
|---|---|---|---|
| Balance | Saldo Inicial | ✅ | ✅ |
| Balance | Cheque de Apertura — crear | ✅ | ✅ |
| Cuenta Corriente | Carga de factura (Factura/NC/Ajuste) | ✅ | ✅ |
| Cuenta Corriente | Registrar Pago (TD/ECheq/Parcial) | ✅ | ✅ |
| Tesorería | Movimiento Manual / Transferencia | ✅ | ✅ |
| Tesorería | Confirmar débito (Cheque Apertura / ECheq) | ✅ | ✅ |
| Tesorería | Anular ECheq | ✅ | ✅ |
| R.R.H.H. | Liquidar sueldos | ❌ No conectado | — |
| R.R.H.H. | Pagar a un empleado | ❌ Ni existe | — |
| Circuito F (de Tomy) | Facturación automática | ⚠️ Sin revisar | ⚠️ Sin revisar |

## REGLA OBLIGATORIA — Nunca identificar una línea de asiento por nombre de cuenta
Siempre por `id_asiento` conocido, nunca `WHERE cuenta_patrimonial = X`. Reconfirmado hoy — el
mismo tipo de error (usar `WHERE id_asiento = X` sin filtrar además por línea puntual) rompió por
un momento el asiento 1671 al corregirlo — se arregló, pero sirve de recordatorio: **al corregir
una sola línea de un asiento con 2+ líneas, filtrar también por algo que identifique esa línea
específica (su propio `id`), no solo por `id_asiento`.**

## REGLA OBLIGATORIA — Todo asiento nuevo tiene que declarar cómo se revierte
Cualquier función que cree un asiento tiene que llamar a `_set_reversion(cur, id_asiento, [...])`
antes de terminar. **Si esas acciones incluyen guardar una fila completa de la base (para poder
recrearla), hay que normalizar sus tipos (fechas, Decimal) antes de guardarlas** — ver bug #2 de
hoy en Parte 2.

## Prioridad 1 — Terminar de conectar `asientos`/`asiento_lineas`
- [ ] Revisar TODOS los endpoints de eliminar por el mismo agujero que tenía `eliminar_operacion`
  (no anulaba el asiento vinculado — ya arreglado ahí, confirmar en el resto).
- [ ] Cheques de Apertura / Vencimientos-confirmar — revisar si falta algo.

## Prioridad 2 — Liquidaciones ↔ Balance (diseño ya cerrado, falta construir)
Sin cambios respecto a lo ya documentado — "Liquidar" tiene que devengar el gasto y generar
"Sueldos a Pagar", con saldo pendiente por empleado (mismo mecanismo que Titulares).

## Pendiente de diseño — IVA a Pagar / Ganancias a Pagar no se calculan solas (nuevo, 19-8-2026)
Se crearon las cuentas "IVA a Pagar" (id 230) y "Ganancias a Pagar" (id 232) como **contenedores
vacíos** — el sistema **no calcula sola** la suma neta (Débito Fiscal − Crédito Fiscal −
Retenciones − Percepciones, y su equivalente para Ganancias) ni la vuelca ahí automáticamente al
cargar comprobantes. Falta diseñar un **asiento de cierre periódico** (mensual, al momento de
liquidar el impuesto) que compense las cuentas de crédito/débito existentes y mueva el neto real a
estas dos cuentas nuevas. Hasta que ese asiento exista, van a quedar siempre en $0.

## Pendiente — Titulares con CUIT duplicado, sin CUIT real cargado (nuevo, 19-8-2026)
Se les borró el CUIT (para no bloquear futuras cargas) a 8 Titulares que compartían CUIT con
nombres distintos: Chirico / Nivel 7 Design / SBG SA, y MACARONS S.R.L. / EL HERALDO / Librum /
TURBOBLENDE / Macarons SRL. **Pendiente:** cargar el CUIT real de cada uno — hoy quedaron sin CUIT
(ninguno tiene uso todavía, así que no hay urgencia ni riesgo).

## Pendiente — Rubro "IVA a Pagar" en Nivel 5, revisar si necesita ajustes
Se confirmó que "IVA a Pagar" ya existe como agrupador de Nivel 5, con 4 cuentas puntuales
adentro (IVA Crédito Fiscal, Crédito por Gastos Bancarios, Débito Fiscal, Percepciones Bancarias
RG 2408) — el sistema de 5 niveles ya resuelve esta agrupación sin necesitar Nivel 6. No confundir
esta agrupación de Nivel 5 con las cuentas nuevas "IVA a Pagar"/"Ganancias a Pagar" (Nivel 6,
contenedores del neto — ver punto de arriba).

## Otros pendientes conocidos (heredados, sin cambios)
- [ ] `cod1`-`cod10` sirven para dos cosas distintas (Tesorería + Facturas) — revisar el día que
  aparezca un Titular que necesite las dos a la vez.
- [ ] N° Comprobante — separar Punto de Venta y Número en 2 campos con formato automático.
- [ ] Validación de rubro entre cuenta de gasto y cuenta patrimonial — no está modelado.
- [ ] Filtros de Tesorería — pasar a estilo checkbox (elegir/descartar), no solo "un valor por vez".
- [ ] Rehacer el anexo "Movimientos Agrupados" (Egresos/Ingresos por cuenta) — perdido en una
  sesión anterior.
- [ ] Carga masiva por Excel para arrancar un cliente nuevo — pendiente de diseño.
- [ ] Corrección de un mes ya liquidado (`es_borrador = false`) — sin diseñar.
- [ ] AFIP/ARCA — sin definir método.
- [ ] Autenticación / multi-tenant — no implementado (Admin sigue con clave simple hardcodeada).
- [ ] Pago parcial con cheque cuyo importe no coincide con la factura — sin tratamiento.
- [ ] Riesgo de doble carga si se aprieta Enter dos veces muy rápido.
- [ ] Circuito F (de Tomy) — sin revisar si genera asientos correctamente.
- [ ] Confirmar con Tomy el detalle de `CircuitoF.js`/`CargaAutomatica.js` antes de tocarlos.
- [ ] Reconsiderar si el mes de corte debería bloquear la carga de Saldos Iniciales en otro mes.
- [ ] Definir qué es la cuenta "Ina" (Resultados, Nivel 2) — preguntarle a Emi antes de tocarla.
- [ ] Decidir cómo mostrar "IVA Crédito Fiscal" (vive en Activo, se quiere ver junto a Pasivo).

## Visión a futuro (no tocar todavía, solo para tener en mente)
- Hoy Balance, Admin y Libro Diario los usan únicamente Emi y Claude (y a veces Tomy) — no hay
  usuarios externos todavía.
- Idea para más adelante: alimentar informes de solo lectura para terceros a partir de Balance.
- Dashboard es el primer paso hacia algo más visual — pensar qué gráficos siguen (Cuenta
  Corriente por Titular, Fondos en el tiempo, comparativo mes a mes) antes de sumar de más.

## Preguntas abiertas
- [ ] Confirmar con Tomy el detalle de `CircuitoF.js` y `CargaAutomatica.js` antes de que Claude los toque alguna vez.
- [ ] ¿La pantalla "Fondos" (con Slots fijos "1EFVO$", "2EFVO$", etc.) debería dejar de depender de
  una lista de 10 slots hardcodeados y mostrar cualquier Fondo activo? Hoy, un Fondo con una
  abreviatura (`abrev`) que no coincide exacto con esos 10 valores queda invisible en esa pantalla,
  aunque exista bien en la base — pasó hoy con 4 Fondos de prueba (ya eliminados). Evaluar si vale
  la pena rediseñar esa pantalla o si el sistema de slots fijos es intencional y hay que
  documentarlo mejor para no crear Fondos con abreviaturas raras.
