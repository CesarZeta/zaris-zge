/**
 * ZARIS Gestión Estatal — Módulo de Validaciones
 * Validación módulo 11 (CUIL/CUIT), email, teléfono y campos generales.
 */
const ZValidaciones = {

    /**
     * Validación de CUIL/CUIT con algoritmo módulo 11.
     * Formato esperado: XX-XXXXXXXX-X (con o sin guiones)
     * Multiplicadores: 5, 4, 3, 2, 7, 6, 5, 4, 3, 2
     * @param {string} cuilCuit - Número de CUIL o CUIT
     * @returns {object} { valido: boolean, formateado: string, error: string }
     */
    validarCuilCuit(cuilCuit) {
        // Limpiar: quitar guiones, espacios
        const limpio = String(cuilCuit).replace(/[-\s]/g, '');

        if (!/^\d{11}$/.test(limpio)) {
            return { valido: false, formateado: '', error: 'Debe contener exactamente 11 dígitos numéricos.' };
        }

        const multiplicadores = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2];
        const digitos = limpio.split('').map(Number);
        const digitoVerificador = digitos[10];

        let suma = 0;
        for (let i = 0; i < 10; i++) {
            suma += digitos[i] * multiplicadores[i];
        }

        const resto = suma % 11;
        let verificadorCalculado;

        if (resto === 0) {
            verificadorCalculado = 0;
        } else if (resto === 1) {
            verificadorCalculado = 9; // Caso especial para sexo femenino
            // Algunos CUIL con tipo 23 y resto 1 usan dígito 4
            // Para simplificar, aceptamos 9 como válido
        } else {
            verificadorCalculado = 11 - resto;
        }

        const valido = digitoVerificador === verificadorCalculado;
        const formateado = `${limpio.substring(0, 2)}-${limpio.substring(2, 10)}-${limpio.substring(10)}`;

        return {
            valido,
            formateado,
            error: valido ? '' : `Dígito verificador inválido. Se esperaba ${verificadorCalculado}.`
        };
    },

    /**
     * Validación de formato de email.
     * @param {string} email
     * @returns {boolean}
     */
    validarEmail(email) {
        const regex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
        return regex.test(String(email).trim());
    },

    /**
     * Validación de teléfono argentino.
     * 10 dígitos sin código de área 0.
     * @param {string} telefono
     * @returns {object} { valido: boolean, error: string }
     */
    validarTelefono(telefono) {
        const limpio = String(telefono).replace(/[-\s()]/g, '');

        if (!/^\d{10}$/.test(limpio)) {
            return { valido: false, error: 'El teléfono debe contener exactamente 10 dígitos (código de área sin 0 + número).' };
        }

        if (limpio.startsWith('0')) {
            return { valido: false, error: 'No incluir el 0 del código de área.' };
        }

        return { valido: true, error: '' };
    },

    /**
     * Validación de número de documento.
     * @param {string} nroDoc
     * @returns {boolean}
     */
    validarDocumento(nroDoc) {
        const limpio = String(nroDoc).replace(/\s/g, '');
        return /^\d{1,10}$/.test(limpio);
    },

    /**
     * Validación de campo requerido.
     * @param {string} value
     * @returns {boolean}
     */
    requerido(value) {
        return value !== null && value !== undefined && String(value).trim() !== '';
    },

    /**
     * Validación de longitud máxima.
     * @param {string} value
     * @param {number} max
     * @returns {boolean}
     */
    maxLength(value, max) {
        return String(value).length <= max;
    },

    /**
     * Aplica validación visual a un campo input.
     * Añade borde verde/rojo y muestra/oculta mensaje de error.
     * @param {HTMLElement} inputEl - El elemento input
     * @param {boolean} isValid - Si el campo es válido
     * @param {string} [errorMsg] - Mensaje de error opcional
     */
    marcarCampo(inputEl, isValid, errorMsg = '') {
        inputEl.classList.remove('input-zaris--error', 'input-zaris--success');

        if (isValid) {
            inputEl.classList.add('input-zaris--success');
        } else {
            inputEl.classList.add('input-zaris--error');
        }

        // Buscar elemento de error siguiente
        const errorEl = inputEl.parentElement.querySelector('.input-error-zaris');
        if (errorEl) {
            if (isValid) {
                errorEl.classList.remove('visible');
                errorEl.textContent = '';
            } else {
                errorEl.classList.add('visible');
                errorEl.textContent = errorMsg;
            }
        }
    },

    /**
     * Limpia la validación visual de un campo.
     * @param {HTMLElement} inputEl
     */
    limpiarCampo(inputEl) {
        inputEl.classList.remove('input-zaris--error', 'input-zaris--success');
        const errorEl = inputEl.parentElement.querySelector('.input-error-zaris');
        if (errorEl) {
            errorEl.classList.remove('visible');
            errorEl.textContent = '';
        }
    },

    /**
     * Valida todo un formulario.
     * @param {HTMLFormElement} formEl
     * @returns {object} { valido: boolean, errores: string[] }
     */
    validarFormulario(formEl) {
        const errores = [];
        const requiredFields = formEl.querySelectorAll('[required]');

        requiredFields.forEach(field => {
            if (!this.requerido(field.value)) {
                const label = formEl.querySelector(`label[for="${field.id}"]`);
                const nombre = label ? label.textContent.replace(' *', '') : field.name || field.id;
                errores.push(`El campo "${nombre}" es obligatorio.`);
                this.marcarCampo(field, false, 'Campo obligatorio');
            }
        });

        return { valido: errores.length === 0, errores };
    },

    /**
     * Verifica si todos los campos [required] visibles del contenedor están
     * completos y con formato válido (CUIL/CUIT, email, teléfono, documento).
     * @param {HTMLElement} containerEl
     * @param {object} [opts] - { extra: (containerEl) => boolean }
     * @returns {boolean}
     */
    formularioCompleto(containerEl, opts = {}) {
        const required = containerEl.querySelectorAll('[required]');
        for (const f of required) {
            if (f.disabled) continue;
            const val = (f.value || '').trim();
            if (!val) return false;
            const id = f.id || '';
            if (id.endsWith('-cuit') || id.endsWith('-cuil') || f.dataset.validate === 'cuilcuit') {
                if (!this.validarCuilCuit(val).valido) return false;
            } else if (id.endsWith('-telefono') || f.dataset.validate === 'telefono') {
                if (!this.validarTelefono(val).valido) return false;
            } else if (f.type === 'email' || f.dataset.validate === 'email') {
                if (!this.validarEmail(val)) return false;
            } else if (id.endsWith('-doc-nro') || f.dataset.validate === 'documento') {
                if (!this.validarDocumento(val)) return false;
            }
        }
        if (typeof opts.extra === 'function' && !opts.extra(containerEl)) return false;
        return true;
    },

    /**
     * Liga un botón "Guardar" a un contenedor: deshabilita hasta que todos
     * los [required] estén completos y con formato válido. Cambios programáticos
     * de campos requieren llamar manualmente al check devuelto.
     * @param {HTMLElement} containerEl
     * @param {HTMLButtonElement} btnEl
     * @param {object} [opts] - { extra }
     * @returns {{ check: () => void }}
     */
    bindGuardarBoton(containerEl, btnEl, opts = {}) {
        const check = () => {
            const ok = this.formularioCompleto(containerEl, opts);
            btnEl.disabled = !ok;
            btnEl.title = ok ? '' : 'Completá todos los campos obligatorios para guardar';
        };
        containerEl.addEventListener('input', check);
        containerEl.addEventListener('change', check);
        check();
        return { check };
    }
};
