/* ============================================================
   ZARIS — Módulo Agenda
   ============================================================ */

'use strict';

// ── Sesión y constantes ─────────────────────────────────────
const session = JSON.parse(localStorage.getItem('zaris_session') || 'null');
if (!session) window.location.href = 'menu.html';

const nivelAcceso = session.nivel_acceso;
const API_BASE    = 'https://zaris-api-production-bf0b.up.railway.app/api/v1/agenda';
const API_BUC     = 'https://zaris-api-production-bf0b.up.railway.app/api/v1/buc';

const authHeaders = () => ({
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${session.token}`,
});

// ── Helpers de bitmask ──────────────────────────────────────
const diasToBitmask = (dias) => dias.reduce((acc, val, i) => acc | (val ? 1 << i : 0), 0);
const bitmaskToDias = (mask) => Array.from({ length: 7 }, (_, i) => !!(mask & (1 << i)));
const DIAS_LABEL = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];

// ── Estado global ───────────────────────────────────────────
let vistaActual = 'mes';   // mes | semana | dia
let capaActual  = 'AGENTES';
let hoy         = new Date();
let navDate     = new Date(hoy);  // fecha de navegación actual
let areas       = [];
let clases      = [];
let usuarios    = [];
let servicios   = [];
let lugares     = [];

// ── API helper ──────────────────────────────────────────────
async function apiFetch(path, opts = {}) {
    const url = path.startsWith('http') ? path : API_BASE + path;
    const res = await fetch(url, { ...opts, headers: { ...authHeaders(), ...(opts.headers || {}) } });
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
}

async function bucFetch(path) {
    const res = await fetch(API_BUC + path, { headers: authHeaders() });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
}

// ── Formato de fechas ───────────────────────────────────────
const fmtFecha  = (d) => new Date(d + 'T00:00:00').toLocaleDateString('es-AR');
const fmtHora   = (t) => t ? t.slice(0, 5) : '';
const padDate   = (d) => {
    const dt = d instanceof Date ? d : new Date(d);
    const y = dt.getFullYear();
    const m = String(dt.getMonth() + 1).padStart(2, '0');
    const dd = String(dt.getDate()).padStart(2, '0');
    return `${y}-${m}-${dd}`;
};

// ── Init ────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
    document.getElementById('headerUsuario').textContent = session.nombre || session.username || '';

    if (nivelAcceso >= 4) {
        document.querySelector('.z-tab--admin').style.display = '';
    }

    // Tabs
    document.getElementById('mainTabs').addEventListener('click', (e) => {
        const btn = e.target.closest('[data-tab]');
        if (!btn) return;
        activarTab(btn.dataset.tab);
    });

    document.getElementById('adminSubtabs').addEventListener('click', (e) => {
        const btn = e.target.closest('[data-sub]');
        if (!btn) return;
        activarSubTab(btn.dataset.sub);
    });

    await Promise.all([loadAreas(), loadClases(), loadUsuarios()]).catch(console.error);
    poblarFiltrosArea();
    loadAlertasBadge();
    recargarCalendario();
});

// ── Tabs ────────────────────────────────────────────────────
function activarTab(tab) {
    document.querySelectorAll('.z-tab').forEach(b => b.classList.remove('z-tab--active'));
    document.querySelector(`[data-tab="${tab}"]`).classList.add('z-tab--active');
    ['calendario', 'mis-turnos', 'alertas', 'admin'].forEach(id => {
        document.getElementById(`sec-${id}`).hidden = id !== tab;
    });
    if (tab === 'alertas')    loadAlertas();
    if (tab === 'mis-turnos') loadMisTurnos();
    if (tab === 'admin')      initAdmin();
}

function activarSubTab(sub) {
    document.querySelectorAll('#adminSubtabs .z-subtab').forEach(b => b.classList.remove('z-subtab--active'));
    document.querySelector(`[data-sub="${sub}"]`).classList.add('z-subtab--active');
    ['agendas-agentes','agendas-servicios','agendas-lugares','catalogos','ausencias'].forEach(id => {
        document.getElementById(`sub-${id}`).hidden = id !== sub;
    });
    if (sub === 'agendas-agentes')   loadAgendasAgentes();
    if (sub === 'agendas-servicios') loadAgendasServicios();
    if (sub === 'agendas-lugares')   loadAgendasLugares();
    if (sub === 'catalogos')         setCatalogo('servicios');
    if (sub === 'ausencias')         { loadAusencias(); poblarSelectUsuarios('ausIdUsuario'); }
}

// ── Carga de datos base ─────────────────────────────────────
async function loadAreas() {
    areas = await apiFetch('/areas');
}

async function loadClases() {
    clases = await apiFetch('/clases');
}

async function loadUsuarios() {
    usuarios = await bucFetch('/usuarios');
}

async function loadServicios() {
    servicios = await apiFetch('/servicios');
}

async function loadLugares() {
    lugares = await apiFetch('/lugares');
}

function poblarFiltrosArea() {
    const selects = ['filtroArea', 'filtroAAArea'];
    areas.forEach(a => {
        selects.forEach(id => {
            const s = document.getElementById(id);
            if (!s) return;
            const opt = document.createElement('option');
            opt.value = a.id;
            opt.textContent = a.nombre;
            s.appendChild(opt);
        });
    });
}

function poblarSelectGenerico(selectId, items, valKey = 'id', labelFn = (i) => i.nombre) {
    const s = document.getElementById(selectId);
    if (!s) return;
    s.innerHTML = '<option value="">Seleccionar...</option>';
    items.forEach(i => {
        const opt = document.createElement('option');
        opt.value = i[valKey];
        opt.textContent = labelFn(i);
        s.appendChild(opt);
    });
}

function poblarSelectUsuarios(selectId) {
    poblarSelectGenerico(selectId, usuarios.filter(u => u.activo), 'id_usuario',
        u => `${u.nombre} (${u.username})`);
}

// ════════════════════════════════════════════════════════════
// CALENDARIO
// ════════════════════════════════════════════════════════════

function setVista(vista) {
    vistaActual = vista;
    ['mes','semana','dia'].forEach(v => {
        const btn = document.getElementById(`btnVista${v.charAt(0).toUpperCase() + v.slice(1)}`);
        if (btn) btn.classList.toggle('z-cal-btn--active', v === vista);
    });
    recargarCalendario();
}

function setCapa(capa) {
    capaActual = capa;
    ['Agentes','Servicios','Lugares'].forEach(c => {
        const btn = document.getElementById(`btnCapa${c}`);
        if (btn) btn.classList.toggle('z-cal-btn--active', c.toUpperCase() === capa);
    });
    recargarCalendario();
}

function navegarAnterior() {
    if (vistaActual === 'mes')    navDate.setMonth(navDate.getMonth() - 1);
    if (vistaActual === 'semana') navDate.setDate(navDate.getDate() - 7);
    if (vistaActual === 'dia')    navDate.setDate(navDate.getDate() - 1);
    recargarCalendario();
}

function navegarSiguiente() {
    if (vistaActual === 'mes')    navDate.setMonth(navDate.getMonth() + 1);
    if (vistaActual === 'semana') navDate.setDate(navDate.getDate() + 7);
    if (vistaActual === 'dia')    navDate.setDate(navDate.getDate() + 1);
    recargarCalendario();
}

function navegarHoy() {
    navDate = new Date(hoy);
    recargarCalendario();
}

async function recargarCalendario() {
    const container = document.getElementById('calContainer');
    container.innerHTML = '';
    actualizarLabel();
    const idArea = document.getElementById('filtroArea').value || undefined;

    try {
        if (vistaActual === 'mes')    await renderMes(idArea);
        if (vistaActual === 'semana') await renderSemana(idArea);
        if (vistaActual === 'dia')    await renderDia(padDate(navDate), idArea);
    } catch (e) {
        console.warn('Agenda calendar:', e.message);
    }
}

function actualizarLabel() {
    const meses = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'];
    const anio = navDate.getFullYear();
    const mes  = navDate.getMonth();
    if (vistaActual === 'mes') {
        document.getElementById('calLabel').textContent = `${meses[mes]} ${anio}`;
    } else if (vistaActual === 'dia') {
        document.getElementById('calLabel').textContent = new Date(navDate)
            .toLocaleDateString('es-AR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
    } else {
        const lunes = new Date(navDate);
        lunes.setDate(navDate.getDate() - (navDate.getDay() + 6) % 7);
        const domingo = new Date(lunes);
        domingo.setDate(lunes.getDate() + 6);
        document.getElementById('calLabel').textContent = `${fmtFecha(padDate(lunes))} – ${fmtFecha(padDate(domingo))}`;
    }
}

// ── Vista Mes ────────────────────────────────────────────────
async function renderMes(idArea) {
    const anio = navDate.getFullYear();
    const mes  = navDate.getMonth() + 1;

    let diasData;
    try {
        const params = new URLSearchParams({ anio, mes, capa: capaActual });
        if (idArea) params.set('id_area', idArea);
        const data = await apiFetch(`/calendario/mes?${params}`);
        diasData = data.dias;
    } catch (_) {
        // Sin datos: generar días vacíos igual para mostrar el calendario
        const totalDias = new Date(anio, mes, 0).getDate();
        diasData = Array.from({ length: totalDias }, (_, i) => ({
            fecha: `${anio}-${String(mes).padStart(2,'0')}-${String(i+1).padStart(2,'0')}`,
            es_feriado: false, feriado_descripcion: null,
            slots_totales: 0, slots_ocupados: 0, estado: 'fuera',
        }));
    }

    // Calcular offset del primer día (0=Lun)
    const primerDia = new Date(anio, mes - 1, 1).getDay();
    const offset = (primerDia + 6) % 7;

    let html = `<div class="z-cal-mes">
        <div class="z-cal-mes__header">
            ${DIAS_LABEL.map(d => `<div class="z-cal-mes__dow">${d}</div>`).join('')}
        </div>
        <div class="z-cal-mes__grid">`;

    // Celdas previas
    for (let i = 0; i < offset; i++) {
        html += `<div class="z-cal-mes__cell z-cal-mes__cell--otro-mes"></div>`;
    }

    diasData.forEach(dia => {
        const numDia = parseInt(dia.fecha.slice(8));
        const estado = dia.estado;
        let info = '';
        if (dia.es_feriado) {
            info = `<div class="z-cal-mes__info" style="color:var(--z-cal-feriado)">${dia.feriado_descripcion}</div>`;
        } else if (dia.slots_totales > 0) {
            info = `<div class="z-cal-mes__info">${dia.slots_ocupados}/${dia.slots_totales} turnos</div>`;
        }
        const colorDot = {
            disponible: 'var(--z-cal-disponible)',
            parcial:    'var(--z-cal-parcial)',
            ocupado:    'var(--z-cal-ocupado)',
            feriado:    'var(--z-cal-feriado)',
            fuera:      'var(--z-cal-fuera)',
        }[estado] || '#ccc';

        html += `<div class="z-cal-mes__cell z-cal-mes__cell--${estado}"
                      onclick="irADia('${dia.fecha}')">
            <div class="z-cal-mes__num">
                <span class="z-cal-mes__dot" style="background:${colorDot}"></span>${numDia}
            </div>
            ${info}
        </div>`;
    });

    // Completar grid hasta múltiplo de 7
    const total = offset + diasData.length;
    const resto = total % 7 === 0 ? 0 : 7 - (total % 7);
    for (let i = 0; i < resto; i++) {
        html += `<div class="z-cal-mes__cell z-cal-mes__cell--otro-mes"></div>`;
    }

    html += `</div></div>`;
    document.getElementById('calContainer').innerHTML = html;
}

function irADia(fecha) {
    vistaActual = 'dia';
    navDate = new Date(fecha + 'T00:00:00');
    ['mes','semana','dia'].forEach(v => {
        const btn = document.getElementById(`btnVista${v.charAt(0).toUpperCase() + v.slice(1)}`);
        if (btn) btn.classList.toggle('z-cal-btn--active', v === 'dia');
    });
    recargarCalendario();
}

// ── Vista Día ─────────────────────────────────────────────────
async function renderDia(fecha, idArea) {
    const params = new URLSearchParams({ fecha, capa: capaActual });
    if (idArea) params.set('id_area', idArea);

    let data = { es_feriado: false, feriado_descripcion: null, slots: [] };
    try {
        data = await apiFetch(`/calendario/dia?${params}`);
    } catch (_) { /* sin datos, mostrar día vacío */ }

    let feriadoTag = '';
    if (data.es_feriado) {
        feriadoTag = `<span class="z-cal-dia__feriado-tag">Feriado: ${data.feriado_descripcion}</span>`;
    }

    let slotsHtml = '';
    if (!data.slots.length) {
        slotsHtml = `<div class="z-cal-dia__empty">No hay agenda configurada para este día y capa.</div>`;
    } else {
        slotsHtml = data.slots.map(s => {
            const label = `${fmtHora(s.hora_inicio)} – ${fmtHora(s.hora_fin)}`;
            if (s.es_feriado) {
                return `<div class="z-slot z-slot--feriado">${label}</div>`;
            }
            if (!s.disponible) {
                return `<div class="z-slot z-slot--ocupado" title="${s.turnos_count} turno(s)">${label} ✗</div>`;
            }
            return `<div class="z-slot z-slot--libre"
                        onclick="abrirModalTurno('${fecha}','${s.hora_inicio}','${s.hora_fin}')"
                        title="Click para reservar">${label}</div>`;
        }).join('');
    }

    document.getElementById('calContainer').innerHTML = `
        <div class="z-cal-dia">
            <div class="z-cal-dia__header">
                <span>${document.getElementById('calLabel').textContent}</span>
                ${feriadoTag}
            </div>
            <div class="z-cal-dia__slots">${slotsHtml}</div>
        </div>`;
}

// ── Vista Semana ──────────────────────────────────────────────
async function renderSemana(idArea) {
    // Ir al lunes de la semana actual
    const lunes = new Date(navDate);
    const dow = (navDate.getDay() + 6) % 7;
    lunes.setDate(navDate.getDate() - dow);

    const params = new URLSearchParams({ fecha_inicio: padDate(lunes), capa: capaActual });
    if (idArea) params.set('id_area', idArea);
    const data = await apiFetch(`/calendario/semana?${params}`);

    const domingo = new Date(lunes);
    domingo.setDate(lunes.getDate() + 6);
    document.getElementById('calLabel').textContent =
        `${fmtFecha(padDate(lunes))} – ${fmtFecha(padDate(domingo))}`;

    const horasRango = Array.from({ length: 32 }, (_, i) => {
        const h = Math.floor(i / 2) + 6;
        const m = i % 2 === 0 ? '00' : '30';
        return `${String(h).padStart(2,'0')}:${m}`;
    });

    // Construir set de slots ocupados por día-hora
    const ocupados = {};
    const feriados = {};
    data.dias.forEach((dia, idx) => {
        const fechaKey = dia.fecha;
        if (dia.es_feriado) feriados[fechaKey] = true;
        dia.slots.forEach(s => {
            if (!s.disponible) {
                const key = `${idx}-${s.hora_inicio.slice(0,5)}`;
                ocupados[key] = true;
            }
        });
    });

    const headers = data.dias.map((dia, i) => {
        const d = new Date(dia.fecha + 'T00:00:00');
        const label = d.toLocaleDateString('es-AR', { weekday: 'short', day: 'numeric', month: 'short' });
        return `<div class="z-cal-semana__header">${label}</div>`;
    });

    const rows = horasRango.map(hora => {
        const cells = data.dias.map((dia, idx) => {
            const isFeriado = feriados[dia.fecha];
            const isOcupado = ocupados[`${idx}-${hora}`];
            let cls = 'z-cal-semana__cell';
            if (isFeriado) cls += ' z-cal-semana__cell--feriado';
            else if (isOcupado) cls += ' z-cal-semana__cell--ocupado';
            const onclick = (!isFeriado && !isOcupado && nivelAcceso >= 2)
                ? `onclick="abrirModalTurno('${dia.fecha}','${hora}:00','${hora}:00')"` : '';
            return `<div class="${cls}" ${onclick}></div>`;
        }).join('');
        return `<div class="z-cal-semana__hora">${hora}</div>${cells}`;
    });

    document.getElementById('calContainer').innerHTML = `
        <div class="z-cal-semana">
            <div class="z-cal-semana__grid">
                <div class="z-cal-semana__header"></div>
                ${headers.join('')}
                ${rows.join('')}
            </div>
        </div>`;
}

// ════════════════════════════════════════════════════════════
// MIS TURNOS
// ════════════════════════════════════════════════════════════

async function loadMisTurnos() {
    const container = document.getElementById('misTurnosContainer');
    container.innerHTML = '<div class="z-agenda-loading">Cargando...</div>';
    try {
        const turnos = await apiFetch(`/turnos?reservado_por=${session.id}&limit=100`);
        if (turnos.length === 0) {
            container.innerHTML = '<p style="color:var(--z-text3);padding:1rem">No tenés turnos registrados.</p>';
            return;
        }
        container.innerHTML = `<table class="z-table">
            <thead><tr>
                <th>Fecha</th><th>Horario</th><th>Tipo</th><th>Estado</th><th>Observaciones</th><th></th>
            </tr></thead>
            <tbody>
            ${turnos.map(t => `
                <tr class="${t.estado === 'CANCELADO' ? 'z-tr--inactivo' : ''}">
                    <td>${fmtFecha(t.fecha)}</td>
                    <td style="font-family:var(--z-font-mono)">${fmtHora(t.hora_inicio)} – ${fmtHora(t.hora_fin)}</td>
                    <td>${t.tipo_agenda}</td>
                    <td><span class="z-badge">${t.estado}</span></td>
                    <td>${t.observaciones || '—'}</td>
                    <td>${['RESERVADO','CONFIRMADO'].includes(t.estado)
                        ? `<button class="z-btn z-btn--danger z-btn--sm" onclick="cancelarTurno(${t.id})">Cancelar</button>`
                        : ''}</td>
                </tr>`).join('')}
            </tbody>
        </table>`;
    } catch (e) {
        container.innerHTML = `<p style="color:var(--z-text-error);padding:1rem">Error: ${e.message}</p>`;
    }
}

async function cancelarTurno(id) {
    if (!confirm('¿Cancelar este turno?')) return;
    try {
        await apiFetch(`/turnos/${id}/cancelar`, { method: 'PATCH' });
        loadMisTurnos();
    } catch (e) {
        alert('Error al cancelar: ' + e.message);
    }
}

// ════════════════════════════════════════════════════════════
// ALERTAS
// ════════════════════════════════════════════════════════════

async function loadAlertasBadge() {
    try {
        const alertas = await apiFetch('/alertas?resuelta=false&limit=200');
        const badge = document.getElementById('alertasBadge');
        badge.textContent = alertas.length > 0 ? String(alertas.length) : '';
    } catch (e) { /* silencioso */ }
}

async function loadAlertas() {
    const container = document.getElementById('alertasContainer');
    container.innerHTML = '<div class="z-agenda-loading">Cargando...</div>';
    const tipo = document.getElementById('filtroAlertaTipo').value;
    const mostrarResueltas = document.getElementById('filtroAlertaResuelta').checked;
    const params = new URLSearchParams({ limit: 100 });
    if (tipo) params.set('tipo_alerta', tipo);
    if (!mostrarResueltas) params.set('resuelta', 'false');

    try {
        const alertas = await apiFetch(`/alertas?${params}`);
        if (alertas.length === 0) {
            container.innerHTML = '<p style="color:var(--z-text3);padding:1rem">No hay alertas.</p>';
            return;
        }
        container.innerHTML = `<table class="z-table">
            <thead><tr>
                <th>Tipo</th><th>Descripción</th><th>Período</th><th>Estado</th>${nivelAcceso >= 4 ? '<th></th>' : ''}
            </tr></thead>
            <tbody>
            ${alertas.map(a => `
                <tr class="${a.resuelta ? 'z-alerta-resuelta' : ''}">
                    <td><span class="z-alerta-tipo z-alerta-tipo--${a.tipo_alerta}">${a.tipo_alerta.replace(/_/g,' ')}</span></td>
                    <td style="font-size:0.85rem">${a.descripcion}</td>
                    <td style="font-family:var(--z-font-mono);font-size:0.82rem">
                        ${a.fecha_desde ? `${fmtFecha(a.fecha_desde)} – ${fmtFecha(a.fecha_hasta)}` : '—'}
                    </td>
                    <td>${a.resuelta
                        ? `<span class="z-badge z-badge--success">Resuelta</span>`
                        : `<span class="z-badge z-badge--danger">Pendiente</span>`}
                    </td>
                    ${nivelAcceso >= 4 ? `<td>${!a.resuelta
                        ? `<button class="z-btn z-btn--sm" onclick="resolverAlerta(${a.id})">Resolver</button>`
                        : ''}</td>` : ''}
                </tr>`).join('')}
            </tbody>
        </table>`;
    } catch (e) {
        container.innerHTML = `<p style="color:var(--z-text-error);padding:1rem">Error: ${e.message}</p>`;
    }
}

async function resolverAlerta(id) {
    if (!confirm('¿Marcar esta alerta como resuelta?')) return;
    try {
        await apiFetch(`/alertas/${id}/resolver`, { method: 'PATCH' });
        loadAlertas();
        loadAlertasBadge();
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

// ════════════════════════════════════════════════════════════
// MODAL NUEVO TURNO
// ════════════════════════════════════════════════════════════

function abrirModalTurno(fecha, horaInicio, horaFin) {
    if (nivelAcceso < 2) return;
    document.getElementById('turnoFecha').value = fecha;
    document.getElementById('turnoHorario').value = `${fmtHora(horaInicio)} – ${fmtHora(horaFin)}`;
    document.getElementById('turnoHoraInicio').value = horaInicio;
    document.getElementById('turnoHoraFin').value = horaFin;
    document.getElementById('turnoTipoAgenda').value = capaActual.slice(0, -1); // AGENTES→AGENTE
    document.getElementById('turnoIdCiudadano').value = '';
    document.getElementById('turnoCiudadanoQ').value = '';
    document.getElementById('turnoObs').value = '';
    document.getElementById('turnoError').style.display = 'none';
    document.getElementById('modalTurno').hidden = false;
}

function cerrarModalTurno() {
    document.getElementById('modalTurno').hidden = true;
}

let _buscarTimeout = null;
function buscarCiudadanoTurno(q) {
    clearTimeout(_buscarTimeout);
    const res = document.getElementById('turnoCiudadanoResultados');
    if (q.length < 2) { res.style.display = 'none'; return; }
    _buscarTimeout = setTimeout(async () => {
        try {
            const items = await fetch(`${API_BUC}/ciudadanos/buscar?q=${encodeURIComponent(q)}&limit=8`,
                { headers: authHeaders() }).then(r => r.json());
            if (!items.length) { res.style.display = 'none'; return; }
            res.style.display = 'block';
            res.innerHTML = items.map(c =>
                `<div style="padding:6px 10px;cursor:pointer;font-size:0.85rem;border-bottom:1px solid var(--z-border)"
                    onmousedown="seleccionarCiudadano(${c.id_ciudadano},'${c.apellido}, ${c.nombre}')">
                    ${c.apellido}, ${c.nombre} — ${c.cuil}
                </div>`
            ).join('');
        } catch (e) { res.style.display = 'none'; }
    }, 300);
}

function seleccionarCiudadano(id, nombre) {
    document.getElementById('turnoIdCiudadano').value = id;
    document.getElementById('turnoCiudadanoQ').value = nombre;
    document.getElementById('turnoCiudadanoResultados').style.display = 'none';
}

async function submitTurno(e) {
    e.preventDefault();
    const errEl = document.getElementById('turnoError');
    errEl.style.display = 'none';
    const payload = {
        tipo_agenda:        document.getElementById('turnoTipoAgenda').value,
        fecha:              document.getElementById('turnoFecha').value,
        hora_inicio:        document.getElementById('turnoHoraInicio').value,
        hora_fin:           document.getElementById('turnoHoraFin').value,
        reservado_por:      session.id,
        origen_reserva:     'OPERADOR',
        observaciones:      document.getElementById('turnoObs').value || null,
    };
    const idC = document.getElementById('turnoIdCiudadano').value;
    if (idC) payload.id_ciudadano = parseInt(idC);
    try {
        await apiFetch('/turnos', { method: 'POST', body: JSON.stringify(payload) });
        cerrarModalTurno();
        recargarCalendario();
    } catch (e2) {
        errEl.textContent = e2.message;
        errEl.style.display = 'block';
    }
}

// ════════════════════════════════════════════════════════════
// ADMINISTRACIÓN
// ════════════════════════════════════════════════════════════

function initAdmin() {
    loadAgendasAgentes();
    poblarSelectUsuarios('ausIdUsuario');
}

// ── Agendas Agentes ──────────────────────────────────────────
async function loadAgendasAgentes() {
    const container = document.getElementById('tablaAgendasAgentes');
    container.innerHTML = '<div class="z-agenda-loading">Cargando...</div>';
    const area   = document.getElementById('filtroAAArea').value;
    const activo = document.getElementById('filtroAAActivo').checked;
    const params = new URLSearchParams({ activo });
    if (area) params.set('id_area', area);
    try {
        const items = await apiFetch(`/agendas/agentes?${params}`);
        if (!items.length) { container.innerHTML = '<p style="color:var(--z-text3);padding:1rem">Sin registros.</p>'; return; }
        container.innerHTML = tablaAgendaAgentes(items);
    } catch (e) {
        container.innerHTML = `<p style="color:var(--z-text-error)">Error: ${e.message}</p>`;
    }
}

function tablaAgendaAgentes(items) {
    return `<table class="z-table">
        <thead><tr><th>Usuario</th><th>Área</th><th>Clase</th><th>Desde</th><th>Hasta</th><th>Horario</th><th>Días</th><th>Estado</th><th></th></tr></thead>
        <tbody>
        ${items.map(ag => {
            const area  = areas.find(a => a.id === ag.id_area)?.nombre || ag.id_area;
            const clase = clases.find(c => c.id === ag.id_clase)?.nombre || ag.id_clase;
            const user  = usuarios.find(u => u.id_usuario === ag.id_usuario);
            const uNombre = user ? user.nombre : `id=${ag.id_usuario}`;
            const diasArr = bitmaskToDias(ag.dias_semana);
            const diasStr = DIAS_LABEL.filter((_, i) => diasArr[i]).join(', ');
            return `<tr class="${ag.activo ? '' : 'z-tr--inactivo'}">
                <td>${uNombre}</td>
                <td>${area}</td>
                <td>${clase}</td>
                <td style="font-family:var(--z-font-mono)">${fmtFecha(ag.fecha_desde)}</td>
                <td style="font-family:var(--z-font-mono)">${ag.fecha_hasta ? fmtFecha(ag.fecha_hasta) : '—'}</td>
                <td style="font-family:var(--z-font-mono)">${fmtHora(ag.hora_inicio)}–${fmtHora(ag.hora_fin)}</td>
                <td style="font-size:0.78rem">${diasStr}</td>
                <td>${ag.activo ? '<span class="z-badge z-badge--success">Activa</span>' : '<span class="z-badge">Baja</span>'}</td>
                <td>${ag.activo ? `<button class="z-btn z-btn--danger z-btn--sm" onclick="bajaAgendaAgente(${ag.id})">Baja</button>` : ''}</td>
            </tr>`;
        }).join('')}
        </tbody>
    </table>`;
}

function abrirFormAgendaAgente() {
    document.getElementById('aaEditId').value = '';
    document.getElementById('formAATitle').textContent = 'Nueva Agenda de Agente';
    document.getElementById('formAgendaAgente').reset();
    poblarSelectUsuarios('aaIdUsuario');
    poblarSelectGenerico('aaIdArea', areas);
    poblarSelectGenerico('aaIdClase', clases, 'id', c => `${c.nombre} (${c.duracion_slot_minutos}min)`);
    document.getElementById('aaError').style.display = 'none';
    document.getElementById('formAgendasAgentesCard').hidden = false;
}

function cerrarFormAgendaAgente() {
    document.getElementById('formAgendasAgentesCard').hidden = true;
}

async function submitAgendaAgente(e) {
    e.preventDefault();
    const errEl = document.getElementById('aaError');
    errEl.style.display = 'none';

    const diasChecks = document.querySelectorAll('#formAgendaAgente [data-bit]');
    const bitmask = diasToBitmask(Array.from(diasChecks).map(cb => cb.checked));
    if (bitmask === 0) { errEl.textContent = 'Seleccioná al menos un día.'; errEl.style.display = 'block'; return; }

    const payload = {
        id_usuario:       parseInt(document.getElementById('aaIdUsuario').value),
        id_area:          parseInt(document.getElementById('aaIdArea').value),
        id_clase:         parseInt(document.getElementById('aaIdClase').value),
        fecha_desde:      document.getElementById('aaFechaDesde').value,
        fecha_hasta:      document.getElementById('aaFechaHasta').value || null,
        hora_inicio:      document.getElementById('aaHoraInicio').value,
        hora_fin:         document.getElementById('aaHoraFin').value,
        dias_semana:      bitmask,
        nombre_parametro: document.getElementById('aaParametro').value || null,
        observaciones:    document.getElementById('aaObservaciones').value || null,
        creado_por:       session.id,
    };

    try {
        const editId = document.getElementById('aaEditId').value;
        if (editId) {
            await apiFetch(`/agendas/agentes/${editId}`, { method: 'PATCH', body: JSON.stringify(payload) });
        } else {
            await apiFetch('/agendas/agentes', { method: 'POST', body: JSON.stringify(payload) });
        }
        cerrarFormAgendaAgente();
        loadAgendasAgentes();
    } catch (e2) {
        errEl.textContent = e2.message;
        errEl.style.display = 'block';
    }
}

async function bajaAgendaAgente(id) {
    if (!confirm('¿Dar de baja esta agenda de agente?')) return;
    try {
        await apiFetch(`/agendas/agentes/${id}/baja`, { method: 'PATCH' });
        loadAgendasAgentes();
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

// ── Agendas Servicios ────────────────────────────────────────
async function loadAgendasServicios() {
    const container = document.getElementById('tablaAgendasServicios');
    container.innerHTML = '<div class="z-agenda-loading">Cargando...</div>';
    try {
        const items = await apiFetch('/agendas/servicios?activo=true');
        if (!items.length) { container.innerHTML = '<p style="color:var(--z-text3);padding:1rem">Sin registros.</p>'; return; }
        container.innerHTML = `<table class="z-table">
            <thead><tr><th>Servicio</th><th>Área</th><th>Desde</th><th>Hasta</th><th>Horario</th><th>Días</th></tr></thead>
            <tbody>
            ${items.map(s => {
                const area = areas.find(a => a.id === s.id_area)?.nombre || s.id_area;
                const dias = bitmaskToDias(s.dias_semana).map((v,i) => v ? DIAS_LABEL[i] : null).filter(Boolean).join(', ');
                return `<tr>
                    <td>id=${s.id_servicio}</td>
                    <td>${area}</td>
                    <td>${fmtFecha(s.fecha_desde)}</td>
                    <td>${s.fecha_hasta ? fmtFecha(s.fecha_hasta) : '—'}</td>
                    <td style="font-family:var(--z-font-mono)">${fmtHora(s.hora_inicio)}–${fmtHora(s.hora_fin)}</td>
                    <td style="font-size:0.78rem">${dias}</td>
                </tr>`;
            }).join('')}
            </tbody>
        </table>`;
    } catch (e) {
        container.innerHTML = `<p style="color:var(--z-text-error)">Error: ${e.message}</p>`;
    }
}

// ── Agendas Lugares ──────────────────────────────────────────
async function loadAgendasLugares() {
    const container = document.getElementById('tablaAgendasLugares');
    container.innerHTML = '<div class="z-agenda-loading">Cargando...</div>';
    try {
        const items = await apiFetch('/agendas/lugares?activo=true');
        if (!items.length) { container.innerHTML = '<p style="color:var(--z-text3);padding:1rem">Sin registros.</p>'; return; }
        container.innerHTML = `<table class="z-table">
            <thead><tr><th>Lugar</th><th>Área</th><th>Independiente</th><th>Desde</th><th>Hasta</th><th>Horario</th></tr></thead>
            <tbody>
            ${items.map(l => {
                const area = areas.find(a => a.id === l.id_area)?.nombre || l.id_area;
                return `<tr>
                    <td>id=${l.id_lugar}</td>
                    <td>${area}</td>
                    <td>${l.independiente_de_servicio ? 'Sí' : 'No'}</td>
                    <td>${fmtFecha(l.fecha_desde)}</td>
                    <td>${l.fecha_hasta ? fmtFecha(l.fecha_hasta) : '—'}</td>
                    <td style="font-family:var(--z-font-mono)">${fmtHora(l.hora_inicio)}–${fmtHora(l.hora_fin)}</td>
                </tr>`;
            }).join('')}
            </tbody>
        </table>`;
    } catch (e) {
        container.innerHTML = `<p style="color:var(--z-text-error)">Error: ${e.message}</p>`;
    }
}

// ── Ausencias ────────────────────────────────────────────────
async function loadAusencias() {
    const container = document.getElementById('tablaAusencias');
    container.innerHTML = '<div class="z-agenda-loading">Cargando...</div>';
    try {
        const items = await apiFetch('/ausencias');
        if (!items.length) { container.innerHTML = '<p style="color:var(--z-text3);padding:1rem">Sin registros.</p>'; return; }
        container.innerHTML = `<table class="z-table">
            <thead><tr><th>Agente</th><th>Desde</th><th>Hasta</th><th>Motivo</th><th>Genera Alerta</th></tr></thead>
            <tbody>
            ${items.map(a => {
                const u = usuarios.find(u => u.id_usuario === a.id_usuario);
                return `<tr>
                    <td>${u ? u.nombre : `id=${a.id_usuario}`}</td>
                    <td>${fmtFecha(a.fecha_desde)}</td>
                    <td>${fmtFecha(a.fecha_hasta)}</td>
                    <td>${a.motivo || '—'}</td>
                    <td>${a.genera_alerta ? 'Sí' : 'No'}</td>
                </tr>`;
            }).join('')}
            </tbody>
        </table>`;
    } catch (e) {
        container.innerHTML = `<p style="color:var(--z-text-error)">Error: ${e.message}</p>`;
    }
}

async function submitAusencia(e) {
    e.preventDefault();
    const errEl = document.getElementById('ausError');
    errEl.style.display = 'none';
    const payload = {
        id_usuario:    parseInt(document.getElementById('ausIdUsuario').value),
        fecha_desde:   document.getElementById('ausFechaDesde').value,
        fecha_hasta:   document.getElementById('ausFechaHasta').value,
        motivo:        document.getElementById('ausMotivo').value || null,
        genera_alerta: document.getElementById('ausGeneraAlerta').checked,
        cargado_por:   session.id,
    };
    try {
        await apiFetch('/ausencias', { method: 'POST', body: JSON.stringify(payload) });
        document.getElementById('formAusenciaCard').hidden = true;
        document.getElementById('formAusencia').reset();
        loadAusencias();
        loadAlertasBadge();
    } catch (e2) {
        errEl.textContent = e2.message;
        errEl.style.display = 'block';
    }
}

// ── Catálogos ─────────────────────────────────────────────────
let catalogoActual = 'servicios';

async function setCatalogo(tipo, btn) {
    catalogoActual = tipo;
    if (btn) {
        btn.closest('.z-subtabs').querySelectorAll('.z-subtab').forEach(b => b.classList.remove('z-subtab--active'));
        btn.classList.add('z-subtab--active');
    }
    const container = document.getElementById('catalogoContainer');
    container.innerHTML = '<div class="z-agenda-loading">Cargando...</div>';
    try {
        if (tipo === 'servicios') await renderCatalogoServicios(container);
        if (tipo === 'lugares')   await renderCatalogoLugares(container);
        if (tipo === 'clases')    await renderCatalogoClases(container);
        if (tipo === 'feriados')  await renderCatalogoFeriados(container);
    } catch (e) {
        container.innerHTML = `<p style="color:var(--z-text-error)">Error: ${e.message}</p>`;
    }
}

async function renderCatalogoServicios(container) {
    const items = await apiFetch('/servicios?solo_activos=false');
    container.innerHTML = `<div class="z-card" style="padding:1.5rem">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
            <h3 class="z-card__title">Servicios</h3>
            <button class="z-btn z-btn--primary z-btn--sm" onclick="abrirModalCatalogoServicio()">+ Nuevo</button>
        </div>
        <table class="z-table"><thead><tr><th>Nombre</th><th>Área</th><th>Cap. Agentes</th><th>Estado</th><th></th></tr></thead>
        <tbody>${items.map(s => {
            const area = areas.find(a => a.id === s.id_area)?.nombre || '—';
            return `<tr class="${s.activo ? '' : 'z-tr--inactivo'}">
                <td>${s.nombre}</td><td>${area}</td><td>${s.capacidad_agentes}</td>
                <td>${s.activo ? '<span class="z-badge z-badge--success">Activo</span>' : '<span class="z-badge">Baja</span>'}</td>
                <td><button class="z-btn z-btn--sm" onclick="editarServicio(${s.id})">Editar</button></td>
            </tr>`;
        }).join('')}</tbody></table>
    </div>`;
}

async function renderCatalogoLugares(container) {
    const items = await apiFetch('/lugares?solo_activos=false');
    container.innerHTML = `<div class="z-card" style="padding:1.5rem">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
            <h3 class="z-card__title">Lugares de Atención</h3>
            <button class="z-btn z-btn--primary z-btn--sm" onclick="abrirModalCatalogoLugar()">+ Nuevo</button>
        </div>
        <table class="z-table"><thead><tr><th>Nombre</th><th>Dirección</th><th>Es Atención</th><th>Cap. Servicios</th><th>Estado</th></tr></thead>
        <tbody>${items.map(l => {
            return `<tr class="${l.activo ? '' : 'z-tr--inactivo'}">
                <td>${l.nombre}</td><td>${l.direccion || '—'}</td>
                <td>${l.es_atencion ? 'Sí' : 'No'}</td><td>${l.capacidad_servicios}</td>
                <td>${l.activo ? '<span class="z-badge z-badge--success">Activo</span>' : '<span class="z-badge">Baja</span>'}</td>
            </tr>`;
        }).join('')}</tbody></table>
    </div>`;
}

async function renderCatalogoClases(container) {
    const items = await apiFetch('/clases?solo_activos=false');
    container.innerHTML = `<div class="z-card" style="padding:1.5rem">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
            <h3 class="z-card__title">Clases de Agenda</h3>
            <button class="z-btn z-btn--primary z-btn--sm" onclick="abrirModalCatalogoClase()">+ Nueva</button>
        </div>
        <table class="z-table"><thead><tr><th>Nombre</th><th>Slot (min)</th><th>Req. RRHH</th><th>Req. Servicio</th><th>Visible Ciudadano</th><th>Estado</th></tr></thead>
        <tbody>${items.map(c => `
            <tr class="${c.activo ? '' : 'z-tr--inactivo'}">
                <td>${c.nombre}</td><td>${c.duracion_slot_minutos}</td>
                <td>${c.requiere_rrhh ? 'Sí' : 'No'}</td><td>${c.requiere_servicio ? 'Sí' : 'No'}</td>
                <td>${c.visible_ciudadano ? 'Sí' : 'No'}</td>
                <td>${c.activo ? '<span class="z-badge z-badge--success">Activa</span>' : '<span class="z-badge">Baja</span>'}</td>
            </tr>`).join('')}
        </tbody></table>
    </div>`;
}

async function renderCatalogoFeriados(container) {
    const anio = navDate.getFullYear();
    const items = await apiFetch(`/feriados?anio=${anio}`);
    container.innerHTML = `<div class="z-card" style="padding:1.5rem">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
            <h3 class="z-card__title">Feriados ${anio}</h3>
            <button class="z-btn z-btn--primary z-btn--sm" onclick="abrirModalFeriado()">+ Nuevo</button>
        </div>
        <table class="z-table"><thead><tr><th>Fecha</th><th>Descripción</th><th>Ámbito</th><th></th></tr></thead>
        <tbody>${items.map(f => `
            <tr>
                <td style="font-family:var(--z-font-mono)">${fmtFecha(f.fecha)}</td>
                <td>${f.descripcion}</td>
                <td>${f.ambito}</td>
                <td><button class="z-btn z-btn--danger z-btn--sm" onclick="bajaFeriado(${f.id})">Baja</button></td>
            </tr>`).join('')}
        </tbody></table>
    </div>`;
}

// ── Modales de catálogo ──────────────────────────────────────
function abrirModalCatalogoServicio(item = null) {
    const title = item ? 'Editar Servicio' : 'Nuevo Servicio';
    const html = `<form onsubmit="submitCatalogoServicio(event,${item?.id || 'null'})">
        <div class="z-form-group"><label class="z-label">Nombre *</label>
            <input class="z-input" id="cSrvNombre" required maxlength="120" value="${item?.nombre || ''}"></div>
        <div class="z-form-group"><label class="z-label">Descripción</label>
            <textarea class="z-input" id="cSrvDesc" rows="2">${item?.descripcion || ''}</textarea></div>
        <div class="z-form-group"><label class="z-label">Área</label>
            <select class="z-input" id="cSrvArea">
                <option value="">Sin área</option>
                ${areas.map(a => `<option value="${a.id}" ${item?.id_area === a.id ? 'selected' : ''}>${a.nombre}</option>`).join('')}
            </select></div>
        <div class="z-form-group"><label class="z-label">Capacidad agentes</label>
            <input class="z-input" id="cSrvCap" type="number" min="1" value="${item?.capacidad_agentes || 1}"></div>
        <div class="z-form-actions" style="margin-top:1rem">
            <button type="submit" class="z-btn z-btn--primary">Guardar</button>
            <button type="button" class="z-btn" onclick="cerrarModalCatalogo()">Cancelar</button>
        </div>
        <p id="cSrvError" style="display:none;color:var(--z-text-error);margin-top:0.5rem"></p>
    </form>`;
    abrirModalCatalogo(title, html);
}

async function submitCatalogoServicio(e, editId) {
    e.preventDefault();
    const errEl = document.getElementById('cSrvError');
    errEl.style.display = 'none';
    const payload = {
        nombre:            document.getElementById('cSrvNombre').value,
        descripcion:       document.getElementById('cSrvDesc').value || null,
        id_area:           parseInt(document.getElementById('cSrvArea').value) || null,
        capacidad_agentes: parseInt(document.getElementById('cSrvCap').value) || 1,
        creado_por:        session.id,
    };
    try {
        if (editId) await apiFetch(`/servicios/${editId}`, { method: 'PATCH', body: JSON.stringify(payload) });
        else        await apiFetch('/servicios', { method: 'POST', body: JSON.stringify(payload) });
        cerrarModalCatalogo();
        await loadServicios();
        setCatalogo('servicios');
    } catch (e2) {
        errEl.textContent = e2.message;
        errEl.style.display = 'block';
    }
}

function abrirModalCatalogoLugar() {
    const html = `<form onsubmit="submitCatalogoLugar(event)">
        <div class="z-form-group"><label class="z-label">Nombre *</label>
            <input class="z-input" id="cLugNombre" required maxlength="120"></div>
        <div class="z-form-group"><label class="z-label">Dirección</label>
            <input class="z-input" id="cLugDir" maxlength="200"></div>
        <div class="z-form-group"><label class="z-label">Área</label>
            <select class="z-input" id="cLugArea">
                <option value="">Sin área</option>
                ${areas.map(a => `<option value="${a.id}">${a.nombre}</option>`).join('')}
            </select></div>
        <div class="z-form-group"><label class="z-label">Cap. servicios</label>
            <input class="z-input" id="cLugCap" type="number" min="1" value="1"></div>
        <label class="z-label" style="display:flex;align-items:center;gap:8px;cursor:pointer;margin-bottom:1rem">
            <input type="checkbox" id="cLugEsAtencion" checked> Es lugar de atención al público
        </label>
        <div class="z-form-actions" style="margin-top:0">
            <button type="submit" class="z-btn z-btn--primary">Guardar</button>
            <button type="button" class="z-btn" onclick="cerrarModalCatalogo()">Cancelar</button>
        </div>
        <p id="cLugError" style="display:none;color:var(--z-text-error);margin-top:0.5rem"></p>
    </form>`;
    abrirModalCatalogo('Nuevo Lugar de Atención', html);
}

async function submitCatalogoLugar(e) {
    e.preventDefault();
    const errEl = document.getElementById('cLugError');
    errEl.style.display = 'none';
    const payload = {
        nombre:              document.getElementById('cLugNombre').value,
        direccion:           document.getElementById('cLugDir').value || null,
        id_area:             parseInt(document.getElementById('cLugArea').value) || null,
        capacidad_servicios: parseInt(document.getElementById('cLugCap').value) || 1,
        es_atencion:         document.getElementById('cLugEsAtencion').checked,
        creado_por:          session.id,
    };
    try {
        await apiFetch('/lugares', { method: 'POST', body: JSON.stringify(payload) });
        cerrarModalCatalogo();
        await loadLugares();
        setCatalogo('lugares');
    } catch (e2) {
        errEl.textContent = e2.message;
        errEl.style.display = 'block';
    }
}

function abrirModalCatalogoClase() {
    const html = `<form onsubmit="submitCatalogoClase(event)">
        <div class="z-form-group"><label class="z-label">Nombre *</label>
            <input class="z-input" id="cClNombre" required maxlength="80"></div>
        <div class="z-form-group"><label class="z-label">Descripción</label>
            <textarea class="z-input" id="cClDesc" rows="2"></textarea></div>
        <div class="z-form-group"><label class="z-label">Duración slot (minutos) *</label>
            <input class="z-input" id="cClSlot" type="number" min="5" max="480" value="30" required></div>
        <div class="z-form-group"><label class="z-label">Área</label>
            <select class="z-input" id="cClArea">
                <option value="">Sin área</option>
                ${areas.map(a => `<option value="${a.id}">${a.nombre}</option>`).join('')}
            </select></div>
        <label class="z-label" style="display:flex;align-items:center;gap:8px;cursor:pointer;margin-bottom:8px">
            <input type="checkbox" id="cClVisible"> Visible para ciudadanos
        </label>
        <div class="z-form-actions" style="margin-top:0.75rem">
            <button type="submit" class="z-btn z-btn--primary">Guardar</button>
            <button type="button" class="z-btn" onclick="cerrarModalCatalogo()">Cancelar</button>
        </div>
        <p id="cClError" style="display:none;color:var(--z-text-error);margin-top:0.5rem"></p>
    </form>`;
    abrirModalCatalogo('Nueva Clase de Agenda', html);
}

async function submitCatalogoClase(e) {
    e.preventDefault();
    const errEl = document.getElementById('cClError');
    errEl.style.display = 'none';
    const payload = {
        nombre:               document.getElementById('cClNombre').value,
        descripcion:          document.getElementById('cClDesc').value || null,
        duracion_slot_minutos:parseInt(document.getElementById('cClSlot').value),
        id_area:              parseInt(document.getElementById('cClArea').value) || null,
        visible_ciudadano:    document.getElementById('cClVisible').checked,
        creado_por:           session.id,
    };
    try {
        await apiFetch('/clases', { method: 'POST', body: JSON.stringify(payload) });
        cerrarModalCatalogo();
        await loadClases();
        setCatalogo('clases');
    } catch (e2) {
        errEl.textContent = e2.message;
        errEl.style.display = 'block';
    }
}

function abrirModalFeriado() {
    const html = `<form onsubmit="submitFeriado(event)">
        <div class="z-form-group"><label class="z-label">Fecha *</label>
            <input class="z-input" id="fFecha" type="date" required></div>
        <div class="z-form-group"><label class="z-label">Descripción *</label>
            <input class="z-input" id="fDesc" maxlength="200" required></div>
        <div class="z-form-group"><label class="z-label">Ámbito</label>
            <select class="z-input" id="fAmbito">
                <option>NACIONAL</option><option>PROVINCIAL</option><option>MUNICIPAL</option>
            </select></div>
        <div class="z-form-actions" style="margin-top:1rem">
            <button type="submit" class="z-btn z-btn--primary">Guardar</button>
            <button type="button" class="z-btn" onclick="cerrarModalCatalogo()">Cancelar</button>
        </div>
        <p id="fError" style="display:none;color:var(--z-text-error);margin-top:0.5rem"></p>
    </form>`;
    abrirModalCatalogo('Nuevo Feriado', html);
}

async function submitFeriado(e) {
    e.preventDefault();
    const errEl = document.getElementById('fError');
    errEl.style.display = 'none';
    const payload = {
        fecha:       document.getElementById('fFecha').value,
        descripcion: document.getElementById('fDesc').value,
        ambito:      document.getElementById('fAmbito').value,
        creado_por:  session.id,
    };
    try {
        await apiFetch('/feriados', { method: 'POST', body: JSON.stringify(payload) });
        cerrarModalCatalogo();
        setCatalogo('feriados');
    } catch (e2) {
        errEl.textContent = e2.message;
        errEl.style.display = 'block';
    }
}

async function bajaFeriado(id) {
    if (!confirm('¿Dar de baja este feriado?')) return;
    try {
        await apiFetch(`/feriados/${id}`, { method: 'PATCH', body: JSON.stringify({ activo: false }) });
        setCatalogo('feriados');
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

function abrirModalCatalogo(title, html) {
    document.getElementById('modalCatalogoTitle').textContent = title;
    document.getElementById('modalCatalogoBody').innerHTML = html;
    document.getElementById('modalCatalogo').hidden = false;
}

function cerrarModalCatalogo() {
    document.getElementById('modalCatalogo').hidden = true;
}

// Cerrar modales con Escape
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        cerrarModalTurno();
        cerrarModalCatalogo();
    }
});
