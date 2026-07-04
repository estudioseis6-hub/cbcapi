// ============================================================
// BALANCE.JSX — CBC Sistema Contable
// ============================================================
import React, { useState, useEffect, useCallback } from "react";

const API = process.env.REACT_APP_API || "https://cbcapi.onrender.com";

const MESES = ["Todos","1-Enero","2-Febrero","3-Marzo","4-Abril","5-Mayo","6-Junio",
               "7-Julio","8-Agosto","9-Septiembre","10-Octubre","11-Noviembre","12-Diciembre"];

const MES_LABELS = {
  "1-Enero": "Enero 2026", "2-Febrero": "Febrero 2026", "3-Marzo": "Marzo 2026",
  "4-Abril": "Abril 2026", "5-Mayo": "Mayo 2026", "6-Junio": "Junio 2026",
  "7-Julio": "Julio 2026", "8-Agosto": "Agosto 2026", "9-Septiembre": "Septiembre 2026",
  "10-Octubre": "Octubre 2026", "11-Noviembre": "Noviembre 2026", "12-Diciembre": "Diciembre 2026",
  "Todos": "Acumulado",
};

// FECHA_INICIO se carga desde configuracion

const fmt = (n) => parseFloat(n || 0).toLocaleString("es-AR", { minimumFractionDigits: 2 });
const color = (n) => parseFloat(n) >= 0 ? "#059669" : "#dc2626";

// ============================================================
// CELDA EDITABLE INLINE para saldo inicial
// ============================================================
function CeldaEditable({ cuenta, saldosIniciales, onGuardar }) {
  const [editando, setEditando] = useState(false);
  const [valor, setValor] = useState("");

  const saldoExistente = saldosIniciales[cuenta];
  const importeActual = saldoExistente ? parseFloat(saldoExistente.importe) : 0;

  const handleClick = () => {
    setValor(importeActual !== 0 ? String(importeActual) : "");
    setEditando(true);
  };

  const handleGuardar = async () => {
    const importe = parseFloat(valor) || 0;
    await onGuardar(cuenta, importe, saldoExistente?.id);
    setEditando(false);
  };

  if (editando) {
    return (
      <input
        type="number"
        autoFocus
        value={valor}
        onChange={e => setValor(e.target.value)}
        onBlur={handleGuardar}
        onKeyDown={e => { if (e.key === "Enter") handleGuardar(); if (e.key === "Escape") setEditando(false); }}
        style={{ width: 110, textAlign: "right", border: "1px solid #2c3e50", borderRadius: 4, padding: "2px 6px", fontSize: 12 }}
      />
    );
  }

  return (
    <span
      onClick={handleClick}
      title="Click para editar saldo inicial"
      style={{ cursor: "pointer", color: importeActual !== 0 ? color(importeActual) : "#cbd5e1", fontWeight: importeActual !== 0 ? 600 : 400 }}
    >
      {importeActual !== 0 ? `$${fmt(importeActual)}` : "—"}
    </span>
  );
}

// ============================================================
// TAB: ESTADO DE RESULTADOS (dos columnas)
// ============================================================
function EstadoResultados({ mes }) {
  const [datos, setDatos] = useState([]);
  const [saldosIniciales, setSaldosIniciales] = useState({});
  const [loading, setLoading] = useState(false);
  const [abiertoCR, setAbiertoCR] = useState(false);
  const [abiertoNiv2, setAbiertoNiv2] = useState({});
  const [fechaInicio, setFechaInicio] = useState("2026-05-31");
  const [labelInicio, setLabelInicio] = useState("Al 31/05/2026");
  const [abiertoNiv3, setAbiertoNiv3] = useState({});
  const toggleNiv2 = (k) => setAbiertoNiv2(prev => ({ ...prev, [k]: !prev[k] }));
  const toggleNiv3 = (k) => setAbiertoNiv3(prev => ({ ...prev, [k]: !prev[k] }));

  const mesNum = mes === "Todos" ? "" : mes.split("-")[0];
  const mesLabel = MES_LABELS[mes] || mes;

  const cargarDatos = useCallback(() => {
    setLoading(true);
    const url = mesNum ? `${API}/balance?mes=${mesNum}` : `${API}/balance`;
    Promise.all([
      fetch(url).then(r => r.json()),
      fetch(`${API}/saldos_iniciales?fecha=${fechaInicio}`).then(r => r.json()),
    ]).then(([balanceData, saldosData]) => {
      setDatos(balanceData);
      const mapa = {};
      saldosData.forEach(s => { mapa[s.cuenta_patrimonial] = s; });
      setSaldosIniciales(mapa);
      setLoading(false);
    });
  }, [mesNum]);

  useEffect(() => {
    fetch(`${API}/configuracion`).then(r => r.json()).then(cfg => {
      const fecha = cfg.fecha_inicio_sistema?.valor || "2026-05-31";
      setFechaInicio(fecha);
      const [anio, mes, dia] = fecha.split("-");
      setLabelInicio(`Al ${dia}/${mes}/${anio}`);
    });
  }, []);

  useEffect(() => { cargarDatos(); }, [cargarDatos]);

  const handleGuardarSaldo = async (cuenta, importe, idExistente) => {
    if (idExistente) {
      await fetch(`${API}/saldos_iniciales/${idExistente}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fecha: fechaInicio, cuenta_patrimonial: cuenta, importe, descripcion: null })
      });
    } else {
      await fetch(`${API}/saldos_iniciales`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fecha: fechaInicio, cuenta_patrimonial: cuenta, importe, descripcion: null })
      });
    }
    cargarDatos();
  };

  // Agrupar por niv1 → niv2 → niv3 → niv4 → niv5
  const agrupado = datos.reduce((acc, d) => {
    const k1 = d.niv1_desc || "—";
    const k2 = d.niv2_desc || "—";
    const k3 = d.niv3_desc || "—";
    const k4 = d.niv4_desc || "—";
    const k5 = d.niv5 || 0;
    if (!acc[k1]) acc[k1] = { niv1: d.niv1, sub: {} };
    if (!acc[k1].sub[k2]) acc[k1].sub[k2] = { niv2: d.niv2, sub: {} };
    if (!acc[k1].sub[k2].sub[k3]) acc[k1].sub[k2].sub[k3] = { niv3: d.niv3, sub: {} };
    if (!acc[k1].sub[k2].sub[k3].sub[k4]) acc[k1].sub[k2].sub[k3].sub[k4] = { niv4: d.niv4, sub: {} };
    if (!acc[k1].sub[k2].sub[k3].sub[k4].sub[k5]) acc[k1].sub[k2].sub[k3].sub[k4].sub[k5] = { cuentas: [] };
    acc[k1].sub[k2].sub[k3].sub[k4].sub[k5].cuentas.push(d);
    return acc;
  }, {});

  const sumCuentas = (cuentas) => cuentas.reduce((s, c) => s + parseFloat(c.importe || 0), 0);
  const sumNiv5 = (niv5obj) => Object.values(niv5obj).reduce((s, v) => s + sumCuentas(v.cuentas), 0);
  const sumNiv4 = (niv4obj) => Object.values(niv4obj).reduce((s, v) => s + sumNiv5(v.sub), 0);
  const sumNiv3 = (niv3obj) => Object.values(niv3obj).reduce((s, v) => s + sumNiv4(v.sub), 0);
  const sumNiv2 = (niv2obj) => Object.values(niv2obj).reduce((s, v) => s + sumNiv3(v.sub), 0);

  // Estilos base de celdas
  const cI = { textAlign: "right", padding: "0 12px", color: "#94a3b8", fontSize: 12, whiteSpace: "nowrap" }; // columna inicio
  const cA = { textAlign: "right", padding: "0 12px", fontSize: 12, whiteSpace: "nowrap" }; // columna actual

  const thStyle = { padding: "8px 12px", fontSize: 11, color: "white", textTransform: "uppercase", letterSpacing: 1, textAlign: "right", whiteSpace: "nowrap" };

  // Header de la tabla — sticky
  const Header = () => (
    <thead>
      <tr style={{ background: "#415A77", position: "sticky", top: 0, zIndex: 9 }}>
        <th style={{ ...thStyle, textAlign: "left", width: "60%" }}>Balance</th>
        <th style={thStyle}>{labelInicio}</th>
        <th style={thStyle}>{mesLabel}</th>
      </tr>
    </thead>
  );

  // FilaGrupo: nivel 0 = título de sección (oscuro), nivel 1 = subgrupo (gris suave), nivel 2+ = sin fondo
  const FilaGrupo = ({ label, inicio, actual, nivel }) => {
    const esSeccion = nivel === 0;
    const esSubgrupo = nivel === 1;
    return (
      <tr style={{
        background: esSeccion ? "#1B263B" : esSubgrupo ? "#f4f5f3" : "white",
        borderTop: nivel >= 1 ? "1px solid #e2e8f0" : "none",
      }}>
        <td style={{
          padding: `${esSeccion ? 8 : 5}px 12px`,
          fontSize: esSeccion ? 12 : nivel === 1 ? 12 : 11,
          color: esSeccion ? "white" : nivel === 1 ? "white" : nivel === 2 ? "#415A77" : "#778DA9",
          fontWeight: esSeccion ? 700 : nivel === 1 ? 600 : 500,
          textTransform: esSeccion ? "uppercase" : "none",
          letterSpacing: esSeccion ? 1 : 0,
        }}>
          {label}
        </td>
        <td style={{ ...cI, fontWeight: esSeccion ? 600 : 500, fontSize: esSeccion ? 12 : 11,
          color: esSeccion ? (inicio !== 0 ? "#A8C0D0" : "rgba(224,225,221,0.4)") : (esSubgrupo ? (inicio !== 0 ? "#A8C0D0" : "rgba(255,255,255,0.3)") : (inicio !== 0 ? color(inicio) : "#cbd5e1")) }}>
          {inicio !== 0 ? `$${fmt(inicio)}` : "—"}
        </td>
        <td style={{ ...cA, fontWeight: esSeccion ? 600 : 500, fontSize: esSeccion ? 12 : 11,
          color: esSeccion ? (actual !== 0 ? "#A8C0D0" : "rgba(224,225,221,0.4)") : (esSubgrupo ? (actual !== 0 ? "#A8C0D0" : "rgba(255,255,255,0.3)") : (actual !== 0 ? color(actual) : "#cbd5e1")) }}>
          {actual !== 0 ? `$${fmt(actual)}` : "—"}
        </td>
      </tr>
    );
  };

  // FilaCuenta: fondo blanco, sin adorno, texto gris claro
  const FilaCuenta = ({ nombre, importe }) => {
    if (parseFloat(importe || 0) === 0) return null;
    return (
      <tr style={{ background: "white", borderTop: "1px solid #DEE7F2" }}>
        <td style={{ padding: "3px 12px", fontSize: 11, color: "#94a3b8", fontWeight: 400 }}>{nombre}</td>
        <td style={{ ...cI, fontSize: 11 }}>—</td>
        <td style={{ ...cA, fontSize: 11, color: color(importe), fontWeight: 400 }}>${fmt(importe)}</td>
      </tr>
    );
  };

  // FilaTotal: línea superior sutil; nivel 0 = oscuro, resto = solo borde
  const FilaTotal = ({ label, inicio, actual, nivel }) => {
    const esTotal = nivel === 0;
    return (
      <tr style={{
        background: esTotal ? "#0D1B2A" : "white",
        borderTop: "1px solid #DEE7F2",
      }}>
        <td style={{
          padding: "5px 12px",
          fontSize: 11,
          color: esTotal ? "white" : "#374151",
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: 0.5,
        }}>
          {label}
        </td>
        <td style={{ ...cI, fontWeight: 600, fontSize: 11,
          color: esTotal ? (inicio !== 0 ? "#A8C0D0" : "rgba(224,225,221,0.4)") : (inicio !== 0 ? color(inicio) : "#cbd5e1") }}>
          {inicio !== 0 ? `$${fmt(inicio)}` : "—"}
        </td>
        <td style={{ ...cA, fontWeight: 600, fontSize: 11,
          color: esTotal ? (actual !== 0 ? (color(actual) === "#059669" ? "#6ee7b7" : "#fca5a5") : "rgba(224,225,221,0.4)") : (actual !== 0 ? color(actual) : "#cbd5e1") }}>
          {actual !== 0 ? `$${fmt(actual)}` : "—"}
        </td>
      </tr>
    );
  };

  const totalVentas = datos.filter(d => d.niv2 === 1 && d.niv1 === 1).reduce((s, d) => s + parseFloat(d.importe || 0), 0);
  const totalDeducciones = datos.filter(d => d.niv2 === 2 && d.niv1 === 1).reduce((s, d) => s + parseFloat(d.importe || 0), 0);
  const totalGastosEstructura = datos.filter(d => d.niv2 === 3 && d.niv1 === 1).reduce((s, d) => s + parseFloat(d.importe || 0), 0);
  const totalGastosExtraord = datos.filter(d => d.niv2 === 4 && d.niv1 === 1).reduce((s, d) => s + parseFloat(d.importe || 0), 0);
  const resultadoBruto = totalVentas + totalDeducciones;
  const resultadoOrdinario = resultadoBruto + totalGastosEstructura;
  const resultadoFinal = resultadoOrdinario + totalGastosExtraord;

  if (loading) return <div style={{ padding: 32, color: "#64748b" }}>Cargando...</div>;

  return (
    <div style={{ borderRadius: 8, border: "1px solid #ADBFCE", overflow: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <Header />
        <tbody>
          <tr><td colSpan={3} style={{ height: 12, background: "#DEE7F2" }} /></tr>
          {/* ESTADO DE RESULTADOS — fila colapsable de primer nivel */}
          {abiertoCR && (() => {
            // Extraer totales por niv2
            const niv2map = {};
            Object.values(agrupado).forEach(v1 => {
              Object.entries(v1.sub).forEach(([k2, v2]) => { niv2map[k2] = v2; });
            });
            const totalVentasCR = niv2map["Ventas"] ? sumNiv3(niv2map["Ventas"].sub) : 0;
            const totalDeduccionesCR = niv2map["Deducciones Variables"] ? sumNiv3(niv2map["Deducciones Variables"].sub) : 0;
            const resultadoBrutoCR = totalVentasCR + totalDeduccionesCR;
            const totalGastosEstrCR = niv2map["Gastos de Estructura"] ? sumNiv3(niv2map["Gastos de Estructura"].sub) : 0;
            const totalExtraordCR = niv2map["Gastos Extraordinarios"] ? sumNiv3(niv2map["Gastos Extraordinarios"].sub) : 0;
            const resultadoOrdinarioCR = resultadoBrutoCR + totalGastosEstrCR;
            const resultadoFinalCR = resultadoOrdinarioCR + totalExtraordCR;

            const FilaSubtotal = ({ label, valor }) => (
              <tr style={{ background: "#415A77", borderTop: "1px solid #DEE7F2" }}>
                <td style={{ padding: "6px 12px 6px 30px", fontSize: 10, color: "white", fontWeight: 600, textTransform: "uppercase", letterSpacing: 1 }}>{label}</td>
                <td style={{ textAlign: "right", padding: "0 12px", fontSize: 11, color: "rgba(224,225,221,0.4)", whiteSpace: "nowrap" }}>—</td>
                <td style={{ textAlign: "right", padding: "0 12px", fontSize: 11, color: valor >= 0 ? "#6ee7b7" : "#fca5a5", fontWeight: 700, whiteSpace: "nowrap" }}>${fmt(valor)}</td>
              </tr>
            );

            // Fila nivel 3 colapsable
            const FilaNiv3 = ({ k3, total, expandido, onToggle }) => (
              <tr style={{ background: "#778DA9", borderTop: "1px solid #DEE7F2", cursor: "pointer" }} onClick={onToggle}>
                <td style={{ padding: "5px 12px", fontSize: 10, color: "white", fontWeight: 600, textTransform: "uppercase", letterSpacing: 1 }}>
                  <span style={{ marginRight: 8, fontSize: 10, color: "#E0E1DD" }}>{expandido ? "▼" : "▲"}</span>
                  {k3}
                </td>
                <td style={{ textAlign: "right", padding: "0 12px", fontSize: 10, color: "rgba(224,225,221,0.4)", whiteSpace: "nowrap" }}>—</td>
                <td style={{ textAlign: "right", padding: "0 12px", fontSize: 10, color: total !== 0 ? (total >= 0 ? "#059669" : "#dc2626") : "#cbd5e1", fontWeight: 600, whiteSpace: "nowrap" }}>
                  {total !== 0 ? `$${fmt(total)}` : "—"}
                </td>
              </tr>
            );

            const renderNiv2 = (k2, v2) => {
              if (!v2) return null;
              const total = sumNiv3(v2.sub);
              const expandido = abiertoNiv2[k2];
              return (
                <React.Fragment key={k2}>
                  {expandido && Object.entries(v2.sub).sort((a, b) => a[1].niv3 - b[1].niv3).map(([k3, v3]) => {
                    const totalNiv3 = sumNiv4(v3.sub);
                    const keyNiv3 = `${k2}__${k3}`;
                    const expandidoNiv3 = abiertoNiv3[keyNiv3];
                    return (
                      <React.Fragment key={k3}>
                        {expandidoNiv3 && Object.entries(v3.sub).sort((a, b) => a[1].niv4 - b[1].niv4).map(([k4, v4]) => {
                          const totalNiv4 = sumNiv5(v4.sub);
                          const tieneNiv5Multiple = Object.keys(v4.sub).length > 1;
                          const haySubgrupo = k4 !== "—";
                          return (
                            <React.Fragment key={k4}>
                              {Object.entries(v4.sub).sort((a, b) => a[0] - b[0]).map(([k5, v5]) => {
                                const totalNiv5 = sumCuentas(v5.cuentas);
                                const cuentasConMov = v5.cuentas.filter(c => parseFloat(c.importe || 0) !== 0);
                                return (
                                  <React.Fragment key={k5}>
                                    {cuentasConMov.map((c, i) => <FilaCuenta key={i} nombre={c.nombre} importe={c.importe} />)}
                                    {tieneNiv5Multiple && totalNiv5 !== 0 && <FilaTotal label={`Total ${k4}`} inicio={0} actual={totalNiv5} nivel={3} />}
                                  </React.Fragment>
                                );
                              })}
                              {haySubgrupo && <FilaTotal label={`Total ${k4}`} inicio={0} actual={totalNiv4} nivel={2} />}
                            </React.Fragment>
                          );
                        })}
                        <FilaNiv3 k3={k3} total={totalNiv3} expandido={expandidoNiv3} onToggle={() => toggleNiv3(keyNiv3)} />
                      </React.Fragment>
                    );
                  })}
                  <tr style={{ background: "#415A77", borderTop: "1px solid #DEE7F2", cursor: "pointer" }} onClick={() => toggleNiv2(k2)}>
                    <td style={{ padding: "6px 12px", fontSize: 10, color: "white", fontWeight: 600, textTransform: "uppercase", letterSpacing: 1 }}>
                      <span style={{ marginRight: 8, fontSize: 10, opacity: 1, color: "#E0E1DD" }}>{expandido ? "▼" : "▲"}</span>
                      Total {k2}
                    </td>
                    <td style={{ textAlign: "right", padding: "0 12px", fontSize: 10, color: "rgba(224,225,221,0.4)", whiteSpace: "nowrap" }}>—</td>
                    <td style={{ textAlign: "right", padding: "0 12px", fontSize: 10, color: total !== 0 ? (total >= 0 ? "#059669" : "#dc2626") : "#cbd5e1", fontWeight: 600, whiteSpace: "nowrap" }}>
                      {total !== 0 ? `$${fmt(total)}` : "—"}
                    </td>
                  </tr>
                </React.Fragment>
              );
            };

            const Divisor = () => <tr><td colSpan={3} style={{ height: 6, background: "#DEE7F2" }} /></tr>;

            return (
              <React.Fragment>
                {renderNiv2("Ventas", niv2map["Ventas"])}
                <Divisor />
                {renderNiv2("Deducciones Variables", niv2map["Deducciones Variables"])}
                <Divisor />
                <FilaSubtotal label="Total Resultado Bruto de Ventas" valor={resultadoBrutoCR} />
                <Divisor />
                {renderNiv2("Gastos de Estructura", niv2map["Gastos de Estructura"])}
                <Divisor />
                <tr style={{ background: "#415A77", borderTop: "1px solid #DEE7F2" }}>
                  <td style={{ padding: "6px 12px 6px 30px", fontSize: 10, color: "white", fontWeight: 600, textTransform: "uppercase", letterSpacing: 1 }}>Total Ingresos No Asignados</td>
                  <td style={{ textAlign: "right", padding: "0 12px", fontSize: 11, color: "rgba(224,225,221,0.4)", whiteSpace: "nowrap" }}>—</td>
                  <td style={{ textAlign: "right", padding: "0 12px", fontSize: 11, color: "rgba(224,225,221,0.4)", whiteSpace: "nowrap" }}>—</td>
                </tr>
                <Divisor />
                <FilaSubtotal label="Total Resultado Ordinario" valor={resultadoOrdinarioCR} />
                <Divisor />
                {renderNiv2("Gastos Extraordinarios", niv2map["Gastos Extraordinarios"])}
                <Divisor />
              </React.Fragment>
            );
          })()}
          <tr style={{ background: "#0D1B2A", cursor: "pointer" }} onClick={() => setAbiertoCR(v => !v)}>
            <td style={{ padding: "8px 12px", fontSize: 12, color: "white", fontWeight: 700, textTransform: "uppercase", letterSpacing: 1 }}>
              <span style={{ marginRight: 8, fontSize: 10, opacity: 1, color: "#E0E1DD" }}>{abiertoCR ? "▼" : "▲"}</span>
              Total Resultados
            </td>
            <td style={{ textAlign: "right", padding: "0 12px", fontSize: 12, color: "rgba(224,225,221,0.4)", whiteSpace: "nowrap" }}>—</td>
            <td style={{ textAlign: "right", padding: "0 12px", fontSize: 12, color: resultadoFinal !== 0 ? "#A8C0D0" : "rgba(224,225,221,0.4)", fontWeight: 600, whiteSpace: "nowrap" }}>
              {resultadoFinal !== 0 ? `$${fmt(resultadoFinal)}` : "—"}
            </td>
          </tr>

          {/* SEPARADOR */}
          <tr><td colSpan={3} style={{ height: 12, background: "#DEE7F2" }} /></tr>

          {/* BLOQUE PATRIMONIAL */}
          <BloquePatrimonial
            mes={mes}
            mesNum={mesNum}
            saldosIniciales={saldosIniciales}
            onGuardarSaldo={handleGuardarSaldo}
            resultadoFinal={resultadoFinal}
            cI={cI}
            cA={cA}
            FilaGrupo={FilaGrupo}
            FilaTotal={FilaTotal}
            FilaCeldaEditable={CeldaEditable}
          />
        </tbody>
      </table>
    </div>
  );
}

// ============================================================
// TAB: MOV. AGRUPADOS
// ============================================================
function MovAgrupados({ mes }) {
  const [fondos, setFondos] = useState([]);
  const [filas, setFilas] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch(`${API}/fondos_admin`).then(r => r.json()).then(setFondos);
  }, []);

  useEffect(() => {
    if (fondos.length === 0) return;
    setLoading(true);
    const mesNum = mes === "Todos" ? "" : mes.split("-")[0];
    const url = mesNum ? `${API}/cashflow?mes=${mesNum}` : `${API}/cashflow`;
    fetch(url).then(r => r.json()).then(movs => {
      const mapa = {};
      movs.forEach(m => {
        const cuenta = m.cod_cuenta;
        if (!cuenta) return;
        if (!mapa[cuenta]) mapa[cuenta] = {};
        const fid = m.id_fondo;
        if (!mapa[cuenta][fid]) mapa[cuenta][fid] = 0;
        mapa[cuenta][fid] += parseFloat(m.importe || 0);
      });
      const resultado = Object.entries(mapa)
        .map(([cuenta, porfondo]) => ({ cuenta, porfondo }))
        .sort((a, b) => a.cuenta.localeCompare(b.cuenta));
      setFilas(resultado);
      setLoading(false);
    });
  }, [mes, fondos]);

  const fondosConDatos = fondos.filter(f => filas.some(fila => fila.porfondo[f.id] !== undefined));
  const totalPorFondo = {};
  fondosConDatos.forEach(f => { totalPorFondo[f.id] = filas.reduce((s, fila) => s + (fila.porfondo[f.id] || 0), 0); });
  const totalGeneral = Object.values(totalPorFondo).reduce((s, v) => s + v, 0);

  const fmtN = (n) => { if (!n || parseFloat(n) === 0) return null; return parseFloat(n).toLocaleString("es-AR", { minimumFractionDigits: 2 }); };
  const colorN = (n) => parseFloat(n) >= 0 ? "#059669" : "#dc2626";
  const th = { padding: "9px 14px", fontSize: 11, color: "white", textTransform: "uppercase", letterSpacing: 1, textAlign: "right", whiteSpace: "nowrap" };
  const thL = { ...th, textAlign: "left" };
  const td = { padding: "8px 14px", fontSize: 12, color: "#1B263B", textAlign: "right", whiteSpace: "nowrap", borderTop: "1px solid #DEE7F2" };
  const tdL = { ...td, textAlign: "left", fontWeight: 500 };

  if (loading) return <div style={{ padding: 32, color: "#64748b" }}>Cargando...</div>;
  if (filas.length === 0) return <div style={{ background: "white", borderRadius: 10, padding: 40, textAlign: "center", color: "#64748b" }}>Sin movimientos para mostrar</div>;

  return (
    <div style={{ borderRadius: 8, border: "1px solid #ADBFCE", overflow: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", tableLayout: "auto" }}>
        <thead>
          <tr style={{ background: "#1B263B" }}>
            <th style={thL}>Cuenta</th>
            {fondosConDatos.map(f => <th key={f.id} style={th}>{f.abrev || f.nombre}</th>)}
            <th style={{ ...th, background: "#0D1B2A" }}>Total</th>
          </tr>
        </thead>
        <tbody>
          {filas.map((fila, i) => {
            const total = fondosConDatos.reduce((s, f) => s + (fila.porfondo[f.id] || 0), 0);
            return (
              <tr key={i} style={{ background: i % 2 === 0 ? "white" : "#f7f7f6" }}>
                <td style={tdL}>{fila.cuenta}</td>
                {fondosConDatos.map(f => {
                  const val = fila.porfondo[f.id];
                  const fmtVal = fmtN(val);
                  return (
                    <td key={f.id} style={td}>
                      {fmtVal ? <span style={{ color: colorN(val) }}>{fmtVal}</span> : <span style={{ color: "#cbd5e1" }}>—</span>}
                    </td>
                  );
                })}
                <td style={{ ...td, fontWeight: 700, background: i % 2 === 0 ? "#f4f5f3" : "#eaebe8" }}>
                  <span style={{ color: colorN(total) }}>{fmtN(total) || "—"}</span>
                </td>
              </tr>
            );
          })}
        </tbody>
        <tfoot>
          <tr style={{ background: "#1B263B" }}>
            <td style={{ ...tdL, color: "white", fontWeight: 700, borderTop: "1px solid #DEE7F2" }}>TOTAL</td>
            {fondosConDatos.map(f => (
              <td key={f.id} style={{ ...td, color: colorN(totalPorFondo[f.id]), fontWeight: 700, borderTop: "1px solid #DEE7F2" }}>
                {fmtN(totalPorFondo[f.id]) || "—"}
              </td>
            ))}
            <td style={{ ...td, color: colorN(totalGeneral), fontWeight: 700, background: "#0D1B2A", borderTop: "1px solid #DEE7F2" }}>
              {fmtN(totalGeneral) || "—"}
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

// ============================================================
// BLOQUE PATRIMONIAL
// ============================================================
function BloquePatrimonial({ mes, mesNum, saldosIniciales, onGuardarSaldo, resultadoFinal, cI, cA, FilaGrupo, FilaTotal, FilaCeldaEditable }) {
  const [patrimonial, setPatrimonial] = useState(null);
  const [abierto, setAbierto] = useState({ efecto: false, causa: false });
  const [abiertoPN, setAbiertoPN] = useState({ activo: false, pasivo: false, capital: false });
  const [abiertoPN3, setAbiertoPN3] = useState({ activoCte: false, activoNoCte: false, pasivoCte: false, pasivoNoCte: false });
  const togglePN = (k) => setAbiertoPN(prev => ({ ...prev, [k]: !prev[k] }));
  const togglePN3 = (k) => setAbiertoPN3(prev => ({ ...prev, [k]: !prev[k] }));

  useEffect(() => {
    const url = mesNum ? `${API}/balance_patrimonial?mes=${mesNum}` : `${API}/balance_patrimonial`;
    fetch(url).then(r => r.json()).then(setPatrimonial);
  }, [mesNum]);

  if (!patrimonial) return null;

  const si = (cuenta) => { const s = saldosIniciales[cuenta]; return s ? parseFloat(s.importe) : 0; };

  // ACTIVO
  const activoDisp = ["Efectivo en Pesos","Efectivo en Dolares","Efectivo Reservado p/Cambio","Efectivo Fondo Local","Saldo en Cta.Bcaria Banco Santander","Saldo en Mercado Pago","Saldo en ( Fondo de Inversion)","Medios Electronicos Pendientes de Acreditación"];
  const activoCreditos = ["Valores a Depositar — Cheques de Terceros","Tarj. Credit. Pend. Acreditacion","Otros Creditos Corrientes","Otros Créditos Corrientes a Cobrar"];
  const activoBienesCambio = ["Bienes de Cambio — Inventario de Mercadería"];
  const activoBienesUso = ["Bienes de Uso — Fondo de Comercio","Bienes de Uso — Mejoras Activadas al Inmueble","Bienes de Uso — Equipamiento Activado"];
  const activoOtros = ["Reservas en Pesos — Fondo Reservado","Reservas en Dólares — Fondo Reservado","Crédito Fiscal — IIBB Saldo a Favor","Crédito Fiscal — Retenciones de Ganancias","Crédito Fiscal — Anticipos de Ganancias"];
  const actValor = (c) => patrimonial.fondos[c] !== undefined ? patrimonial.fondos[c] : c === "Tarj. Credit. Pend. Acreditacion" ? patrimonial.tarjetas_pendientes : 0;
  const siValorEmitidos = (c) => c === "Valores Emitidos — Cheques Pendientes" ? -(patrimonial.cheques_apertura || 0) : si(c);
  const sumActual = (cs) => cs.reduce((s, c) => s + actValor(c), 0);
  const sumInicio = (cs) => cs.reduce((s, c) => s + si(c), 0);
  const totalActivoDisp = sumActual(activoDisp); const totalActivoInicioDisp = sumInicio(activoDisp);
  const totalActivoCreditos = sumActual(activoCreditos); const totalActivoInicioCreditos = sumInicio(activoCreditos);
  const totalActivoBCambio = sumActual(activoBienesCambio); const totalActivoInicioBCambio = sumInicio(activoBienesCambio);
  const totalActivoBUso = sumActual(activoBienesUso); const totalActivoInicioBUso = sumInicio(activoBienesUso);
  const totalActivoOtros = sumActual(activoOtros); const totalActivoInicioOtros = sumInicio(activoOtros);
  const totalActivo = totalActivoDisp + totalActivoCreditos + totalActivoBCambio + totalActivoBUso + totalActivoOtros;
  const totalActivoInicio = totalActivoInicioDisp + totalActivoInicioCreditos + totalActivoInicioBCambio + totalActivoInicioBUso + totalActivoInicioOtros;

  // PASIVO
  const pasivoProveedores = ["Proveedores de Alimentos a Pagar","Proveedores de Bebidas a Pagar","Otros Proveedores a Pagar"];
  const pasivoImpositivo = ["Cargas Sociales a Pagar","Aportes Sindicales a Pagar","IVA a Pagar","Ingresos Brutos a Pagar","Planes AFIP a Corto Plazo"];
  const pasivoValores = ["Valores Emitidos — Cheques Pendientes"];
  const pasivoRemuneraciones = ["Remuneraciones a Pagar — Sueldos","Remuneraciones a Pagar — Aguinaldos"];
  const pasivoOtros = ["Planes AFIP a Largo Plazo","Préstamos Recibidos a Pagar Largo Plazo","Otros Pasivos No Ctes.","Anticipos de Clientes — Señas Cobradas","Propinas Cobradas Pendientes de Distribución","Préstamos Recibidos a Pagar Corto Plazo","Distribuciones de Capital a Pagar","Otras Deudas Corrientes"];
  const _pccActual = patrimonial.pasivo_cc_actual || patrimonial.pasivo_cc || {};
  const _pccInicio = patrimonial.pasivo_cc_inicio || {};
  const pasValor = (c) => { 
    const inicio = _pccInicio[c] || 0; 
    const actual = _pccActual[c] || 0; 
    const total = inicio + actual; 
    if (c === "Valores Emitidos — Cheques Pendientes") {
      const pendientes = patrimonial.cheques_apertura || 0;
      const debitados = patrimonial.cheques_apertura_debitados || 0;
      return -(pendientes - debitados);
    }
    return total !== 0 ? -Math.abs(total) : c === "Valores Emitidos — Cheques Pendientes" ? patrimonial.echeqs_pendientes : 0; 
  };
  const pasValorInicio = (c) => _pccInicio[c] !== undefined ? -Math.abs(_pccInicio[c]) : 0;
  const sumPasActual = (cs) => cs.reduce((s, c) => s + pasValor(c), 0);
  const sumPasInicio = (cs) => cs.reduce((s, c) => s + (pasValorInicio(c) || siValorEmitidos(c)), 0);
  const totalPasProveedores = sumPasActual(pasivoProveedores); const totalPasInicioProveedores = sumPasInicio(pasivoProveedores);
  const totalPasImpositivo = sumPasActual(pasivoImpositivo); const totalPasInicioImpositivo = sumPasInicio(pasivoImpositivo);
  const totalPasValores = sumPasActual(pasivoValores); const totalPasInicioValores = sumPasInicio(pasivoValores);
  const totalPasRemuneraciones = sumPasActual(pasivoRemuneraciones); const totalPasInicioRemuneraciones = sumPasInicio(pasivoRemuneraciones);
  const totalPasOtros = sumPasActual(pasivoOtros); const totalPasInicioOtros = sumPasInicio(pasivoOtros);
  const totalPasivo = totalPasProveedores + totalPasImpositivo + totalPasValores + totalPasRemuneraciones + totalPasOtros;
  const totalPasivoInicio = totalPasInicioProveedores + totalPasInicioImpositivo + totalPasInicioValores + totalPasInicioRemuneraciones + totalPasInicioOtros;

  // PN
  const pnCapitalBase = ["Aportes de Capital Recibidos","Distribución de Capital a Socios"];
  const totalPNCapitalBase = sumInicio(pnCapitalBase);
  const saldoApertura = totalActivoInicio + totalPasivoInicio - totalPNCapitalBase;
  const totalPNCausaInicio = totalPNCapitalBase + saldoApertura;
  const totalPNCausaActual = totalPNCausaInicio + resultadoFinal;
  const totalPNEfectoInicio = totalActivoInicio + totalPasivoInicio;
  const totalPNEfectoActual = totalActivo + totalPasivo;
  const ecuacionActual = totalPNEfectoActual - totalPNCausaActual;

  const FilaCuenta = ({ nombre, getFn, getFnInicio }) => {
    const valorInicio = getFnInicio ? getFnInicio(nombre) : null;
    return (
    <tr style={{ background: "white", borderTop: "1px solid #DEE7F2" }}>
      <td style={{ padding: "3px 12px", fontSize: 11, color: "#94a3b8", fontWeight: 400 }}>{nombre}</td>
      <td style={{ ...cI }}>
        {getFnInicio && valorInicio !== 0 ? 
          <span style={{ color: valorInicio >= 0 ? "#059669" : "#dc2626", fontSize: 11 }}>${fmt(valorInicio)}</span> :
          <FilaCeldaEditable cuenta={nombre} saldosIniciales={saldosIniciales} onGuardar={onGuardarSaldo} />
        }
      </td>
      <td style={{ ...cA, color: getFn && getFn(nombre) !== 0 ? (getFn(nombre) >= 0 ? "#059669" : "#dc2626") : "#cbd5e1", fontWeight: 400, fontSize: 11 }}>
        {getFn && getFn(nombre) !== 0 ? `$${fmt(getFn(nombre))}` : "—"}
      </td>
    </tr>
    );
  };

  const FilaSeccion = ({ label, inicio, actual, id }) => {
    const expandido = abierto[id];
    return (
      <tr style={{ background: "#1B263B", cursor: "pointer" }} onClick={() => setAbierto(prev => ({ ...prev, [id]: !prev[id] }))}>
        <td style={{ padding: "8px 12px", fontSize: 12, color: "white", fontWeight: 700, textTransform: "uppercase", letterSpacing: 1 }}>
          <span style={{ marginRight: 8, fontSize: 10, opacity: 1, color: "#E0E1DD" }}>{expandido ? "▼" : "▲"}</span>
          {label}
        </td>
        <td style={{ ...cI, fontWeight: 600, color: inicio !== 0 ? "#A8C0D0" : "rgba(224,225,221,0.4)" }}>
          {inicio !== 0 ? `$${fmt(inicio)}` : "—"}
        </td>
        <td style={{ ...cA, fontWeight: 600, color: actual !== 0 ? "#A8C0D0" : "rgba(224,225,221,0.4)" }}>
          {actual !== 0 ? `$${fmt(actual)}` : "—"}
        </td>
      </tr>
    );
  };

  const FilaSubgrupo = ({ label, inicio, actual, id, id3, togglePN3, abiertoPN3 }) => {
    const expandido = id ? abiertoPN[id] : id3 ? abiertoPN3[id3] : false;
    const clickable = !!(id || id3);
    const handleClick = id ? () => togglePN(id) : id3 ? () => togglePN3(id3) : undefined;
    const esNiv3 = !!id3;
    return (
      <tr style={{ background: esNiv3 ? "#778DA9" : "#415A77", borderTop: "1px solid #DEE7F2", cursor: clickable ? "pointer" : "default" }}
          onClick={clickable ? handleClick : undefined}>
        <td style={{ padding: "6px 12px", fontSize: esNiv3 ? 10 : 10, color: "white", fontWeight: 600, textTransform: "uppercase", letterSpacing: 1 }}>
          {clickable && <span style={{ marginRight: 8, fontSize: 10, opacity: 1, color: "#E0E1DD" }}>{expandido ? "▼" : "▲"}</span>}
          {label}
        </td>
        <td style={{ ...cI, fontWeight: 600, fontSize: 10, color: inicio !== 0 ? "#A8C0D0" : "rgba(224,225,221,0.4)" }}>{inicio !== 0 ? `$${fmt(inicio)}` : "—"}</td>
        <td style={{ ...cA, fontWeight: 600, fontSize: 10, color: actual !== 0 ? "#A8C0D0" : "rgba(224,225,221,0.4)" }}>{actual !== 0 ? `$${fmt(actual)}` : "—"}</td>
      </tr>
    );
  };

  const FilaTotalSub = ({ label, inicio, actual }) => (
    <tr style={{ background: "white", borderTop: "1px solid #DEE7F2" }}>
      <td style={{ padding: "4px 12px", fontSize: 11, color: "#374151", fontWeight: 600, textTransform: "uppercase", letterSpacing: 1 }}>{label}</td>
      <td style={{ ...cI, fontWeight: 600, fontSize: 11, color: inicio !== 0 ? color(inicio) : "#cbd5e1" }}>{inicio !== 0 ? `$${fmt(inicio)}` : "—"}</td>
      <td style={{ ...cA, fontWeight: 600, fontSize: 11, color: actual !== 0 ? color(actual) : "#cbd5e1" }}>{actual !== 0 ? `$${fmt(actual)}` : "—"}</td>
    </tr>
  );

  const color = (n) => parseFloat(n) >= 0 ? "#059669" : "#dc2626";

  return (
    <React.Fragment>
      {/* PN — EFECTO (detalle arriba, título abajo) */}
      {abierto.efecto && (
        <React.Fragment>
          <tr><td colSpan={3} style={{ height: 5, background: "#DEE7F2" }} /></tr>
          {/* ACTIVO — detalle arriba, título abajo */}
          {abiertoPN.activo && (
            <React.Fragment>
              {abiertoPN3.activoCte && (
                <React.Fragment>
                  {activoDisp.map(c => <FilaCuenta key={c} nombre={c} getFn={actValor} />)}
                  <FilaSubgrupo label="Total Disponibilidades" inicio={totalActivoInicioDisp} actual={totalActivoDisp} />
                  {activoCreditos.map(c => <FilaCuenta key={c} nombre={c} getFn={actValor} />)}
                  <FilaSubgrupo label="Total Créditos Corrientes" inicio={totalActivoInicioCreditos} actual={totalActivoCreditos} />
                  {activoBienesCambio.map(c => <FilaCuenta key={c} nombre={c} getFn={actValor} />)}
                  <FilaSubgrupo label="Total Bienes de Cambio" inicio={totalActivoInicioBCambio} actual={totalActivoBCambio} />
                </React.Fragment>
              )}
              <FilaSubgrupo label="Total Activo Corriente" inicio={totalActivoInicioDisp + totalActivoInicioCreditos + totalActivoInicioBCambio} actual={totalActivoDisp + totalActivoCreditos + totalActivoBCambio} id3="activoCte" togglePN3={togglePN3} abiertoPN3={abiertoPN3} />
              {abiertoPN3.activoNoCte && (
                <React.Fragment>
                  {activoBienesUso.map(c => <FilaCuenta key={c} nombre={c} getFn={actValor} />)}
                  <FilaSubgrupo label="Total Bienes de Uso" inicio={totalActivoInicioBUso} actual={totalActivoBUso} />
                  {activoOtros.map(c => <FilaCuenta key={c} nombre={c} getFn={actValor} />)}
                  <FilaSubgrupo label="Total Otros Activos" inicio={totalActivoInicioOtros} actual={totalActivoOtros} />
                </React.Fragment>
              )}
              <FilaSubgrupo label="Total Activo No Corriente" inicio={totalActivoInicioBUso + totalActivoInicioOtros} actual={totalActivoBUso + totalActivoOtros} id3="activoNoCte" togglePN3={togglePN3} abiertoPN3={abiertoPN3} />
            </React.Fragment>
          )}
          <FilaSubgrupo label="Total Activo" inicio={totalActivoInicio} actual={totalActivo} id="activo" />
          {/* PASIVO — detalle arriba, título abajo */}
          {abiertoPN.pasivo && (
            <React.Fragment>
              {abiertoPN3.pasivoCte && (
                <React.Fragment>
                  {pasivoProveedores.map(c => <FilaCuenta key={c} nombre={c} getFn={pasValor} />)}
                  <FilaSubgrupo label="Total Proveedores a Pagar" inicio={totalPasInicioProveedores} actual={totalPasProveedores} />
                  {pasivoImpositivo.map(c => <FilaCuenta key={c} nombre={c} getFn={pasValor} />)}
                  <FilaSubgrupo label="Total Deudas Impositivas y Previsionales" inicio={totalPasInicioImpositivo} actual={totalPasImpositivo} />
                  {pasivoValores.map(c => <FilaCuenta key={c} nombre={c} getFn={pasValor} getFnInicio={siValorEmitidos} />)}
                  <FilaSubgrupo label="Total Valores Emitidos" inicio={totalPasInicioValores} actual={totalPasValores} />
                  {pasivoRemuneraciones.map(c => <FilaCuenta key={c} nombre={c} getFn={pasValor} />)}
                  <FilaSubgrupo label="Total Remuneraciones a Pagar" inicio={totalPasInicioRemuneraciones} actual={totalPasRemuneraciones} />
                </React.Fragment>
              )}
              <FilaSubgrupo label="Total Pasivo Corriente" inicio={totalPasInicioProveedores + totalPasInicioImpositivo + totalPasInicioValores + totalPasInicioRemuneraciones} actual={totalPasProveedores + totalPasImpositivo + totalPasValores + totalPasRemuneraciones} id3="pasivoCte" togglePN3={togglePN3} abiertoPN3={abiertoPN3} />
              {abiertoPN3.pasivoNoCte && (
                <React.Fragment>
                  {pasivoOtros.map(c => <FilaCuenta key={c} nombre={c} getFn={pasValor} />)}
                  <FilaSubgrupo label="Total Otros Pasivos" inicio={totalPasInicioOtros} actual={totalPasOtros} />
                </React.Fragment>
              )}
              <FilaSubgrupo label="Total Pasivo No Corriente" inicio={totalPasInicioOtros} actual={totalPasOtros} id3="pasivoNoCte" togglePN3={togglePN3} abiertoPN3={abiertoPN3} />
            </React.Fragment>
          )}
          <FilaSubgrupo label="Total Pasivo" inicio={totalPasivoInicio} actual={totalPasivo} id="pasivo" />
        </React.Fragment>
      )}
      <FilaSeccion label="PN — Efecto (Activo − Pasivo)" inicio={totalPNEfectoInicio} actual={totalPNEfectoActual} id="efecto" />

      <tr><td colSpan={3} style={{ height: 11, background: "#DEE7F2" }} /></tr>

      {/* PN — CAUSA (detalle arriba, título abajo) */}
      {abierto.causa && (
        <React.Fragment>
          <tr><td colSpan={3} style={{ height: 5, background: "#DEE7F2" }} /></tr>
          {pnCapitalBase.map(c => <FilaCuenta key={c} nombre={c} getFn={() => 0} />)}
          <tr style={{ background: "white", borderTop: "1px solid #DEE7F2" }}>
            <td style={{ padding: "3px 12px", fontSize: 11, color: "#94a3b8", fontStyle: "italic" }}>Saldo Patrimonial de Apertura</td>
            <td style={{ ...cI, color: saldoApertura !== 0 ? (saldoApertura >= 0 ? "#059669" : "#dc2626") : "#cbd5e1", fontSize: 11 }}>
              {saldoApertura !== 0 ? `$${fmt(saldoApertura)}` : "—"}
            </td>
            <td style={{ ...cA, color: "#cbd5e1", fontSize: 11 }}>—</td>
          </tr>
          <FilaSubgrupo label="Total Capital" inicio={totalPNCapitalBase + saldoApertura} actual={totalPNCapitalBase + saldoApertura} />
          <tr style={{ background: "white", borderTop: "1px solid #DEE7F2" }}>
            <td style={{ padding: "3px 12px", fontSize: 11, color: "#94a3b8" }}>Resultado del Período</td>
            <td style={{ ...cI, color: "#cbd5e1", fontSize: 11 }}>—</td>
            <td style={{ ...cA, color: resultadoFinal >= 0 ? "#059669" : "#dc2626", fontWeight: 400, fontSize: 11 }}>${fmt(resultadoFinal)}</td>
          </tr>
        </React.Fragment>
      )}
      <FilaSeccion label="PN — Causa (Aportes ± Distrib. + Resultados)" inicio={totalPNCausaInicio} actual={totalPNCausaActual} id="causa" />

      <tr><td colSpan={3} style={{ height: 11, background: "#DEE7F2" }} /></tr>

      {/* ECUACIÓN */}
      <tr style={{ background: "#f4f5f3", borderTop: "1px solid #DEE7F2" }}>
        <td style={{ padding: "8px 12px", fontSize: 11, fontWeight: 700, color: "#1B263B", textTransform: "uppercase", letterSpacing: 1 }}>
          PN Efecto = PN Causa {Math.abs(ecuacionActual) < 0.01 ? "✓" : "⚠"}
        </td>
        <td style={{ ...cI, fontWeight: 700, fontSize: 11, color: "#059669" }}>✓ Cuadra</td>
        <td style={{ ...cA, fontWeight: 700, fontSize: 11, color: Math.abs(ecuacionActual) < 0.01 ? "#059669" : "#dc2626" }}>
          {Math.abs(ecuacionActual) < 0.01 ? "✓ Cuadra" : `Dif: $${fmt(ecuacionActual)}`}
        </td>
      </tr>
    </React.Fragment>
  );
}


// ============================================================
// TAB: CHEQUES DE APERTURA
// ============================================================
function ChequesApertura() {
  const [cheques, setCheques] = useState([]);
  const [titulares, setTitulares] = useState([]);
  const [modal, setModal] = useState(false);
  const [form, setForm] = useState({ fecha_emision: "", fecha_cheque: "", numero: "", id_titular: "", id_fondo: "", importe: "", descripcion: "", debitado: false });
  const [editId, setEditId] = useState(null);
  const [fondos, setFondos] = useState([]);
  const [loading, setLoading] = useState(false);

  const cargar = () => fetch(`${API}/cheques_apertura`).then(r => r.json()).then(setCheques);

  useEffect(() => {
    cargar();
    fetch(`${API}/titulares`).then(r => r.json()).then(t => setTitulares(t.filter(x => x.nivel1 !== "SISTEMA")));
    fetch(`${API}/fondos`).then(r => r.json()).then(f => setFondos(f.filter(x => x.activo)));
  }, []);

  const abrirNuevo = () => {
    setForm({ fecha_emision: "", fecha_cheque: "", numero: "", id_titular: "", id_fondo: "", importe: "", descripcion: "", debitado: false });
    setEditId(null);
    setModal(true);
  };

  const abrirEditar = (c) => {
    setForm({ fecha_emision: c.fecha_emision?.slice(0,10) || "", fecha_cheque: c.fecha_cheque?.slice(0,10) || "", numero: c.numero || "", id_titular: c.id_titular || "", id_fondo: c.id_fondo || "", importe: c.importe || "", descripcion: c.descripcion || "", debitado: c.debitado || false });
    setEditId(c.id);
    setModal(true);
  };

  const guardar = async () => {
    if (!form.fecha_emision || !form.fecha_cheque || !form.importe) return;
    setLoading(true);
    const url = editId ? `${API}/cheques_apertura/${editId}` : `${API}/cheques_apertura`;
    const method = editId ? "PUT" : "POST";
    await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...form, importe: parseFloat(form.importe), id_titular: form.id_titular ? parseInt(form.id_titular) : null, id_fondo: form.id_fondo ? parseInt(form.id_fondo) : null }) });
    cargar();
    setModal(false);
    setLoading(false);
  };

  const eliminar = async (id) => {
    if (!window.confirm("¿Eliminar este cheque?")) return;
    await fetch(`${API}/cheques_apertura/${id}`, { method: "DELETE" });
    cargar();
  };

  const totalPendiente = cheques.filter(c => !c.debitado).reduce((s, c) => s + parseFloat(c.importe), 0);

  const inp = { width: "100%", padding: "8px 12px", border: "1px solid #e2e8f0", borderRadius: 8, fontSize: 13, boxSizing: "border-box" };
  const lbl = { display: "block", fontSize: 12, color: "#374151", marginBottom: 4 };
  const th = { padding: "9px 14px", fontSize: 11, color: "white", textTransform: "uppercase", letterSpacing: 1, textAlign: "left", whiteSpace: "nowrap" };
  const td = { padding: "8px 14px", fontSize: 12, color: "#374151", borderTop: "1px solid #DEE7F2" };

  return (
    <div>
      {modal && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
          <div style={{ background: "white", borderRadius: 12, padding: 32, width: 480, boxShadow: "0 8px 32px rgba(0,0,0,0.2)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
              <div style={{ fontSize: 15, color: "#1B263B", fontWeight: 600 }}>{editId ? "Editar cheque" : "Nuevo cheque de apertura"}</div>
              <div onClick={() => setModal(false)} style={{ cursor: "pointer", color: "#94a3b8", fontSize: 20 }}>×</div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
              <div>
                <label style={lbl}>Fecha de emisión</label>
                <input type="date" value={form.fecha_emision} onChange={e => setForm({...form, fecha_emision: e.target.value})} style={inp} />
              </div>
              <div>
                <label style={lbl}>Fecha del cheque</label>
                <input type="date" value={form.fecha_cheque} onChange={e => setForm({...form, fecha_cheque: e.target.value})} style={inp} />
              </div>
              <div>
                <label style={lbl}>Número de cheque</label>
                <input type="text" value={form.numero} onChange={e => setForm({...form, numero: e.target.value})} style={inp} placeholder="Nro." />
              </div>
              <div>
                <label style={lbl}>Importe</label>
                <input type="number" value={form.importe} onChange={e => setForm({...form, importe: e.target.value})} style={inp} placeholder="$0,00" />
              </div>
              <div style={{ gridColumn: "1 / -1" }}>
                <label style={lbl}>Banco / Fondo de origen</label>
                <select value={form.id_fondo} onChange={e => setForm({...form, id_fondo: e.target.value})} style={inp}>
                  <option value="">— Seleccionar fondo —</option>
                  {fondos.map(f => <option key={f.id} value={f.id}>{f.nombre}</option>)}
                </select>
              </div>
              <div style={{ gridColumn: "1 / -1" }}>
                <label style={lbl}>Beneficiario (titular)</label>
                <select value={form.id_titular} onChange={e => setForm({...form, id_titular: e.target.value})} style={inp}>
                  <option value="">— Sin especificar —</option>
                  {titulares.map(t => <option key={t.id} value={t.id}>{t.nombre}</option>)}
                </select>
              </div>
              <div style={{ gridColumn: "1 / -1" }}>
                <label style={lbl}>Descripción</label>
                <input type="text" value={form.descripcion} onChange={e => setForm({...form, descripcion: e.target.value})} style={inp} placeholder="Opcional" />
              </div>
              <div style={{ gridColumn: "1 / -1" }}>
                <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, cursor: "pointer" }}>
                  <input type="checkbox" checked={form.debitado} onChange={e => setForm({...form, debitado: e.target.checked})} />
                  Ya debitado
                </label>
              </div>
            </div>
            <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
              <div onClick={() => setModal(false)} style={{ padding: "8px 20px", borderRadius: 8, border: "1px solid #e2e8f0", cursor: "pointer", fontSize: 13, color: "#64748b" }}>Cancelar</div>
              <div onClick={guardar} style={{ padding: "8px 20px", borderRadius: 8, background: "#1B263B", color: "white", cursor: "pointer", fontSize: 13 }}>
                {loading ? "Guardando..." : "Guardar"}
              </div>
            </div>
          </div>
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <div>
          <div style={{ fontSize: 13, color: "#64748b" }}>Cheques emitidos antes del corte patrimonial, pendientes de débito</div>
          <div style={{ fontSize: 15, fontWeight: 700, color: "#1B263B", marginTop: 4 }}>
            Total pendiente: ${fmt(totalPendiente)}
          </div>
        </div>
        <div onClick={abrirNuevo} style={{ padding: "8px 18px", background: "#1B263B", color: "white", borderRadius: 8, cursor: "pointer", fontSize: 13 }}>+ Nuevo cheque</div>
      </div>

      <div style={{ borderRadius: 8, border: "1px solid #ADBFCE", overflow: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "#415A77" }}>
              <th style={th}>Fecha emisión</th>
              <th style={th}>Fecha cheque</th>
              <th style={th}>Número</th>
              <th style={th}>Beneficiario</th>
              <th style={{ ...th, textAlign: "right" }}>Importe</th>
              <th style={th}>Estado</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {cheques.length === 0 && (
              <tr><td colSpan={7} style={{ padding: 32, textAlign: "center", color: "#94a3b8", fontSize: 13 }}>Sin cheques cargados</td></tr>
            )}
            {cheques.map((c, i) => (
              <tr key={i} style={{ background: c.debitado ? "#f7f7f6" : "white", opacity: c.debitado ? 0.6 : 1 }}>
                <td style={td}>{c.fecha_emision?.slice(0,10)}</td>
                <td style={td}>{c.fecha_cheque?.slice(0,10)}</td>
                <td style={{ ...td, fontFamily: "monospace" }}>{c.numero || "—"}</td>
                <td style={td}>{c.titular_nombre || "—"}</td>
                <td style={{ ...td, textAlign: "right", fontWeight: 600, color: "#dc2626" }}>${fmt(c.importe)}</td>
                <td style={td}>
                  <span style={{ padding: "2px 10px", borderRadius: 12, fontSize: 11, background: c.debitado ? "#e2e8f0" : "#fee2e2", color: c.debitado ? "#64748b" : "#dc2626" }}>
                    {c.debitado ? "DEBITADO" : "PENDIENTE"}
                  </span>
                </td>
                <td style={{ ...td, textAlign: "right" }}>
                  <span onClick={() => abrirEditar(c)} style={{ cursor: "pointer", color: "#415A77", marginRight: 12, fontSize: 12 }}>Editar</span>
                  <span onClick={() => eliminar(c.id)} style={{ cursor: "pointer", color: "#dc2626", fontSize: 12 }}>×</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ============================================================
// COMPONENTE PRINCIPAL
// ============================================================
export default function Balance() {
  const [mes, setMes] = useState("6-Junio");
  const [tab, setTab] = useState("resultados");

  const tabBtn = (id) => ({
    padding: "7px 18px", borderRadius: 6, cursor: "pointer", fontSize: 12, fontWeight: 600,
    background: tab === id ? "#1B263B" : "white",
    color: tab === id ? "white" : "#1B263B",
    border: "1px solid #ADBFCE",
  });

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
        <select value={mes} onChange={e => setMes(e.target.value)}
          style={{ padding: "8px 12px", border: "1px solid #e2e8f0", borderRadius: 8, fontSize: 14, background: "white" }}>
          {MESES.filter(m => m !== "Todos").map(m => <option key={m} value={m}>{m}</option>)}
        </select>
        <div style={{ display: "flex", gap: 6 }}>
          <div onClick={() => setTab("resultados")} style={tabBtn("resultados")}>Estado de Resultados</div>
          <div onClick={() => setTab("cheques")} style={tabBtn("cheques")}>Cheques de Apertura</div>
          <div onClick={() => setTab("agrupados")} style={tabBtn("agrupados")}>Mov. Agrupados</div>
        </div>
      </div>

      {tab === "resultados" && <EstadoResultados mes={mes} />}
      {tab === "cheques" && <ChequesApertura />}
      {tab === "agrupados" && <MovAgrupados mes={mes} />}
    </div>
  );
}

// Nota: el bloque Patrimonial se integra dentro de EstadoResultados
// en la misma tabla — ver FilaPatrimonial abajo
