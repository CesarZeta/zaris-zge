// Shared primitives for the ZARIS web app UI kit.
// No imports — these become window globals for cross-file use.

const ZBtn = ({ variant = 'surface', children, onClick, style, icon }) => {
  const base = {
    fontFamily: 'var(--font-display)',
    fontSize: 14,
    lineHeight: 1,
    fontWeight: 400,
    padding: '10px 12px 10px 14px',
    borderRadius: 8,
    border: 'none',
    outline: 'none',
    cursor: 'pointer',
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    transition: 'color .15s ease, background .15s ease, box-shadow .2s ease',
  };
  const variants = {
    surface: { background: '#ebeae5', color: '#26251e', boxShadow: '0 0 0 1px rgba(38,37,30,.1)' },
    primary: { background: '#26251e', color: '#f2f1ed' },
    accent:  { background: '#f54e00', color: '#f2f1ed' },
    ghost:   { background: 'rgba(38,37,30,.06)', color: 'rgba(38,37,30,.7)', padding: '6px 12px' },
    pill:    { background: '#e6e5e0', color: 'rgba(38,37,30,.6)', padding: '4px 10px', borderRadius: 9999 },
  };
  const [hover, setHover] = React.useState(false);
  const hoverColor = variant === 'primary' || variant === 'accent' ? null : '#cf2d56';
  return (
    <button
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onClick={onClick}
      style={{ ...base, ...variants[variant], ...(hover && hoverColor ? { color: hoverColor } : {}), ...style }}
    >
      {icon}{children}
    </button>
  );
};

const ZPill = ({ active, children, onClick }) => (
  <button
    onClick={onClick}
    style={{
      fontFamily: 'var(--font-display)',
      fontSize: 13,
      padding: '4px 10px',
      borderRadius: 9999,
      border: 'none',
      cursor: 'pointer',
      background: active ? '#e1e0db' : '#e6e5e0',
      color: active ? 'rgba(38,37,30,.9)' : 'rgba(38,37,30,.6)',
      transition: 'color .15s ease',
    }}
  >{children}</button>
);

const ZBadge = ({ color = 'neutral', dot, children }) => {
  const map = {
    success: { bg: 'rgba(31,138,101,.14)', fg: '#1f8a65', dot: '#1f8a65' },
    error:   { bg: 'rgba(207,45,86,.14)',  fg: '#cf2d56', dot: '#cf2d56' },
    warn:    { bg: 'rgba(192,133,50,.18)', fg: '#c08532', dot: '#c08532' },
    neutral: { bg: '#e6e5e0',              fg: 'rgba(38,37,30,.7)', dot: 'rgba(38,37,30,.55)' },
  }[color];
  return (
    <span style={{ fontFamily: 'var(--font-display)', fontSize: 12, fontWeight: 500, padding: '3px 10px', borderRadius: 9999, background: map.bg, color: map.fg, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      {dot && <span style={{ width: 6, height: 6, borderRadius: 9999, background: map.dot }}/>}
      {children}
    </span>
  );
};

const ZInput = ({ icon, placeholder, value, onChange, style }) => {
  const [focus, setFocus] = React.useState(false);
  return (
    <div style={{ position: 'relative', width: '100%', ...style }}>
      {icon && <span style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'rgba(38,37,30,.55)', pointerEvents: 'none' }}>{icon}</span>}
      <input
        value={value ?? ''}
        onChange={onChange}
        onFocus={() => setFocus(true)}
        onBlur={() => setFocus(false)}
        placeholder={placeholder}
        style={{
          fontFamily: 'var(--font-display)', fontSize: 14, color: '#26251e',
          background: 'transparent',
          padding: icon ? '9px 12px 9px 36px' : '9px 12px',
          border: `1px solid ${focus ? 'rgba(38,37,30,.2)' : 'rgba(38,37,30,.1)'}`,
          borderRadius: 8, outline: 'none', width: '100%', boxSizing: 'border-box',
          boxShadow: focus ? '0 4px 12px rgba(0,0,0,.1)' : 'none',
          transition: 'border-color .15s ease, box-shadow .2s ease',
        }}
      />
    </div>
  );
};

const ZCard = ({ variant = 'ring', children, style, ...rest }) => {
  const shadows = {
    ring:     '0 0 0 1px rgba(38,37,30,.1)',
    ambient:  'rgba(0,0,0,.02) 0 0 16px, rgba(0,0,0,.008) 0 0 8px, 0 0 0 1px rgba(38,37,30,.1)',
    elevated: 'rgba(0,0,0,.14) 0 28px 70px, rgba(0,0,0,.1) 0 14px 32px, 0 0 0 1px rgba(38,37,30,.1)',
  };
  return (
    <div style={{ background: '#e6e5e0', borderRadius: variant === 'elevated' ? 10 : 8, padding: 16, boxShadow: shadows[variant], ...style }} {...rest}>
      {children}
    </div>
  );
};

// Lucide-style stroke icons — inline, currentColor.
const Icon = ({ name, size = 16, style }) => {
  const paths = {
    search: <g><circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/></g>,
    plus: <path d="M12 5v14M5 12h14"/>,
    folder: <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>,
    file: <g><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/></g>,
    command: <path d="M18 3a3 3 0 0 0-3 3v12a3 3 0 0 0 3 3 3 3 0 0 0 3-3 3 3 0 0 0-3-3H6a3 3 0 0 0-3 3 3 3 0 0 0 3 3 3 3 0 0 0 3-3V6a3 3 0 0 0-3-3 3 3 0 0 0-3 3 3 3 0 0 0 3 3h12a3 3 0 0 0 3-3 3 3 0 0 0-3-3z"/>,
    user: <g><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></g>,
    settings: <g><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1A1.7 1.7 0 0 0 4.6 9a1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></g>,
    send: <path d="m22 2-7 20-4-9-9-4z"/>,
    sparkles: <g><path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M5.6 18.4l2.8-2.8M15.6 8.4l2.8-2.8"/></g>,
    arrow: <path d="M5 12h14M13 5l7 7-7 7"/>,
    chevron: <path d="m9 6 6 6-6 6"/>,
    close: <path d="M18 6 6 18M6 6l12 12"/>,
    more: <g><circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/></g>,
    home: <path d="M3 11 12 4l9 7v9a2 2 0 0 1-2 2h-3v-7h-8v7H5a2 2 0 0 1-2-2z"/>,
    layers: <g><path d="m12 2 10 6-10 6-10-6z"/><path d="m2 16 10 6 10-6"/></g>,
    zap: <path d="m13 2-9 12h7l-1 8 9-12h-7z"/>,
  };
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" style={style}>
      {paths[name]}
    </svg>
  );
};

Object.assign(window, { ZBtn, ZPill, ZBadge, ZInput, ZCard, Icon });
