// ZARIS Shell — acordeón de navegación + datos de sesión

(function () {

  // ── Sesión ──────────────────────────────────────────────────
  const session = JSON.parse(localStorage.getItem('zaris_session') || 'null');
  const user    = session?.user;

  const avatarEl  = document.querySelector('.topbar__avatar');
  const contextEl = document.querySelector('.topbar__context');

  if (avatarEl) {
    const name = user?.nombre || user?.username || '';
    const initials = name
      .split(' ').slice(0, 2)
      .map(w => w[0] || '').join('').toUpperCase() || 'ZG';
    avatarEl.textContent = initials;
  }

  if (contextEl && user) {
    const nivel = { 1: 'Admin', 2: 'Supervisor', 3: 'Operador', 4: 'Consultor' }[user.nivel_acceso] || 'Usuario';
    const nombre = user.nombre || user.username || 'Usuario';
    contextEl.innerHTML = `<strong>${nombre}</strong> · ${nivel}`;
  }

  // ── Log de acciones ─────────────────────────────────────────
  const log = document.getElementById('log');
  function setLog(text) {
    if (log) log.innerHTML = `<span style="color:var(--fg-1)">${text}</span>`;
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

      const label = btn.querySelector('span')?.textContent?.trim();
      if (label) setLog(`${isOpen ? 'Cerrado' : 'Abierto'}: ${label}`);
    });
  });

  // ── Shell navigation (iframe) ──────────────────────────────────
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
