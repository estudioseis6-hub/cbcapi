import React, { useState, useEffect } from "react";

const API = process.env.REACT_APP_API || "https://cbcapi.onrender.com";

const NIV1_OPCIONES = [
  { niv1: 1, desc: "Resultados" },
  { niv1: 2, desc: "Patrimonial" },
  { niv1: 3, desc: "Movimiento" },
];

const NIV2_OPCIONES = [
  { niv1: 1, niv2: 1, desc: "Ventas" },
  { niv1: 1, niv2: 2, desc: "Deducciones Variables" },
  { niv1: 1, niv2: 3, desc: "Gastos" },
  { niv1: 2, niv2: 1, desc: "Activo" },
  { niv1: 2, niv2: 2, desc: "Pasivo" },
  { niv1: 2, niv2: 3, desc: "Patrimonio" },
  { niv1: 3, niv2: 1, desc: "Mov. Fondos" },
];

function ModalCuenta({ cuenta, fondos, onCerrar, onGuardado }) {
  const esNueva = !cuenta;
  const [form, setForm] = useState({
    niv1: cuenta?.niv1 || 1,
    niv1_desc: cuenta?.niv1_desc || "Resultados",
    niv2: cuenta?.niv2 || 1,
    niv2_desc: cuenta?.niv2_desc || "Ventas",
    niv3: cuenta?.niv3 || 1,
    niv3_desc: cuenta?.niv3_desc || "",
    niv4: cuenta?.niv4 || 1,
    niv4_desc: cuenta?.niv4_desc || "",
    niv5: cuenta?.niv5 || 1,
    nombre: cuenta?.nombre || "",
    cod_cbc: cuenta?.cod_cbc ? String(cuenta.cod_cbc) : "",
    fondo: cuenta?.fondo || "",
    signo: cuenta?.signo || "",
    moneda: cuenta?.moneda || "ARS",
    dd: cuenta?.dd || false,
    activo: cuenta?.activo ?? true,
  });
  const [grupos, setGrupos] = useState([]);
  const [subgrupos, setSubgrupos] = useState([]);
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState(null);

  const niv2Filtradas = NIV2_OPCIONES.filter(n => n.niv1 === parseInt(form.niv1));

  const cargarGrupos = (niv1, niv2, niv3) => {
    fetch(`${API}/plan_cuentas_grupos?niv1=${niv1}&niv2=${niv2}`)
      .then(r => r.json())
      .then(data => {
        const niv3Unicos = [...new Map(data.map(g => [g.niv3, g])).values()];
        setGrupos(niv3Unicos);
        setSubgrupos(data.filter(g => g.niv3 === parseInt(niv3) && g.niv4 !== null));
      });
  };

  useEffect(() => {
    cargarGrupos(form.niv1, form.niv2, form.niv3);
  }, []);

  useEffect(() => {
    cargarGrupos(form.niv1, form.niv2, form.niv3);
  }, [form.niv1, form.niv2]);

  useEffect(() => {
    if (!form.niv3) return;
    fetch(`${API}/plan_cuentas_grupos?niv1=${form.niv1}&niv2=${form.niv2}&niv3=${form.niv3}`)
      .then(r => r.json())
      .then(data => {
        setSubgrupos(data.filter(g => g.niv4 !== null));
      });
  }, [form.niv3]);

  const handleNiv1Change = (e) => {
    const niv1 = parseInt(e.target.value);
    const desc = NIV1_OPCIONES.find(n => n.niv1 === niv1)?.desc || "";
    const primeroNiv2 = NIV2_OPCIONES.find(n => n.niv1 === niv1);
    setForm({ ...form, niv1, niv1_desc: desc, niv2: primeroNiv2?.niv2 || 1, niv2_desc: primeroNiv2?.desc || "", niv3: 1, niv3_desc: "", niv4: 1, niv4_desc: "" });
  };

  const handleNiv2Change = (e) => {
    const niv2 = parseInt(e.target.value);
    const desc = NIV2_OPCIONES.find(n => n.niv1 === parseInt(form.niv1) && n.niv2 === niv2)?.desc || "";
    setForm({ ...form, niv2, niv2_desc: desc, niv3: 1, niv3_desc: "", niv4: 1, niv4_desc: "" });
  };

  const handleNiv3Change = (e) => {
    const niv3 = parseInt(e.target.value);
    const grupo = grupos.find(g => g.niv3 === niv3);
    setForm({ ...form, niv3, niv3_desc: grupo?.niv3_desc || "", niv4: 1, niv4_desc: "" });
  };

  const handleNiv4Change = (e) => {
    const niv4 = parseInt(e.target.value);
    const sub = subgrupos.find(s => s.niv4 === niv4);
    setForm({ ...form, niv4, niv4_desc: sub?.niv4_desc || "" });
  };

  const handleSubmit = async () => {
    if (!form.nombre.trim()) { setMsg("El nombre es obligatorio."); return; }
    setLoading(true);
    try {
      const payload = {
  ...form,
  niv1: parseInt(form.niv1),
  niv2: parseInt(form.niv2),
  niv3: parseInt(form.niv3) || 1,
  niv4: parseInt(form.niv4) || 1,
  niv5: parseInt(form.niv5) || 1,
  cod_cbc: form.cod_cbc ? String(form.cod_cbc) : null,
};
      const url = esNueva ? `${API}/plan_cuentas` : `${API}/plan_cuentas/${parseInt(cuenta.id)}`;
      const method = esNueva ? "POST" : "PUT";
      const r = await fetch(url, {
        method, headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (r.ok) { onGuardado(); onCerrar(); }
      else setMsg("Error al guardar.");
    } catch { setMsg("Error de conexion."); }
    setLoading(false);
  };

  const lbl = { display: "block", fontSize: 13, color: "#374151", marginBottom: 6 };
  const inp = { width: "100%", padding: "8px 12px", border: "1px solid #e2e8f0", borderRadius: 8, fontSize: 14, boxSizing: "border-box" };

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
      <div style={{ background: "white", borderRadius: 12, padding: 32, width: 560, boxShadow: "0 8px 32px rgba(0,0,0,0.2)", maxHeight: "90vh", overflowY: "auto" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
          <div style={{ fontSize: 16, color: "#2c3e50" }}>{esNueva ? "Nueva cuenta" : `Editar — ${cuenta.nombre}`}</div>
          <div onClick={onCerrar} style={{ cursor: "pointer", color: "#94a3b8", fontSize: 20 }}>×</div>
        </div>
        {msg && <div style={{ padding: "10px 16px", borderRadius: 8, marginBottom: 16, background: "#fee2e2", color: "#991b1b" }}>{msg}</div>}

        <div style={{ fontSize: 11, fontWeight: 600, color: "#64748b", textTransform: "uppercase", letterSpacing: 1, marginBottom: 10 }}>Jerarquía</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 }}>
          <div>
            <label style={lbl}>Bloque (niv1)</label>
            <select value={form.niv1} onChange={handleNiv1Change} style={inp}>
              {NIV1_OPCIONES.map(n => <option key={n.niv1} value={n.niv1}>{n.desc}</option>)}
            </select>
          </div>
          <div>
            <label style={lbl}>Subbloque (niv2)</label>
            <select value={form.niv2} onChange={handleNiv2Change} style={inp}>
              {niv2Filtradas.map(n => <option key={n.niv2} value={n.niv2}>{n.desc}</option>)}
            </select>
          </div>
          <div>
            <label style={lbl}>Grupo (niv3)</label>
            <select value={form.niv3} onChange={handleNiv3Change} style={inp}>
              <option value="">— Seleccionar —</option>
              {grupos.map(g => <option key={g.niv3} value={g.niv3}>{g.niv3_desc}</option>)}
            </select>
          </div>
          <div>
            <label style={lbl}>Subgrupo (niv4)</label>
            {subgrupos.length > 0 ? (
              <select value={form.niv4} onChange={handleNiv4Change} style={inp}>
                <option value="">— Sin subgrupo —</option>
                {subgrupos.map(s => <option key={s.niv4} value={s.niv4}>{s.niv4_desc}</option>)}
              </select>
            ) : (
              <div style={{ ...inp, background: "#f8fafc", color: "#94a3b8", display: "flex", alignItems: "center" }}>
                Sin subgrupos en este grupo
              </div>
            )}
          </div>
          <div style={{ gridColumn: "1 / -1" }}>
            <label style={lbl}>Nombre de la cuenta (nivel 5)</label>
            <input type="text" value={form.nombre} onChange={e => setForm({...form, nombre: e.target.value})} style={inp} placeholder="Ej: Costo de Carnes" />
          </div>
          <div>
            <label style={lbl}>Orden niv5</label>
            <input type="number" value={form.niv5} onChange={e => setForm({...form, niv5: parseInt(e.target.value) || 1})} style={inp} min="1" />
          </div>
        </div>

        <div style={{ fontSize: 11, fontWeight: 600, color: "#64748b", textTransform: "uppercase", letterSpacing: 1, marginBottom: 10 }}>Configuración</div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 }}>
          <div>
            <label style={lbl}>Código CBC</label>
            <input type="text" value={form.cod_cbc} onChange={e => setForm({...form, cod_cbc: e.target.value})} style={inp} placeholder="Ej: 1.1.1" />
          </div>
          <div>
            <label style={lbl}>Moneda</label>
            <select value={form.moneda} onChange={e => setForm({...form, moneda: e.target.value})} style={inp}>
              <option value="ARS">ARS</option>
              <option value="USD">USD</option>
            </select>
          </div>
          <div>
            <label style={lbl}>Fondo asociado</label>
            <select value={form.fondo || ""} onChange={e => setForm({...form, fondo: e.target.value})} style={inp}>
              <option value="">— Sin fondo —</option>
              {fondos.map(f => <option key={f.id} value={f.nombre}>{f.nombre}</option>)}
            </select>
          </div>
          <div>
            <label style={lbl}>Signo</label>
            <input type="text" value={form.signo || ""} onChange={e => setForm({...form, signo: e.target.value})} style={inp} placeholder="+ o -" />
          </div>
        </div>

        <div style={{ display: "flex", gap: 24, marginBottom: 24 }}>
          <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 13, color: "#374151" }}>
            <input type="checkbox" checked={!!form.dd} onChange={e => setForm({...form, dd: e.target.checked})} />
            Débito directo (DD)
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer", fontSize: 13, color: "#374151" }}>
            <input type="checkbox" checked={!!form.activo} onChange={e => setForm({...form, activo: e.target.checked})} />
            Activo
          </label>
        </div>

        <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
          <div onClick={onCerrar} style={{ padding: "10px 20px", borderRadius: 8, border: "1px solid #e2e8f0", cursor: "pointer", fontSize: 13, color: "#64748b" }}>Cancelar</div>
          <div onClick={handleSubmit} style={{ padding: "10px 20px", borderRadius: 8, background: "#2c3e50", color: "white", cursor: "pointer", fontSize: 13 }}>
            {loading ? "Guardando..." : "Guardar"}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Admin({ onNavegar }) {
  const [seccion, setSeccion] = useState("titulares");
  const [titulares, setTitulares] = useState([]);
  const [cashflow, setCashflow] = useState([]);
  const [operaciones, setOperaciones] = useState([]);
  const [cuentas, setCuentas] = useState([]);
  const [fondos, setFondos] = useState([]);
  const [buscar, setBuscar] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [msg, setMsg] = useState(null);
  const [modalCuenta, setModalCuenta] = useState(false);

  useEffect(() => {
    fetch(`${API}/fondos`).then(r => r.json()).then(setFondos);
  }, []);

  useEffect(() => {
    if (seccion === "titulares") fetch(`${API}/titulares`).then(r => r.json()).then(setTitulares);
    if (seccion === "cashflow") fetch(`${API}/cashflow`).then(r => r.json()).then(setCashflow);
    if (seccion === "operaciones") fetch(`${API}/operaciones`).then(r => r.json()).then(setOperaciones);
    if (seccion === "plan_cuentas") fetch(`${API}/plan_cuentas`).then(r => r.json()).then(setCuentas);
  }, [seccion]);

  const cargarCuentas = () => fetch(`${API}/plan_cuentas`).then(r => r.json()).then(setCuentas);

  const eliminar = async (endpoint, id) => {
    try {
      const r = await fetch(`${API}/${endpoint}/${id}`, { method: "DELETE" });
      if (r.ok) {
        setMsg({ tipo: "ok", texto: "Eliminado correctamente" });
        setConfirmDelete(null);
        if (seccion === "titulares") fetch(`${API}/titulares`).then(r => r.json()).then(setTitulares);
        if (seccion === "cashflow") fetch(`${API}/cashflow`).then(r => r.json()).then(setCashflow);
        if (seccion === "operaciones") fetch(`${API}/operaciones`).then(r => r.json()).then(setOperaciones);
        if (seccion === "plan_cuentas") cargarCuentas();
      } else {
        setMsg({ tipo: "error", texto: "Error al eliminar" });
      }
    } catch {
      setMsg({ tipo: "error", texto: "Error de conexion" });
    }
    setTimeout(() => setMsg(null), 3000);
  };

  const td = { padding: "9px 14px", fontSize: 13, color: "#374151" };
  const SECCIONES = ["titulares", "cashflow", "operaciones", "plan_cuentas"];

  const titularesFiltrados = titulares
    .filter(t => t.nivel1 !== "SISTEMA")
    .filter(t => t.nombre?.toLowerCase().includes(buscar.toLowerCase()) || t.id?.toString().includes(buscar));

  const cashflowFiltrados = cashflow
    .filter(m => m.titular?.toLowerCase().includes(buscar.toLowerCase()) || m.detalle?.toLowerCase().includes(buscar.toLowerCase()));

  const operacionesFiltradas = operaciones
    .filter(o => o.titular?.toLowerCase().includes(buscar.toLowerCase()) || o.concepto?.toLowerCase().includes(buscar.toLowerCase()));

  const cuentasFiltradas = cuentas
    .filter(c => c.nombre?.toLowerCase().includes(buscar.toLowerCase()) ||
                 c.niv2_desc?.toLowerCase().includes(buscar.toLowerCase()) ||
                 c.niv3_desc?.toLowerCase().includes(buscar.toLowerCase()));

  const cuentasAgrupadas = cuentasFiltradas.reduce((acc, c) => {
    const k1 = c.niv1_desc || "—";
    const k2 = c.niv2_desc || "—";
    const k3 = c.niv3_desc || "—";
    if (!acc[k1]) acc[k1] = {};
    if (!acc[k1][k2]) acc[k1][k2] = {};
    if (!acc[k1][k2][k3]) acc[k1][k2][k3] = [];
    acc[k1][k2][k3].push(c);
    return acc;
  }, {});

  return (
    <div>
      {confirmDelete && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
          <div style={{ background: "white", borderRadius: 12, padding: 32, width: 380, boxShadow: "0 8px 32px rgba(0,0,0,0.2)" }}>
            <div style={{ fontSize: 16, color: "#2c3e50", marginBottom: 12 }}>¿Confirmar eliminación?</div>
            <div style={{ fontSize: 13, color: "#64748b", marginBottom: 24 }}>{confirmDelete.descripcion}</div>
            <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
              <div onClick={() => setConfirmDelete(null)} style={{ padding: "8px 20px", borderRadius: 8, border: "1px solid #e2e8f0", cursor: "pointer", fontSize: 13, color: "#64748b" }}>Cancelar</div>
              <div onClick={() => eliminar(confirmDelete.endpoint, confirmDelete.id)}
                style={{ padding: "8px 20px", borderRadius: 8, background: "#e00000", color: "white", cursor: "pointer", fontSize: 13 }}>
                Eliminar
              </div>
            </div>
          </div>
        </div>
      )}

      {modalCuenta !== false && (
        <ModalCuenta
          cuenta={modalCuenta === true ? null : modalCuenta}
          fondos={fondos}
          onCerrar={() => setModalCuenta(false)}
          onGuardado={cargarCuentas}
        />
      )}

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <div style={{ fontSize: 18, color: "#2c3e50", fontWeight: 500 }}>Panel de Administración</div>
        <div onClick={() => onNavegar("Inicio")} style={{ fontSize: 13, color: "#2e6da4", cursor: "pointer" }}>← Inicio</div>
      </div>

      {msg && (
        <div style={{ padding: "10px 16px", borderRadius: 8, marginBottom: 16, background: msg.tipo === "ok" ? "#d1fae5" : "#fee2e2", color: msg.tipo === "ok" ? "#065f46" : "#991b1b" }}>
          {msg.texto}
        </div>
      )}

      <div style={{ display: "flex", gap: 4, marginBottom: 16, borderBottom: "1px solid #9CB7D8" }}>
        {SECCIONES.map(s => (
          <div key={s} onClick={() => { setSeccion(s); setBuscar(""); }}
            style={{ padding: "10px 20px", cursor: "pointer", fontSize: 13,
              borderBottom: seccion === s ? "2px solid #2e6da4" : "2px solid transparent",
              color: seccion === s ? "#2e6da4" : "#64748b" }}>
            {s === "plan_cuentas" ? "Plan de Cuentas" : s.charAt(0).toUpperCase() + s.slice(1)}
          </div>
        ))}
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <input value={buscar} onChange={e => setBuscar(e.target.value)}
          placeholder="Buscar..."
          style={{ padding: "8px 12px", border: "1px solid #e2e8f0", borderRadius: 8, fontSize: 14, width: 300 }} />
        {seccion === "plan_cuentas" && (
          <div onClick={() => setModalCuenta(true)}
            style={{ padding: "8px 18px", background: "#2c3e50", color: "white", borderRadius: 8, cursor: "pointer", fontSize: 13 }}>
            + Nueva cuenta
          </div>
        )}
      </div>

      {seccion === "titulares" && (
        <div style={{ borderRadius: 8, border: "1px solid #9CB7D8", overflow: "auto", maxHeight: "calc(100vh - 280px)" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead style={{ position: "sticky", top: 0, zIndex: 9 }}>
              <tr style={{ background: "#d4dfe6" }}>
                {["ID", "Nombre", "Tipo", "CUIT", "Activo", ""].map(h => (
                  <th key={h} style={{ padding: "9px 14px", textAlign: "left", fontSize: 11, fontWeight: 600, color: "#2c3e50", textTransform: "uppercase", letterSpacing: 1 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {titularesFiltrados.map((t, i) => (
                <tr key={i} style={{ borderTop: "1px solid #DEE7F2", background: "white" }}>
                  <td style={{ ...td, fontSize: 11, color: "#94a3b8", fontFamily: "monospace" }}>{t.id}</td>
                  <td style={{ ...td, fontWeight: 500 }}>{t.nombre}</td>
                  <td style={{ ...td, fontSize: 12, color: "#64748b" }}>{t.tipo_titular}</td>
                  <td style={{ ...td, fontSize: 12, color: "#64748b" }}>{t.cuit || "—"}</td>
                  <td style={td}>{t.activo ? <span style={{ color: "#059669" }}>✓</span> : <span style={{ color: "#e00000" }}>✗</span>}</td>
                  <td style={{ padding: "9px 14px", textAlign: "right" }}>
                    <div onClick={() => setConfirmDelete({ id: t.id, endpoint: "titulares", descripcion: `Eliminar titular: ${t.nombre}` })}
                      style={{ fontSize: 12, color: "#e00000", cursor: "pointer" }}>Eliminar</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {seccion === "cashflow" && (
        <div style={{ borderRadius: 8, border: "1px solid #9CB7D8", overflow: "auto", maxHeight: "calc(100vh - 280px)" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead style={{ position: "sticky", top: 0, zIndex: 9 }}>
              <tr style={{ background: "#d4dfe6" }}>
                {["ID", "Fecha", "Titular", "Detalle", "Importe", "Fondo", ""].map(h => (
                  <th key={h} style={{ padding: "9px 14px", textAlign: "left", fontSize: 11, fontWeight: 600, color: "#2c3e50", textTransform: "uppercase", letterSpacing: 1 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {cashflowFiltrados.map((m, i) => (
                <tr key={i} style={{ borderTop: "1px solid #DEE7F2", background: "white" }}>
                  <td style={{ ...td, fontSize: 11, color: "#94a3b8" }}>{m.id}</td>
                  <td style={{ ...td, fontSize: 12 }}>{m.fecha?.slice(0,10)}</td>
                  <td style={td}>{m.titular}</td>
                  <td style={td}>{m.detalle}</td>
                  <td style={{ ...td, color: m.importe >= 0 ? "#2c3e50" : "#e00000" }}>
                    ${parseFloat(m.importe).toLocaleString("es-AR", {minimumFractionDigits: 2})}
                  </td>
                  <td style={{ ...td, fontSize: 12, color: "#64748b" }}>{m.fondo}</td>
                  <td style={{ padding: "9px 14px", textAlign: "right" }}>
                    <div onClick={() => setConfirmDelete({ id: m.id, endpoint: "cashflow", descripcion: `Eliminar movimiento: ${m.detalle} — ${m.titular}` })}
                      style={{ fontSize: 12, color: "#e00000", cursor: "pointer" }}>Eliminar</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {seccion === "operaciones" && (
        <div style={{ borderRadius: 8, border: "1px solid #9CB7D8", overflow: "auto", maxHeight: "calc(100vh - 280px)" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead style={{ position: "sticky", top: 0, zIndex: 9 }}>
              <tr style={{ background: "#d4dfe6" }}>
                {["ID", "Fecha", "Titular", "Concepto", "Importe", "Estado", ""].map(h => (
                  <th key={h} style={{ padding: "9px 14px", textAlign: "left", fontSize: 11, fontWeight: 600, color: "#2c3e50", textTransform: "uppercase", letterSpacing: 1 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {operacionesFiltradas.map((o, i) => (
                <tr key={i} style={{ borderTop: "1px solid #DEE7F2", background: "white" }}>
                  <td style={{ ...td, fontSize: 11, color: "#94a3b8" }}>{o.id}</td>
                  <td style={{ ...td, fontSize: 12 }}>{o.fecha?.slice(0,10)}</td>
                  <td style={td}>{o.titular}</td>
                  <td style={td}>{o.concepto}</td>
                  <td style={{ ...td, color: "#2c3e50" }}>${parseFloat(o.importe).toLocaleString("es-AR", {minimumFractionDigits: 2})}</td>
                  <td style={td}>
                    <span style={{ padding: "2px 8px", borderRadius: 20, fontSize: 11,
                      background: o.estado === "IMPAGO" ? "#fee2e2" : "#d1fae5",
                      color: o.estado === "IMPAGO" ? "#991b1b" : "#065f46" }}>
                      {o.estado}
                    </span>
                  </td>
                  <td style={{ padding: "9px 14px", textAlign: "right" }}>
                    <div onClick={() => setConfirmDelete({ id: o.id, endpoint: "operaciones", descripcion: `Eliminar comprobante: ${o.concepto} — ${o.titular}` })}
                      style={{ fontSize: 12, color: "#e00000", cursor: "pointer" }}>Eliminar</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {seccion === "plan_cuentas" && (
        <div style={{ overflow: "auto", maxHeight: "calc(100vh - 280px)" }}>
          {Object.entries(cuentasAgrupadas).map(([bloque, subbloques]) => (
            <div key={bloque} style={{ marginBottom: 28 }}>
              <div style={{ fontSize: 13, fontWeight: 700, textTransform: "uppercase", letterSpacing: 1, marginBottom: 12, padding: "8px 14px", background: "#2c3e50", color: "white", borderRadius: 6 }}>
                {bloque}
              </div>
              {Object.entries(subbloques).map(([subbloque, grupos]) => (
                <div key={subbloque} style={{ marginBottom: 16, marginLeft: 8 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: "#2c3e50", textTransform: "uppercase", letterSpacing: 1, marginBottom: 8, padding: "6px 14px", background: "#d4dfe6", borderRadius: 6 }}>
                    {subbloque}
                  </div>
                  {Object.entries(grupos).map(([grupo, cuentasGrupo]) => (
                    <div key={grupo} style={{ marginBottom: 12, marginLeft: 8 }}>
                      {grupo !== "—" && (
                        <div style={{ fontSize: 11, fontWeight: 600, color: "#64748b", textTransform: "uppercase", letterSpacing: 1, marginBottom: 6, padding: "4px 14px", background: "#f1f5f9", borderRadius: 4 }}>
                          {grupo}
                        </div>
                      )}
                      <div style={{ borderRadius: 8, border: "1px solid #9CB7D8", overflow: "hidden", marginLeft: grupo !== "—" ? 8 : 0 }}>
                        <table style={{ width: "100%", borderCollapse: "collapse" }}>
                          <thead>
                            <tr style={{ background: "#f8fafc" }}>
                              <th style={{ padding: "7px 14px", textAlign: "left", fontSize: 10, fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", letterSpacing: 1, width: 50 }}>ID</th>
                              <th style={{ padding: "7px 14px", textAlign: "left", fontSize: 10, fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", letterSpacing: 1 }}>Cuenta</th>
                              <th style={{ padding: "7px 14px", textAlign: "left", fontSize: 10, fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", letterSpacing: 1 }}>Subgrupo</th>
                              <th style={{ padding: "7px 14px", textAlign: "left", fontSize: 10, fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", letterSpacing: 1 }}>Fondo</th>
                              <th style={{ padding: "7px 14px", textAlign: "left", fontSize: 10, fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", letterSpacing: 1, width: 40 }}>DD</th>
                              <th style={{ padding: "7px 14px", textAlign: "left", fontSize: 10, fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", letterSpacing: 1, width: 40 }}>Act</th>
                              <th style={{ width: 120 }}></th>
                            </tr>
                          </thead>
                          <tbody>
                            {cuentasGrupo.map((c, i) => (
                              <tr key={i} style={{ borderTop: i > 0 ? "1px solid #DEE7F2" : "none", background: "white" }}>
                                <td style={{ ...td, fontSize: 11, color: "#94a3b8", fontFamily: "monospace" }}>{c.id}</td>
                                <td style={{ ...td, fontWeight: 500 }}>{c.nombre}</td>
                                <td style={{ ...td, fontSize: 12, color: "#64748b" }}>{c.niv4_desc || <span style={{ color: "#cbd5e1" }}>—</span>}</td>
                                <td style={{ ...td, fontSize: 12, color: "#64748b" }}>{c.fondo || <span style={{ color: "#cbd5e1" }}>—</span>}</td>
                                <td style={{ ...td, fontSize: 12 }}>{c.dd ? <span style={{ color: "#059669" }}>✓</span> : <span style={{ color: "#cbd5e1" }}>—</span>}</td>
                                <td style={{ ...td, fontSize: 12 }}>{c.activo ? <span style={{ color: "#059669" }}>✓</span> : <span style={{ color: "#e00000" }}>✗</span>}</td>
                                <td style={{ padding: "9px 14px", textAlign: "right" }}>
                                  <div style={{ display: "flex", gap: 16, justifyContent: "flex-end" }}>
                                    <div onClick={() => setModalCuenta(c)} style={{ fontSize: 12, color: "#2e6da4", cursor: "pointer" }}>Editar</div>
                                    <div onClick={() => setConfirmDelete({ id: c.id, endpoint: "plan_cuentas", descripcion: `Eliminar cuenta: ${c.nombre}` })}
                                      style={{ fontSize: 12, color: "#e00000", cursor: "pointer" }}>Eliminar</div>
                                  </div>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
