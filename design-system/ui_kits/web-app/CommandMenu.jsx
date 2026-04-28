const CommandMenu = ({ open, onClose }) => {
  if (!open) return null;
  const items = [
    { icon: 'plus',     kind: 'Create', label: 'New project', hint: '⌘ N' },
    { icon: 'file',     kind: 'Create', label: 'New document', hint: '⌘ ⇧ N' },
    { icon: 'sparkles', kind: 'Go',     label: 'Open composer', hint: '⌘ K' },
    { icon: 'layers',   kind: 'Go',     label: 'View timeline', hint: '⌘ T' },
    { icon: 'settings', kind: 'Go',     label: 'Settings', hint: '⌘ ,' },
    { icon: 'zap',      kind: 'Action', label: 'Deploy current project' },
  ];
  return (
    <div onClick={onClose} style={{
      position: 'absolute', inset: 0, background: 'rgba(38,37,30,.22)',
      display: 'flex', alignItems: 'flex-start', justifyContent: 'center',
      paddingTop: 110, zIndex: 50,
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        width: 540, background: '#f2f1ed', borderRadius: 10,
        boxShadow: 'rgba(0,0,0,.14) 0 28px 70px, rgba(0,0,0,.1) 0 14px 32px, 0 0 0 1px rgba(38,37,30,.1)',
        overflow: 'hidden',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '14px 18px', borderBottom: '1px solid rgba(38,37,30,.1)' }}>
          <Icon name="search" size={15} style={{ color: 'rgba(38,37,30,.55)' }}/>
          <input autoFocus placeholder="Search or run command..." style={{ flex: 1, border: 'none', background: 'transparent', outline: 'none', fontFamily: 'var(--font-display)', fontSize: 15, color: '#26251e' }}/>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, color: 'rgba(38,37,30,.55)', background: '#ebeae5', padding: '2px 6px', borderRadius: 3 }}>esc</span>
        </div>
        <div style={{ padding: 8, display: 'flex', flexDirection: 'column', gap: 2, maxHeight: 340, overflow: 'auto' }}>
          {items.map((it, i) => (
            <button key={i} style={{
              display: 'flex', alignItems: 'center', gap: 12, padding: '9px 10px', borderRadius: 6,
              background: i === 0 ? 'rgba(38,37,30,.06)' : 'transparent', border: 'none', cursor: 'pointer',
              textAlign: 'left', fontFamily: 'var(--font-display)', color: '#26251e',
            }}>
              <Icon name={it.icon} size={14} style={{ color: 'rgba(38,37,30,.55)' }}/>
              <span style={{ fontFamily: 'var(--font-system)', fontSize: 10.5, letterSpacing: '.05em', textTransform: 'uppercase', color: 'rgba(38,37,30,.55)', minWidth: 52 }}>{it.kind}</span>
              <span style={{ flex: 1, fontSize: 14 }}>{it.label}</span>
              {it.hint && <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, color: 'rgba(38,37,30,.55)' }}>{it.hint}</span>}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};

Object.assign(window, { CommandMenu });
