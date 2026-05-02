const Footer = () => {
  const cols = [
    { h: 'Product',   l: ['Composer', 'Timeline', 'Projects', 'Changelog'] },
    { h: 'Resources', l: ['Docs', 'Guides', 'API reference', 'Blog'] },
    { h: 'Company',   l: ['About', 'Careers', 'Brand', 'Contact'] },
  ];
  return (
    <footer style={{ background: '#f2f1ed', padding: '64px 32px 32px', borderTop: '1px solid rgba(38,37,30,.1)' }}>
      <div style={{ maxWidth: 1140, margin: '0 auto', display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr', gap: 40 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 22, height: 22, background: '#26251e', borderRadius: 4, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <svg width="11" height="11" viewBox="0 0 28 28"><path d="M6 6h16L8 22h16" stroke="#f2f1ed" strokeWidth="3" fill="none" strokeLinecap="square"/></svg>
            </div>
            <span style={{ fontFamily: 'var(--font-display)', fontSize: 17, fontWeight: 500, letterSpacing: '-0.8px' }}>ZARIS</span>
          </div>
          <p style={{ margin: 0, fontFamily: 'var(--font-serif)', fontSize: 14, lineHeight: 1.5, color: 'rgba(38,37,30,.55)', maxWidth: 300, fontFeatureSettings: "'ss01' on" }}>
            Design for web apps. Made by people who think the editor is the IDE.
          </p>
        </div>
        {cols.map((c, i) => (
          <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div style={{ fontFamily: 'var(--font-system)', fontSize: 10.5, letterSpacing: '.06em', textTransform: 'uppercase', color: 'rgba(38,37,30,.55)', fontWeight: 500 }}>{c.h}</div>
            {c.l.map(x => <a key={x} href="#" style={{ fontFamily: 'var(--font-display)', fontSize: 13.5, color: '#26251e', textDecoration: 'none' }}
              onMouseEnter={e => e.currentTarget.style.color = '#cf2d56'}
              onMouseLeave={e => e.currentTarget.style.color = '#26251e'}>{x}</a>)}
          </div>
        ))}
      </div>
      <div style={{ maxWidth: 1140, margin: '48px auto 0', paddingTop: 24, borderTop: '1px solid rgba(38,37,30,.1)', display: 'flex', justifyContent: 'space-between', fontFamily: 'var(--font-mono)', fontSize: 11.5, color: 'rgba(38,37,30,.55)' }}>
        <span>© 2026 ZARIS · Made with care.</span>
        <span>status · terms · privacy</span>
      </div>
    </footer>
  );
};

Object.assign(window, { Footer });
