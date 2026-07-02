/**
 * ZARIS — Padrón de Usuarios
 */
document.addEventListener('DOMContentLoaded', () => {

    const NIVELES = { 1: 'Administrador', 2: 'Supervisor', 3: 'Atención', 4: 'Gestión', 5: 'Consultor' };

    // Etiquetas legibles para los códigos de módulo (catálogo §30).
    const MODULO_LABEL = {
        reclamos: 'Reclamos', padrones: 'Padrones', agenda: 'Agenda',
        turnos: 'Turnos', entradas: 'Entradas', tramites: 'Trámites',
        encuestas: 'Encuestas', usuarios: 'Usuarios', admin_tablas: 'Maestros',
        ot_agente: 'OT·Agente', ot_supervisor: 'OT·Supervisor', ot_auditoria: 'OT·Auditoría',
        guias: 'Guías',
    };

    // Renderiza los módulos permitidos como chips. Devuelve HTML escapado.
    function modChips(mods) {
        const arr = Array.isArray(mods) ? mods : [];
        if (!arr.length) return '<span class="mod-chip mod-chip--none">sin acceso</span>';
        return arr.map(c => `<span class="mod-chip">${esc(MODULO_LABEL[c] || c)}</span>`).join('');
    }

    // Fecha+hora legible (es-AR) para "último login". Null → "Nunca".
    function fmtFechaHora(iso) {
        if (!iso) return 'Nunca';
        const d = new Date(iso);
        if (isNaN(d)) return '—';
        return d.toLocaleString('es-AR', {
            day: '2-digit', month: '2-digit', year: 'numeric',
            hour: '2-digit', minute: '2-digit',
        });
    }

    // Catálogo de módulos (modulo_codigo → min_nivel_acceso) para previsualizar,
    // al cambiar el nivel en el form, qué módulos otorgaría por defecto. Los
    // overrides por usuario no se ven acá (el form no los edita); el detalle de
    // un usuario cargado usa sus modulos_permitidos reales (ya resueltos).
    let _modCatalogo = null;
    async function cargarModCatalogo() {
        if (_modCatalogo) return _modCatalogo;
        try {
            const data = await ZUtils.apiFetch('/admin/permisos/modulos', { base: 'root' });
            _modCatalogo = data.filter(m => m.activo !== false)
                .map(m => ({ codigo: m.modulo_codigo, min: m.min_nivel_acceso }));
        } catch (_) { _modCatalogo = []; }
        return _modCatalogo;
    }

    // Pinta los chips de acceso en el form. Si hay un usuario cargado usa sus
    // módulos reales; si no (alta nueva), deriva del nivel elegido + catálogo.
    async function renderModulosAcceso() {
        const chips = $('usr-modulos-chips');
        if (!chips) return;
        if (state.usuario && Array.isArray(state.usuario.modulos_permitidos)) {
            chips.innerHTML = modChips(state.usuario.modulos_permitidos);
            return;
        }
        const nivel = parseInt($('usr-nivel').value);
        if (!nivel) { chips.innerHTML = '<span class="mod-chip mod-chip--none">elegí un nivel</span>'; return; }
        const cat = await cargarModCatalogo();
        const mods = cat.filter(m => m.min >= nivel).map(m => m.codigo).sort();
        chips.innerHTML = modChips(mods);
    }

    // ── State ──────────────────────────────────────────────────────────────────
    const state = {
        modo:    null,   // 'nuevo' | 'edicion' | 'consulta'
        usuario: null,
    };

    let _listadoData = [];

    // ── Refs ───────────────────────────────────────────────────────────────────
    const $ = id => document.getElementById(id);

    // ── Buscador predictivo de subárea ───────────────────────────────────────────
    // (input + dropdown debounced; skipNextRef evita reabrir el dropdown al pickear, §29)
    let _subareaDebounce = null;
    let _subareaSkipNext = false;

    function setSubareaSeleccionada(id, nombre, areaNombre) {
        $('usr-subarea').value = id != null ? id : '';
        if (id != null) {
            $('usr-subarea-q').value = nombre || '';
            $('usr-subarea-selected').textContent = areaNombre ? `Área: ${areaNombre}` : '';
        } else {
            $('usr-subarea-q').value = '';
            $('usr-subarea-selected').textContent = '';
        }
        $('usr-subarea-results').classList.remove('visible');
    }

    async function buscarSubareas(q) {
        const box = $('usr-subarea-results');
        try {
            const data = await ZUtils.apiFetch(`/subareas/buscar?q=${encodeURIComponent(q)}&limit=20`);
            if (!data.length) {
                box.innerHTML = '<div class="subarea-results__empty">Sin resultados</div>';
                box.classList.add('visible');
                return;
            }
            box.innerHTML = data.map(s => `
                <div class="subarea-item" data-id="${s.id_subarea}" data-nombre="${esc(s.nombre)}" data-area="${esc(s.area_nombre || '')}">
                    <span class="subarea-item__nombre">${esc(s.nombre)}</span>
                    ${s.area_nombre ? `<span class="subarea-item__area">${esc(s.area_nombre)}</span>` : ''}
                </div>`).join('');
            box.classList.add('visible');
            box.querySelectorAll('.subarea-item').forEach(el =>
                el.addEventListener('click', () => {
                    _subareaSkipNext = true;
                    setSubareaSeleccionada(parseInt(el.dataset.id), el.dataset.nombre, el.dataset.area);
                })
            );
        } catch (err) {
            box.innerHTML = `<div class="subarea-results__empty">Error: ${esc(err.message)}</div>`;
            box.classList.add('visible');
        }
    }

    $('usr-subarea-q').addEventListener('input', () => {
        if (_subareaSkipNext) { _subareaSkipNext = false; return; }
        // Al tipear manualmente se invalida la selección previa.
        $('usr-subarea').value = '';
        $('usr-subarea-selected').textContent = '';
        const q = $('usr-subarea-q').value.trim();
        clearTimeout(_subareaDebounce);
        if (q.length < 1) { $('usr-subarea-results').classList.remove('visible'); return; }
        _subareaDebounce = setTimeout(() => buscarSubareas(q), 280);
    });

    // Click-outside cierra el dropdown
    document.addEventListener('click', (e) => {
        if (!e.target.closest('#row-subarea-wrap') && !e.target.closest('#usr-subarea-q')
            && !e.target.closest('#usr-subarea-results')) {
            $('usr-subarea-results').classList.remove('visible');
        }
    });

    // Toggle: usuario externo deshabilita y limpia subárea
    $('usr-externo').addEventListener('change', aplicarToggleExterno);

    function aplicarToggleExterno() {
        const externo = $('usr-externo').checked;
        $('usr-subarea-q').disabled = externo;
        if (externo) {
            setSubareaSeleccionada(null);
            $('usr-subarea-q').placeholder = 'No aplica (usuario externo)';
            const lbl = document.querySelector('label[for="usr-subarea-q"]');
            if (lbl) lbl.classList.remove('label-zaris--required');
        } else {
            $('usr-subarea-q').placeholder = 'Escribí para buscar subárea...';
            const lbl = document.querySelector('label[for="usr-subarea-q"]');
            if (lbl) lbl.classList.add('label-zaris--required');
        }
    }

    // ── Inicialización ─────────────────────────────────────────────────────────
    $('btn-buscar').addEventListener('click', buscar);
    $('search-query').addEventListener('keydown', e => { if (e.key === 'Enter') buscar(); });
    // Búsqueda predictiva en vivo (debounce 280ms). El botón "Buscar" sigue disponible.
    let _buscarDebounce = null;
    $('search-query').addEventListener('input', () => {
        clearTimeout(_buscarDebounce);
        const q = $('search-query').value.trim();
        if (q.length < 1) { $('search-result').classList.remove('visible'); return; }
        _buscarDebounce = setTimeout(buscar, 280);
    });
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
    // Filtro en vivo mientras se escribe (filtrado en memoria, instantáneo).
    let _filtroDebounce = null;
    $('lst-texto').addEventListener('input', () => {
        clearTimeout(_filtroDebounce);
        _filtroDebounce = setTimeout(aplicarFiltros, 200);
    });
    $('lst-subarea').addEventListener('change', aplicarFiltros);
    $('lst-nivel').addEventListener('change', aplicarFiltros);

    const _guardarBtn = ZValidaciones.bindGuardarBoton($('form-card'), $('btn-guardar'), {
        extra: () => {
            const pwd = $('usr-password').value;
            const cf  = $('usr-password-confirm').value;
            if (state.modo === 'nuevo') {
                // El alta ya no pide contraseña (la genera el sistema y la manda
                // por mail), pero el email pasa a ser obligatorio y real.
                const email = $('usr-email').value.trim();
                if (!email || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return false;
            } else if (state.modo === 'edicion' && pwd) {
                if (pwd.length < 8) return false;
                if (pwd !== cf) return false;
            }
            return true;
        }
    });
    // Los campos se pueblan programáticamente al editar/consultar (setear .value no
    // dispara input/change), así que el botón no se re-evalúa solo. Llamarlo a mano
    // tras cada cambio de modo o populación del form.
    function revalidarGuardar() { _guardarBtn.check(); pistaPassword(); }

    // Pista en vivo del estado de la contraseña: como el botón Guardar se deshabilita
    // cuando falta confirmar (o no coinciden), el usuario no puede apretarlo para ver
    // el error. Mostramos el motivo en el hint de "Confirmar contraseña" mientras tipea.
    function pistaPassword() {
        const err = $('err-password-confirm');
        if (!err) return;
        const pwd = $('usr-password').value;
        const cf  = $('usr-password-confirm').value;
        const show = (msg, esError) => {
            err.textContent = msg;
            err.style.display = msg ? 'block' : 'none';
            err.style.color = esError ? 'var(--color-error)' : 'var(--fg-3)';
        };
        if (!pwd) { show('', false); return; }            // sin contraseña: nada que confirmar
        if (pwd.length < 8) { show('La nueva contraseña debe tener mínimo 8 caracteres.', true); return; }
        if (!cf) { show('Repetí la contraseña para confirmar el cambio.', false); return; }
        if (pwd !== cf) { show('Las contraseñas no coinciden.', true); return; }
        show('La contraseña coincide.', false);
    }
    $('usr-password').addEventListener('input', pistaPassword);
    $('usr-password-confirm').addEventListener('input', pistaPassword);
    // En alta el email es obligatorio y gobierna el botón Guardar → revalidar al tipear.
    $('usr-email').addEventListener('input', () => { if (state.modo === 'nuevo') _guardarBtn.check(); });

    // Al cambiar el nivel en alta nueva, refrescar los módulos que otorgaría.
    $('usr-nivel').addEventListener('change', () => {
        if (state.modo === 'nuevo') renderModulosAcceso();
    });

    // Historial de accesos (auditoría)
    $('btn-ver-historial').addEventListener('click', abrirHistorial);
    $('btn-cerrar-historial').addEventListener('click', cerrarHistorial);
    $('historial-overlay').addEventListener('click', (e) => {
        if (e.target === $('historial-overlay')) cerrarHistorial();
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && $('historial-overlay').style.display === 'flex') cerrarHistorial();
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
            name.textContent   = u.username;
            detail.textContent = `${NIVELES[u.nivel_acceso] || 'Nivel ' + u.nivel_acceso} — ${u.es_externo ? 'Externo' : (u.subarea_nombre || 'Sin subárea')} — ${u.activo ? 'Activo' : 'Inactivo'}`;
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
            row.style.cssText = 'display:flex;align-items:center;justify-content:space-between;padding:7px 0;border-bottom:1px solid var(--border-primary);';
            row.innerHTML = `
                <span style="font-size:0.88rem;">
                    <strong>${esc(u.username)}</strong>
                    <span style="color:var(--fg-3);margin-left:8px;font-size:0.78rem;">${NIVELES[u.nivel_acceso] || ''}</span>
                    ${!u.activo ? '<span style="color:var(--color-error);font-size:0.75rem;margin-left:6px;">[Inactivo]</span>' : ''}
                </span>
                <span style="display:flex;gap:6px;">
                    <button class="btn-zaris btn-zaris--xs btn-zaris--primary" data-id="${u.id_usuario}" data-modo="edicion">Editar</button>
                    <button class="btn-zaris btn-zaris--xs btn-zaris--ghost"   data-id="${u.id_usuario}" data-modo="consulta">Ver</button>
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
        $('usr-username').value        = u.username   || '';
        $('usr-email').value           = u.email      || '';
        $('usr-nivel').value           = u.nivel_acceso || '';
        $('usr-buc-acceso').checked    = u.buc_acceso || false;
        $('usr-externo').checked       = u.es_externo || false;
        setSubareaSeleccionada(u.id_subarea ?? null, u.subarea_nombre, null);
        aplicarToggleExterno();
        $('usr-password').value        = '';
        $('usr-password-confirm').value = '';
        const badge = $('activo-badge');
        badge.textContent  = u.activo ? 'Activo' : 'Inactivo';
        badge.className    = u.activo ? 'badge-activo' : 'badge-inactivo';
        // Módulos a los que accede (al lado del nivel) + último login (al final).
        renderModulosAcceso();
        $('ultimo-login-row').style.display = 'block';
        $('usr-ultimo-login').textContent   = fmtFechaHora(u.fecha_ultimo_login);
        revalidarGuardar();
    }

    function activarModoNuevo() {
        state.modo    = 'nuevo';
        state.usuario = null;
        resetFormulario();
        mostrarFormCard();
        $('form-title').textContent      = 'Alta de Usuario';
        $('form-state').textContent      = 'NUEVO';
        $('form-state').className        = 'form-state form-state--new';
        $('activo-row').style.display    = 'none';
        $('usr-username').readOnly       = false;
        // Alta: el sistema genera la clave temporal y la manda por mail → ocultar
        // los campos de contraseña y mostrar el aviso.
        $('password-aviso-alta').style.display = 'block';
        $('password-campos').style.display     = 'none';
        setFieldsDisabled(false);
        $('btn-guardar').style.display   = 'inline-flex';
        $('btn-editar').style.display    = 'none';
        $('btn-baja').style.display      = 'none';
        $('btn-reactivar').style.display = 'none';
        $('btn-cancelar').textContent    = 'Cancelar';
        $('ultimo-login-row').style.display = 'none';  // un alta nueva nunca inició sesión
        renderModulosAcceso();
        revalidarGuardar();
        $('usr-username').focus();
    }

    function activarModoEdicion() {
        state.modo = 'edicion';
        const u = state.usuario;
        $('form-title').textContent      = 'Editar Usuario';
        $('form-state').textContent      = 'EDICIÓN';
        $('form-state').className        = 'form-state form-state--edit';
        $('activo-row').style.display    = 'block';
        $('usr-username').readOnly       = true;
        // Edición: el admin puede resetear la contraseña manualmente → mostrar campos.
        $('password-aviso-alta').style.display = 'none';
        $('password-campos').style.display     = 'flex';
        $('password-req-star').style.display = 'none';
        $('password-hint').textContent   = 'Dejar vacío para no cambiar la contraseña.';
        setFieldsDisabled(false);
        $('btn-guardar').style.display   = 'inline-flex';
        $('btn-editar').style.display    = 'none';
        $('btn-cancelar').textContent    = 'Salir';
        $('btn-baja').style.display      = (u && u.activo)  ? 'inline-flex' : 'none';
        $('btn-reactivar').style.display = (u && !u.activo) ? 'inline-flex' : 'none';
        revalidarGuardar();
    }

    function activarModoConsulta() {
        state.modo = 'consulta';
        $('form-title').textContent      = 'Consulta de Usuario';
        $('form-state').textContent      = 'CONSULTA';
        $('form-state').className        = 'form-state form-state--view';
        $('activo-row').style.display    = 'block';
        $('password-aviso-alta').style.display = 'none';
        $('password-campos').style.display     = 'flex';
        setFieldsDisabled(true);
        $('btn-guardar').style.display   = 'none';
        $('btn-baja').style.display      = 'none';
        $('btn-reactivar').style.display = 'none';
        $('btn-editar').style.display    = 'inline-flex';
        $('btn-cancelar').textContent    = 'Salir';
    }

    function setFieldsDisabled(dis) {
        ['usr-username','usr-email','usr-nivel',
         'usr-buc-acceso','usr-externo','usr-subarea-q','usr-password','usr-password-confirm'].forEach(id => {
            const el = $(id); if (el) el.disabled = dis;
        });
        // En modo no-consulta, el input de subárea respeta el toggle de externo.
        if (!dis) aplicarToggleExterno();
    }

    function resetFormulario() {
        ['usr-id','usr-username','usr-email',
         'usr-password','usr-password-confirm'].forEach(id => { const el=$(id); if(el) el.value=''; });
        $('usr-nivel').value      = '';
        $('usr-buc-acceso').checked = false;
        $('usr-externo').checked    = false;
        setSubareaSeleccionada(null);
        aplicarToggleExterno();
        document.querySelectorAll('.input-error-zaris').forEach(el => { el.textContent=''; el.style.display='none'; });
    }

    function mostrarFormCard() {
        $('form-card').style.display = 'block';
        $('form-card').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    async function handleCancelar() {
        if (state.modo === 'nuevo') {
            const tieneData = $('usr-username').value || $('usr-email').value || $('usr-password').value;
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
        document.querySelectorAll('.input-error-zaris').forEach(el => { el.textContent=''; el.style.display='none'; });
        let ok = true;

        const showErr = (id, msg) => { const el=$(id); if(el){el.textContent=msg;el.style.display='block';} };

        if (!$('usr-username').value.trim())  { showErr('err-username', 'El nombre de usuario es requerido'); ok=false; }
        else if (!/^[a-zA-Z0-9_.\-]+$/.test($('usr-username').value.trim()))
            { showErr('err-username', 'Solo letras, números, puntos y guiones'); ok=false; }
        if (!$('usr-nivel').value)            { showErr('err-nivel',    'Seleccioná un nivel de acceso'); ok=false; }

        if (!$('usr-externo').checked && !$('usr-subarea').value) {
            showErr('err-subarea', 'La subárea es obligatoria (o marcá "Usuario externo")'); ok=false;
        }

        // En alta el email es obligatorio (canal de entrega de la clave temporal).
        if (state.modo === 'nuevo') {
            const email = $('usr-email').value.trim();
            if (!email)                                         { showErr('err-email', 'El email es requerido'); ok=false; }
            else if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) { showErr('err-email', 'Formato de email inválido'); ok=false; }
        }

        // La contraseña solo se valida en EDICIÓN (reset manual por admin). En alta
        // la genera el sistema, no hay campos que validar.
        if (state.modo === 'edicion') {
            const pass = $('usr-password').value;
            const cf   = $('usr-password-confirm').value;
            if (pass && pass.length < 8) { showErr('err-password', 'Mínimo 8 caracteres'); ok=false; }
            if (pass && pass !== cf)     { showErr('err-password-confirm', 'Las contraseñas no coinciden'); ok=false; }
        }

        return ok;
    }

    // ── Guardar ────────────────────────────────────────────────────────────────
    async function guardar() {
        if (!validar()) return;

        const externo = $('usr-externo').checked;
        const payload = {
            nivel_acceso: parseInt($('usr-nivel').value),
            buc_acceso:   $('usr-buc-acceso').checked,
            es_externo:   externo,
            id_subarea:   externo ? null : (parseInt($('usr-subarea').value) || null),
        };
        const emailVal = $('usr-email').value.trim();
        if (emailVal) payload.email = emailVal;  // obligatorio en alta; el backend rechaza alta sin email
        // En alta NO se manda password (la genera el sistema). En edición, solo si
        // el admin quiere resetearla.
        if (state.modo !== 'nuevo' && $('usr-password').value) payload.password = $('usr-password').value;

        try {
            $('btn-guardar').disabled    = true;
            $('btn-guardar').textContent = 'Guardando...';

            if (state.modo === 'nuevo') {
                payload.username = $('usr-username').value.trim();
                const u = await ZUtils.apiFetch('/usuarios', { method:'POST', body:JSON.stringify(payload) });
                cargarVistaPrevia();
                ZUtils.modalGuardado(
                    'Usuario creado',
                    `El usuario ${u.username} fue registrado. Se le envió una contraseña temporal a ${u.email}; deberá cambiarla en su primer ingreso.`,
                    activarModoNuevo
                    // onSalir omitido: usa _zarisGoInicio() (shell vanilla → dashboard)
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
            ? `¿Reactivar al usuario ${state.usuario.username}?`
            : `¿Dar de baja al usuario ${state.usuario.username}? No podrá iniciar sesión.`;
        const ok = await ZUtils.confirm(titulo, msg, {
            cancelLabel:  'Cancelar',
            confirmLabel: nuevoActivo ? 'Sí, reactivar' : 'Sí, dar de baja',
            danger:       !nuevoActivo,
        });
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

    // ── Historial de accesos (auditoría) ─────────────────────────────────────────
    async function abrirHistorial() {
        if (!state.usuario) return;
        const u = state.usuario;
        $('historial-title').textContent = `Historial de accesos — ${u.username}`;
        $('historial-body').innerHTML = '<tr><td colspan="3" style="text-align:center;color:var(--fg-3);">Cargando...</td></tr>';
        $('historial-empty').style.display = 'none';
        $('historial-overlay').style.display = 'flex';
        try {
            const data = await ZUtils.apiFetch(`/usuarios/${u.id_usuario}/login-log?limit=50`);
            if (!data.length) {
                $('historial-body').innerHTML = '';
                $('historial-empty').style.display = 'block';
                return;
            }
            $('historial-body').innerHTML = data.map(l => `
                <tr>
                    <td class="mono">${esc(fmtFechaHora(l.fecha_login))}</td>
                    <td class="mono">${esc(l.ip || '—')}</td>
                    <td style="max-width:340px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${esc(l.user_agent || '')}">${esc(l.user_agent || '—')}</td>
                </tr>`).join('');
        } catch (err) {
            $('historial-body').innerHTML = `<tr><td colspan="3" style="color:var(--color-error);">Error: ${esc(err.message)}</td></tr>`;
        }
    }

    function cerrarHistorial() {
        $('historial-overlay').style.display = 'none';
    }

    // ── Vista previa ───────────────────────────────────────────────────────────
    async function cargarVistaPrevia() {
        const container = $('preview-rows');
        if (!container) return;
        container.innerHTML = '<div style="color:var(--fg-3);font-size:0.82rem;padding:0.5rem 0;">Cargando...</div>';
        try {
            const data = await ZUtils.apiFetch('/usuarios?solo_activos=false');
            // Ordenar por última actividad (fecha_modif desc) → muestra tanto
            // los recién ingresados como los recién modificados. Fallback a id.
            const ts = u => Date.parse(u.fecha_modif || u.fecha_alta || '') || (u.id_usuario || 0);
            const recientes = [...data]
                .sort((a, b) => ts(b) - ts(a))
                .slice(0, 5);

            if (recientes.length === 0) {
                container.innerHTML = '<div style="color:var(--fg-3);font-size:0.82rem;padding:0.5rem 0;">Sin registros</div>';
                return;
            }

            // El usuario ES la identidad (no mostramos nombre/cargo/cuil): username
            // como label principal + nivel + subárea + último login + estado. Los
            // módulos a los que accede NO van acá — se ven en el detalle, al lado
            // del nivel.
            container.innerHTML = recientes.map(u => `
                <div class="preview-row" data-id="${u.id_usuario}">
                    <span class="preview-row__nombre">${esc(u.username)}</span>
                    <span class="preview-row__nivel">${NIVELES[u.nivel_acceso] || 'Nivel ' + u.nivel_acceso}</span>
                    <span class="preview-row__nivel" style="flex:1;min-width:0;">${u.es_externo ? 'Externo' : esc(u.subarea_nombre || '—')}</span>
                    <span class="preview-row__nivel" title="Último inicio de sesión">↪ ${fmtFechaHora(u.fecha_ultimo_login)}</span>
                    <span class="preview-row__estado preview-row__estado--${u.activo ? 'activo' : 'inactivo'}">${u.activo ? 'Activo' : 'Inactivo'}</span>
                    <span class="preview-row__cta">Ver →</span>
                </div>
            `).join('');

            container.querySelectorAll('.preview-row').forEach(row =>
                row.addEventListener('click', () => cargarUsuario(parseInt(row.dataset.id), 'consulta'))
            );
        } catch (err) {
            console.error('[Preview usuarios]', err);
            container.innerHTML = `<div style="color:var(--fg-3);font-size:0.82rem;padding:0.5rem 0;">No se pudo cargar la vista previa (${err.message})</div>`;
        }
    }

    // ── Listado completo ───────────────────────────────────────────────────────
    async function abrirListado() {
        $('search-panel').style.display  = 'none';
        $('preview-section').style.display = 'none';
        $('form-card').style.display     = 'none';
        $('listado-section').style.display = 'block';
        $('listado-contenido').innerHTML = '<div style="text-align:center;padding:2rem;color:var(--fg-3);">Cargando...</div>';
        $('lst-count').textContent = '';
        try {
            _listadoData = await ZUtils.apiFetch('/usuarios?solo_activos=false');
            poblarFiltroSubareas();
            aplicarFiltros();
        } catch (err) {
            $('listado-contenido').innerHTML =
                `<div style="color:var(--color-error);padding:1rem;">Error al cargar: ${err.message}</div>`;
        }
    }

    function cerrarListado() {
        $('listado-section').style.display  = 'none';
        $('search-panel').style.display     = 'block';
        $('preview-section').style.display  = 'block';
    }

    function poblarFiltroSubareas() {
        const sel = $('lst-subarea');
        if (!sel) return;
        const vistos = new Map();
        _listadoData.forEach(u => {
            if (u.id_subarea != null && u.subarea_nombre && !vistos.has(u.id_subarea)) {
                vistos.set(u.id_subarea, u.subarea_nombre);
            }
        });
        const opciones = [...vistos.entries()].sort((a, b) => a[1].localeCompare(b[1], 'es'));
        sel.innerHTML = '<option value="">Todas</option>'
            + '<option value="__externo">Externos (sin subárea)</option>'
            + opciones.map(([id, nombre]) => `<option value="${id}">${esc(nombre)}</option>`).join('');
    }

    function aplicarFiltros() {
        let rows   = [..._listadoData];
        const txt  = ($('lst-texto').value  || '').toLowerCase().trim();
        const niv  = $('lst-nivel').value   || '';
        const sub  = $('lst-subarea').value || '';
        const ord  = $('lst-orden').value   || 'reciente';
        const desd = $('lst-desde').value   || '';
        const hast = $('lst-hasta').value   || '';

        if (txt) rows = rows.filter(u =>
            (u.username      || '').toLowerCase().includes(txt) ||
            (u.subarea_nombre|| '').toLowerCase().includes(txt)
        );
        if (niv) rows = rows.filter(u => String(u.nivel_acceso) === niv);
        if (sub === '__externo') rows = rows.filter(u => u.es_externo);
        else if (sub) rows = rows.filter(u => String(u.id_subarea) === sub);
        if (desd || hast) rows = rows.filter(u => {
            const d = (u.fecha_alta || '').slice(0, 10);
            if (!d) return true;
            if (desd && d < desd) return false;
            if (hast && d > hast) return false;
            return true;
        });

        if      (ord === 'reciente') rows.sort((a,b) => (b.id_usuario||0)-(a.id_usuario||0));
        else if (ord === 'antiguo')  rows.sort((a,b) => (a.id_usuario||0)-(b.id_usuario||0));
        else if (ord === 'az')       rows.sort((a,b) => (a.username||'').localeCompare(b.username||'','es'));
        else if (ord === 'za')       rows.sort((a,b) => (b.username||'').localeCompare(a.username||'','es'));

        renderListado(rows);
    }

    function limpiarFiltros() {
        ['lst-texto','lst-desde','lst-hasta'].forEach(id => { const el=$(id); if(el) el.value=''; });
        $('lst-nivel').value = '';
        $('lst-subarea').value = '';
        $('lst-orden').value = 'reciente';
        aplicarFiltros();
    }

    function renderListado(rows) {
        const fecha = new Date().toLocaleDateString('es-AR', { day:'2-digit', month:'2-digit', year:'numeric' });
        $('lst-print-header').innerHTML =
            `<h2>Maestro de Usuarios — ZARIS</h2><p>Listado generado el ${fecha} · ${rows.length} registro${rows.length!==1?'s':''}</p>`;
        $('lst-count').textContent = `${rows.length} usuario${rows.length!==1?'s':''} encontrado${rows.length!==1?'s':''}`;

        if (rows.length === 0) {
            $('listado-contenido').innerHTML =
                '<div style="text-align:center;padding:2.5rem;color:var(--fg-3);">Sin resultados para los filtros aplicados</div>';
            return;
        }

        const bodyRows = rows.map(u => `
            <tr>
                <td class="mono">${esc(u.username)}</td>
                <td>${NIVELES[u.nivel_acceso] || u.nivel_acceso}</td>
                <td>${u.es_externo ? '<span style="color:var(--fg-3);font-style:italic;">Externo</span>' : esc(u.subarea_nombre || '—')}</td>
                <td><span class="badge-${u.activo?'activo':'inactivo'}">${u.activo?'Activo':'Inactivo'}</span></td>
                <td>
                    <button class="tbl-btn" data-id="${u.id_usuario}" data-modo="consulta">Ver</button>
                    <button class="tbl-btn" data-id="${u.id_usuario}" data-modo="edicion">Editar</button>
                </td>
            </tr>`).join('');

        $('listado-contenido').innerHTML = `
            <div class="listado-wrap">
                <table>
                    <thead><tr>
                        <th>Usuario</th><th>Nivel</th><th>Subárea</th>
                        <th>Estado</th><th>Acciones</th>
                    </tr></thead>
                    <tbody>${bodyRows}</tbody>
                </table>
            </div>`;

        $('listado-contenido').querySelectorAll('.tbl-btn').forEach(btn =>
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
