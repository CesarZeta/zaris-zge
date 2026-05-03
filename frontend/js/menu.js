// ZARIS Shell — acordeón de navegación + datos de sesión

(function () {

  // ── Sesión ──────────────────────────────────────────────────
  const session = JSON.parse(localStorage.getItem('zaris_session') || 'null');
  const user    = session?.user;

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

})();
