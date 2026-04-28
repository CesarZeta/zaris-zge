const Sidebar = ({ activeView, onView }) => {
  const items = [
    { id: 'home', label: 'Home', icon: 'home' },
    { id: 'projects', label: 'Projects', icon: 'folder' },
    { id: 'composer', label: 'Composer', icon: 'sparkles' },
    { id: 'timeline', label: 'Timeline', icon: 'layers' },
    { id: 'settings', label: 'Settings', icon: 'settings' },
  ];
  const projects = ['ZARIS landing', 'Acme dashboard', 'Docs rewrite'];
  return (
    <aside style={{
      width: 232, background: '#ebeae5', borderRight: '1px solid rgba(38,37,30,.1)',
      display: 'flex', flexDirection: 'column', padding: '20px 14px', gap: 20,
      fontFamily: 'var(--font-display)', flexShrink: 0,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '0 6px' }}>
        <div style={{ width: 26, height: 26, background: '#26251e', borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <svg width="13" height="13" viewBox="0 0 28 28"><path d="M6 6h16L8 22h16" stroke="#f2f1ed" strokeWidth="3" fill="none" strokeLinecap="square"/></svg>
        </div>
        <span style={{ fontSize: 17, fontWeight: 500, letterSpacing: '-0.8px', color: '#26251e' }}>ZARIS</span>
      </div>

      <nav style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {items.map(it => (
          <button key={it.id} onClick={() => onView(it.id)}
            style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '7px 10px', borderRadius: 6, border: 'none',
              background: activeView === it.id ? 'rgba(38,37,30,.08)' : 'transparent',
              color: activeView === it.id ? '#26251e' : 'rgba(38,37,30,.7)',
              fontFamily: 'var(--font-display)', fontSize: 13.5, cursor: 'pointer',
              textAlign: 'left',
            }}>
            <Icon name={it.icon} size={15} />
            {it.label}
          </button>
        ))}
      </nav>

      <div style={{ borderTop: '1px solid rgba(38,37,30,.1)', paddingTop: 14, display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div style={{ fontFamily: 'var(--font-system)', fontSize: 10.5, letterSpacing: '.05em', textTransform: 'uppercase', color: 'rgba(38,37,30,.55)', padding: '2px 6px' }}>Projects</div>
        {projects.map(p => (
          <button key={p} style={{
            fontFamily: 'var(--font-display)', fontSize: 13, textAlign: 'left',
            padding: '5px 10px', borderRadius: 5, background: 'transparent', border: 'none',
            color: 'rgba(38,37,30,.7)', cursor: 'pointer',
          }}>{p}</button>
        ))}
      </div>

      <div style={{ marginTop: 'auto', display: 'flex', alignItems: 'center', gap: 10, padding: '8px 6px', borderTop: '1px solid rgba(38,37,30,.1)' }}>
        <div style={{ width: 26, height: 26, borderRadius: 9999, background: '#dfa88f', display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: 'var(--font-display)', fontSize: 12, color: '#26251e', fontWeight: 500 }}>MK</div>
        <div style={{ display: 'flex', flexDirection: 'column', lineHeight: 1.15 }}>
          <span style={{ fontSize: 12.5, color: '#26251e' }}>Marcus K.</span>
          <span style={{ fontSize: 10.5, color: 'rgba(38,37,30,.55)', fontFamily: 'var(--font-mono)' }}>Pro · team</span>
        </div>
      </div>
    </aside>
  );
};

Object.assign(window, { Sidebar });
