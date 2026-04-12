/**
 * ZARIS — Lógica del Formulario de Ciudadano
 * Maneja búsqueda, alta, edición y flujo hacia empresa.
 */
document.addEventListener('DOMContentLoaded', () => {
    // ── State ──
    const state = {
        mode: 'search',       // 'search' | 'new' | 'edit'
        ciudadanoId: null,
        ciudadanoGuardado: false,
        nacionalidades: [],
        tipoRepresentacion: [],
        actividades: []
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
        btnBuscar:          document.getElementById('btn-buscar'),
        btnNuevo:           document.getElementById('btn-nuevo'),
        btnEditarEncontrado: document.getElementById('btn-editar-encontrado'),
        btnNuevoForzar:     document.getElementById('btn-nuevo-forzar'),
        btnGuardar:         document.getElementById('btn-guardar'),
        btnCancelar:        document.getElementById('btn-cancelar'),

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
        // Búsqueda
        els.btnBuscar.addEventListener('click', handleBuscar);
        els.searchQuery.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') { e.preventDefault(); handleBuscar(); }
        });

        // Nuevo
        els.btnNuevo.addEventListener('click', () => activarModoNuevo());
        els.btnNuevoForzar.addEventListener('click', () => activarModoNuevo());
        els.btnEditarEncontrado.addEventListener('click', () => activarModoEdicion());

        // CUIL Auto-generado: se recalcula cuando cambia Sexo o DNI
        document.getElementById('cid-sexo').addEventListener('change', generarCuilAutomatico);
        document.getElementById('cid-doc-nro').addEventListener('input', generarCuilAutomatico);
        document.getElementById('cid-doc-tipo').addEventListener('change', generarCuilAutomatico);

        // Guardar/Cancelar
        els.btnGuardar.addEventListener('click', handleGuardar);
        els.btnCancelar.addEventListener('click', handleCancelar);

        // Empresa
        els.btnGuardarEmpresa.addEventListener('click', handleGuardarEmpresa);
        els.btnCancelarEmpresa.addEventListener('click', handleCancelarEmpresa);
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

    // ── Auto-generar CUIL desde Sexo + DNI (Módulo 11) ──
    function calcularDigitoVerificador(prefijo, dni) {
        const base = `${prefijo}${dni.padStart(8, '0')}`;
        const coeficientes = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2];
        let suma = 0;
        for (let i = 0; i < 10; i++) {
            suma += parseInt(base[i]) * coeficientes[i];
        }
        const resto = suma % 11;
        if (resto === 0) return 0;
        if (resto === 1) return prefijo === '20' ? 9 : prefijo === '27' ? 4 : 9;
        return 11 - resto;
    }

    function generarCuilAutomatico() {
        const sexo = document.getElementById('cid-sexo').value;
        const docTipo = document.getElementById('cid-doc-tipo').value;
        const docNro = document.getElementById('cid-doc-nro').value.replace(/\D/g, '');
        const cuilInput = document.getElementById('cid-cuil');

        // Solo genera para DNI (Pasaporte no tiene CUIL calculable)
        if (!sexo || docTipo !== 'DNI' || docNro.length < 7) {
            cuilInput.value = '';
            cuilInput.style.color = '';
            return;
        }

        // Prefijo según sexo
        const prefijo = (sexo === 'MUJER') ? '27' : '20';

        const digitoV = calcularDigitoVerificador(prefijo, docNro);
        const cuil = `${prefijo}-${docNro.padStart(8, '0')}-${digitoV}`;

        cuilInput.value = cuil;
        cuilInput.style.color = 'var(--z-primary)';
        ZValidaciones.marcarCampo(cuilInput, true);
    }

    // ── Búsqueda ──
    async function handleBuscar() {
        const query = els.searchQuery.value.trim();
        if (!query) {
            ZUtils.toast('Ingresá un Nro. de Documento o Email para buscar.', 'warning');
            els.searchQuery.focus();
            return;
        }

        try {
            const resultados = await ZUtils.apiFetch(`/ciudadanos/buscar?q=${encodeURIComponent(query)}`);
            if (resultados.length === 0) {
                ZUtils.toast('No se encontró ningún ciudadano con esos datos.', 'info');
                els.searchResult.classList.remove('visible');
            } else {
                mostrarResultado(resultados[0]);
                state.ciudadanoEncontrado = resultados[0];
            }
        } catch (err) {
            ZUtils.toast('Error en la búsqueda: ' + err.message, 'error');
        }
    }

    function mostrarResultado(ciudadano) {
        els.resultName.textContent = `${ciudadano.apellido}, ${ciudadano.nombre}`;
        els.resultDetail.textContent = `${ciudadano.doc_tipo} ${ciudadano.doc_nro} | CUIL: ${ciudadano.cuil} | ${ciudadano.email}`;
        els.searchResult.classList.add('visible');
    }

    // ── Modo Nuevo ──
    function activarModoNuevo() {
        state.mode = 'new';
        state.ciudadanoId = null;
        state.ciudadanoGuardado = false;

        els.formCiudadano.reset();
        els.formCard.style.display = 'block';
        els.formTitle.textContent = 'Alta de Ciudadano';
        els.formState.className = 'z-form-state z-form-state--new';
        els.formState.textContent = '● NUEVO';
        els.empresaPanel.classList.remove('open');
        els.searchResult.classList.remove('visible');
        els.obsCount.textContent = '0';

        // Limpiar validaciones visuales
        els.formCiudadano.querySelectorAll('.z-input, .z-select, .z-textarea').forEach(el => {
            ZValidaciones.limpiarCampo(el);
        });

        // Scroll al formulario
        setTimeout(() => {
            els.formCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 100);

        document.getElementById('cid-doc-tipo').focus();
    }

    // ── Modo Edición ──
    function activarModoEdicion() {
        state.mode = 'edit';
        els.formCard.style.display = 'block';
        els.formTitle.textContent = 'Modificar Ciudadano';
        els.formState.className = 'z-form-state z-form-state--edit';
        els.formState.textContent = '✏️ EDICIÓN';

        setTimeout(() => {
            els.formCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 100);
    }

    // ── Validar CUIL (legacy, usado solo en modo edición si se edita manualmente) ──
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

        // Validar CUIL auto-generado
        const cuil = document.getElementById('cid-cuil').value;
        if (!cuil) {
            // Intentar generarlo ahora si faltan datos
            generarCuilAutomatico();
            const cuilActualizado = document.getElementById('cid-cuil').value;
            if (!cuilActualizado) {
                errores.push('CUIL no generado: verificar DNI y Sexo');
                ZValidaciones.marcarCampo(document.getElementById('cid-cuil'), false, 'Completar DNI y Sexo para generar el CUIL');
            }
        }

        const email = document.getElementById('cid-email').value;
        if (email && !ZValidaciones.validarEmail(email)) {
            ZValidaciones.marcarCampo(document.getElementById('cid-email'), false, 'Formato de email inválido');
            errores.push('Email inválido');
        }

        const telefono = document.getElementById('cid-telefono').value;
        if (telefono) {
            const telResult = ZValidaciones.validarTelefono(telefono);
            if (!telResult.valido) {
                ZValidaciones.marcarCampo(document.getElementById('cid-telefono'), false, telResult.error);
                errores.push('Teléfono inválido');
            }
        }

        if (errores.length > 0) {
            ZUtils.toast(`Hay ${errores.length} error(es) en el formulario. Revisá los campos marcados.`, 'error');
            return;
        }

        // Recopilar datos
        const formData = new FormData(els.formCiudadano);
        const data = Object.fromEntries(formData.entries());
        data.emp_chk = els.empChk.checked;
        data.ren_chk = false;
        data.email_chk = false;

        // El CUIL ya está formateado (auto-generado), enviarlo tal cual
        // No re-validar ni re-formatear para evitar errores

        try {
            const response = await ZUtils.apiFetch('/ciudadanos', {
                method: 'POST',
                body: JSON.stringify(data)
            });

            state.ciudadanoId = response.id_ciudadano;
            state.ciudadanoGuardado = true;

            ZUtils.toast('Ciudadano guardado exitosamente (ID: ' + response.id_ciudadano + ')', 'success');

            // Si emp_chk está marcado, desplegar panel empresa
            if (els.empChk.checked) {
                document.getElementById('ev-ciudadano-id').value = state.ciudadanoId;
                els.empresaPanel.classList.add('open');
                setTimeout(() => {
                    els.empresaPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }, 400);
            } else {
                // Volver al menú o limpiar para siguiente alta
                setTimeout(() => {
                    if (confirm('¿Deseas dar de alta otro ciudadano?')) {
                        activarModoNuevo();
                    } else {
                        window.location.href = 'menu.html';
                    }
                }, 1000);
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

            setTimeout(() => {
                if (confirm('¿Deseas dar de alta otro ciudadano?')) {
                    activarModoNuevo();
                } else {
                    window.location.href = 'menu.html';
                }
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

    // ── Datos de nacionalidades (hardcodeados para preview) ──
    function getNacionalidadesData() {
        return [
            {id:1,pais:'Argentina',region:'América'},{id:2,pais:'Bolivia',region:'América'},
            {id:3,pais:'Brasil',region:'América'},{id:4,pais:'Chile',region:'América'},
            {id:5,pais:'Colombia',region:'América'},{id:6,pais:'Costa Rica',region:'América'},
            {id:7,pais:'Cuba',region:'América'},{id:8,pais:'Ecuador',region:'América'},
            {id:9,pais:'El Salvador',region:'América'},{id:10,pais:'Estados Unidos',region:'América'},
            {id:11,pais:'Guatemala',region:'América'},{id:12,pais:'Haití',region:'América'},
            {id:13,pais:'Honduras',region:'América'},{id:14,pais:'Jamaica',region:'América'},
            {id:15,pais:'México',region:'América'},{id:16,pais:'Nicaragua',region:'América'},
            {id:17,pais:'Panamá',region:'América'},{id:18,pais:'Paraguay',region:'América'},
            {id:19,pais:'Perú',region:'América'},{id:20,pais:'Puerto Rico',region:'América'},
            {id:21,pais:'República Dominicana',region:'América'},{id:22,pais:'Trinidad y Tobago',region:'América'},
            {id:23,pais:'Uruguay',region:'América'},{id:24,pais:'Venezuela',region:'América'},
            {id:25,pais:'Canadá',region:'América'},{id:26,pais:'Alemania',region:'Europa'},
            {id:27,pais:'Austria',region:'Europa'},{id:28,pais:'Bélgica',region:'Europa'},
            {id:29,pais:'Bulgaria',region:'Europa'},{id:30,pais:'Croacia',region:'Europa'},
            {id:31,pais:'Dinamarca',region:'Europa'},{id:32,pais:'Eslovaquia',region:'Europa'},
            {id:33,pais:'Eslovenia',region:'Europa'},{id:34,pais:'España',region:'Europa'},
            {id:35,pais:'Estonia',region:'Europa'},{id:36,pais:'Finlandia',region:'Europa'},
            {id:37,pais:'Francia',region:'Europa'},{id:38,pais:'Grecia',region:'Europa'},
            {id:39,pais:'Hungría',region:'Europa'},{id:40,pais:'Irlanda',region:'Europa'},
            {id:41,pais:'Italia',region:'Europa'},{id:42,pais:'Letonia',region:'Europa'},
            {id:43,pais:'Lituania',region:'Europa'},{id:44,pais:'Luxemburgo',region:'Europa'},
            {id:45,pais:'Malta',region:'Europa'},{id:46,pais:'Países Bajos',region:'Europa'},
            {id:47,pais:'Polonia',region:'Europa'},{id:48,pais:'Portugal',region:'Europa'},
            {id:49,pais:'Reino Unido',region:'Europa'},{id:50,pais:'República Checa',region:'Europa'},
            {id:51,pais:'Rumania',region:'Europa'},{id:52,pais:'Suecia',region:'Europa'},
            {id:53,pais:'Suiza',region:'Europa'},{id:54,pais:'Noruega',region:'Europa'},
            {id:55,pais:'Ucrania',region:'Europa'},{id:56,pais:'Rusia',region:'Europa'},
            {id:57,pais:'China',region:'Otros'},{id:58,pais:'Corea del Sur',region:'Otros'},
            {id:59,pais:'India',region:'Otros'},{id:60,pais:'Israel',region:'Otros'},
            {id:61,pais:'Japón',region:'Otros'},{id:62,pais:'Líbano',region:'Otros'},
            {id:63,pais:'Siria',region:'Otros'},{id:64,pais:'Turquía',region:'Otros'},
            {id:65,pais:'Australia',region:'Otros'}
        ];
    }

    // ── Datos de actividades (hardcodeados para preview) ──
    function getActividadesData() {
        return [
            {id:1,codigo_clae:471100,descripcion:'Venta menor - alimentos (no especializados)',categoria_tasa:'comercio'},
            {id:2,codigo_clae:472100,descripcion:'Venta menor - alimentos (especializados)',categoria_tasa:'comercio'},
            {id:3,codigo_clae:473000,descripcion:'Venta menor - combustibles',categoria_tasa:'comercio'},
            {id:4,codigo_clae:475100,descripcion:'Venta menor - textiles',categoria_tasa:'comercio'},
            {id:5,codigo_clae:476100,descripcion:'Venta menor - libros/papelería',categoria_tasa:'comercio'},
            {id:6,codigo_clae:477100,descripcion:'Venta menor - prendas de vestir',categoria_tasa:'comercio'},
            {id:7,codigo_clae:478100,descripcion:'Venta menor - alimentos móviles',categoria_tasa:'comercio'},
            {id:8,codigo_clae:461000,descripcion:'Venta mayor - retribución/contrata',categoria_tasa:'comercio'},
            {id:9,codigo_clae:551000,descripcion:'Alojamiento hotelero',categoria_tasa:'servicios'},
            {id:10,codigo_clae:561000,descripcion:'Restaurantes y expendio de comidas',categoria_tasa:'servicios'},
            {id:11,codigo_clae:620100,descripcion:'Programación informática',categoria_tasa:'servicios'},
            {id:12,codigo_clae:631100,descripcion:'Procesamiento de datos',categoria_tasa:'servicios'},
            {id:13,codigo_clae:641900,descripcion:'Intermediación monetaria',categoria_tasa:'servicios'},
            {id:14,codigo_clae:681000,descripcion:'Actividades inmobiliarias',categoria_tasa:'servicios'},
            {id:15,codigo_clae:691000,descripcion:'Actividades jurídicas',categoria_tasa:'servicios'},
            {id:16,codigo_clae:692000,descripcion:'Contabilidad y auditoría',categoria_tasa:'servicios'},
            {id:17,codigo_clae:711000,descripcion:'Arquitectura e ingeniería',categoria_tasa:'servicios'},
            {id:18,codigo_clae:750000,descripcion:'Actividades veterinarias',categoria_tasa:'servicios'},
            {id:19,codigo_clae:851000,descripcion:'Enseñanza inicial y primaria',categoria_tasa:'servicios'},
            {id:20,codigo_clae:862000,descripcion:'Médicos y odontólogos',categoria_tasa:'servicios'},
            {id:21,codigo_clae:101000,descripcion:'Elaboración de carne',categoria_tasa:'industria'},
            {id:22,codigo_clae:105000,descripcion:'Productos lácteos',categoria_tasa:'industria'},
            {id:23,codigo_clae:110000,descripcion:'Elaboración de bebidas',categoria_tasa:'industria'},
            {id:24,codigo_clae:251100,descripcion:'Productos metálicos estructurales',categoria_tasa:'industria'},
            {id:25,codigo_clae:310000,descripcion:'Muebles y colchones',categoria_tasa:'industria'}
        ];
    }
});
