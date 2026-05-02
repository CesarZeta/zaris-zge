const Timeline = ({ steps }) => (
  <div style={{ position: 'relative', paddingLeft: 26, display: 'flex', flexDirection: 'column', gap: 14 }}>
    <div style={{ position: 'absolute', left: 7, top: 10, bottom: 10, width: 1.5, background: 'rgba(38,37,30,.1)' }} />
    {steps.map((s, i) => {
      const colors = { thinking: '#dfa88f', grep: '#9fc9a2', read: '#9fbbe0', edit: '#c0a8dd' };
      return (
        <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 14, position: 'relative' }}>
          <span style={{
            position: 'absolute', left: -26, top: 4,
            width: 14, height: 14, borderRadius: 9999,
            background: colors[s.kind], boxShadow: '0 0 0 3px #f2f1ed',
          }} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            <span style={{ fontFamily: 'var(--font-system)', fontSize: 11, letterSpacing: '.05em', textTransform: 'uppercase', color: 'rgba(38,37,30,.55)', fontWeight: 500 }}>{s.kind}</span>
            <span style={{ fontFamily: 'var(--font-display)', fontSize: 14.5, color: '#26251e', lineHeight: 1.4 }}>{s.label}</span>
            {s.detail && <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5, color: 'rgba(38,37,30,.55)', marginTop: 2 }}>{s.detail}</span>}
          </div>
        </div>
      );
    })}
  </div>
);

Object.assign(window, { Timeline });
