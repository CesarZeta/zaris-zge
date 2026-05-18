// ZARIS Shell — acordeón de navegación + datos de sesión

(async function () {

  // ── API base (se usa para identidad y refresh de modulos_permitidos) ──
  const _local = ['localhost', '127.0.0.1', '0.0.0.0'];
  const API = _local.includes(window.location.hostname)
    ? 'http://127.0.0.1:8000'
    : 'https://zaris-api-production-bf0b.up.railway.app';

  // ── Sesión ──────────────────────────────────────────────────
  const session = JSON.parse(localStorage.getItem('zaris_session') || 'null');
  let user      = session?.user;

  // Si la sesion fue cargada antes del feature de permisos por modulo
  // (sin modulos_permitidos), refresheamos contra /auth/me. Asi un usuario
  // logueado desde antes del deploy ve el sidebar filtrado sin re-loguear.
  if (user && !Array.isArray(user.modulos_permitidos)) {
    try {
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
    // Soporta el sidebar plano nuevo (.nav-flat__item) y el legacy (.nav__link).
    // Para items con data-modulo-fallback (ej OT: ot_supervisor con fallback a
    // ot_agente/ot_auditoria) basta con que CUALQUIERA de los códigos esté
    // permitido para mostrar el item.
    document.querySelectorAll('.nav-flat__item[data-modulo], .nav__link[data-modulo]').forEach(link => {
      const principal = link.dataset.modulo;
      const fallback = (link.dataset.moduloFallback || '').split(',').map(s => s.trim()).filter(Boolean);
      const todos = [principal, ...fallback];
      const algunoPermitido = todos.some(m => modulosPermitidos.has(m));
      if (!algunoPermitido) link.hidden = true;
    });
    // Legacy: ocultar grupos vacios del sidebar viejo
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
    if (frame) frame.src = url || 'web-app/dist/index.html#/dashboard';
  };

  // Handler para links del sidebar plano (nav-flat__item) y legacy (nav__link).
  document.querySelectorAll('.nav-flat__item[href], .nav__link[href]').forEach(link => {
    link.addEventListener('click', function (e) {
      e.preventDefault();
      document.querySelectorAll('.nav-flat__item, .nav__link').forEach(l => l.classList.remove('active'));
      link.classList.add('active');
      window.shellNavigate(link.getAttribute('href'));
    });
  });

  // ── Identidad del topbar (nombre/logo municipio) ──
  // GET /api/v1/config/identidad es publico. Cualquier valor que falle queda
  // con los defaults del HTML. El nombre de la app ("GESTION ESTADO") es
  // hardcoded del producto, no editable por usuario.
  (async function cargarIdentidad() {
    try {
      const res = await fetch(`${API}/api/v1/config/identidad`);
      if (!res.ok) return;
      const data = await res.json();
      const muniNombreEl = document.getElementById('topbar-muni-nombre');
      const muniLogoEl = document.getElementById('topbar-muni-logo');
      if (muniNombreEl && data.municipio_nombre) muniNombreEl.textContent = data.municipio_nombre;
      if (muniLogoEl && data.municipio_logo_url) {
        muniLogoEl.src = data.municipio_logo_url;
        muniLogoEl.hidden = false;
        // Si la imagen falla al cargar, la ocultamos para no mostrar el icono roto.
        muniLogoEl.addEventListener('error', () => { muniLogoEl.hidden = true; }, { once: true });
      }
    } catch (e) { /* fail-open: defaults del HTML */ }
  })();

  // ── Campana de notificaciones ─────────────────────────────────
  // Conectada a /api/v1/notificaciones (entregado 2026-05-18).
  // Polling cada 30s. Click en item: marca leida + navega al recurso.
  function _authToken() {
    const s = JSON.parse(localStorage.getItem('zaris_session') || 'null');
    return s?.state?.accessToken ?? s?.access_token ?? null;
  }
  function _authHeaders() {
    const t = _authToken();
    return t ? { 'Authorization': `Bearer ${t}` } : {};
  }
  function _fmtFechaRelativa(iso) {
    const d = new Date(iso);
    const diffMin = Math.round((Date.now() - d.getTime()) / 60000);
    if (diffMin < 1) return 'ahora';
    if (diffMin < 60) return `hace ${diffMin} min`;
    const diffHr = Math.round(diffMin / 60);
    if (diffHr < 24) return `hace ${diffHr} h`;
    return d.toLocaleDateString('es-AR', { day: '2-digit', month: 'short' });
  }
  function _escapeHtml(s) {
    return String(s || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }
  function _renderNotifList(items) {
    const list = document.getElementById('notif-menu-list');
    if (!list) return;
    if (!items || items.length === 0) {
      list.innerHTML = '<p class="notif-menu__empty">Sin notificaciones</p>';
      return;
    }
    list.innerHTML = items.map(n => {
      const cls = n.leida ? 'notif-menu__item' : 'notif-menu__item notif-menu__item--unread';
      const dot = n.leida ? '' : '<span class="notif-menu__dot" aria-label="No leida"></span>';
      const msg = n.mensaje ? `<p class="notif-menu__item-msg">${_escapeHtml(n.mensaje)}</p>` : '';
      return `<button type="button" class="${cls}" data-id="${n.id_notificacion}" data-url="${_escapeHtml(n.url_destino || '')}">
        <div class="notif-menu__item-body">
          <p class="notif-menu__item-title">${_escapeHtml(n.titulo)}</p>
          ${msg}
          <p class="notif-menu__item-date">${_escapeHtml(_fmtFechaRelativa(n.fecha_alta))}</p>
        </div>
        ${dot}
      </button>`;
    }).join('');
    // Bind click handlers (event delegation seria mas limpia pero esto es chico)
    list.querySelectorAll('.notif-menu__item').forEach(btn => {
      btn.addEventListener('click', () => _onClickNotif(parseInt(btn.dataset.id, 10), btn.dataset.url));
    });
  }
  async function _onClickNotif(id, url) {
    try {
      await fetch(`${API}/api/v1/notificaciones/${id}/leer`, { method: 'PATCH', headers: _authHeaders() });
    } catch (e) { /* fail-open */ }
    _closeNotif();
    void _refrescarNotifBadge();
    if (url && url.startsWith('#/')) {
      // Navegar el iframe al bundle React. El shell vanilla mantiene contexto.
      window.shellNavigate(`web-app/dist/index.html${url}`);
    }
  }
  async function _refrescarNotifBadge() {
    const badge = document.getElementById('topbar-bell-badge');
    if (!badge || !_authToken()) return;
    try {
      const res = await fetch(`${API}/api/v1/notificaciones/count`, { headers: _authHeaders() });
      if (!res.ok) { badge.hidden = true; return; }
      const data = await res.json();
      const n = data?.no_leidas ?? 0;
      if (n > 0) {
        badge.textContent = n > 9 ? '9+' : String(n);
        badge.hidden = false;
      } else {
        badge.hidden = true;
      }
    } catch (e) { /* fail-open: dejar oculto */ }
  }
  async function _cargarNotifLista() {
    const list = document.getElementById('notif-menu-list');
    if (!list || !_authToken()) return;
    list.innerHTML = '<p class="notif-menu__empty">Cargando…</p>';
    try {
      const res = await fetch(`${API}/api/v1/notificaciones?limit=20`, { headers: _authHeaders() });
      if (!res.ok) { list.innerHTML = '<p class="notif-menu__empty">Error al cargar</p>'; return; }
      const data = await res.json();
      _renderNotifList(data?.items || []);
    } catch (e) {
      list.innerHTML = '<p class="notif-menu__empty">Sin conexion</p>';
    }
  }
  function _openNotif() {
    const dd = document.getElementById('notif-menu-dropdown');
    const bell = document.getElementById('topbar-bell');
    if (!dd) return;
    dd.hidden = false;
    if (bell) bell.setAttribute('aria-expanded', 'true');
    void _cargarNotifLista();
  }
  function _closeNotif() {
    const dd = document.getElementById('notif-menu-dropdown');
    const bell = document.getElementById('topbar-bell');
    if (!dd) return;
    dd.hidden = true;
    if (bell) bell.setAttribute('aria-expanded', 'false');
  }
  (function _initNotif() {
    const bell = document.getElementById('topbar-bell');
    const dd = document.getElementById('notif-menu-dropdown');
    const markAll = document.getElementById('notif-menu-mark-all');
    if (!bell || !dd) return;

    bell.addEventListener('click', function (e) {
      e.stopPropagation();
      dd.hidden ? _openNotif() : _closeNotif();
    });
    document.addEventListener('click', function (e) {
      if (!dd.hidden && !dd.contains(e.target) && e.target !== bell && !bell.contains(e.target)) {
        _closeNotif();
      }
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !dd.hidden) _closeNotif();
    });
    if (markAll) {
      markAll.addEventListener('click', async function (e) {
        e.stopPropagation();
        try {
          await fetch(`${API}/api/v1/notificaciones/leer-todas`, { method: 'PATCH', headers: _authHeaders() });
          void _refrescarNotifBadge();
          void _cargarNotifLista();
        } catch (err) { /* fail-open */ }
      });
    }

    // Polling de badge cada 30s. Tambien refrescar al volver de background.
    void _refrescarNotifBadge();
    setInterval(_refrescarNotifBadge, 30000);
    document.addEventListener('visibilitychange', function () {
      if (!document.hidden) void _refrescarNotifBadge();
    });
  })();

  // ── Reloj del topbar ──────────────────────────────────────────
  // Formato "mar 13 may, 14:32". Refresca cada 30s (granularidad de minuto).
  const MESES = ['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'];
  const DIAS  = ['dom','lun','mar','mié','jue','vie','sáb'];
  function _fmtFechaHora(d) {
    const dia  = DIAS[d.getDay()];
    const num  = d.getDate();
    const mes  = MESES[d.getMonth()];
    const hh   = String(d.getHours()).padStart(2, '0');
    const mm   = String(d.getMinutes()).padStart(2, '0');
    return `${dia} ${num} ${mes}, ${hh}:${mm}`;
  }
  function _refrescarReloj() {
    const el = document.getElementById('topbar-clock');
    if (!el) return;
    const d = new Date();
    el.textContent = _fmtFechaHora(d);
    el.setAttribute('datetime', d.toISOString());
  }
  _refrescarReloj();
  setInterval(_refrescarReloj, 30000);

  // ── Auto-cargar módulo desde ?modulo=<ruta> ───────────────────
  // Permite que un acceso standalone (vanilla o bundle React) sea
  // redirigido al shell con ?modulo=<ruta> y aterrice con la sidebar visible.
  // La whitelist acepta:
  //   - frontend/<nombre>.html(?...)?
  //   - web-app/dist/index.html(#/...)?
  // y evita open redirects rechazando cualquier otro path.
  try {
    const params = new URLSearchParams(window.location.search);
    const mod = params.get('modulo');
    const isVanilla = /^frontend\/[a-z0-9_-]+\.html(\?.*)?$/i.test(mod || '');
    const isReact   = /^web-app\/dist\/index\.html(#\/.*)?$/i.test(mod || '');
    if (mod && (isVanilla || isReact)) {
      const frame = document.getElementById('module-frame');
      if (frame) frame.src = mod;
      // Marcar el nav-link correspondiente como activo si existe.
      // Para vanilla compara sin la query; para React sin el hash.
      const linkPath = mod.split('?')[0].split('#')[0];
      const linkFull = mod.split('?')[0];                      // vanilla con query
      document.querySelectorAll('.nav-flat__item[href], .nav__link[href]').forEach(l => {
        const href = l.getAttribute('href') || '';
        if (href === mod || href === linkFull || href === linkPath) l.classList.add('active');
      });
    }
  } catch (e) { /* ignorar */ }

})();
