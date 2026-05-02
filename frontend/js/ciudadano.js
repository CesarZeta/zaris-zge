/**
 * ZARIS — Lógica del Formulario de Ciudadano
 * Maneja búsqueda, alta, edición y flujo hacia empresa.
 */
document.addEventListener('DOMContentLoaded', () => {
    // ── State ──
    const state = {
        mode: 'search',
        ciudadanoId: null,
        ciudadanoGuardado: false,
        ciudadanoEncontrado: null,
        nacionalidades: [],
        tipoRepresentacion: [],
        actividades: [],
        busquedaTipo: 'numero'
    };

    // ── Elements ──
    const els = {
        searchPanel:    document.getElementById('search-panel'),
        searchQuery:    document.getElementById('search-query'),
        searchResult:   document.getElementById('search-result'),
        resultName:     document.getElementById('result-name'),
        resultDetail:   document.getElementById('result-detail'),
        formCard:       document.getElementById('form-card'),
        formCiudadano:  document.getElementById('form-ciudadano'),
        formTitle:      document.getElementById('form-title'),
        formState:      document.getElementById('form-state'),
        empresaPanel:   document.getElementById('empresa-panel'),
        empChk:         document.getElementById('cid-emp-chk'),
        obsTextarea:    document.getElementById('cid-observaciones'),
        obsCount:       document.getElementById('obs-count'),

        // Buttons
        btnBuscar:                document.getElementById('btn-buscar'),
        btnNuevo:                 document.getElementById('btn-nuevo'),
        btnEditarEncontrado:      document.getElementById('btn-editar-encontrado'),
        btnConsultarEncontrado:   document.getElementById('btn-consultar-encontrado'),
        btnBajaEncontrado:        document.getElementById('btn-baja-encontrado'),
        btnNuevoForzar:           document.getElementById('btn-nuevo-forzar'),
        btnGuardar:               document.getElementById('btn-guardar'),
        btnCancelar:              document.getElementById('btn-cancelar'),
        btnModoNumero:            document.getElementById('btn-modo-numero'),
        btnModoTexto:             document.getElementById('btn-modo-texto'),
        resultList:               document.getElementById('result-list'),

        // Empresa vinculada
        btnGuardarEmpresa:  document.getElementById('btn-guardar-empresa'),
        btnCancelarEmpresa: document.getElementById('btn-cancelar-empresa'),
        btnValidarCuitEv:   document.getElementById('btn-validar-cuit-ev'),
        formEmpresaVinculada: document.getElementById('form-empresa-vinculada'),
    };

    // ── Init ──
    init();

    async function init() {
        attachEvents();
        await cargarCatalogos();
        els.searchQuery.focus();
    }

    // ── Cargar catálogos desde la API ──
    async function cargarCatalogos() {
        try {
            // Nacionalidades
            state.nacionalidades = await ZUtils.apiFetch('/nacionalidades');
            const selNac = document.getElementById('cid-nacionalidad');
            selNac.innerHTML = '<option value="">Seleccionar...</option>';
            state.nacionalidades.forEach(n => {
                const opt = document.createElement('option');
                opt.value = n.id;
                opt.textContent = `${n.pais} (${n.region})`;
                selNac.appendChild(opt);
            });

            // Tipo representación
            state.tipoRepresentacion = await ZUtils.apiFetch('/tipo-representacion');
            const selTipoRep = document.getElementById('ev-tipo-rep');
            selTipoRep.innerHTML = '<option value="">Seleccionar...</option>';
            state.tipoRepresentacion.forEach(t => {
                const opt = document.createElement('option');
                opt.value = t.id;
                opt.textContent = t.tipo;
                selTipoRep.appendChild(opt);
            });

            // Actividades
            state.actividades = await ZUtils.apiFetch('/actividades');
            const selAct = document.getElementById('ev-actividad');
            selAct.innerHTML = '<option value="">Seleccionar...</option>';
            state.actividades.forEach(a => {
                const opt = document.createElement('option');
                opt.value = a.id;
                opt.textContent = `${a.codigo_clae} — ${a.descripcion}`;
                selAct.appendChild(opt);
            });

            console.log('[ZARIS] Catálogos cargados desde API');
        } catch (err) {
            console.error('[ZARIS] Error cargando catálogos:', err);
            ZUtils.toast('Error cargando catálogos desde el servidor', 'error');
        }
    }

    // ── Eventos ──
    function attachEvents() {
        // Toggle tipo búsqueda
        els.btnModoNumero.addEventListener('click', () => setModoBusqueda('numero'));
        els.btnModoTexto.addEventListener('click',  () => setModoBusqueda('texto'));

        // Búsqueda
        els.btnBuscar.addEventListener('click', handleBuscar);
        els.searchQuery.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') { e.preventDefault(); handleBuscar(); }
        });

        // Nuevo / Editar / Consultar
        els.btnNuevo.addEventListener('click', () => activarModoNuevo());
        els.btnNuevoForzar.addEventListener('click', () => activarModoNuevo());
        els.btnEditarEncontrado.addEventListener('click', () => activarModoEdicion(state.ciudadanoEncontrado));
        els.btnConsultarEncontrado.addEventListener('click', () => activarModoConsulta(state.ciudadanoEncontrado));
        els.btnBajaEncontrado.addEventListener('click', () => darBajaCiudadano(state.ciudadanoEncontrado));

        // DNI → auto-calcula CUIL (si CUIL no fue editado manualmente)
        const dniInput  = document.getElementById('cid-doc-nro');
        const cuilInput = document.getElementById('cid-cuil');

        dniInput.addEventListener('input', () => {
            if (!cuilInput.dataset.manualInput) generarCuilDesdeDni();
            // Lookup existente cuando DNI está completo (min 7 dígitos)
            const digits = dniInput.value.replace(/\D/g, '');
            if (digits.length >= 7) buscarPorIdentificadorExistente('doc_nro', digits);
        });
        document.getElementById('cid-sexo').addEventListener('change', () => {
            if (!cuilInput.dataset.manualInput) generarCuilDesdeDni();
        });
        document.getElementById('cid-doc-tipo').addEventListener('change', () => {
            if (!cuilInput.dataset.manualInput) generarCuilDesdeDni();
        });

        // CUIL: formateo + lookup al completar
        cuilInput.addEventListener('input', (e) => {
            formatCuilInput(e);
            cuilInput.dataset.manualInput = cuilInput.value ? '1' : '';
            const digits = cuilInput.value.replace(/\D/g, '');
            if (digits.length === 11) buscarPorIdentificadorExistente('cuil', cuilInput.value);
        });

        // CUIL blur → extrae DNI si DNI está vacío
        cuilInput.addEventListener('blur', () => {
            const cuil = cuilInput.value.trim();
            const dni  = dniInput.value.trim();
            if (cuil && !dni) {
                const extracted = extraerDniDeCuil(cuil);
                if (extracted) {
                    dniInput.value = extracted;
                    ZValidaciones.marcarCampo(dniInput, true);
                }
            }
        });

        // Botones Validar (placeholders)
        document.getElementById('btn-validar-dni').addEventListener('click', () => {
            ZUtils.toast('Validación con RENAPER: próximamente disponible.', 'info');
        });
        document.getElementById('btn-validar-cuil').addEventListener('click', () => {
            const input = document.getElementById('cid-cuil');
            if (!input.value) { ZUtils.toast('Ingresá un CUIL para validar.', 'warning'); return; }
            const result = ZValidaciones.validarCuilCuit(input.value);
            if (result.valido) {
                input.value = result.formateado;
                ZValidaciones.marcarCampo(input, true);
                ZUtils.toast('CUIL válido (dígito verificador correcto) ✓', 'success');
            } else {
                ZValidaciones.marcarCampo(input, false, result.error);
                ZUtils.toast(result.error, 'error');
            }
        });

        // Duplicados email y teléfono (on blur)
        document.getElementById('cid-email').addEventListener('blur', async (e) => {
            const val = e.target.value.trim();
            if (!val) return;
            const r = await ZUtils.verificarDuplicado('ciudadanos', 'email', val, state.ciudadanoId);
            if (r.existe) {
                ZValidaciones.marcarCampo(e.target, false, `Ya registrado: ${r.nombre}`);
                ZUtils.toast(`⚠️ Email ya registrado en ciudadano "${r.nombre}"`, 'warning', 5000);
            }
        });
        document.getElementById('cid-telefono').addEventListener('blur', async (e) => {
            const val = e.target.value.trim();
            if (!val) return;
            const r = await ZUtils.verificarDuplicado('ciudadanos', 'telefono', val, state.ciudadanoId);
            if (r.existe) {
                ZValidaciones.marcarCampo(e.target, false, `Ya registrado: ${r.nombre}`);
                ZUtils.toast(`⚠️ Teléfono ya registrado en ciudadano "${r.nombre}"`, 'warning', 5000);
            }
        });

        // Guardar/Cancelar
        els.btnGuardar.addEventListener('click', handleGuardar);
        els.btnCancelar.addEventListener('click', handleCancelar);

        // Guardar disabled hasta que el form esté completo
        state.checkGuardar = ZValidaciones.bindGuardarBoton(els.formCiudadano, els.btnGuardar).check;

        // Empresa
        els.btnGuardarEmpresa.addEventListener('click', handleGuardarEmpresa);
        els.btnCancelarEmpresa.addEventListener('click', handleCancelarEmpresa);

        // emp_chk change: en modo edición, habilitar panel empresa de inmediato
        // (sin necesidad de guardar el ciudadano primero)
        els.empChk.addEventListener('change', () => {
            if (!els.empChk.checked) {
                els.empresaPanel.classList.remove('open');
                return;
            }
            if (state.mode === 'edit') {
                // En edición: si ya tiene empresa vinculada la muestra, si no abre panel vacío para vincular
                const haTenidoEmpresa = !!state.ciudadanoId;
                if (haTenidoEmpresa) {
                    // intentar cargar empresa existente, si no tiene, abrir panel editable
                    cargarEmpresaVinculada(state.ciudadanoId, false).then(loaded => {
                        if (!loaded) {
                            // No tiene empresa vinculada — abrir panel en blanco para vincular
                            document.getElementById('ev-ciudadano-id').value = state.ciudadanoId;
                            els.empresaPanel.classList.add('open');
                            setTimeout(() => els.empresaPanel.scrollIntoView({ behavior: 'smooth', block: 'start' }), 300);
                        }
                    });
                }
            } else if (state.mode === 'new') {
                // En nuevo: solo despliega panel luego de guardar (comportamiento existente)
                ZUtils.toast('Guarde el ciudadano primero para vincular la empresa.', 'info', 3000);
                // Mantiene el tick marcado para que se procese al guardar
            }
        });
        if (els.btnValidarCuitEv) {
            els.btnValidarCuitEv.addEventListener('click', () => {
                const input = document.getElementById('ev-cuit');
                const result = ZValidaciones.validarCuilCuit(input.value);
                if (result.valido) {
                    input.value = result.formateado;
                    ZValidaciones.marcarCampo(input, true);
                    ZUtils.toast('CUIT válido ✓', 'success');
                } else {
                    ZValidaciones.marcarCampo(input, false, result.error);
                    ZUtils.toast(result.error, 'error');
                }
            });
        }

        // Observaciones counter
        els.obsTextarea.addEventListener('input', () => {
            els.obsCount.textContent = els.obsTextarea.value.length;
        });
    }

    // ── Toggle modo búsqueda ──
    function setModoBusqueda(modo) {
        state.busquedaTipo = modo;
        els.btnModoNumero.className = modo === 'numero'
            ? 'z-btn z-btn--xs z-btn--primary' : 'z-btn z-btn--xs z-btn--ghost';
        els.btnModoTexto.className = modo === 'texto'
            ? 'z-btn z-btn--xs z-btn--primary' : 'z-btn z-btn--xs z-btn--ghost';
        els.searchQuery.placeholder = modo === 'numero'
            ? 'Ingresá DNI o CUIL...'
            : 'Ingresá nombre o apellido...';
        els.searchQuery.value = '';
        els.searchResult.classList.remove('visible');
        els.searchQuery.focus();
    }

    // ── Calcular dígito verificador CUIL/CUIT (Módulo 11) ──
    function calcularDigitoVerificador(prefijo, dni) {
        const base = `${prefijo}${dni.padStart(8, '0')}`;
        const coeficientes = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2];
        let suma = 0;
        for (let i = 0; i < 10; i++) suma += parseInt(base[i]) * coeficientes[i];
        const resto = suma % 11;
        if (resto === 0) return 0;
        if (resto === 1) return prefijo === '27' ? 4 : 9;
        return 11 - resto;
    }

    // DNI → auto-genera CUIL (no sobreescribe si fue editado manualmente)
    function generarCuilDesdeDni() {
        const sexo = document.getElementById('cid-sexo').value;
        const docTipo = document.getElementById('cid-doc-tipo').value;
        const docNro = document.getElementById('cid-doc-nro').value.replace(/\D/g, '');
        const cuilInput = document.getElementById('cid-cuil');

        if (!sexo || docTipo !== 'DNI' || docNro.length < 7) {
            if (!cuilInput.dataset.manualInput) cuilInput.value = '';
            return;
        }
        const prefijo = (sexo === 'MUJER') ? '27' : '20';
        const digitoV = calcularDigitoVerificador(prefijo, docNro);
        cuilInput.value = `${prefijo}-${docNro.padStart(8, '0')}-${digitoV}`;
        ZValidaciones.marcarCampo(cuilInput, true);
    }

    // Alias para compatibilidad
    const generarCuilAutomatico = generarCuilDesdeDni;

    // CUIL → extrae DNI (dígitos centrales, posiciones 2-9)
    function extraerDniDeCuil(cuil) {
        const digits = cuil.replace(/\D/g, '');
        if (digits.length !== 11) return null;
        return parseInt(digits.substring(2, 10)).toString();
    }

    // Formateo del CUIL mientras se escribe: XX-XXXXXXXX-X
    function formatCuilInput(e) {
        const digits = e.target.value.replace(/\D/g, '');
        let val = digits;
        if (digits.length > 2 && digits.length <= 10) {
            val = digits.substring(0, 2) + '-' + digits.substring(2);
        } else if (digits.length > 10) {
            val = digits.substring(0, 2) + '-' + digits.substring(2, 10) + '-' + digits.substring(10, 11);
        }
        e.target.value = val;
    }

    // ── Lookup CUIL/DNI existente (auto-check al tipear) ──
    let _lookupTimer = null;
    async function buscarPorIdentificadorExistente(campo, valor) {
        clearTimeout(_lookupTimer);
        _lookupTimer = setTimeout(async () => {
            try {
                const r = await ZUtils.verificarDuplicado('ciudadanos', campo, valor, state.ciudadanoId);
                if (r.existe) {
                    ZUtils.toast(`⚠️ ${campo === 'cuil' ? 'CUIL' : 'DNI'} ya registrado: "${r.nombre}". Usá Consultar o Modificar para traer los datos.`, 'warning', 6000);
                    const ciudadano = await ZUtils.apiFetch(`/ciudadanos/${r.id}`);
                    mostrarResultadoUnico(ciudadano);
                }
            } catch { /* silencioso */ }
        }, 800);
    }

    // ── Búsqueda ──
    async function handleBuscar() {
        const query = els.searchQuery.value.trim();
        if (!query) {
            ZUtils.toast('Ingresá un valor para buscar.', 'warning');
            els.searchQuery.focus();
            return;
        }

        try {
            const resultados = await ZUtils.apiFetch(
                `/ciudadanos/buscar?q=${encodeURIComponent(query)}&tipo=${state.busquedaTipo}`
            );
            if (resultados.length === 0 && state.busquedaTipo === 'texto') {
                // Fallback: backend puede no tener el param 'tipo' — reintentar sin él
                const fallback = await ZUtils.apiFetch(
                    `/ciudadanos/buscar?q=${encodeURIComponent(query)}`
                ).catch(() => []);
                if (fallback.length > 0) {
                    if (fallback.length === 1) mostrarResultadoUnico(fallback[0]);
                    else mostrarListaResultados(fallback);
                    return;
                }
            }
            if (resultados.length === 0) {
                ZUtils.toast('No se encontró ningún ciudadano con esos datos.', 'info');
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

    function mostrarResultadoUnico(ciudadano) {
        state.ciudadanoEncontrado = ciudadano;
        els.resultName.textContent = `${ciudadano.apellido}, ${ciudadano.nombre}`;
        els.resultDetail.textContent = `${ciudadano.doc_tipo} ${ciudadano.doc_nro} │ CUIL: ${ciudadano.cuil} │ ☎ ${ciudadano.telefono} │ ✉ ${ciudadano.email}`;
        els.resultList.innerHTML = '';
        document.getElementById('btn-editar-encontrado').style.display    = 'inline-flex';
        document.getElementById('btn-consultar-encontrado').style.display = 'inline-flex';
        document.getElementById('btn-baja-encontrado').style.display      = 'inline-flex';
        els.searchResult.classList.add('visible');
    }

    async function darBajaCiudadano(ciudadano) {
        if (!ciudadano) return;
        const ok = await ZUtils.confirm(
            'Confirmar baja',
            `¿Dar de baja a ${ciudadano.apellido}, ${ciudadano.nombre} (CUIL ${ciudadano.cuil})?\nEl registro quedará inactivo y no aparecerá en búsquedas.`
        );
        if (!ok) return;
        try {
            await ZUtils.apiFetch(`/ciudadanos/${ciudadano.id_ciudadano}/estado?activo=false`, { method: 'PUT' });
            ZUtils.toast('Ciudadano dado de baja correctamente', 'success');
            els.searchResult.classList.remove('visible');
            els.searchQuery.value = '';
            state.ciudadanoEncontrado = null;
        } catch (err) {
            ZUtils.toast(`Error al dar de baja: ${err.message}`, 'error');
        }
    }

    function mostrarListaResultados(resultados) {
        state.ciudadanoEncontrado = null;
        els.resultName.textContent   = `Se encontraron ${resultados.length} ciudadanos:`;
        els.resultDetail.textContent = '';
        document.getElementById('btn-editar-encontrado').style.display    = 'none';
        document.getElementById('btn-consultar-encontrado').style.display = 'none';

        els.resultList.innerHTML = resultados.map((c, i) => `
            <div style="padding:8px 0;border-bottom:1px solid var(--z-border);display:flex;align-items:flex-start;gap:8px;">
                <div style="flex:1;">
                    <strong style="color:var(--z-primary);font-size:0.95rem;">${c.apellido}, ${c.nombre}</strong>
                    <div style="font-size:0.82rem;color:var(--z-text2);margin-top:2px;">
                        <span>${c.doc_tipo} ${c.doc_nro}</span>
                        <span style="margin-left:8px;">☎ ${c.telefono || '-'}</span>
                        <span style="margin-left:8px;">✉ ${c.email || '-'}</span>
                    </div>
                </div>
                <button class="z-btn z-btn--xs z-btn--primary" data-idx="${i}" data-action="editar">✏️ Editar</button>
                <button class="z-btn z-btn--xs z-btn--ghost"   data-idx="${i}" data-action="consultar">👁 Ver</button>
            </div>
        `).join('');

        els.resultList.addEventListener('click', (e) => {
            const btn = e.target.closest('[data-action]');
            if (!btn) return;
            const ciudadano = resultados[parseInt(btn.dataset.idx)];
            state.ciudadanoEncontrado = ciudadano;
            if (btn.dataset.action === 'editar') activarModoEdicion(ciudadano);
            else activarModoConsulta(ciudadano);
        }, { once: true });

        els.searchResult.classList.add('visible');
    }

    // ── Modo Nuevo ──
    function activarModoNuevo() {
        state.mode = 'new';
        state.ciudadanoId = null;
        state.ciudadanoGuardado = false;
        state.ciudadanoEncontrado = null;

        els.formCiudadano.reset();
        els.formCard.style.display = 'block';
        els.formTitle.textContent = 'Alta de Ciudadano';
        els.formState.className = 'z-form-state z-form-state--new';
        els.formState.textContent = '● NUEVO';
        els.empresaPanel.classList.remove('open');
        els.searchResult.classList.remove('visible');
        els.obsCount.textContent = '0';
        setFormReadonly(false);

        // Limpiar validaciones visuales y estado manual CUIL
        els.formCiudadano.querySelectorAll('.z-input, .z-select, .z-textarea').forEach(el => {
            ZValidaciones.limpiarCampo(el);
        });
        delete document.getElementById('cid-cuil').dataset.manualInput;

        setTimeout(() => els.formCard.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
        setTimeout(() => document.getElementById('cid-doc-tipo').focus(), 150);
        state.checkGuardar && state.checkGuardar();
    }

    // ── Modo Consulta (solo lectura) ──
    function activarModoConsulta(ciudadano) {
        state.mode = 'view';
        state.ciudadanoId = ciudadano ? ciudadano.id_ciudadano : null;
        state.ciudadanoGuardado = false;

        els.formCiudadano.reset();
        els.formCard.style.display = 'block';
        els.formTitle.textContent = 'Consulta de Ciudadano';
        els.formState.className = 'z-form-state z-form-state--view';
        els.formState.textContent = '👁 CONSULTA';
        els.empresaPanel.classList.remove('open');
        els.searchResult.classList.remove('visible');

        delete document.getElementById('cid-cuil').dataset.manualInput;

        if (ciudadano) poblarFormulario(ciudadano);
        setFormReadonly(true);

        if (ciudadano && ciudadano.emp_chk) {
            cargarEmpresaVinculada(ciudadano.id_ciudadano, true);
        }

        setTimeout(() => els.formCard.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
    }

    function setFormReadonly(readonly) {
        // Excluir el checkbox de empresa (debe ser visible siempre en consulta/edición)
        els.formCiudadano.querySelectorAll('.z-input:not([type=hidden]), .z-select, .z-textarea').forEach(el => {
            el.readOnly = readonly;
            el.disabled = readonly;
            el.style.background = readonly ? '#F5F5F5' : '';
            el.style.cursor     = readonly ? 'not-allowed' : '';
        });
        // Los checkboxes de validación batch ya son siempre disabled
        // El checkbox emp_chk también debe verse, pero no editarse en modo consulta
        if (els.empChk) {
            els.empChk.disabled = readonly;
            els.empChk.style.cursor = readonly ? 'not-allowed' : '';
        }
        els.btnGuardar.style.display = readonly ? 'none' : '';
        // En modo solo lectura (consulta): cambiar botón Cancelar por Salir al Menú
        if (readonly) {
            els.btnCancelar.textContent = '↗ Salir al Menú';
            els.btnCancelar.className = 'z-btn z-btn--ghost';
            els.btnCancelar.onclick = () => { window.location.href = 'menu.html'; };
        } else {
            els.btnCancelar.innerHTML = '✕ Cancelar';
            els.btnCancelar.onclick = null;  // restaura el listener original
        }
    }
    // ── Poblar formulario con datos de un ciudadano (edición y consulta) ──
    function poblarFormulario(ciudadano) {
        document.getElementById('cid-id').value               = ciudadano.id_ciudadano || '';
        document.getElementById('cid-doc-tipo').value         = ciudadano.doc_tipo     || '';
        document.getElementById('cid-doc-nro').value          = ciudadano.doc_nro      || '';
        document.getElementById('cid-cuil').value             = ciudadano.cuil         || '';
        document.getElementById('cid-nombre').value           = ciudadano.nombre       || '';
        document.getElementById('cid-apellido').value         = ciudadano.apellido     || '';
        document.getElementById('cid-sexo').value             = ciudadano.sexo         || '';
        document.getElementById('cid-fecha-nac').value        = ciudadano.fecha_nac ? ciudadano.fecha_nac.substring(0, 10) : '';
        document.getElementById('cid-nacionalidad').value     = ciudadano.id_nacionalidad || '';
        document.getElementById('cid-calle').value            = ciudadano.calle        || '';
        document.getElementById('cid-localidad').value        = ciudadano.localidad    || '';
        document.getElementById('cid-provincia').value        = ciudadano.provincia    || '';
        document.getElementById('cid-latitud').value          = ciudadano.latitud      || '';
        document.getElementById('cid-longitud').value         = ciudadano.longitud     || '';
        document.getElementById('cid-telefono').value         = ciudadano.telefono     || '';
        document.getElementById('cid-email').value            = ciudadano.email        || '';
        document.getElementById('cid-observaciones').value    = ciudadano.observaciones || '';
        document.getElementById('cid-dni-validado').checked   = !!ciudadano.ren_chk;
        document.getElementById('cid-cuil-validado').checked  = !!ciudadano.cuil_chk;
        document.getElementById('cid-email-verificado').checked = !!ciudadano.email_chk;
        if (els.empChk) els.empChk.checked = !!ciudadano.emp_chk;
        els.obsCount.textContent = (ciudadano.observaciones || '').length;
    }

    // ── Modo Edición ──
    function activarModoEdicion(ciudadano) {
        state.mode = 'edit';
        state.ciudadanoId = ciudadano ? ciudadano.id_ciudadano : null;
        state.ciudadanoGuardado = false;

        els.formCiudadano.reset();
        els.formCard.style.display = 'block';
        els.formTitle.textContent = 'Modificar Ciudadano';
        els.formState.className = 'z-form-state z-form-state--edit';
        els.formState.textContent = '✏️ EDICIÓN';
        els.empresaPanel.classList.remove('open');
        els.searchResult.classList.remove('visible');
        setFormReadonly(false);

        delete document.getElementById('cid-cuil').dataset.manualInput;

        if (ciudadano) poblarFormulario(ciudadano);

        setTimeout(() => els.formCard.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
        state.checkGuardar && state.checkGuardar();

        if (ciudadano && ciudadano.emp_chk) {
            cargarEmpresaVinculada(ciudadano.id_ciudadano, false);
        }
    }

    // ── Cargar Empresa Vinculada al ciudadano ──
    async function cargarEmpresaVinculada(ciudadanoId, soloLectura = true) {
        try {
            const empresas = await ZUtils.apiFetch(`/ciudadanos/${ciudadanoId}/empresas-vinculadas`);
            if (!empresas || empresas.length === 0) return false;  // sin empresa vinculada

            const emp = empresas[0];
            els.empresaPanel.classList.add('open');

            const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val || ''; };
            set('ev-cuit',          emp.cuit);
            set('ev-nombre',        emp.nombre);
            set('ev-calle',         emp.calle);
            set('ev-localidad',     emp.localidad);
            set('ev-provincia',     emp.provincia);
            set('ev-telefono',      emp.telefono);
            set('ev-email',         emp.email);
            set('ev-observaciones', emp.observaciones);  // ← incluir observaciones
            const selAct = document.getElementById('ev-actividad');
            if (selAct && emp.id_actividad) selAct.value = emp.id_actividad;
            const selTipoRep = document.getElementById('ev-tipo-rep');
            if (selTipoRep && emp.id_tipo_representacion) selTipoRep.value = emp.id_tipo_representacion;
            const evId = document.getElementById('ev-empresa-id');
            if (evId) evId.value = emp.id_empresa || '';

            // En consulta O edición: nunca mostrar el botón "Cancelar Alta Empresa"
            els.btnCancelarEmpresa.style.display = 'none';

            if (soloLectura) {
                // Modo consulta: todo deshabilitado, sin guardar empresa
                els.formEmpresaVinculada.querySelectorAll('.z-input, .z-select, .z-textarea').forEach(el => {
                    el.readOnly = true;
                    el.disabled = true;
                    el.style.background = '#F5F5F5';
                });
                els.btnGuardarEmpresa.style.display = 'none';
                const panelTitle = els.empresaPanel.querySelector('.z-card__title');
                if (panelTitle) panelTitle.innerHTML = '🏢 Empresa Representada <small style="font-size:0.75rem;color:var(--z-text2);margin-left:8px;">(solo lectura)</small>';
            } else {
                // Modo edición: campos habilitados, puede modificar empresa vinculada
                els.formEmpresaVinculada.querySelectorAll('.z-input, .z-select, .z-textarea').forEach(el => {
                    el.readOnly = false;
                    el.disabled = false;
                    el.style.background = '';
                });
                els.btnGuardarEmpresa.style.display = '';
                const panelTitle = els.empresaPanel.querySelector('.z-card__title');
                if (panelTitle) panelTitle.innerHTML = '🏢 Empresa Vinculada <small style="font-size:0.75rem;color:var(--z-accent);margin-left:8px;">(editable)</small>';
            }

            setTimeout(() => els.empresaPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 600);
            return true;  // empresa encontrada y cargada
        } catch (err) {
            console.warn('[ZARIS] empresas-vinculadas no disponible: ', err.message);
            return false;
        }
    }

    // ── Validar CUIL (legacy) ──
    function handleValidarCuil() {
        const input = document.getElementById('cid-cuil');
        const result = ZValidaciones.validarCuilCuit(input.value);
        if (result.valido) {
            input.value = result.formateado;
            ZValidaciones.marcarCampo(input, true);
            ZUtils.toast('CUIL válido ✓', 'success');
        } else {
            ZValidaciones.marcarCampo(input, false, result.error);
            ZUtils.toast(result.error, 'error');
        }
    }

    // ── Guardar Ciudadano ──
    async function handleGuardar() {
        // Validar formulario
        const { valido, errores } = ZValidaciones.validarFormulario(els.formCiudadano);

        // ── Validar que al menos DNI o CUIL estén cargados ──
        const cuil = document.getElementById('cid-cuil').value.trim();
        const docNro = document.getElementById('cid-doc-nro').value.trim();

        if (!cuil && !docNro) {
            errores.push('Se requiere al menos DNI o CUIL');
            ZValidaciones.marcarCampo(document.getElementById('cid-doc-nro'), false, 'Ingresá el DNI o el CUIL');
            ZValidaciones.marcarCampo(document.getElementById('cid-cuil'), false, 'Ingresá el CUIL o el DNI');
        }

        // ── Verificar duplicados email/tel — solo en ALTA (en edición se omite) ──
        const email    = document.getElementById('cid-email').value;
        const telefono = document.getElementById('cid-telefono').value;
        const isEditGuard = state.mode === 'edit' && state.ciudadanoId;
        if (!isEditGuard) {
            if (email) {
                const rVal = ZValidaciones.validarEmail(email);
                if (!rVal) {
                    ZValidaciones.marcarCampo(document.getElementById('cid-email'), false, 'Formato de email inválido');
                    errores.push('Email inválido');
                } else {
                    const rDup = await ZUtils.verificarDuplicado('ciudadanos', 'email', email, state.ciudadanoId);
                    if (rDup.existe) {
                        ZValidaciones.marcarCampo(document.getElementById('cid-email'), false, `Ya registrado: ${rDup.nombre}`);
                        errores.push('Email duplicado');
                    }
                }
            }
            if (telefono) {
                const telResult = ZValidaciones.validarTelefono(telefono);
                if (!telResult.valido) {
                    ZValidaciones.marcarCampo(document.getElementById('cid-telefono'), false, telResult.error);
                    errores.push('Teléfono inválido');
                } else {
                    const rDup = await ZUtils.verificarDuplicado('ciudadanos', 'telefono', telefono, state.ciudadanoId);
                    if (rDup.existe) {
                        ZValidaciones.marcarCampo(document.getElementById('cid-telefono'), false, `Ya registrado: ${rDup.nombre}`);
                        errores.push('Teléfono duplicado');
                    }
                }
            }
        }

        if (errores.length > 0) {
            ZUtils.toast(`Hay ${errores.length} error(es) en el formulario. Revisá los campos marcados.`, 'error');
            return;
        }

        // Recopilar datos del formulario
        const formData = new FormData(els.formCiudadano);
        const data = Object.fromEntries(formData.entries());

        // Checkboxes disabled: FormData no los incluye → leer con .checked directamente
        data.emp_chk   = els.empChk.checked;
        data.ren_chk   = document.getElementById('cid-dni-validado').checked;
        data.email_chk = document.getElementById('cid-email-verificado').checked;

        const cuilFinal = document.getElementById('cid-cuil').value.trim();
        const dniNro   = document.getElementById('cid-doc-nro').value.trim();

        // Si se ingresó CUIL pero no DNI → extraer DNI del CUIL
        if (cuilFinal && !dniNro) {
            const extraido = extraerDniDeCuil(cuilFinal);
            if (extraido) data.doc_nro = extraido;
        }
        // Si se ingresó DNI pero no CUIL → calcular CUIL
        if (dniNro && !cuilFinal) {
            generarCuilDesdeDni();
            data.cuil = document.getElementById('cid-cuil').value.trim();
        }

        try {
            const isEdit = state.mode === 'edit' && state.ciudadanoId;
            const endpoint = isEdit ? `/ciudadanos/${state.ciudadanoId}` : '/ciudadanos';
            const method   = isEdit ? 'PUT' : 'POST';

            const response = await ZUtils.apiFetch(endpoint, {
                method,
                body: JSON.stringify(data)
            });

            state.ciudadanoId = response.id_ciudadano || state.ciudadanoId;
            state.ciudadanoGuardado = true;

            const accion = isEdit ? 'actualizado' : 'guardado';
            ZUtils.modalGuardado(
                `Ciudadano ${accion}`,
                `${response.apellido || ''}, ${response.nombre || ''}`,
                () => activarModoNuevo(),
                () => { window.location.href = 'menu.html'; }
            );

            // Si emp_chk está marcado, desplegar panel empresa
            if (els.empChk.checked && !isEdit) {
                document.getElementById('ev-ciudadano-id').value = state.ciudadanoId;
                els.empresaPanel.classList.add('open');
                setTimeout(() => els.empresaPanel.scrollIntoView({ behavior: 'smooth', block: 'start' }), 400);
            }
        } catch (err) {
            ZUtils.toast(`Error al guardar: ${err.message}`, 'error');
        }
    }

    // ── Cancelar ──
    async function handleCancelar() {
        const confirmed = await ZUtils.confirm(
            '¿Salir del formulario?',
            'Los datos no guardados se perderán. ¿Estás seguro que deseas salir?'
        );
        if (confirmed) {
            window.location.href = 'menu.html';
        }
    }

    // ── Guardar Empresa (desde flujo ciudadano) ──
    async function handleGuardarEmpresa() {
        const formEmpresa = els.formEmpresaVinculada;
        const { valido, errores } = ZValidaciones.validarFormulario(formEmpresa);

        // Validar CUIT
        const cuit = document.getElementById('ev-cuit').value;
        if (cuit) {
            const cuitResult = ZValidaciones.validarCuilCuit(cuit);
            if (!cuitResult.valido) {
                ZValidaciones.marcarCampo(document.getElementById('ev-cuit'), false, cuitResult.error);
                errores.push('CUIT inválido');
            }
        }

        const emailEmp = document.getElementById('ev-email').value;
        if (emailEmp && !ZValidaciones.validarEmail(emailEmp)) {
            ZValidaciones.marcarCampo(document.getElementById('ev-email'), false, 'Formato de email inválido');
            errores.push('Email inválido');
        }

        if (errores.length > 0) {
            ZUtils.toast(`Hay ${errores.length} error(es). Revisá los campos.`, 'error');
            return;
        }

        const formData = new FormData(formEmpresa);
        const data = Object.fromEntries(formData.entries());
        data.id_ciudadano = state.ciudadanoId;

        // Formatear CUIT
        const cuitResult = ZValidaciones.validarCuilCuit(data.cuit);
        if (cuitResult.valido) data.cuit = cuitResult.formateado;

        try {
            // 1. Crear empresa
            const empResponse = await ZUtils.apiFetch('/empresas', {
                method: 'POST',
                body: JSON.stringify(data)
            });

            // 2. Crear relación ciudadano-empresa
            await ZUtils.apiFetch('/ciudadano-empresa', {
                method: 'POST',
                body: JSON.stringify({
                    id_ciudadano: state.ciudadanoId,
                    id_empresa: empResponse.id_empresa,
                    id_tipo_representacion: parseInt(data.id_tipo_representacion)
                })
            });

            ZUtils.toast('Empresa guardada y vinculada al ciudadano (ID: ' + empResponse.id_empresa + ')', 'success');

            setTimeout(async () => {
                const otraAlta = await ZUtils.confirm('Empresa guardada', '¿Deseás dar de alta otro ciudadano?');
                if (otraAlta) activarModoNuevo();
                else window.location.href = 'menu.html';
            }, 1000);
        } catch (err) {
            ZUtils.toast(`Error al guardar empresa: ${err.message}`, 'error');
        }
    }

    // ── Cancelar Empresa ──
    async function handleCancelarEmpresa() {
        const confirmed = await ZUtils.confirm(
            '¿Cancelar alta de empresa?',
            'El ciudadano ya fue guardado. Si cancela, se desvinculará la marca de representante (emp_chk).'
        );

        if (confirmed) {
            // Revertir emp_chk a false
            els.empChk.checked = false;
            console.log('[ZARIS] Revirtiendo emp_chk a false para ciudadano:', state.ciudadanoId);

            els.empresaPanel.classList.remove('open');
            els.formEmpresaVinculada.reset();
            ZUtils.toast('Alta de empresa cancelada. emp_chk revertido.', 'info');
        }
    }

    // ── Util ──────────────────────────────────────────────────────────────
    function esc(s) {
        return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    }

    // ── Vista previa ──────────────────────────────────────────────────────
    async function cargarVistaPrevia() {
        const container = document.getElementById('preview-rows');
        if (!container) return;
        container.innerHTML = '<div style="color:var(--z-text3);font-size:.82rem;padding:.5rem 0;">Cargando...</div>';
        try {
            const data = await ZUtils.apiFetch('/ciudadanos?solo_activos=false&limit=200');
            const recientes = data.slice(0, 5); // ya vienen ordenados por id desc
            if (recientes.length === 0) {
                container.innerHTML = '<div style="color:var(--z-text3);font-size:.82rem;padding:.5rem 0;">Sin registros</div>';
                return;
            }
            container.innerHTML = recientes.map(c => `
                <div class="z-preview-row" data-id="${c.id_ciudadano}">
                    <span class="z-preview-row__nombre">${esc(c.apellido)}, ${esc(c.nombre)}</span>
                    <span class="z-preview-row__mono">${c.doc_tipo || ''} ${esc(c.doc_nro || '—')}</span>
                    <span class="z-preview-row__meta">${esc(c.cuil || '—')}</span>
                    <span class="z-preview-row__estado z-preview-row__estado--${c.activo ? 'activo' : 'inactivo'}">${c.activo ? 'Activo' : 'Inactivo'}</span>
                    <span class="z-preview-row__cta">Ver →</span>
                </div>`).join('');
            container.querySelectorAll('.z-preview-row').forEach(row =>
                row.addEventListener('click', () => cargarCiudadanoDesdePrevia(parseInt(row.dataset.id)))
            );
        } catch (err) {
            console.error('[Preview ciudadanos]', err);
            container.innerHTML = `<div style="color:var(--z-text3);font-size:.82rem;padding:.5rem 0;">No se pudo cargar (${err.message})</div>`;
        }
    }

    async function cargarCiudadanoDesdePrevia(id) {
        try {
            const c = await ZUtils.apiFetch(`/ciudadanos/${id}`);
            mostrarResultadoUnico(c);
        } catch (err) {
            ZUtils.toast('Error al cargar ciudadano', 'error');
        }
    }

    // ── Listado completo ──────────────────────────────────────────────────
    let _listadoData = [];

    async function abrirListado() {
        document.getElementById('search-panel').style.display   = 'none';
        document.getElementById('preview-section').style.display = 'none';
        document.getElementById('form-card').style.display      = 'none';
        document.getElementById('listado-section').style.display = 'block';
        document.getElementById('listado-contenido').innerHTML  = '<div style="text-align:center;padding:2rem;color:var(--z-text3);">Cargando...</div>';
        document.getElementById('lst-count').textContent = '';
        try {
            _listadoData = await ZUtils.apiFetch('/ciudadanos?solo_activos=false&limit=1000');
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

        if (txt) rows = rows.filter(c =>
            (c.nombre   || '').toLowerCase().includes(txt) ||
            (c.apellido || '').toLowerCase().includes(txt) ||
            (c.doc_nro  || '').includes(txt) ||
            (c.cuil     || '').includes(txt)
        );
        if (desd || hast) rows = rows.filter(c => {
            const d = (c.fecha_alta || '').slice(0,10);
            if (!d) return true;
            if (desd && d < desd) return false;
            if (hast && d > hast) return false;
            return true;
        });
        if      (ord === 'reciente') rows.sort((a,b) => (b.id_ciudadano||0)-(a.id_ciudadano||0));
        else if (ord === 'antiguo')  rows.sort((a,b) => (a.id_ciudadano||0)-(b.id_ciudadano||0));
        else if (ord === 'az')       rows.sort((a,b) => (a.apellido||'').localeCompare(b.apellido||'','es'));
        else if (ord === 'za')       rows.sort((a,b) => (b.apellido||'').localeCompare(a.apellido||'','es'));
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
            `<h2>Padrón de Ciudadanos — ZARIS</h2><p>Listado generado el ${fecha} · ${rows.length} registro${rows.length!==1?'s':''}</p>`;
        document.getElementById('lst-count').textContent =
            `${rows.length} ciudadano${rows.length!==1?'s':''} encontrado${rows.length!==1?'s':''}`;

        if (rows.length === 0) {
            document.getElementById('listado-contenido').innerHTML =
                '<div style="text-align:center;padding:2.5rem;color:var(--z-text3);">Sin resultados</div>';
            return;
        }
        const bodyRows = rows.map(c => `<tr>
            <td>${esc(c.apellido)}, ${esc(c.nombre)}</td>
            <td class="mono">${esc(c.doc_tipo||'')} ${esc(c.doc_nro||'—')}</td>
            <td class="mono">${esc(c.cuil||'—')}</td>
            <td>${esc(c.email||'—')}</td>
            <td><span class="z-badge-${c.activo?'activo':'inactivo'}">${c.activo?'Activo':'Inactivo'}</span></td>
            <td>
                <button class="z-tbl-btn" data-id="${c.id_ciudadano}" data-modo="consulta">Ver</button>
                <button class="z-tbl-btn" data-id="${c.id_ciudadano}" data-modo="edicion">Editar</button>
            </td></tr>`).join('');

        document.getElementById('listado-contenido').innerHTML = `
            <div class="z-listado-wrap"><table>
                <thead><tr><th>Apellido, Nombre</th><th>Documento</th><th>CUIL</th><th>Email</th><th>Estado</th><th>Acciones</th></tr></thead>
                <tbody>${bodyRows}</tbody>
            </table></div>`;

        document.getElementById('listado-contenido').querySelectorAll('.z-tbl-btn').forEach(btn =>
            btn.addEventListener('click', () => {
                const c = _listadoData.find(x => x.id_ciudadano === parseInt(btn.dataset.id));
                cerrarListado();
                if (c) mostrarResultadoUnico(c);
                else cargarCiudadanoDesdePrevia(parseInt(btn.dataset.id));
            })
        );
    }

    // Registrar eventos listado + preview
    document.getElementById('btn-listado')?.addEventListener('click', abrirListado);
    document.getElementById('btn-cerrar-listado')?.addEventListener('click', cerrarListado);
    document.getElementById('btn-imprimir-lst')?.addEventListener('click', () => window.print());
    document.getElementById('btn-filtrar-lst')?.addEventListener('click', aplicarFiltros);
    document.getElementById('btn-limpiar-lst')?.addEventListener('click', limpiarFiltros);
    document.getElementById('lst-texto')?.addEventListener('keydown', e => { if(e.key==='Enter') aplicarFiltros(); });

    cargarVistaPrevia();

});
