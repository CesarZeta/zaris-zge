/**
 * ZARIS Gestión Estatal — Configuración Global
 * Centraliza URLs de API y constantes del sistema.
 */
const ZARIS_CONFIG = {
    API_BASE: (() => {
        const local = ['localhost', '127.0.0.1', '0.0.0.0'];
        return local.includes(window.location.hostname)
            ? 'http://127.0.0.1:8000/api'
            : 'https://zaris-api-production-bf0b.up.railway.app/api';
    })(),
    API_VERSION: 'v1',
    APP_VERSION: '1.0.0',
    APP_NAME: 'ZARIS Gestión Estatal',
    MODULE_NAME: 'BUC',

    get API_BUC() {
        return `${this.API_BASE}/${this.API_VERSION}/buc`;
    }
};

/**
 * Valores fijos para combos internos (sin tabla externa)
 */
const ZARIS_ENUMS = {
    TIPO_DOCUMENTO: [
        { value: 'DNI', label: 'DNI' },
        { value: 'PASAPORTE', label: 'Pasaporte' }
    ],
    SEXO: [
        { value: 'HOMBRE', label: 'Hombre' },
        { value: 'MUJER', label: 'Mujer' },
        { value: 'OTROS', label: 'Otros' }
    ]
};

/**
 * Utilidades generales
 */
const ZUtils = {
    /**
     * Fetch wrapper con manejo de errores
     */
    async apiFetch(endpoint, options = {}) {
        const url = `${ZARIS_CONFIG.API_BUC}${endpoint}`;
        const session = JSON.parse(localStorage.getItem('zaris_session') || 'null');
        const token = session?.access_token;
        const defaults = {
            headers: {
                'Content-Type': 'application/json',
                ...(token ? { 'Authorization': `Bearer ${token}` } : {})
            }
        };
        const config = { ...defaults, ...options, headers: { ...defaults.headers, ...(options.headers || {}) } };

        try {
            const response = await fetch(url, config);
            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || `Error ${response.status}`);
            }
            return await response.json();
        } catch (err) {
            console.error(`[ZARIS API] ${err.message}`, { url, options });
            throw err;
        }
    },

    /**
     * Muestra una notificación toast
     */
    toast(message, type = 'success', duration = 4000) {
        let container = document.querySelector('.z-toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'z-toast-container';
            document.body.appendChild(container);
        }

        const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
        const toast = document.createElement('div');
        toast.className = `z-toast z-toast--${type}`;
        toast.innerHTML = `
            <span class="z-toast__icon">${icons[type] || icons.info}</span>
            <span class="z-toast__message">${message}</span>
        `;
        container.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(40px)';
            toast.style.transition = 'all 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    },

    /**
     * Muestra modal de confirmación
     */
    confirm(title, message) {
        return new Promise((resolve) => {
            const overlay = document.createElement('div');
            overlay.className = 'z-modal-overlay active';
            overlay.innerHTML = `
                <div class="z-modal">
                    <div class="z-modal__header">
                        <h3 class="z-modal__title">${title}</h3>
                        <button class="z-modal__close" data-action="cancel">&times;</button>
                    </div>
                    <div class="z-modal__body">
                        <p>${message}</p>
                    </div>
                    <div class="z-modal__footer">
                        <button class="z-btn z-btn--ghost" data-action="cancel">No, continuar</button>
                        <button class="z-btn z-btn--primary" data-action="confirm">Sí, salir</button>
                    </div>
                </div>
            `;
            document.body.appendChild(overlay);

            overlay.addEventListener('click', (e) => {
                const action = e.target.dataset.action;
                if (action === 'confirm') {
                    resolve(true);
                    overlay.remove();
                } else if (action === 'cancel' || e.target === overlay) {
                    resolve(false);
                    overlay.remove();
                }
            });
        });
    },

    /**
     * Modal post-guardado: OK (nueva alta) o Salir (volver al menú)
     * onOk: función a llamar cuando elige "OK"
     * onSalir: función a llamar cuando elige "Salir" (default: ir a menu.html)
     */
    modalGuardado(titulo, detalle, onOk, onSalir) {
        const overlay = document.createElement('div');
        overlay.className = 'z-modal-overlay active';
        overlay.innerHTML = `
            <div class="z-modal" style="max-width:420px;">
                <div class="z-modal__header" style="background:linear-gradient(135deg,#1B5E20,#2E7D32);color:#fff;border-radius:12px 12px 0 0;">
                    <h3 class="z-modal__title" style="color:#fff;">✅ ${titulo}</h3>
                </div>
                <div class="z-modal__body" style="text-align:center;padding:1.5rem 2rem;">
                    <p style="font-size:1rem;color:var(--z-text);margin-bottom:0.3rem;">${detalle}</p>
                    <p style="font-size:0.85rem;color:var(--z-text2);">¿Qué desea hacer a continuación?</p>
                </div>
                <div class="z-modal__footer" style="justify-content:center;gap:1rem;">
                    <button class="z-btn z-btn--ghost z-btn--lg" data-action="salir">↗ Salir al Menú</button>
                    <button class="z-btn z-btn--primary z-btn--lg" data-action="ok">✚ Nueva Alta</button>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);
        overlay.addEventListener('click', (e) => {
            const action = e.target.closest('[data-action]')?.dataset.action;
            if (action === 'ok') {
                overlay.remove();
                if (onOk) onOk();
            } else if (action === 'salir' || e.target === overlay) {
                overlay.remove();
                if (onSalir) onSalir(); else window.location.href = 'menu.html';
            }
        });
    },

    /**
     * Verificar duplicado vía API
     * entidad: 'ciudadanos' | 'empresas'
     * campo: 'email' | 'telefono' | 'cuil' | 'cuit' | 'doc_nro'
     * valor: valor a verificar
     * excluirId: ID a excluir (para edición)
     * Retorna objeto {existe, id, nombre} o {existe: false}
     */
    async verificarDuplicado(entidad, campo, valor, excluirId = null) {
        if (!valor || valor.trim() === '') return { existe: false };
        try {
            let url = `/ciudadanos/verificar-duplicado`;
            if (entidad === 'empresas') url = `/empresas/verificar-duplicado`;
            let qs = `campo=${campo}&valor=${encodeURIComponent(valor)}`;
            if (excluirId) qs += `&excluir_id=${excluirId}`;
            return await ZUtils.apiFetch(`${url}?${qs}`);
        } catch {
            return { existe: false };
        }
    },

    /**
     * Poblar un <select> con opciones
     */
    populateSelect(selectEl, options, valueProp = 'value', labelProp = 'label', placeholder = 'Seleccionar...') {
        selectEl.innerHTML = `<option value="">${placeholder}</option>`;
        options.forEach(opt => {
            const option = document.createElement('option');
            option.value = typeof opt === 'object' ? opt[valueProp] : opt;
            option.textContent = typeof opt === 'object' ? opt[labelProp] : opt;
            selectEl.appendChild(option);
        });
    },

    /**
     * Formatea fecha a DD/MM/AAAA
     */
    formatDate(dateStr) {
        if (!dateStr) return '';
        const d = new Date(dateStr);
        return d.toLocaleDateString('es-AR');
    }
};
