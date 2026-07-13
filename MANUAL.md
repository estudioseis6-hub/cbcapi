MANUAL — CBC Sistema Contable
Cómo se administra este documento: vive en GitHub, repo `cbcapi`, en la raíz (al lado de `main.py`). Se edita ahí mismo. Al empezar una sesión nueva con Claude, se sube este archivo antes de pedir cualquier cosa.
---
PARTE 1 — GUÍA FUNCIONAL (paso a paso, qué hace cada cosa)
Recorrido general del sistema
El sistema arranca en la pantalla Inicio, que tiene los links a todo lo demás. Lo primero que
hay que hacer, siempre, es ir a Configuración y completar lo que el sistema pida ahí (datos de
la empresa, convenio laboral, fecha de corte patrimonial, etc.) — varias pantallas no dejan
avanzar hasta que esto esté completo.
Después de Configuración, el orden natural de uso es:
RRHH — cargar empleados y liquidar sueldos.
Tesorería — el día a día de ingresos y egresos de plata.
Cuenta Corriente — la deuda con Proveedores/Titulares, y el pago de facturas.
Balance — la foto contable completa: Resultados y Situación Patrimonial, más la carga inicial (Saldos Iniciales, Cheques de Apertura).
---
TESORERÍA — cómo funciona, paso a paso
En Tesorería se cargan y se ven todos los ingresos y egresos de plata, organizados por Fondo
(cada caja, cada cuenta bancaria es un Fondo separado). Todo lo que cargás acá modifica el saldo
del Fondo que elegiste — nunca "la plata en general", siempre un fondo puntual.
Cada movimiento que ves en la lista tiene un Estado:
Histórico: ya pasó, está confirmado.
Hoy: pasa hoy.
Proyectado: todavía no pasó, es una fecha futura.
Y dentro de "Proyectado", hay 3 tipos distintos de registro — esto es importante porque cada
uno se maneja diferente:
1. Movimiento Directo
Lo cargás vos a mano, sin que venga de ninguna factura. Puede ser algo que ya pasó (Histórico/Hoy)
o algo que planeás que pase en el futuro (Proyectado).
Qué le hace al Balance: apenas queda confirmado (o si lo cargaste como ya ocurrido),
suma o resta directo al saldo del Fondo elegido — y por lo tanto al Activo (Caja/Banco) del Balance.
Se puede eliminar directo desde Tesorería. Si eliminás un movimiento directo, listo, desaparece.
Se puede reprogramar: sí, cambiarle la fecha con "Reprogramar".
Ojo con esto: si ese movimiento directo en realidad había sido un pago que cancelaba facturas
en Cuenta Corriente, al eliminarlo esas facturas vuelven a estado IMPAGO — es decir, revive la deuda.
2. Obligación Proyectada
Esta NO la cargás en Tesorería — aparece sola porque viene de una factura cargada en Cuenta
Corriente. Es la proyección de "esto vamos a tener que pagar tal fecha".
Qué le hace al Balance: mientras está proyectada, no movió nada todavía — es solo una
advertencia de lo que se viene. El Pasivo real ya lo generó la factura en sí (en Cuenta Corriente),
no esta proyección.
NO se puede eliminar desde Tesorería. Si querés sacarla, tenés que ir a Cuenta Corriente y
eliminar la factura de origen ahí.
Sí se puede reprogramar la fecha desde Tesorería (por ejemplo, si sabés que vas a pagar más tarde).
3. Estimación Proyectada
Una proyección manual tuya de "esto va a pasar", pero sin que exista todavía una factura real
detrás — un cálculo o expectativa que cargaste a mano.
Qué le hace al Balance: nada todavía, es solo informativa hasta que se confirme.
Se puede eliminar y reprogramar libremente — es tuya, no depende de nada más.
Confirmar un Proyectado
Cualquiera de los tres, cuando llega el momento, se puede Confirmar (botón "✓ Confirmar") —
eso lo pasa de "Proyectado" a real, y ahí sí impacta el saldo del Fondo.
Transferencia entre Fondos
Mover plata de un Fondo a otro (ej. de Caja a Banco). Genera dos movimientos ligados (uno de
egreso en el fondo de origen, uno de ingreso en el de destino) — si eliminás uno, se eliminan los
dos juntos, para que nunca quede una transferencia con solo una mitad registrada.
---
CUENTA CORRIENTE — cómo funciona, paso a paso
Acá vive la deuda con Proveedores y otros Titulares — y es donde se registra el pago. Hay una
distinción importante que separa todo el circuito en dos caminos, según el Titular:
Titular con "genera cuenta corriente" activado (proveedores habituales, con seguimiento de
deuda en el tiempo): la factura se carga acá, en Cuenta Corriente, con percepciones
impositivas (IVA, IIBB, otras) si corresponde.
Titular SIN "genera cuenta corriente" (algo puntual, un gasto suelto): la factura se carga
desde "Cargar Comprobante" (pantalla aparte), más simple, sin percepciones. Si se intenta
cargar ahí una factura de un titular que sí maneja cuenta corriente, el sistema frena y manda para acá.
Tipos de registro en Cuenta Corriente
1. Factura (Comprobante) — se carga con Titular, Tipo de Comprobante, Número, Importe, y las
percepciones si corresponde.
Qué le hace al Balance: genera una deuda — el Pasivo del Titular sube. Queda en estado IMPAGO.
No mueve ninguna Caja/Banco todavía — es solo el reconocimiento de que se debe.
2. Registrar Pago — se eligen una o varias facturas IMPAGAS de un Titular y se marcan como
pagadas, junto con el medio de pago:
TD (Transferencia Directa): el pago sale ya, de un Fondo elegido (Caja o Banco).
Qué le hace al Balance: dos cosas a la vez — resta de la Caja/Banco elegido (Activo) y
cancela la deuda de esas facturas puntuales (baja el Pasivo). Las facturas pasan de IMPAGO a PAGO.
ECHEQ: el pago se hace con un cheque electrónico, con fecha de vencimiento futura.
Qué le hace al Balance: la deuda con el Proveedor se cancela (pasa a PAGO) pero se
reemplaza por una deuda de "Valores Emitidos — Cheques Pendientes" hasta la fecha de
vencimiento del cheque, donde recién ahí sale la plata de verdad del Fondo.
Ojo: las operaciones marcadas como "informales" (sin factura) solo se pueden pagar en
efectivo, no con ECheq.
Si un pago se elimina desde Tesorería
Si en Tesorería se elimina un movimiento que había sido un pago TD, las facturas que ese pago
había cancelado vuelven a estado IMPAGO — la deuda revive. Por eso, para deshacer un pago, es
más prolijo hacerlo desde Cuenta Corriente si se puede, para no perder de vista qué facturas se
ven afectadas.
---
RRHH y LIQUIDACIONES — cómo funciona, paso a paso
Escala Convenio y Sueldos por Categoría
Acá se cargan los mínimos y estándares salariales, mes a mes, por Categoría (convenio) o Posición
(real). Si un mes no tiene carga propia, el sistema arrastra automáticamente el último mes
anterior que sí tenga algo cargado — no hace falta cargar todos los meses si no cambió nada.
Alta de Empleado
El "Sueldo Formal" y "Sueldo Real" que se cargan acá son solo de referencia — no son lo que
Liquidaciones termina usando para calcular (ver abajo). Jornada se declara en horas mensuales
(192 = completa, 96 = media jornada).
Liquidaciones — el corazón de RRHH
Por cada empleado, cada mes, hay dos "circuitos" (Formal y Real) que se calculan por separado.
De dónde sale el Sueldo Formal: 1° si ya se liquidó ese empleado antes, se respeta lo que
ya quedó guardado ese mes. 2° si es la primera vez, va directo a la Escala Convenio del mes
que se está liquidando (no la de "hoy").
Jornada: todo se prorratea según las horas declaradas (básico, adicionales) — excepto la
Obra Social (uno de los Aportes), que por acuerdo paritario se paga completa sin importar la
jornada.
Presentismo: se anula automáticamente si el empleado tuvo alguna ausencia (justificada o no)
ese mes.
Aportes: se desglosan en 5 líneas separadas (Jubilación, Ley 19.032, Obra Social, Sindicato,
Seguro de Vida y Sepelio), cada uno auditable por separado, no solo un total.
Guardar Cambios vs Liquidar: "Guardar Cambios" guarda el trabajo en progreso, sin
consecuencias — se puede seguir editando después. "Liquidar" (con confirmación) cierra el mes
de verdad — a partir de ahí, ya no se puede tocar la Escala Convenio de ese mes.
Importante, todavía no resuelto: apretar "Liquidar" hoy no genera ningún efecto en
Balance — no devenga sueldos en Resultados, no crea "Sueldos a Pagar" en el Pasivo. Es un
pendiente de diseño grande (ver Parte 3).
---
BALANCE — cómo funciona, paso a paso
Balance tiene dos partes que se ven juntas pero son independientes: el Cuadro de Resultados
(Ventas, Gastos, Ganancia/Pérdida del período) y el Estado de Situación Patrimonial (Activo,
Pasivo, Patrimonio Neto). Además, acá vive la carga de Saldos Iniciales y Cheques de
Apertura — la foto de "cómo empezaba todo" el día del corte.
Saldos Iniciales
Cada cuenta del Balance (Activo o Pasivo) tiene una celda donde se carga su valor de apertura con
un click — un campo que dice "Cargue aquí" si está vacío.
Para qué sirve: declarar cuánto había (o se debía) de esa cuenta el día del corte, antes de
que el sistema empezara a registrar movimientos día a día.
Qué le hace al Balance: ese valor se mantiene igual mes a mes (no tiene movimientos propios)
hasta que alguien lo edite o lo anule — si se carga una deuda de apertura, va a seguir
apareciendo en Junio, Julio, etc., no solo en el mes del corte.
Para anularlo: click en la "✕" al lado del valor. No se borra el registro — queda anotado
que existió y se anuló, con un ID propio (ver "Asientos" abajo), así que si fue un error se puede
rastrear y revertir con confianza.
Cuentas de Fondos (Caja/Banco): estas sí tienen su propio movimiento (lo que entra y sale
por Tesorería) además del saldo de apertura — el saldo inicial es solo el punto de partida.
Cheques de Apertura
Cheques que la empresa ya había emitido antes del corte, y que todavía no se debitaron del banco.
Estado Pendiente: todavía no salió la plata — cuenta como deuda ("Valores Emitidos —
Cheques Pendientes") en el Pasivo.
Estado Debitado: ya salió la plata del banco — deja de contar como deuda pendiente.
El mecanismo de "Asiento"
Cada vez que se carga algo que afecta el Balance (por ahora: Saldos Iniciales, movimientos de
Tesorería, transferencias entre fondos), el sistema crea por adentro un Asiento — un recibo
con su propio número, que dice qué tipo de carga fue y cuándo se hizo. Si después hace falta
deshacer esa carga porque fue un error, el sistema anula el Asiento completo (no borra nada a lo
bruto) — queda constancia de que existió y se dio de baja, en vez de desaparecer sin dejar rastro.
Todavía no todo pasa por acá — Comprobantes/Facturas y Registrar Pago (los más importantes)
todavía no generan su Asiento propio. Ver Parte 3, Prioridad 1.
---
PARTE 2 — REFERENCIA TÉCNICA (arquitectura, para Claude y para ir aprendiendo)
Arquitectura
Capa	Tecnología	Dónde vive
Frontend	React	repo `cbcfront`, Vercel
Backend	FastAPI (Python)	repo `cbcapi`, Render
Base de datos	PostgreSQL	Neon
`main.py` se edita pegando directo en GitHub. Archivos `.js`/`.jsx` se reemplazan completos. SQL se corre a mano en Neon.
Para bajar TODO un repo de una vez: botón verde "Code" → "Download ZIP".
Render no siempre redeploya solo. Vercel sí, pero el navegador cachea fuerte (Ctrl+Shift+R antes de asumir un bug).
Números: separador de miles + 1 decimal, siempre, en todo el sistema.
Mapa de archivos del frontend (`cbcfront/src`)
Archivo	Qué es
`App.js`	Layout, navegación, bloqueo de pantallas si falta configuración
`Inicio.js`	Pantalla de bienvenida
`Configuracion.jsx`	Datos de empresa, convenio, corte, checklist
`RRHH.jsx`	Empleados, Escala Convenio, Sueldos por Categoría, Liquidaciones, Conceptos de Liquidación
`Balance.js`	Cuadro de Resultados + Situación Patrimonial + Saldos Iniciales + Cheques de Apertura
`Titulares.js`	Alta/edición de Proveedores y clientes
`PlanCuentas.js`	Asignar un Fondo a cada cuenta del Plan de Cuentas
`Fondos.js`	Alta/edición de Fondos (caja/banco)
`CargarMovimiento.js`	"Cargar Comprobante" — factura simple, para titulares sin cuenta corriente
`CuentaCorriente.js`	Deuda por Titular, carga de facturas con percepciones, Registrar Pago
`GestionSaldos.js`	Vista de consulta de operaciones (solo lectura)
`Tesoreria.js`	Movimientos de caja/banco, transferencias, confirmar vencimientos
`Admin.js`	Gestión directa del Plan de Cuentas (niveles, estructura)
`CircuitoF.js`	De Tomy — no tocar sin que él lo pida.
`CargaAutomatica.js`	De Tomy — no tocar sin que él lo pida. Lectura automática de facturas.
Niveles del Plan de Cuentas
Nivel 1: 3 valores en todo el sistema — "Resultados", "Patrimonial", "Movimiento".
Nivel 2: dentro de Resultados → Ventas, Deducciones Variables, Gastos. Dentro de Patrimonial → Activo, Pasivo, Patrimonio. Dentro de Movimiento → Mov. Fondos.
Nivel 3, 4: subdivisiones cada vez más finas.
Nivel 5: cuentas puntuales, la hoja final del árbol.
Detalles técnicos de Liquidaciones
Jornada completa = 192 horas mensuales. Todo prorratea linealmente salvo Obra Social (excepción explicada en Parte 1).
`conceptos_liquidacion.calculo`: `MANUAL` / `AUTOMATICO` (% del básico) / `AUTOMATICO_BRUTO` (% del Bruto, segunda pasada — los 5 Aportes). Campo `activo` prende/apaga sin tocar código.
`liquidaciones.es_borrador`: `true` = "Guardar Cambios" (sin bloqueos). `false` = "Liquidar" (cierra el mes). No puede volver a `true` por accidente una vez `false`.
Suma No Remunerativa: de Escala Convenio, prorrateada, se suma al Neto después de Aportes (no infla Bruto ni la base de Aportes).
Detalles técnicos de Balance
`EstadoResultados` y `BloquePatrimonial` son dos componentes de React separados dentro de `Balance.js`, cada uno con su propio estado de expandir/colapsar.
Framework "Causa vs Efecto" (terminología propia de Emi): PN-Causa = lo que generó el patrimonio con el tiempo; PN-Efecto = Activo menos Pasivo, la foto actual.
`saldos_genericos`: cualquier saldo inicial que no sea de Fondos se suma al Activo o Pasivo según corresponda — resuelve deudas de apertura sin factura puntual, y cuentas de Activo que no son caja/banco.
Nombres de cuenta patrimonial para Pasivo/Activo son listas de texto exactas, hardcodeadas en `Balance.js` — un nombre que no calce carácter por carácter no se toma.
El mecanismo de `asientos` — detalle técnico
Tabla `asientos` (id, tipo_origen, descripción, `anulado`). Cada acción que toca el Balance crea un asiento primero, y la fila que genera (`saldos_iniciales`/`cashflow`/`operaciones`) queda con `id_asiento`. Anular = `PUT /asientos/{id}/anular` — no borra nada, las consultas de Balance ya ignoran lo anulado.
Ya conectado: Saldos Iniciales, Movimiento manual de Tesorería, Transferencia entre fondos.
No conectado todavía: Comprobantes (`operaciones`), Registrar Pago, Cheques de Apertura, Vencimientos/confirmar.
---
PARTE 3 — PENDIENTES (lista viva, actualizar seguido)
Prioridad 1 — Terminar de conectar `asientos`
[ ] Comprobantes (`CargarMovimiento.js` / `CuentaCorriente.js` → `operaciones`).
[ ] Registrar Pago — el más delicado: mueve Caja/Banco Y cancela deuda a la vez. Diseñar con calma: ¿un asiento para las dos partes, o dos asientos relacionados?
[ ] Cheques de Apertura.
[ ] Vencimientos/confirmar en Tesorería.
Prioridad 2 — Liquidaciones ↔ Balance (nunca se construyó)
[ ] Diseñar qué pasa contablemente al "Liquidar": ¿devenga en Resultados? ¿genera "Sueldos a Pagar" en Pasivo? ¿con qué asiento?
[ ] Módulo "Pagar Sueldos" (conectar el pago real de la liquidación a Tesorería).
Otros pendientes conocidos
[ ] Referencias de "hoy" vs "mes que se está liquidando" en algunos avisos de mínimo de Liquidaciones.
[ ] Corrección de un mes ya liquidado (`es_borrador = false`) — sin diseñar.
[ ] Unificar expandir/colapsar entre `EstadoResultados` y `BloquePatrimonial` (por ahora, los dos arrancan desplegados — alcanza).
[ ] Impresión de recibos de sueldo (placeholder sin funcionalidad).
[ ] AFIP/ARCA — sin definir método.
[ ] Autenticación / multi-tenant — no implementado.
Preguntas abiertas
[ ] Confirmar con Tomy el detalle de `CircuitoF.js` y `CargaAutomatica.js` antes de que Claude los toque alguna vez.
