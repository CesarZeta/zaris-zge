const MBtn = ({ variant = 'primary', children, onClick, ...rest }) => {
  const base = { fontFamily: 'var(--font-display)', fontSize: 14, lineHeight: 1, fontWeight: 400, padding: '11px 16px', borderRadius: 8, border: 'none', cursor: 'pointer', transition: 'color .15s, background .15s' };
  const v = {
    primary: { background: '#26251e', color: '#f2f1ed' },
    surface: { background: '#ebeae5', color: '#26251e', boxShadow: '0 0 0 1px rgba(38,37,30,.1)' },
    accent:  { background: '#f54e00', color: '#f2f1ed' },
    link:    { background: 'transparent', color: '#f54e00', padding: 0, textDecoration: 'none' },
  }[variant];
  const [h, sh] = React.useState(false);
  const hoverC = variant === 'primary' ? null : variant === 'accent' ? null : '#cf2d56';
  const hoverBg = variant === 'primary' ? '#1b1a15' : variant === 'accent' ? '#d84300' : null;
  return <button onMouseEnter={() => sh(true)} onMouseLeave={() => sh(false)} onClick={onClick} style={{ ...base, ...v, ...(h && hoverC ? { color: hoverC } : {}), ...(h && hoverBg ? { background: hoverBg } : {}) }} {...rest}>{children}</button>;
};

const MSection = ({ children, bg = '#f2f1ed', style }) => (
  <section style={{ background: bg, padding: '80px 32px', ...style }}>
    <div style={{ maxWidth: 1140, margin: '0 auto' }}>{children}</div>
  </section>
);

const MIcon = ({ name, size = 18 }) => {
  const p = {
    sparkles: <g><path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M5.6 18.4l2.8-2.8M15.6 8.4l2.8-2.8"/></g>,
    layers: <g><path d="m12 2 10 6-10 6-10-6z"/><path d="m2 16 10 6 10-6"/></g>,
    zap: <path d="m13 2-9 12h7l-1 8 9-12h-7z"/>,
    arrow: <path d="M5 12h14M13 5l7 7-7 7"/>,
    check: <path d="M20 6 9 17l-5-5"/>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">{p[name]}</svg>;
};

Object.assign(window, { MBtn, MSection, MIcon });
