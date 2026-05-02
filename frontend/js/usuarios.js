/**
 * ZARIS — Padrón de Usuarios
 */
document.addEventListener('DOMContentLoaded', () => {

    const NIVELES = { 1: 'Administrador', 2: 'Supervisor', 3: 'Operador', 4: 'Consultor' };

    // ── State ──────────────────────────────────────────────────────────────────
    const state = {
        modo:    null,   // 'nuevo' | 'edicion' | 'consulta'
        usuario: null,
    };

    let _listadoData = [];

    // ── Refs ───────────────────────────────────────────────────────────────────
    const $ = id => document.getElementById(id);

    // ── Inicialización ─────────────────────────────────────────────────────────
    $('btn-buscar').addEventListener('click', buscar);
    $('search-query').addEventListener('keydown', e => { if (e.key === 'Enter') buscar(); });
    $('btn-nuevo').addEventListener('click', activarModoNuevo);
    $('btn-nuevo-forzar').addEventListener('click', activarModoNuevo);
    $('btn-cancelar').addEventListener('click', handleCancelar);
    $('btn-editar').addEventListener('click', activarModoEdicion);
    $('btn-guardar').addEventListener('click', guardar);
    $('btn-baja').addEventListener('click', () => cambiarEstado(false));
    $('btn-reactivar').addEventListener('click', () => cambiarEstado(true));

    $('btn-listado').addEventListener('click', abrirListado);
    $('btn-cerrar-listado').addEventListener('click', cerrarListado);
    $('btn-imprimir-lst').addEventListener('click', () => window.print());
    $('btn-filtrar-lst').addEventListener('click', aplicarFiltros);
    $('btn-limpiar-lst').addEventListener('click', limpiarFiltros);
    $('lst-texto').addEventListener('keydown', e => { if (e.key === 'Enter') aplicarFiltros(); });

    ZValidaciones.bindGuardarBoton($('form-card'), $('btn-guardar'), {
        extra: () => {
            const pwd = $('usr-password').value;
            const cf  = $('usr-password-confirm').value;
            if (state.modo === 'nuevo') {
                if (!pwd || pwd.length < 8) return false;
                if (pwd !== cf) return false;
            } else if (state.modo === 'edicion' && pwd) {
                if (pwd.length < 8) return false;
                if (pwd !== cf) return false;
            }
            return true;
        }
    });

    $('search-query').focus();
    cargarVistaPrevia();

    // ── Búsqueda ───────────────────────────────────────────────────────────────
    async function buscar() {
        const q = $('search-query').value.trim();
        if (!q) { ZUtils.toast('Ingresá un término de búsqueda', 'warning'); return; }

        $('search-result').classList.remove('visible');
        $('result-list').innerHTML = '';

        try {
            const data = await ZUtils.apiFetch(
                `/usuarios/buscar?q=${encodeURIComponent(q)}&tipo=texto`
            );
            mostrarResultados(data);
        } catch (err) {
            ZUtils.toast(err.message || 'Error al buscar', 'error');
        }
    }

    function mostrarResultados(usuarios) {
        const panel  = $('search-result');
        const name   = $('result-name');
        const detail = $('result-detail');
        const list   = $('result-list');
        const btnE   = $('btn-editar-encontrado');
        const btnC   = $('btn-consultar-encontrado');

        panel.classList.add('visible');
        list.innerHTML = '';
        btnE.style.display = 'none';
        btnC.style.display = 'none';

        if (usuarios.length === 0) {
            name.textContent   = 'Sin resultados';
            detail.textContent = 'No se encontraron usuarios con ese criterio.';
            return;
        }

        if (usuarios.length === 1) {
            const u = usuarios[0];
            name.textContent   = u.nombre;
            detail.textContent = `${u.username} — ${NIVELES[u.nivel_acceso] || 'Nivel ' + u.nivel_acceso} — ${u.activo ? 'Activo' : 'Inactivo'}`;
            btnE.style.display = 'inline-flex';
            btnC.style.display = 'inline-flex';
            btnE.onclick = () => cargarUsuario(u.id_usuario, 'edicion');
            btnC.onclick = () => cargarUsuario(u.id_usuario, 'consulta');
            return;
        }

        name.textContent   = `${usuarios.length} usuarios encontrados`;
        detail.textContent = 'Seleccioná uno para continuar:';

        usuarios.forEach(u => {
            const row = document.createElement('div');
            row.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:7px 0;border-bottom:1px solid var(--z-border);';
            row.innerHTML = `
                <span style="font-size:0.88rem;">
                    <strong>${u.nombre}</strong>
                    <span style="color:var(--z-text2);margin-left:8px;">${u.username}</span>
                    <span style="color:var(--z-text3);margin-left:6px;font-size:0.78rem;">${NIVELES[u.nivel_acceso] || ''}</span>
                    ${!u.activo ? '<span style="color:#cf2d56;font-size:0.75rem;margin-left:6px;">[Inactivo]</span>' : ''}
                </span>
                <span style="display:flex;gap:6px;">
                    <button class="z-btn z-btn--xs z-btn--primary" data-id="${u.id_usuario}" data-modo="edicion">Editar</button>
                    <button class="z-btn z-btn--xs z-btn--ghost"   data-id="${u.id_usuario}" data-modo="consulta">Ver</button>
                </span>`;
            row.querySelectorAll('button').forEach(btn =>
                btn.addEventListener('click', () => cargarUsuario(parseInt(btn.dataset.id), btn.dataset.modo))
            );
            list.appendChild(row);
        });
    }

    // ── Cargar usuario ─────────────────────────────────────────────────────────
    async function cargarUsuario(id, modo = 'consulta') {
        try {
            const u = await ZUtils.apiFetch(`/usuarios/${id}`);
            state.usuario = u;
            poblarFormulario(u);
            if (modo === 'edicion') activarModoEdicion();
            else activarModoConsulta();
            mostrarFormCard();
        } catch (err) {
            ZUtils.toast(err.message || 'Error al cargar usuario', 'error');
        }
    }

    // ── Formulario ─────────────────────────────────────────────────────────────
    function poblarFormulario(u) {
        $('usr-id').value              = u.id_usuario || '';
        $('usr-nombre').value          = u.nombre     || '';
        $('usr-username').value        = u.username   || '';
        $('usr-nivel').value           = u.nivel_acceso || '';
        $('usr-cargo').value           = u.id_cargo   || '';
        $('usr-cuil').value            = u.cuil       || '';
        $('usr-buc-acceso').checked    = u.buc_acceso || false;
        $('usr-password').value        = '';
        $('usr-password-confirm').value = '';
        const badge = $('activo-badge');
        badge.textContent  = u.activo ? 'Activo' : 'Inactivo';
        badge.className    = u.activo ? 'z-badge-activo' : 'z-badge-inactivo';
    }

    function activarModoNuevo() {
        state.modo    = 'nuevo';
        state.usuario = null;
        resetFormulario();
        mostrarFormCard();
        $('form-title').textContent      = 'Alta de Usuario';
        $('form-state').textContent      = 'NUEVO';
        $('form-state').className        = 'z-form-state z-form-state--new';
        $('activo-row').style.display    = 'none';
        $('usr-username').readOnly       = false;
        $('password-req-star').style.display = 'inline';
        $('password-hint').textContent   = 'Requerida. Mínimo 8 caracteres.';
        setFieldsDisabled(false);
        $('btn-guardar').style.display   = 'inline-flex';
        $('btn-editar').style.display    = 'none';
        $('btn-baja').style.display      = 'none';
        $('btn-reactivar').style.display = 'none';
        $('btn-cancelar').textContent    = 'Cancelar';
        $('usr-nombre').focus();
    }

    function activarModoEdicion() {
        state.modo = 'edicion';
        const u = state.usuario;
        $('form-title').textContent      = 'Editar Usuario';
        $('form-state').textContent      = 'EDICIÓN';
        $('form-state').className        = 'z-form-state z-form-state--edit';
        $('activo-row').style.display    = 'block';
        $('usr-username').readOnly       = true;
        $('password-req-star').style.display = 'none';
        $('password-hint').textContent   = 'Dejar vacío para no cambiar la contraseña.';
        setFieldsDisabled(false);
        $('btn-guardar').style.display   = 'inline-flex';
        $('btn-editar').style.display    = 'none';
        $('btn-cancelar').textContent    = 'Salir';
        $('btn-baja').style.display      = (u && u.activo)  ? 'inline-flex' : 'none';
        $('btn-reactivar').style.display = (u && !u.activo) ? 'inline-flex' : 'none';
    }

    function activarModoConsulta() {
        state.modo = 'consulta';
        $('form-title').textContent      = 'Consulta de Usuario';
        $('form-state').textContent      = 'CONSULTA';
        $('form-state').className        = 'z-form-state z-form-state--view';
        $('activo-row').style.display    = 'block';
        setFieldsDisabled(true);
        $('btn-guardar').style.display   = 'none';
        $('btn-baja').style.display      = 'none';
        $('btn-reactivar').style.display = 'none';
        $('btn-editar').style.display    = 'inline-flex';
        $('btn-cancelar').textContent    = 'Salir';
    }

    function setFieldsDisabled(dis) {
        ['usr-nombre','usr-username','usr-nivel','usr-cargo','usr-cuil',
         'usr-buc-acceso','usr-password','usr-password-confirm'].forEach(id => {
            const el = $(id); if (el) el.disabled = dis;
        });
    }

    function resetFormulario() {
        ['usr-id','usr-nombre','usr-username','usr-cargo','usr-cuil',
         'usr-password','usr-password-confirm'].forEach(id => { const el=$(id); if(el) el.value=''; });
        $('usr-nivel').value      = '';
        $('usr-buc-acceso').checked = false;
        document.querySelectorAll('.z-input-error').forEach(el => { el.textContent=''; el.style.display='none'; });
    }

    function mostrarFormCard() {
        $('form-card').style.display = 'block';
        $('form-card').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    async function handleCancelar() {
        if (state.modo === 'nuevo') {
            const tieneData = $('usr-nombre').value || $('usr-username').value || $('usr-password').value;
            if (tieneData) {
                const ok = await ZUtils.confirm('Cancelar alta', '¿Descartar los datos ingresados?');
                if (!ok) return;
            }
        }
        $('form-card').style.display = 'none';
        state.modo    = null;
        state.usuario = null;
    }

    // ── Validación ─────────────────────────────────────────────────────────────
    function validar() {
        document.querySelectorAll('.z-input-error').forEach(el => { el.textContent=''; el.style.display='none'; });
        let ok = true;

        const showErr = (id, msg) => { const el=$(id); if(el){el.textContent=msg;el.style.display='block';} };

        if (!$('usr-nombre').value.trim())    { showErr('err-nombre',   'El nombre es requerido'); ok=false; }
        if (!$('usr-username').value.trim())  { showErr('err-username', 'El nombre de usuario es requerido'); ok=false; }
        else if (!/^[a-zA-Z0-9_.\-]+$/.test($('usr-username').value.trim()))
            { showErr('err-username', 'Solo letras, números, puntos y guiones'); ok=false; }
        if (!$('usr-nivel').value)            { showErr('err-nivel',    'Seleccioná un nivel de acceso'); ok=false; }

        const pass = $('usr-password').value;
        const cf   = $('usr-password-confirm').value;
        if (state.modo === 'nuevo') {
            if (!pass)            { showErr('err-password', 'La contraseña es requerida'); ok=false; }
            else if (pass.length < 8) { showErr('err-password', 'Mínimo 8 caracteres'); ok=false; }
        } else if (pass && pass.length < 8) { showErr('err-password', 'Mínimo 8 caracteres'); ok=false; }

        if (pass && pass !== cf) { showErr('err-password-confirm', 'Las contraseñas no coinciden'); ok=false; }

        if ($('usr-cuil').value.trim()) {
            const cuil = $('usr-cuil').value.replace(/[-\s]/g,'');
            if (!/^\d{11}$/.test(cuil)) { showErr('err-cuil', 'El CUIL debe contener 11 dígitos'); ok=false; }
        }
        return ok;
    }

    // ── Guardar ────────────────────────────────────────────────────────────────
    async function guardar() {
        if (!validar()) return;

        const payload = {
            nombre:       $('usr-nombre').value.trim(),
            nivel_acceso: parseInt($('usr-nivel').value),
            id_cargo:     $('usr-cargo').value.trim() || null,
            cuil:         $('usr-cuil').value.replace(/[-\s]/g,'') || null,
            buc_acceso:   $('usr-buc-acceso').checked,
        };
        if ($('usr-password').value) payload.password = $('usr-password').value;

        try {
            $('btn-guardar').disabled    = true;
            $('btn-guardar').textContent = 'Guardando...';

            if (state.modo === 'nuevo') {
                payload.username = $('usr-username').value.trim();
                const u = await ZUtils.apiFetch('/usuarios', { method:'POST', body:JSON.stringify(payload) });
                cargarVistaPrevia();
                ZUtils.modalGuardado(
                    'Usuario creado',
                    `${u.nombre} (${u.username}) fue registrado correctamente.`,
                    activarModoNuevo,
                    () => window.location.href = 'mainconfig.html'
                );
            } else {
                const u = await ZUtils.apiFetch(`/usuarios/${state.usuario.id_usuario}`, { method:'PUT', body:JSON.stringify(payload) });
                state.usuario = u;
                poblarFormulario(u);
                activarModoConsulta();
                ZUtils.toast('Usuario guardado correctamente', 'success');
                cargarVistaPrevia();
            }
        } catch (err) {
            ZUtils.toast(err.message || 'Error al guardar', 'error');
        } finally {
            $('btn-guardar').disabled    = false;
            $('btn-guardar').textContent = 'Guardar Usuario';
        }
    }

    // ── Baja / Reactivar ───────────────────────────────────────────────────────
    async function cambiarEstado(nuevoActivo) {
        const titulo = nuevoActivo ? 'Reactivar usuario' : 'Dar de baja usuario';
        const msg    = nuevoActivo
            ? `¿Reactivar a <strong>${state.usuario.nombre}</strong>?`
            : `¿Dar de baja a <strong>${state.usuario.nombre}</strong>? No podrá iniciar sesión.`;
        const ok = await ZUtils.confirm(titulo, msg);
        if (!ok) return;
        try {
            const u = await ZUtils.apiFetch(
                `/usuarios/${state.usuario.id_usuario}/estado?activo=${nuevoActivo}`,
                { method: 'PUT' }
            );
            state.usuario = u;
            poblarFormulario(u);
            activarModoEdicion();
            ZUtils.toast(nuevoActivo ? 'Usuario reactivado' : 'Usuario dado de baja', 'success');
            cargarVistaPrevia();
        } catch (err) {
            ZUtils.toast(err.message || 'Error', 'error');
        }
    }

    // ── Vista previa ───────────────────────────────────────────────────────────
    async function cargarVistaPrevia() {
        const container = $('preview-rows');
        if (!container) return;
        container.innerHTML = '<div style="color:var(--z-text3);font-size:0.82rem;padding:0.5rem 0;">Cargando...</div>';
        try {
            const data = await ZUtils.apiFetch('/usuarios?solo_activos=false');
            // Ordenar por id desc (más alto = más reciente) y tomar primeros 5
            const recientes = [...data]
                .sort((a, b) => (b.id_usuario || 0) - (a.id_usuario || 0))
                .slice(0, 5);

            if (recientes.length === 0) {
                container.innerHTML = '<div style="color:var(--z-text3);font-size:0.82rem;padding:0.5rem 0;">Sin registros</div>';
                return;
            }

            container.innerHTML = recientes.map(u => `
                <div class="z-preview-row" data-id="${u.id_usuario}">
                    <span class="z-preview-row__nombre">${esc(u.nombre)}</span>
                    <span class="z-preview-row__username">${esc(u.username)}</span>
                    <span class="z-preview-row__nivel">${NIVELES[u.nivel_acceso] || 'Nivel ' + u.nivel_acceso}</span>
                    <span class="z-preview-row__estado z-preview-row__estado--${u.activo ? 'activo' : 'inactivo'}">${u.activo ? 'Activo' : 'Inactivo'}</span>
                    <span class="z-preview-row__cta">Ver →</span>
                </div>
            `).join('');

            container.querySelectorAll('.z-preview-row').forEach(row =>
                row.addEventListener('click', () => cargarUsuario(parseInt(row.dataset.id), 'consulta'))
            );
        } catch (err) {
            console.error('[Preview usuarios]', err);
            container.innerHTML = `<div style="color:var(--z-text3);font-size:0.82rem;padding:0.5rem 0;">No se pudo cargar la vista previa (${err.message})</div>`;
        }
    }

    // ── Listado completo ───────────────────────────────────────────────────────
    async function abrirListado() {
        $('search-panel').style.display  = 'none';
        $('preview-section').style.display = 'none';
        $('form-card').style.display     = 'none';
        $('listado-section').style.display = 'block';
        $('listado-contenido').innerHTML = '<div style="text-align:center;padding:2rem;color:var(--z-text3);">Cargando...</div>';
        $('lst-count').textContent = '';
        try {
            _listadoData = await ZUtils.apiFetch('/usuarios?solo_activos=false');
            aplicarFiltros();
        } catch (err) {
            $('listado-contenido').innerHTML =
                `<div style="color:#cf2d56;padding:1rem;">Error al cargar: ${err.message}</div>`;
        }
    }

    function cerrarListado() {
        $('listado-section').style.display  = 'none';
        $('search-panel').style.display     = 'block';
        $('preview-section').style.display  = 'block';
    }

    function aplicarFiltros() {
        let rows   = [..._listadoData];
        const txt  = ($('lst-texto').value  || '').toLowerCase().trim();
        const niv  = $('lst-nivel').value   || '';
        const ord  = $('lst-orden').value   || 'reciente';
        const desd = $('lst-desde').value   || '';
        const hast = $('lst-hasta').value   || '';

        if (txt) rows = rows.filter(u =>
            (u.nombre   || '').toLowerCase().includes(txt) ||
            (u.username || '').toLowerCase().includes(txt) ||
            (u.cuil     || '').includes(txt)
        );
        if (niv) rows = rows.filter(u => String(u.nivel_acceso) === niv);
        if (desd || hast) rows = rows.filter(u => {
            const d = (u.fecha_alta || '').slice(0, 10);
            if (!d) return true;
            if (desd && d < desd) return false;
            if (hast && d > hast) return false;
            return true;
        });

        if      (ord === 'reciente') rows.sort((a,b) => (b.id_usuario||0)-(a.id_usuario||0));
        else if (ord === 'antiguo')  rows.sort((a,b) => (a.id_usuario||0)-(b.id_usuario||0));
        else if (ord === 'az')       rows.sort((a,b) => (a.nombre||'').localeCompare(b.nombre||'','es'));
        else if (ord === 'za')       rows.sort((a,b) => (b.nombre||'').localeCompare(a.nombre||'','es'));

        renderListado(rows);
    }

    function limpiarFiltros() {
        ['lst-texto','lst-desde','lst-hasta'].forEach(id => { const el=$(id); if(el) el.value=''; });
        $('lst-nivel').value = '';
        $('lst-orden').value = 'reciente';
        aplicarFiltros();
    }

    function renderListado(rows) {
        const fecha = new Date().toLocaleDateString('es-AR', { day:'2-digit', month:'2-digit', year:'numeric' });
        $('lst-print-header').innerHTML =
            `<h2>Padrón de Usuarios — ZARIS</h2><p>Listado generado el ${fecha} · ${rows.length} registro${rows.length!==1?'s':''}</p>`;
        $('lst-count').textContent = `${rows.length} usuario${rows.length!==1?'s':''} encontrado${rows.length!==1?'s':''}`;

        if (rows.length === 0) {
            $('listado-contenido').innerHTML =
                '<div style="text-align:center;padding:2.5rem;color:var(--z-text3);">Sin resultados para los filtros aplicados</div>';
            return;
        }

        const bodyRows = rows.map(u => `
            <tr>
                <td>${esc(u.nombre)}</td>
                <td class="mono">${esc(u.username)}</td>
                <td>${NIVELES[u.nivel_acceso] || u.nivel_acceso}</td>
                <td class="mono">${u.cuil || '—'}</td>
                <td><span class="z-badge-${u.activo?'activo':'inactivo'}">${u.activo?'Activo':'Inactivo'}</span></td>
                <td>
                    <button class="z-tbl-btn" data-id="${u.id_usuario}" data-modo="consulta">Ver</button>
                    <button class="z-tbl-btn" data-id="${u.id_usuario}" data-modo="edicion">Editar</button>
                </td>
            </tr>`).join('');

        $('listado-contenido').innerHTML = `
            <div class="z-listado-wrap">
                <table>
                    <thead><tr>
                        <th>Nombre</th><th>Usuario</th><th>Nivel</th>
                        <th>CUIL</th><th>Estado</th><th>Acciones</th>
                    </tr></thead>
                    <tbody>${bodyRows}</tbody>
                </table>
            </div>`;

        $('listado-contenido').querySelectorAll('.z-tbl-btn').forEach(btn =>
            btn.addEventListener('click', () => {
                cerrarListado();
                cargarUsuario(parseInt(btn.dataset.id), btn.dataset.modo);
            })
        );
    }

    // ── Util ───────────────────────────────────────────────────────────────────
    function esc(s) {
        return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    }

});
