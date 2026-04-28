const PricingTable = () => {
  const tiers = [
    { name: 'Solo', price: '0', meta: 'free forever', features: ['3 projects', 'Composer + timeline', 'Community support', 'Deploy to zaris.app'], cta: 'Start free', primary: false },
    { name: 'Team', price: '24', meta: 'per seat · monthly', features: ['Unlimited projects', 'Shared workspaces', 'Priority support', 'Custom domains', 'Role-based access'], cta: 'Start a team trial', primary: true },
  ];
  return (
    <MSection bg="#f2f1ed">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 36 }}>
        <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <span style={{ fontFamily: 'var(--font-system)', fontSize: 11, letterSpacing: '.08em', textTransform: 'uppercase', color: 'rgba(38,37,30,.55)', fontWeight: 500 }}>Pricing</span>
          <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 36, lineHeight: 1.2, letterSpacing: '-0.72px', color: '#26251e', fontWeight: 400 }}>Two plans. No upsell theatre.</h2>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 18, maxWidth: 820, margin: '0 auto', width: '100%' }}>
          {tiers.map((t, i) => (
            <article key={i} style={{
              background: t.primary ? '#26251e' : '#e6e5e0',
              color: t.primary ? '#f2f1ed' : '#26251e',
              borderRadius: 10, padding: '28px 28px',
              boxShadow: t.primary
                ? 'rgba(0,0,0,.14) 0 28px 70px, rgba(0,0,0,.1) 0 14px 32px'
                : '0 0 0 1px rgba(38,37,30,.1)',
              display: 'flex', flexDirection: 'column', gap: 18,
            }}>
              <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
                <span style={{ fontFamily: 'var(--font-display)', fontSize: 22, fontWeight: 500, letterSpacing: '-0.11px' }}>{t.name}</span>
                {t.primary && <span style={{ fontFamily: 'var(--font-system)', fontSize: 10.5, letterSpacing: '.06em', textTransform: 'uppercase', color: '#f54e00', fontWeight: 500 }}>Most picked</span>}
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                <span style={{ fontFamily: 'var(--font-display)', fontSize: 56, letterSpacing: '-1.6px', lineHeight: 1, fontWeight: 400 }}>${t.price}</span>
                <span style={{ fontFamily: 'var(--font-serif)', fontSize: 14, opacity: .7, fontStyle: 'italic' }}>{t.meta}</span>
              </div>
              <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 9 }}>
                {t.features.map((f, j) => (
                  <li key={j} style={{ display: 'flex', alignItems: 'center', gap: 10, fontFamily: 'var(--font-serif)', fontSize: 15.5, lineHeight: 1.4, fontFeatureSettings: "'ss01' on" }}>
                    <span style={{ color: t.primary ? '#9fc9a2' : '#1f8a65' }}><MIcon name="check" size={15}/></span>
                    {f}
                  </li>
                ))}
              </ul>
              <button style={{
                marginTop: 'auto',
                fontFamily: 'var(--font-display)', fontSize: 14, padding: '12px 16px', borderRadius: 8, cursor: 'pointer', border: 'none',
                background: t.primary ? '#f54e00' : '#26251e',
                color: '#f2f1ed', transition: 'background .15s',
              }}>{t.cta}</button>
            </article>
          ))}
        </div>
      </div>
    </MSection>
  );
};

Object.assign(window, { PricingTable });
