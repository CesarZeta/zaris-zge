/**
 * ZARIS — Lógica del Formulario de Empresa (independiente)
 * Lookup CUIT, duplicados email/tel, búsqueda numérica/texto, CLAE filtro.
 */
document.addEventListener('DOMContentLoaded', () => {
    // ── State ──
    const state = {
        mode: 'search',       // 'search' | 'new' | 'edit' | 'view'
        empresaId: null,
        empresaEncontrada: null,
        actividades: [],
        busquedaTipo: 'numero' // 'numero' | 'texto'
    };

    // ── Elements ──
    const els = {
        searchQuery:      document.getElementById('search-query'),
        searchResult:     document.getElementById('search-result'),
        resultName:       document.getElementById('result-name'),
        resultDetail:     document.getElementById('result-detail'),
        resultList:       document.getElementById('result-list'),
        formCard:         document.getElementById('form-card'),
        formEmpresa:      document.getElementById('form-empresa'),
        formTitle:        document.getElementById('form-title'),
        formState:        document.getElementById('form-state'),
        obsTextarea:      document.getElementById('emp-observaciones'),
        obsCount:         document.getElementById('obs-count'),
        badgeCategoria:   document.getElementById('badge-categoria'),
        btnBuscar:                document.getElementById('btn-buscar'),
        btnNuevo:                 document.getElementById('btn-nuevo'),
        btnEditarEncontrado:      document.getElementById('btn-editar-encontrado'),
        btnConsultarEncontrado:   document.getElementById('btn-consultar-encontrado'),
        btnBajaEncontrado:        document.getElementById('btn-baja-encontrado'),
        btnNuevoForzar:           document.getElementById('btn-nuevo-forzar'),
        btnGuardar:               document.getElementById('btn-guardar'),
        btnCancelar:              document.getElementById('btn-cancelar'),
        btnValidarCuit:           document.getElementById('btn-validar-cuit'),
        btnModoNumero:            document.getElementById('btn-modo-numero'),
        btnModoTexto:             document.getElementById('btn-modo-texto'),
        claeFiltro:               document.getElementById('clae-filtro'),
        selActividad:             document.getElementById('emp-actividad'),
    };

    // ── Init ──
    init();

    async function init() {
        attachEvents();
        await cargarActividades();
        els.searchQuery.focus();
    }

    // ─────────────────────────────────────────────────────────
    // ACTIVIDADES CLAE
    // ─────────────────────────────────────────────────────────
    async function cargarActividades() {
        try {
            state.actividades = await ZUtils.apiFetch('/actividades');
            renderActividades('');
        } catch (err) {
            console.error('[ZARIS] Error cargando actividades:', err);
            ZUtils.toast('Error cargando actividades desde el servidor', 'error');
        }
    }

    function renderActividades(filtro) {
        const sel = els.selActividad;
        const valorActual = sel.value;
        sel.innerHTML = '<option value="">Seleccionar actividad...</option>';

        const filtroLower = filtro.toLowerCase();
        const grupos = {};
        state.actividades.forEach(a => {
            if (filtroLower && !a.descripcion.toLowerCase().includes(filtroLower) &&
                !String(a.codigo_clae).includes(filtroLower)) return;
            if (!grupos[a.categoria_tasa]) grupos[a.categoria_tasa] = [];
            grupos[a.categoria_tasa].push(a);
        });

        Object.entries(grupos).forEach(([cat, acts]) => {
            const optgroup = document.createElement('optgroup');
            optgroup.label = cat.charAt(0).toUpperCase() + cat.slice(1);
            acts.forEach(a => {
                const opt = document.createElement('option');
                opt.value = a.id;
                opt.dataset.categoria = a.categoria_tasa;
                opt.textContent = `${a.codigo_clae} — ${a.descripcion}`;
                optgroup.appendChild(opt);
            });
            sel.appendChild(optgroup);
        });

        // Restaurar valor seleccionado si sigue disponible
        if (valorActual) sel.value = valorActual;
        actualizarBadgeCategoria();
    }

    function actualizarBadgeCategoria() {
        const selected = els.selActividad.options[els.selActividad.selectedIndex];
        if (selected && selected.dataset.categoria) {
            const cat = selected.dataset.categoria;
            const colors = {
                comercio: { bg: '#E3F2FD', color: '#1565C0' },
                servicios: { bg: '#E8F5E9', color: '#2E7D32' },
                industria: { bg: '#FFF8E1', color: '#F57F17' }
            };
            const c = colors[cat] || { bg: '#F5F5F5', color: '#333' };
            els.badgeCategoria.textContent = `Categoría: ${cat.toUpperCase()}`;
            els.badgeCategoria.style.background = c.bg;
            els.badgeCategoria.style.color = c.color;
            els.badgeCategoria.style.display = 'inline-flex';
        } else {
            els.badgeCategoria.style.display = 'none';
        }
    }

    // ─────────────────────────────────────────────────────────
    // EVENTOS
    // ─────────────────────────────────────────────────────────
    function attachEvents() {
        // Toggle búsqueda
        els.btnModoNumero.addEventListener('click', () => setModoBusqueda('numero'));
        els.btnModoTexto.addEventListener('click',  () => setModoBusqueda('texto'));

        // Búsqueda
        els.btnBuscar.addEventListener('click', handleBuscar);
        els.searchQuery.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') { e.preventDefault(); handleBuscar(); }
        });

        // Nuevo
        els.btnNuevo.addEventListener('click', () => activarModoNuevo());
        els.btnNuevoForzar.addEventListener('click', () => activarModoNuevo());
        els.btnEditarEncontrado.addEventListener('click', () => activarModoEdicion(state.empresaEncontrada));
        els.btnConsultarEncontrado.addEventListener('click', () => activarModoConsulta(state.empresaEncontrada));
        els.btnBajaEncontrado.addEventListener('click', () => darBajaEmpresa(state.empresaEncontrada));

        // CUIT: formato + lookup automático al completar
        const cuitInput = document.getElementById('emp-cuit');
        cuitInput.addEventListener('input', (e) => {
            formatCuitInput(e);
            const digits = cuitInput.value.replace(/\D/g, '');
            if (digits.length === 11) buscarPorCuitExistente(cuitInput.value);
        });

        // CLAE filtro
        els.claeFiltro.addEventListener('input', () => renderActividades(els.claeFiltro.value));

        // Actividad → badge categoría
        els.selActividad.addEventListener('change', actualizarBadgeCategoria);

        // Duplicados email/teléfono (on blur)
        document.getElementById('emp-email').addEventListener('blur', async (e) => {
            const val = e.target.value.trim();
            if (!val) return;
            const r = await ZUtils.verificarDuplicado('empresas', 'email', val, state.empresaId);
            if (r.existe) {
                ZValidaciones.marcarCampo(e.target, false, `Ya registrado en: ${r.nombre}`);
                ZUtils.toast(`⚠️ Email ya registrado en empresa "${r.nombre}"`, 'warning', 5000);
            }
        });
        document.getElementById('emp-telefono').addEventListener('blur', async (e) => {
            const val = e.target.value.trim();
            if (!val) return;
            const r = await ZUtils.verificarDuplicado('empresas', 'telefono', val, state.empresaId);
            if (r.existe) {
                ZValidaciones.marcarCampo(e.target, false, `Ya registrado en: ${r.nombre}`);
                ZUtils.toast(`⚠️ Teléfono ya registrado en empresa "${r.nombre}"`, 'warning', 5000);
            }
        });

        // Validar CUIT
        els.btnValidarCuit.addEventListener('click', handleValidarCuit);

        // Guardar/Cancelar
        els.btnGuardar.addEventListener('click', handleGuardar);
        els.btnCancelar.addEventListener('click', handleCancelar);

        // Observaciones counter
        els.obsTextarea.addEventListener('input', () => {
            els.obsCount.textContent = els.obsTextarea.value.length;
        });

        // Guardar disabled hasta que el form esté completo
        state.checkGuardar = ZValidaciones.bindGuardarBoton(els.formEmpresa, els.btnGuardar).check;
    }

    // ─────────────────────────────────────────────────────────
    // TOGGLE MODO BÚSQUEDA
    // ─────────────────────────────────────────────────────────
    function setModoBusqueda(modo) {
        state.busquedaTipo = modo;
        els.btnModoNumero.className = modo === 'numero'
            ? 'z-btn z-btn--xs z-btn--primary'
            : 'z-btn z-btn--xs z-btn--ghost';
        els.btnModoTexto.className = modo === 'texto'
            ? 'z-btn z-btn--xs z-btn--primary'
            : 'z-btn z-btn--xs z-btn--ghost';
        els.searchQuery.placeholder = modo === 'numero'
            ? 'Ingresá CUIT de la empresa...'
            : 'Ingresá nombre o razón social...';
        els.searchQuery.value = '';
        els.searchResult.classList.remove('visible');
        els.searchQuery.focus();
    }

    // ─────────────────────────────────────────────────────────
    // BÚSQUEDA
    // ─────────────────────────────────────────────────────────
    async function handleBuscar() {
        const query = els.searchQuery.value.trim();
        if (!query) {
            ZUtils.toast('Ingresá un valor para buscar.', 'warning');
            els.searchQuery.focus();
            return;
        }

        try {
            // Para búsqueda numérica de CUIT: enviar con y sin guiones
            let queryEnviar = query;
            if (state.busquedaTipo === 'numero') {
                // Strip guiones para búsqueda flexible
                queryEnviar = query.replace(/-/g, '');
            }

            const resultados = await ZUtils.apiFetch(
                `/empresas/buscar?q=${encodeURIComponent(queryEnviar)}&tipo=${state.busquedaTipo}`
            );
            if (resultados.length === 0) {
                ZUtils.toast('No se encontró ninguna empresa con esos datos.', 'info');
                els.searchResult.classList.remove('visible');
                els.resultList.innerHTML = '';
            } else if (resultados.length === 1) {
                mostrarResultadoUnico(resultados[0]);
            } else {
                mostrarListaResultados(resultados);
            }
        } catch (err) {
            ZUtils.toast('Error en la búsqueda: ' + err.message, 'error');
        }
    }

    function mostrarResultadoUnico(emp) {
        state.empresaEncontrada = emp;
        els.resultName.textContent = emp.nombre;
        els.resultDetail.textContent = `CUIT: ${emp.cuit} │ ☎ ${emp.telefono || '-'} │ ✉ ${emp.email || '-'} │ ${emp.localidad || ''}`;
        els.resultList.innerHTML = '';
        els.btnEditarEncontrado.style.display    = 'inline-flex';
        els.btnConsultarEncontrado.style.display = 'inline-flex';
        els.btnBajaEncontrado.style.display      = 'inline-flex';
        els.searchResult.classList.add('visible');
    }

    function mostrarListaResultados(resultados) {
        state.empresaEncontrada = null;
        els.resultName.textContent    = `Se encontraron ${resultados.length} empresas:`;
        els.resultDetail.textContent  = '';
        els.btnEditarEncontrado.style.display    = 'none';
        els.btnConsultarEncontrado.style.display = 'none';

        els.resultList.innerHTML = resultados.map((emp, i) => `
            <div style="padding:8px 0;border-bottom:1px solid var(--z-border);display:flex;align-items:flex-start;gap:8px;">
                <div style="flex:1;">
                    <strong style="color:var(--z-primary);font-size:0.95rem;">${emp.nombre}</strong>
                    <div style="font-size:0.82rem;color:var(--z-text2);margin-top:2px;">
                        <span>CUIT: ${emp.cuit}</span>
                        <span style="margin-left:8px;">☎ ${emp.telefono || '-'}</span>
                        <span style="margin-left:8px;">✉ ${emp.email || '-'}</span>
                    </div>
                </div>
                <button class="z-btn z-btn--xs z-btn--primary" data-idx="${i}" data-action="editar">✏️ Editar</button>
                <button class="z-btn z-btn--xs z-btn--ghost"   data-idx="${i}" data-action="consultar">👁 Ver</button>
            </div>
        `).join('');

        els.resultList.addEventListener('click', (e) => {
            const btn = e.target.closest('[data-action]');
            if (!btn) return;
            const emp = resultados[parseInt(btn.dataset.idx)];
            state.empresaEncontrada = emp;
            if (btn.dataset.action === 'editar') activarModoEdicion(emp);
            else activarModoConsulta(emp);
        }, { once: true });

        els.searchResult.classList.add('visible');
    }

    // ─────────────────────────────────────────────────────────
    // LOOKUP CUIT (auto-check si ya existe)
    // ─────────────────────────────────────────────────────────
    async function buscarPorCuitExistente(cuit) {
        try {
            const r = await ZUtils.verificarDuplicado('empresas', 'cuit', cuit, state.empresaId);
            if (r.existe) {
                ZUtils.toast(`⚠️ CUIT ya registrado: "${r.nombre}". Usá Consultar o Modificar para traer los datos.`, 'warning', 6000);
                const emp = await ZUtils.apiFetch(`/empresas/${r.id}`);
                mostrarResultadoUnico(emp);
            }
        } catch { /* silencioso */ }
    }

    // ─────────────────────────────────────────────────────────
    // MODOS
    // ─────────────────────────────────────────────────────────
    function setFormReadonly(readonly) {
        els.formEmpresa.querySelectorAll('.z-input, .z-select, .z-textarea').forEach(el => {
            if (el.type === 'hidden') return;
            el.readOnly = readonly;
            el.disabled = readonly;
            el.style.background = readonly ? '#F5F5F5' : '';
            el.style.cursor     = readonly ? 'not-allowed' : '';
        });
        els.btnGuardar.style.display  = readonly ? 'none' : '';
        els.claeFiltro.disabled = readonly;
        // En modo consulta: cambiar Cancelar por Salir al Menú
        if (readonly) {
            els.btnCancelar.textContent = '↗ Salir al Menú';
            els.btnCancelar.onclick = () => { window.location.href = 'menu.html'; };
        } else {
            els.btnCancelar.innerHTML = '✕ Cancelar';
            els.btnCancelar.onclick = null;
        }
    }

    function activarModoNuevo() {
        state.mode = 'new';
        state.empresaId = null;
        state.empresaEncontrada = null;

        els.formEmpresa.reset();
        els.claeFiltro.value = '';
        renderActividades('');
        els.formCard.style.display = 'block';
        els.formTitle.textContent = 'Alta de Empresa';
        els.formState.className = 'z-form-state z-form-state--new';
        els.formState.textContent = '● NUEVO';
        els.badgeCategoria.style.display = 'none';
        els.searchResult.classList.remove('visible');
        els.obsCount.textContent = '0';
        setFormReadonly(false);

        els.formEmpresa.querySelectorAll('.z-input, .z-select, .z-textarea').forEach(el => {
            ZValidaciones.limpiarCampo(el);
        });

        setTimeout(() => els.formCard.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
        setTimeout(() => document.getElementById('emp-cuit').focus(), 150);
        state.checkGuardar && state.checkGuardar();
    }

    function activarModoEdicion(empresa) {
        state.mode = 'edit';
        state.empresaId = empresa ? empresa.id_empresa : null;

        els.formEmpresa.reset();
        els.claeFiltro.value = '';
        renderActividades('');
        els.formCard.style.display = 'block';
        els.formTitle.textContent = 'Modificar Empresa';
        els.formState.className = 'z-form-state z-form-state--edit';
        els.formState.textContent = '✏️ EDICIÓN';
        els.searchResult.classList.remove('visible');
        setFormReadonly(false);

        if (empresa) poblarFormulario(empresa);

        setTimeout(() => els.formCard.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
        state.checkGuardar && state.checkGuardar();
    }

    function activarModoConsulta(empresa) {
        state.mode = 'view';
        state.empresaId = empresa ? empresa.id_empresa : null;
        state.empresaEncontrada = empresa;

        els.formEmpresa.reset();
        els.claeFiltro.value = '';
        renderActividades('');
        els.formCard.style.display = 'block';
        els.formTitle.textContent = 'Consulta de Empresa';
        els.formState.className = 'z-form-state z-form-state--view';
        els.formState.textContent = '👁 CONSULTA';
        els.searchResult.classList.remove('visible');

        if (empresa) poblarFormulario(empresa);
        setFormReadonly(true);

        setTimeout(() => els.formCard.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
    }

    function poblarFormulario(empresa) {
        document.getElementById('emp-id').value          = empresa.id_empresa || '';
        document.getElementById('emp-cuit').value        = empresa.cuit || '';
        document.getElementById('emp-nombre').value      = empresa.nombre || '';
        document.getElementById('emp-calle').value       = empresa.calle || '';
        document.getElementById('emp-localidad').value   = empresa.localidad || '';
        document.getElementById('emp-provincia').value   = empresa.provincia || '';
        document.getElementById('emp-latitud').value     = empresa.latitud || '';
        document.getElementById('emp-longitud').value    = empresa.longitud || '';
        document.getElementById('emp-telefono').value    = empresa.telefono || '';
        document.getElementById('emp-email').value       = empresa.email || '';
        document.getElementById('emp-observaciones').value = empresa.observaciones || '';
        els.obsCount.textContent = (empresa.observaciones || '').length;

        if (empresa.id_actividad) {
            els.selActividad.value = empresa.id_actividad;
            actualizarBadgeCategoria();
        }
    }

    // ─────────────────────────────────────────────────────────
    // VALIDAR CUIT
    // ─────────────────────────────────────────────────────────
    function handleValidarCuit() {
        const input = document.getElementById('emp-cuit');
        const result = ZValidaciones.validarCuilCuit(input.value);
        if (result.valido) {
            input.value = result.formateado;
            ZValidaciones.marcarCampo(input, true);
            ZUtils.toast('CUIT válido ✓', 'success');
        } else {
            ZValidaciones.marcarCampo(input, false, result.error);
            ZUtils.toast(result.error, 'error');
        }
    }

    function formatCuitInput(e) {
        const digits = e.target.value.replace(/\D/g, '');
        let val = digits;
        if (digits.length > 2 && digits.length <= 10) {
            val = digits.substring(0, 2) + '-' + digits.substring(2);
        } else if (digits.length > 10) {
            val = digits.substring(0, 2) + '-' + digits.substring(2, 10) + '-' + digits.substring(10, 11);
        }
        e.target.value = val;
    }

    // ─────────────────────────────────────────────────────────
    // GUARDAR
    // ─────────────────────────────────────────────────────────
    async function handleGuardar() {
        const { valido, errores } = ZValidaciones.validarFormulario(els.formEmpresa);

        // CUIT
        const cuit = document.getElementById('emp-cuit').value;
        if (cuit) {
            const cuitResult = ZValidaciones.validarCuilCuit(cuit);
            if (!cuitResult.valido) {
                ZValidaciones.marcarCampo(document.getElementById('emp-cuit'), false, cuitResult.error);
                errores.push('CUIT inválido');
            }
        }

        // Email formato
        const email = document.getElementById('emp-email').value;
        if (email && !ZValidaciones.validarEmail(email)) {
            ZValidaciones.marcarCampo(document.getElementById('emp-email'), false, 'Formato de email inválido');
            errores.push('Email inválido');
        }

        // Teléfono
        const telefono = document.getElementById('emp-telefono').value;
        if (telefono) {
            const telResult = ZValidaciones.validarTelefono(telefono);
            if (!telResult.valido) {
                ZValidaciones.marcarCampo(document.getElementById('emp-telefono'), false, telResult.error);
                errores.push('Teléfono inválido');
            }
        }

        // Verificar duplicados email/tel — solo en ALTA (no en edición)
        const isEditCheck = state.mode === 'edit' && state.empresaId;
        if (!isEditCheck) {
            if (email) {
                const rEmail = await ZUtils.verificarDuplicado('empresas', 'email', email, state.empresaId);
                if (rEmail.existe) {
                    ZValidaciones.marcarCampo(document.getElementById('emp-email'), false, `Ya registrado en: ${rEmail.nombre}`);
                    errores.push('Email duplicado');
                }
            }
            if (telefono && telefono.length >= 8) {
                const rTel = await ZUtils.verificarDuplicado('empresas', 'telefono', telefono, state.empresaId);
                if (rTel.existe) {
                    ZValidaciones.marcarCampo(document.getElementById('emp-telefono'), false, `Ya registrado en: ${rTel.nombre}`);
                    errores.push('Teléfono duplicado');
                }
            }
        }

        if (errores.length > 0) {
            ZUtils.toast(`Hay ${errores.length} error(es). Revisá los campos marcados.`, 'error');
            return;
        }

        const formData = new FormData(els.formEmpresa);
        const data = Object.fromEntries(formData.entries());
        data.email_chk = false;

        // Formatear CUIT
        const cuitResult = ZValidaciones.validarCuilCuit(data.cuit);
        if (cuitResult.valido) data.cuit = cuitResult.formateado;

        try {
            const isEdit  = state.mode === 'edit' && state.empresaId;
            const endpoint = isEdit ? `/empresas/${state.empresaId}` : '/empresas';
            const method   = isEdit ? 'PUT' : 'POST';

            const response = await ZUtils.apiFetch(endpoint, { method, body: JSON.stringify(data) });
            state.empresaId = response.id_empresa || state.empresaId;

            const accion = isEdit ? 'actualizada' : 'guardada';
            ZUtils.modalGuardado(
                `Empresa ${accion}`,
                `${response.nombre || data.nombre}`,
                () => activarModoNuevo(),
                () => { window.location.href = 'menu.html'; }
            );
        } catch (err) {
            ZUtils.toast(`Error al guardar: ${err.message}`, 'error');
        }
    }

    // ─────────────────────────────────────────────────────────
    // BAJA LÓGICA
    // ─────────────────────────────────────────────────────────
    async function darBajaEmpresa(empresa) {
        if (!empresa) return;
        const ok = await ZUtils.confirm(
            'Confirmar baja',
            `¿Dar de baja a "${empresa.nombre}"?\n\nEsta acción desactiva la empresa. Se puede reactivar posteriormente.`
        );
        if (!ok) return;
        try {
            await ZUtils.apiFetch(`/empresas/${empresa.id_empresa}/estado?activo=false`, { method: 'PUT' });
            ZUtils.toast('Empresa dada de baja correctamente', 'success');
            els.searchResult.classList.remove('visible');
            els.searchQuery.value = '';
            state.empresaEncontrada = null;
        } catch (err) {
            ZUtils.toast(`Error al dar de baja: ${err.message}`, 'error');
        }
    }

    // ─────────────────────────────────────────────────────────
    // CANCELAR
    // ─────────────────────────────────────────────────────────
    async function handleCancelar() {
        const confirmed = await ZUtils.confirm(
            '¿Salir del formulario?',
            'Los datos no guardados se perderán. ¿Estás seguro que deseas salir?'
        );
        if (confirmed) window.location.href = 'menu.html';
    }

    // ─────────────────────────────────────────────────────────
    // UTIL
    // ─────────────────────────────────────────────────────────
    function esc(s) {
        return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    }

    // ─────────────────────────────────────────────────────────
    // VISTA PREVIA
    // ─────────────────────────────────────────────────────────
    async function cargarVistaPrevia() {
        const container = document.getElementById('preview-rows');
        if (!container) return;
        container.innerHTML = '<div style="color:var(--z-text3);font-size:.82rem;padding:.5rem 0;">Cargando...</div>';
        try {
            const data = await ZUtils.apiFetch('/empresas?solo_activos=false&limit=200');
            const recientes = data.slice(0, 5);
            if (recientes.length === 0) {
                container.innerHTML = '<div style="color:var(--z-text3);font-size:.82rem;padding:.5rem 0;">Sin registros</div>';
                return;
            }
            container.innerHTML = recientes.map(e => `
                <div class="z-preview-row" data-id="${e.id_empresa}">
                    <span class="z-preview-row__nombre">${esc(e.nombre)}</span>
                    <span class="z-preview-row__mono">${esc(e.cuit || '—')}</span>
                    <span class="z-preview-row__meta">${esc(e.localidad || e.provincia || '—')}</span>
                    <span class="z-preview-row__estado z-preview-row__estado--${e.activo ? 'activo' : 'inactivo'}">${e.activo ? 'Activo' : 'Inactivo'}</span>
                    <span class="z-preview-row__cta">Ver →</span>
                </div>`).join('');
            container.querySelectorAll('.z-preview-row').forEach(row =>
                row.addEventListener('click', async () => {
                    try {
                        const emp = await ZUtils.apiFetch(`/empresas/${row.dataset.id}`);
                        mostrarResultadoUnico(emp);
                    } catch(err) { ZUtils.toast('Error al cargar empresa', 'error'); }
                })
            );
        } catch (err) {
            console.error('[Preview empresas]', err);
            container.innerHTML = `<div style="color:var(--z-text3);font-size:.82rem;padding:.5rem 0;">No se pudo cargar (${err.message})</div>`;
        }
    }

    // ─────────────────────────────────────────────────────────
    // LISTADO COMPLETO
    // ─────────────────────────────────────────────────────────
    let _listadoData = [];

    async function abrirListado() {
        document.getElementById('search-panel').style.display    = 'none';
        document.getElementById('preview-section').style.display = 'none';
        document.getElementById('form-card').style.display       = 'none';
        document.getElementById('listado-section').style.display = 'block';
        document.getElementById('listado-contenido').innerHTML   = '<div style="text-align:center;padding:2rem;color:var(--z-text3);">Cargando...</div>';
        document.getElementById('lst-count').textContent = '';
        try {
            _listadoData = await ZUtils.apiFetch('/empresas?solo_activos=false&limit=1000');
            aplicarFiltros();
        } catch (err) {
            document.getElementById('listado-contenido').innerHTML =
                `<div style="color:#cf2d56;padding:1rem;">Error: ${err.message}</div>`;
        }
    }

    function cerrarListado() {
        document.getElementById('listado-section').style.display  = 'none';
        document.getElementById('search-panel').style.display     = 'block';
        document.getElementById('preview-section').style.display  = 'block';
    }

    function aplicarFiltros() {
        let rows  = [..._listadoData];
        const txt  = (document.getElementById('lst-texto').value  || '').toLowerCase().trim();
        const ord  = document.getElementById('lst-orden').value   || 'reciente';
        const desd = document.getElementById('lst-desde').value   || '';
        const hast = document.getElementById('lst-hasta').value   || '';

        if (txt) rows = rows.filter(e =>
            (e.nombre || '').toLowerCase().includes(txt) ||
            (e.cuit   || '').replace(/-/g,'').includes(txt.replace(/-/g,''))
        );
        if (desd || hast) rows = rows.filter(e => {
            const d = (e.fecha_alta || '').slice(0,10);
            if (!d) return true;
            if (desd && d < desd) return false;
            if (hast && d > hast) return false;
            return true;
        });
        if      (ord === 'reciente') rows.sort((a,b) => (b.id_empresa||0)-(a.id_empresa||0));
        else if (ord === 'antiguo')  rows.sort((a,b) => (a.id_empresa||0)-(b.id_empresa||0));
        else if (ord === 'az')       rows.sort((a,b) => (a.nombre||'').localeCompare(b.nombre||'','es'));
        else if (ord === 'za')       rows.sort((a,b) => (b.nombre||'').localeCompare(a.nombre||'','es'));
        renderListado(rows);
    }

    function limpiarFiltros() {
        ['lst-texto','lst-desde','lst-hasta'].forEach(id => { const el=document.getElementById(id); if(el) el.value=''; });
        document.getElementById('lst-orden').value = 'reciente';
        aplicarFiltros();
    }

    function renderListado(rows) {
        const fecha = new Date().toLocaleDateString('es-AR',{day:'2-digit',month:'2-digit',year:'numeric'});
        document.getElementById('lst-print-header').innerHTML =
            `<h2>Padrón de Empresas — ZARIS</h2><p>Listado generado el ${fecha} · ${rows.length} registro${rows.length!==1?'s':''}</p>`;
        document.getElementById('lst-count').textContent =
            `${rows.length} empresa${rows.length!==1?'s':''} encontrada${rows.length!==1?'s':''}`;

        if (rows.length === 0) {
            document.getElementById('listado-contenido').innerHTML =
                '<div style="text-align:center;padding:2.5rem;color:var(--z-text3);">Sin resultados</div>';
            return;
        }
        const bodyRows = rows.map(e => `<tr>
            <td>${esc(e.nombre)}</td>
            <td class="mono">${esc(e.cuit||'—')}</td>
            <td>${esc(e.localidad||'—')}</td>
            <td>${esc(e.provincia||'—')}</td>
            <td><span class="z-badge-${e.activo?'activo':'inactivo'}">${e.activo?'Activo':'Inactivo'}</span></td>
            <td>
                <button class="z-tbl-btn" data-id="${e.id_empresa}">Ver / Editar</button>
            </td></tr>`).join('');

        document.getElementById('listado-contenido').innerHTML = `
            <div class="z-listado-wrap"><table>
                <thead><tr><th>Nombre</th><th>CUIT</th><th>Localidad</th><th>Provincia</th><th>Estado</th><th>Acciones</th></tr></thead>
                <tbody>${bodyRows}</tbody>
            </table></div>`;

        document.getElementById('listado-contenido').querySelectorAll('.z-tbl-btn').forEach(btn =>
            btn.addEventListener('click', async () => {
                cerrarListado();
                try {
                    const emp = await ZUtils.apiFetch(`/empresas/${btn.dataset.id}`);
                    mostrarResultadoUnico(emp);
                } catch(err) { ZUtils.toast('Error al cargar empresa', 'error'); }
            })
        );
    }

    document.getElementById('btn-listado')?.addEventListener('click', abrirListado);
    document.getElementById('btn-cerrar-listado')?.addEventListener('click', cerrarListado);
    document.getElementById('btn-imprimir-lst')?.addEventListener('click', () => window.print());
    document.getElementById('btn-filtrar-lst')?.addEventListener('click', aplicarFiltros);
    document.getElementById('btn-limpiar-lst')?.addEventListener('click', limpiarFiltros);
    document.getElementById('lst-texto')?.addEventListener('keydown', e => { if(e.key==='Enter') aplicarFiltros(); });

    cargarVistaPrevia();
});
