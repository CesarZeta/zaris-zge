const Nav = () => (
  <nav style={{
    position: 'sticky', top: 0, zIndex: 20,
    background: 'rgba(242,241,237,.82)', backdropFilter: 'blur(12px) saturate(1.2)',
    borderBottom: '1px solid rgba(38,37,30,.1)',
    padding: '14px 32px',
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 36 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{ width: 24, height: 24, background: '#26251e', borderRadius: 5, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <svg width="12" height="12" viewBox="0 0 28 28"><path d="M6 6h16L8 22h16" stroke="#f2f1ed" strokeWidth="3" fill="none" strokeLinecap="square"/></svg>
        </div>
        <span style={{ fontFamily: 'var(--font-display)', fontSize: 18, fontWeight: 500, letterSpacing: '-0.9px', color: '#26251e' }}>ZARIS</span>
      </div>
      <div style={{ display: 'flex', gap: 22 }}>
        {['docs', 'pricing', 'changelog', 'blog'].map(l => (
          <a key={l} href="#" style={{ fontFamily: 'var(--font-system)', fontSize: 13.5, fontWeight: 500, color: 'rgba(38,37,30,.7)', textDecoration: 'none' }}
             onMouseEnter={e => e.currentTarget.style.color = '#cf2d56'}
             onMouseLeave={e => e.currentTarget.style.color = 'rgba(38,37,30,.7)'}>{l}</a>
        ))}
      </div>
    </div>
    <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
      <a href="#" style={{ fontFamily: 'var(--font-system)', fontSize: 13.5, fontWeight: 500, color: 'rgba(38,37,30,.7)', textDecoration: 'none' }}>Sign in</a>
      <MBtn variant="surface">Open app</MBtn>
    </div>
  </nav>
);

Object.assign(window, { Nav });
