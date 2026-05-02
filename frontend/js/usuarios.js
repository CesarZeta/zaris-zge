/**
 * ZARIS — Lógica del Padrón de Usuarios
 * Alta, baja, modificación y consulta de usuarios del sistema.
 */
document.addEventListener('DOMContentLoaded', () => {

    // ── State ──────────────────────────────────────────────────
    const state = {
        modo: null,          // 'nuevo' | 'edicion' | 'consulta'
        usuario: null,       // objeto usuario cargado
        busquedaTipo: 'texto'
    };

    const NIVELES = { 1: 'Administrador', 2: 'Supervisor', 3: 'Operador', 4: 'Consultor' };

    // ── Elements ───────────────────────────────────────────────
    const els = {
        searchPanel:   document.getElementById('search-panel'),
        searchQuery:   document.getElementById('search-query'),
        searchResult:  document.getElementById('search-result'),
        resultName:    document.getElementById('result-name'),
        resultDetail:  document.getElementById('result-detail'),
        resultList:    document.getElementById('result-list'),
        formCard:      document.getElementById('form-card'),
        formTitle:     document.getElementById('form-title'),
        formState:     document.getElementById('form-state'),
        activoRow:     document.getElementById('activo-row'),
        activoBadge:   document.getElementById('activo-badge'),

        id:              document.getElementById('usr-id'),
        nombre:          document.getElementById('usr-nombre'),
        username:        document.getElementById('usr-username'),
        nivel:           document.getElementById('usr-nivel'),
        cargo:           document.getElementById('usr-cargo'),
        cuil:            document.getElementById('usr-cuil'),
        bucAcceso:       document.getElementById('usr-buc-acceso'),
        password:        document.getElementById('usr-password'),
        passwordConfirm: document.getElementById('usr-password-confirm'),
        passwordReqStar: document.getElementById('password-req-star'),
        passwordHint:    document.getElementById('password-hint'),

        btnBuscar:             document.getElementById('btn-buscar'),
        btnNuevo:              document.getElementById('btn-nuevo'),
        btnNuevoForzar:        document.getElementById('btn-nuevo-forzar'),
        btnEditarEncontrado:   document.getElementById('btn-editar-encontrado'),
        btnConsultarEncontrado:document.getElementById('btn-consultar-encontrado'),
        btnGuardar:            document.getElementById('btn-guardar'),
        btnCancelar:           document.getElementById('btn-cancelar'),
        btnEditar:             document.getElementById('btn-editar'),
        btnBaja:               document.getElementById('btn-baja'),
        btnReactivar:          document.getElementById('btn-reactivar'),
        btnModoTexto:          document.getElementById('btn-modo-texto'),
        btnModoNumero:         document.getElementById('btn-modo-numero'),
    };

    // ── Init ───────────────────────────────────────────────────
    attachEvents();
    els.searchQuery.focus();

    // ── Eventos ────────────────────────────────────────────────
    function attachEvents() {
        els.btnBuscar.addEventListener('click', buscar);
        els.searchQuery.addEventListener('keydown', e => { if (e.key === 'Enter') buscar(); });

        els.btnNuevo.addEventListener('click', activarModoNuevo);
        els.btnNuevoForzar.addEventListener('click', activarModoNuevo);
        els.btnCancelar.addEventListener('click', handleCancelar);
        els.btnEditar.addEventListener('click', activarModoEdicion);
        els.btnGuardar.addEventListener('click', guardar);
        els.btnBaja.addEventListener('click', () => cambiarEstado(false));
        els.btnReactivar.addEventListener('click', () => cambiarEstado(true));

        els.btnModoTexto.addEventListener('click', () => setModoBusqueda('texto'));
        els.btnModoNumero.addEventListener('click', () => setModoBusqueda('numero'));

        // Guardar disabled hasta que el form esté completo
        // (required + password rules según modo nuevo/edicion)
        state.checkGuardar = ZValidaciones.bindGuardarBoton(els.formCard, els.btnGuardar, {
            extra: () => {
                const pwd = els.password.value;
                const cf  = els.passwordConfirm.value;
                if (state.modo === 'nuevo') {
                    if (!pwd || pwd.length < 8) return false;
                    if (pwd !== cf) return false;
                } else if (state.modo === 'edicion') {
                    if (pwd) {
                        if (pwd.length < 8) return false;
                        if (pwd !== cf) return false;
                    }
                }
                return true;
            }
        }).check;
    }

    function setModoBusqueda(tipo) {
        state.busquedaTipo = tipo;
        if (tipo === 'texto') {
            els.btnModoTexto.classList.replace('z-btn--ghost', 'z-btn--primary');
            els.btnModoNumero.classList.replace('z-btn--primary', 'z-btn--ghost');
            els.searchQuery.placeholder = 'Ingresá nombre del usuario...';
        } else {
            els.btnModoNumero.classList.replace('z-btn--ghost', 'z-btn--primary');
            els.btnModoTexto.classList.replace('z-btn--primary', 'z-btn--ghost');
            els.searchQuery.placeholder = 'Ingresá CUIL o nombre de usuario...';
        }
        els.searchQuery.focus();
    }

    // ── Búsqueda ───────────────────────────────────────────────
    async function buscar() {
        const q = els.searchQuery.value.trim();
        if (!q) { ZUtils.toast('Ingresá un término de búsqueda', 'warning'); return; }

        ocultarResultados();
        try {
            const data = await ZUtils.apiFetch(
                `/usuarios/buscar?q=${encodeURIComponent(q)}&tipo=${state.busquedaTipo}`
            );
            mostrarResultados(data);
        } catch (err) {
            ZUtils.toast(err.message || 'Error al buscar', 'error');
        }
    }

    function mostrarResultados(usuarios) {
        els.searchResult.classList.add('visible');
        els.resultList.innerHTML = '';
        els.btnEditarEncontrado.style.display   = 'none';
        els.btnConsultarEncontrado.style.display = 'none';

        if (usuarios.length === 0) {
            els.resultName.textContent   = 'Sin resultados';
            els.resultDetail.textContent = 'No se encontraron usuarios con ese criterio.';
            return;
        }

        if (usuarios.length === 1) {
            const u = usuarios[0];
            els.resultName.textContent   = u.nombre;
            els.resultDetail.textContent = `${u.username} — Nivel ${u.nivel_acceso} (${NIVELES[u.nivel_acceso] || ''}) — ${u.activo ? 'Activo' : 'Inactivo'}`;
            els.btnEditarEncontrado.style.display    = 'inline-flex';
            els.btnConsultarEncontrado.style.display = 'inline-flex';

            els.btnEditarEncontrado.onclick    = () => cargarUsuario(u.id_usuario, 'edicion');
            els.btnConsultarEncontrado.onclick = () => cargarUsuario(u.id_usuario, 'consulta');
            return;
        }

        els.resultName.textContent   = `${usuarios.length} usuarios encontrados`;
        els.resultDetail.textContent = 'Seleccioná uno para continuar:';

        usuarios.forEach(u => {
            const row = document.createElement('div');
            row.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:7px 0;border-bottom:1px solid var(--z-border);';
            row.innerHTML = `
                <span style="font-size:0.88rem;">
                    <strong>${u.nombre}</strong>
                    <span style="color:var(--z-text2);margin-left:8px;">${u.username}</span>
                    <span style="color:var(--z-text3);margin-left:6px;font-size:0.78rem;">Nivel ${u.nivel_acceso}</span>
                    ${!u.activo ? '<span style="color:#C62828;font-size:0.75rem;margin-left:6px;">[Inactivo]</span>' : ''}
                </span>
                <span style="display:flex;gap:6px;">
                    <button class="z-btn z-btn--xs z-btn--primary" data-id="${u.id_usuario}" data-modo="edicion">Editar</button>
                    <button class="z-btn z-btn--xs z-btn--ghost"   data-id="${u.id_usuario}" data-modo="consulta">Ver</button>
                </span>
            `;
            row.querySelectorAll('button').forEach(btn => {
                btn.addEventListener('click', () =>
                    cargarUsuario(parseInt(btn.dataset.id), btn.dataset.modo)
                );
            });
            els.resultList.appendChild(row);
        });
    }

    function ocultarResultados() {
        els.searchResult.classList.remove('visible');
        els.resultList.innerHTML = '';
    }

    // ── Cargar usuario ─────────────────────────────────────────
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

    // ── Poblar formulario ──────────────────────────────────────
    function poblarFormulario(u) {
        els.id.value              = u.id_usuario || '';
        els.nombre.value          = u.nombre     || '';
        els.username.value        = u.username   || '';
        els.nivel.value           = u.nivel_acceso || '';
        els.cargo.value           = u.id_cargo   || '';
        els.cuil.value            = u.cuil       || '';
        els.bucAcceso.checked     = u.buc_acceso || false;
        els.password.value        = '';
        els.passwordConfirm.value = '';
        actualizarBadgeActivo(u.activo);
    }

    function actualizarBadgeActivo(activo) {
        els.activoBadge.textContent = activo ? '● ACTIVO' : '● INACTIVO';
        els.activoBadge.className = 'z-form-state ' + (activo ? 'z-user-activo' : 'z-user-inactivo');
    }

    // ── Modos de formulario ────────────────────────────────────
    function activarModoNuevo() {
        state.modo    = 'nuevo';
        state.usuario = null;
        resetFormulario();
        mostrarFormCard();

        els.formTitle.textContent = 'Alta de Usuario';
        els.formState.textContent = '● NUEVO';
        els.formState.className   = 'z-form-state z-form-state--new';
        els.activoRow.style.display = 'none';

        setFieldsDisabled(false);
        els.username.readOnly = false;

        els.passwordReqStar.style.display = 'inline';
        els.passwordHint.textContent      = 'Requerida. Mínimo 8 caracteres.';
        els.passwordHint.className        = 'z-password-hint';

        els.btnGuardar.style.display   = 'inline-flex';
        els.btnEditar.style.display    = 'none';
        els.btnBaja.style.display      = 'none';
        els.btnReactivar.style.display = 'none';
        els.btnCancelar.textContent    = '✕ Cancelar';
        els.nombre.focus();
        state.checkGuardar && state.checkGuardar();
    }

    function activarModoEdicion() {
        state.modo = 'edicion';
        const u = state.usuario;

        els.formTitle.textContent = 'Editar Usuario';
        els.formState.textContent = '● EDICIÓN';
        els.formState.className   = 'z-form-state z-form-state--edit';
        els.activoRow.style.display = 'block';

        setFieldsDisabled(false);
        els.username.readOnly = true; // username no se puede cambiar

        els.passwordReqStar.style.display = 'none';
        els.passwordHint.textContent      = 'Dejar vacío para no cambiar la contraseña.';
        els.passwordHint.className        = 'z-password-hint z-password-hint--optional';

        els.btnGuardar.style.display   = 'inline-flex';
        els.btnEditar.style.display    = 'none';
        els.btnCancelar.textContent    = '✕ Salir';

        if (u && u.activo) {
            els.btnBaja.style.display      = 'inline-flex';
            els.btnReactivar.style.display = 'none';
        } else {
            els.btnBaja.style.display      = 'none';
            els.btnReactivar.style.display = 'inline-flex';
        }
        state.checkGuardar && state.checkGuardar();
    }

    function activarModoConsulta() {
        state.modo = 'consulta';

        els.formTitle.textContent = 'Consulta de Usuario';
        els.formState.textContent = '● CONSULTA';
        els.formState.className   = 'z-form-state z-form-state--view';
        els.activoRow.style.display = 'block';

        setFieldsDisabled(true);

        els.btnGuardar.style.display   = 'none';
        els.btnBaja.style.display      = 'none';
        els.btnReactivar.style.display = 'none';
        els.btnEditar.style.display    = 'inline-flex';
        els.btnCancelar.textContent    = '✕ Salir';
    }

    function setFieldsDisabled(disabled) {
        [els.nombre, els.username, els.nivel, els.cargo, els.cuil,
         els.bucAcceso, els.password, els.passwordConfirm].forEach(el => {
            el.disabled = disabled;
        });
    }

    function resetFormulario() {
        [els.id, els.nombre, els.username, els.cargo, els.cuil,
         els.password, els.passwordConfirm].forEach(el => el.value = '');
        els.nivel.value      = '';
        els.bucAcceso.checked = false;
        limpiarErrores();
    }

    function mostrarFormCard() {
        els.formCard.style.display = 'block';
        els.formCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    // ── Cancelar ───────────────────────────────────────────────
    async function handleCancelar() {
        if (state.modo === 'nuevo') {
            const tieneData = els.nombre.value || els.username.value || els.password.value;
            if (tieneData) {
                const ok = await ZUtils.confirm('Cancelar alta', '¿Descartár los datos ingresados?');
                if (!ok) return;
            }
            ocultarFormCard();
        } else {
            ocultarFormCard();
        }
    }

    function ocultarFormCard() {
        els.formCard.style.display = 'none';
        state.modo    = null;
        state.usuario = null;
    }

    // ── Validación ─────────────────────────────────────────────
    function validar() {
        limpiarErrores();
        let ok = true;

        if (!els.nombre.value.trim()) {
            showError('err-nombre', 'El nombre es requerido');
            ok = false;
        }
        if (!els.username.value.trim()) {
            showError('err-username', 'El nombre de usuario es requerido');
            ok = false;
        } else if (!/^[a-zA-Z0-9_.\-]+$/.test(els.username.value.trim())) {
            showError('err-username', 'Solo letras, números, puntos, guiones y guiones bajos');
            ok = false;
        }
        if (!els.nivel.value) {
            showError('err-nivel', 'Seleccioná un nivel de acceso');
            ok = false;
        }

        const pass = els.password.value;
        const passConfirm = els.passwordConfirm.value;

        if (state.modo === 'nuevo') {
            if (!pass) {
                showError('err-password', 'La contraseña es requerida');
                ok = false;
            } else if (pass.length < 8) {
                showError('err-password', 'Mínimo 8 caracteres');
                ok = false;
            }
        } else if (pass) {
            if (pass.length < 8) {
                showError('err-password', 'Mínimo 8 caracteres');
                ok = false;
            }
        }

        if (pass && pass !== passConfirm) {
            showError('err-password-confirm', 'Las contraseñas no coinciden');
            ok = false;
        }

        if (els.cuil.value.trim()) {
            const cuil = els.cuil.value.replace(/[-\s]/g, '');
            if (!/^\d{11}$/.test(cuil)) {
                showError('err-cuil', 'El CUIL debe contener 11 dígitos');
                ok = false;
            }
        }

        return ok;
    }

    function showError(id, msg) {
        const el = document.getElementById(id);
        if (el) { el.textContent = msg; el.style.display = 'block'; }
    }

    function limpiarErrores() {
        document.querySelectorAll('.z-input-error').forEach(el => {
            el.textContent = '';
            el.style.display = 'none';
        });
    }

    // ── Guardar ────────────────────────────────────────────────
    async function guardar() {
        if (!validar()) return;

        const payload = {
            nombre:       els.nombre.value.trim(),
            nivel_acceso: parseInt(els.nivel.value),
            id_cargo:     els.cargo.value.trim() || null,
            cuil:         els.cuil.value.replace(/[-\s]/g, '') || null,
            buc_acceso:   els.bucAcceso.checked,
        };

        if (els.password.value) payload.password = els.password.value;

        try {
            els.btnGuardar.disabled = true;
            els.btnGuardar.textContent = '⏳ Guardando...';

            if (state.modo === 'nuevo') {
                payload.username = els.username.value.trim();
                const u = await ZUtils.apiFetch('/usuarios', {
                    method: 'POST',
                    body: JSON.stringify(payload)
                });
                cargarVistaPrevia();
                ZUtils.modalGuardado(
                    'Usuario creado',
                    `${u.nombre} (${u.username}) fue registrado correctamente.`,
                    activarModoNuevo,
                    () => window.location.href = 'mainconfig.html'
                );
            } else {
                const u = await ZUtils.apiFetch(`/usuarios/${state.usuario.id_usuario}`, {
                    method: 'PUT',
                    body: JSON.stringify(payload)
                });
                state.usuario = u;
                poblarFormulario(u);
                activarModoConsulta();
                ZUtils.toast('Usuario guardado correctamente', 'success');
            }
        } catch (err) {
            ZUtils.toast(err.message || 'Error al guardar', 'error');
        } finally {
            els.btnGuardar.disabled = false;
            els.btnGuardar.textContent = '💾 Guardar';
        }
    }

    // ── Vista previa: últimos 5 usuarios ──────────────────────
    async function cargarVistaPrevia() {
        const container = document.getElementById('preview-rows');
        if (!container) return;
        try {
            const data = await ZUtils.apiFetch('/usuarios?solo_activos=true');
            const recientes = [...data].reverse().slice(0, 5);
            if (recientes.length === 0) {
                container.innerHTML = '<div style="color:var(--z-text3);font-size:0.82rem;">Sin registros</div>';
                return;
            }
            container.innerHTML = recientes.map(u => `
                <div class="z-preview-row" data-id="${u.id_usuario}" data-modo="consulta">
                    <span class="z-preview-row__main">${u.nombre}</span>
                    <span class="z-preview-row__meta">${u.username}</span>
                    <span class="z-preview-row__meta" style="margin-left:4px;">Nivel ${u.nivel_acceso}${!u.activo ? ' · <span style="color:#cf2d56">Inactivo</span>' : ''}</span>
                    <span class="z-preview-row__action">Ver →</span>
                </div>
            `).join('');
            container.querySelectorAll('.z-preview-row').forEach(row => {
                row.addEventListener('click', () =>
                    cargarUsuario(parseInt(row.dataset.id), 'consulta')
                );
            });
        } catch {
            container.innerHTML = '<div style="color:var(--z-text3);font-size:0.82rem;">No se pudo cargar la vista previa</div>';
        }
    }

    // ── Listado completo ───────────────────────────────────────
    let _listadoData = [];

    async function abrirListado() {
        document.getElementById('preview-section').style.display = 'none';
        document.getElementById('listado-section').style.display = 'block';
        document.getElementById('form-card').style.display       = 'none';
        document.getElementById('search-panel').style.display    = 'none';
        document.getElementById('listado-contenido').innerHTML   =
            '<div style="text-align:center;padding:2rem;"><span class="z-spinner"></span></div>';
        try {
            _listadoData = await ZUtils.apiFetch('/usuarios?solo_activos=false');
            aplicarFiltrosListado();
        } catch (err) {
            document.getElementById('listado-contenido').innerHTML =
                `<div style="color:var(--z-text-error);padding:1rem;">Error: ${err.message}</div>`;
        }
    }

    function cerrarListado() {
        document.getElementById('listado-section').style.display = 'none';
        document.getElementById('preview-section').style.display = 'block';
        document.getElementById('search-panel').style.display    = 'block';
    }

    function aplicarFiltrosListado() {
        let rows = [..._listadoData];
        const txt   = (document.getElementById('lst-texto')?.value  || '').toLowerCase().trim();
        const orden = document.getElementById('lst-orden')?.value   || 'reciente';
        const desde = document.getElementById('lst-desde')?.value   || '';
        const hasta = document.getElementById('lst-hasta')?.value   || '';

        if (txt) {
            rows = rows.filter(u =>
                (u.nombre   || '').toLowerCase().includes(txt) ||
                (u.username || '').toLowerCase().includes(txt) ||
                (u.cuil     || '').includes(txt)
            );
        }
        if (desde || hasta) {
            rows = rows.filter(u => {
                const d = (u.fecha_alta || '').slice(0, 10);
                if (!d) return true;
                if (desde && d < desde) return false;
                if (hasta && d > hasta) return false;
                return true;
            });
        }
        if (orden === 'reciente') rows = rows.reverse();
        else if (orden === 'az') rows.sort((a, b) => (a.nombre || '').localeCompare(b.nombre || '', 'es'));
        else if (orden === 'za') rows.sort((a, b) => (b.nombre || '').localeCompare(a.nombre || '', 'es'));
        // 'antiguo' ya viene asc de la API

        renderListado(rows);
    }

    function limpiarFiltrosListado() {
        ['lst-texto', 'lst-desde', 'lst-hasta'].forEach(id => {
            const el = document.getElementById(id); if (el) el.value = '';
        });
        const ord = document.getElementById('lst-orden');
        if (ord) ord.value = 'reciente';
        aplicarFiltrosListado();
    }

    function renderListado(rows) {
        const fecha = new Date().toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric' });
        document.getElementById('lst-print-header').innerHTML =
            `<h2>Padrón de Usuarios — ZARIS</h2><p>Listado generado el ${fecha} · ${rows.length} registro${rows.length !== 1 ? 's' : ''}</p>`;

        const bodyRows = rows.length === 0
            ? `<tr><td colspan="6" style="text-align:center;padding:2rem;color:var(--z-text3);">Sin resultados</td></tr>`
            : rows.map(u => `<tr>
                <td>${u.nombre}</td>
                <td class="mono">${u.username}</td>
                <td>${NIVELES[u.nivel_acceso] || u.nivel_acceso}</td>
                <td class="mono">${u.cuil || '—'}</td>
                <td><span style="color:${u.activo ? 'var(--color-success)' : '#cf2d56'};font-size:0.78rem;font-weight:600;">${u.activo ? 'Activo' : 'Inactivo'}</span></td>
                <td>
                    <button class="z-tbl-btn" data-id="${u.id_usuario}" data-modo="consulta">Ver</button>
                    <button class="z-tbl-btn" data-id="${u.id_usuario}" data-modo="edicion" style="margin-left:4px;">Editar</button>
                </td>
            </tr>`).join('');

        document.getElementById('listado-contenido').innerHTML = `
            <div style="font-size:0.78rem;color:var(--z-text3);margin-bottom:0.6rem;">${rows.length} usuario${rows.length !== 1 ? 's' : ''} encontrado${rows.length !== 1 ? 's' : ''}</div>
            <div class="z-listado-wrap">
                <table>
                    <thead><tr><th>Nombre</th><th>Usuario</th><th>Nivel</th><th>CUIL</th><th>Estado</th><th>Acciones</th></tr></thead>
                    <tbody>${bodyRows}</tbody>
                </table>
            </div>`;

        document.getElementById('listado-contenido').querySelectorAll('.z-tbl-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                cerrarListado();
                cargarUsuario(parseInt(btn.dataset.id), btn.dataset.modo);
            });
        });
    }

    // Registrar eventos listado
    document.getElementById('btn-listado')?.addEventListener('click', abrirListado);
    document.getElementById('btn-cerrar-listado')?.addEventListener('click', cerrarListado);
    document.getElementById('btn-filtrar-lst')?.addEventListener('click', aplicarFiltrosListado);
    document.getElementById('btn-limpiar-lst')?.addEventListener('click', limpiarFiltrosListado);
    document.getElementById('lst-texto')?.addEventListener('keydown', e => { if (e.key === 'Enter') aplicarFiltrosListado(); });

    // Cargar vista previa al iniciar
    cargarVistaPrevia();

    // ── Alta / Baja ────────────────────────────────────────────
    async function cambiarEstado(nuevoActivo) {
        const accion = nuevoActivo ? 'reactivar' : 'dar de baja';
        const titulo = nuevoActivo ? 'Reactivar usuario' : 'Dar de baja usuario';
        const msg    = nuevoActivo
            ? `¿Reactivar al usuario <strong>${state.usuario.nombre}</strong>?`
            : `¿Dar de baja al usuario <strong>${state.usuario.nombre}</strong>? No podrá iniciar sesión.`;

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
        } catch (err) {
            ZUtils.toast(err.message || `Error al ${accion}`, 'error');
        }
    }

});
