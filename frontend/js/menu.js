// ZARIS Shell — acordeón de navegación + datos de sesión

(async function () {

  // ── Sesión ──────────────────────────────────────────────────
  const session = JSON.parse(localStorage.getItem('zaris_session') || 'null');
  let user      = session?.user;

  // Si la sesion fue cargada antes del feature de permisos por modulo
  // (sin modulos_permitidos), refresheamos contra /auth/me. Asi un usuario
  // logueado desde antes del deploy ve el sidebar filtrado sin re-loguear.
  if (user && !Array.isArray(user.modulos_permitidos)) {
    try {
      const _local = ['localhost', '127.0.0.1', '0.0.0.0'];
      const API = _local.includes(window.location.hostname)
        ? 'http://127.0.0.1:8000'
        : 'https://zaris-api-production-bf0b.up.railway.app';
      const token = session?.access_token || session?.state?.accessToken;
      if (token) {
        const res = await fetch(`${API}/api/v1/auth/me`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });
        if (res.ok) {
          const me = await res.json();
          if (Array.isArray(me.modulos_permitidos)) {
            user = { ...user, modulos_permitidos: me.modulos_permitidos };
            // Persistir mantiene ambas shapes (§29)
            const updated = {
              ...(session || {}),
              user,
              state: { ...(session?.state || {}), user },
            };
            localStorage.setItem('zaris_session', JSON.stringify(updated));
          }
        }
      }
    } catch (e) { /* fail-open: si no responde, no filtro */ }
  }

  const avatarEl  = document.getElementById('topbar-avatar');
  const contextEl = document.getElementById('topbar-context');
  const infoEl    = document.getElementById('user-menu-info');

  const NIVELES = { 1: 'Administrador', 2: 'Supervisor', 3: 'Operador', 4: 'Consultor' };

  if (user) {
    const name     = user.nombre || user.username || '';
    const initials = name.split(' ').slice(0, 2).map(w => w[0] || '').join('').toUpperCase() || 'ZG';
    const nivel    = NIVELES[user.nivel_acceso] || 'Usuario';

    if (avatarEl)  avatarEl.textContent = initials;
    if (contextEl) contextEl.innerHTML  = `<strong>${name.split(' ')[0]}</strong> · ${nivel}`;
    if (infoEl)    infoEl.innerHTML     = `
      <div class="user-menu__info-name">${name}</div>
      <div class="user-menu__info-role">${nivel}</div>`;
  }

  // ── User menu dropdown ──────────────────────────────────────
  const trigger  = document.getElementById('user-menu-trigger');
  const dropdown = document.getElementById('user-menu-dropdown');
  const btnLogout = document.getElementById('btn-logout');

  function openMenu()  { dropdown.hidden = false; trigger.setAttribute('aria-expanded', 'true'); }
  function closeMenu() { dropdown.hidden = true;  trigger.setAttribute('aria-expanded', 'false'); }

  if (trigger) {
    trigger.addEventListener('click', function (e) {
      e.stopPropagation();
      dropdown.hidden ? openMenu() : closeMenu();
    });
  }

  document.addEventListener('click', function (e) {
    if (dropdown && !dropdown.hidden && !dropdown.contains(e.target) && e.target !== trigger) {
      closeMenu();
    }
  });

  if (btnLogout) {
    btnLogout.addEventListener('click', function () {
      localStorage.removeItem('zaris_session');
      window.location.replace('frontend/login.html');
    });
  }

  // ── Acordeón ─────────────────────────────────────────────────
  document.querySelectorAll('[data-toggle]').forEach(btn => {
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      const type   = btn.dataset.toggle;
      const parent = type === 'group'
        ? btn.closest('.nav__group')
        : btn.closest('.nav__item');
      if (!parent) return;
      const isOpen = parent.dataset.open === 'true';
      parent.dataset.open = isOpen ? 'false' : 'true';
      btn.setAttribute('aria-expanded', String(!isOpen));
    });
  });

  // ── Filtrado de modulos por permisos (CLAUDE.md §30) ─────────
  // user.modulos_permitidos viene de /auth/login y /auth/me. Si el usuario
  // tiene una sesion antigua sin ese campo, no filtramos (fail-open en UI;
  // el guard real esta en el backend con `require_modulo`).
  const modulosPermitidos = Array.isArray(user?.modulos_permitidos)
    ? new Set(user.modulos_permitidos)
    : null;

  if (modulosPermitidos) {
    document.querySelectorAll('.nav__link[data-modulo]').forEach(link => {
      if (!modulosPermitidos.has(link.dataset.modulo)) {
        link.hidden = true;
      }
    });
    // Ocultar grupos que quedaron sin links visibles
    document.querySelectorAll('.nav__panel, .nav__subpanel').forEach(panel => {
      const visible = panel.querySelectorAll('.nav__link:not([hidden])').length;
      if (visible === 0) {
        const group = panel.closest('.nav__group');
        if (group) group.hidden = true;
      }
    });
  }

  // ── Shell navigation (iframe) ─────────────────────────────────
  window.shellNavigate = function (url) {
    const frame = document.getElementById('module-frame');
    if (frame) frame.src = url || 'frontend/welcome.html';
  };

  document.querySelectorAll('.nav__link[href]').forEach(link => {
    link.addEventListener('click', function (e) {
      e.preventDefault();
      document.querySelectorAll('.nav__link').forEach(l => l.classList.remove('active'));
      link.classList.add('active');
      window.shellNavigate(link.href);
    });
  });

  // ── Auto-cargar módulo desde ?modulo=<ruta> ───────────────────
  // Permite que un acceso standalone (ej: frontend/ot_supervisor.html) sea
  // redirigido al shell con ?modulo=frontend/ot_supervisor.html y aterrice
  // con la sidebar visible. La whitelist evita open redirects.
  try {
    const params = new URLSearchParams(window.location.search);
    const mod = params.get('modulo');
    if (mod && /^frontend\/[a-z0-9_-]+\.html(\?.*)?$/i.test(mod)) {
      const frame = document.getElementById('module-frame');
      if (frame) frame.src = mod;
      // Marcar el nav-link correspondiente como activo si existe
      const linkPath = mod.split('?')[0];
      document.querySelectorAll('.nav__link[href]').forEach(l => {
        if (l.getAttribute('href') === linkPath) l.classList.add('active');
      });
    }
  } catch (e) { /* ignorar */ }

})();
