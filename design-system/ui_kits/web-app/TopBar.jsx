const TopBar = ({ onCmdK }) => (
  <header style={{
    height: 52, flexShrink: 0, background: 'rgba(242,241,237,.85)', backdropFilter: 'blur(12px) saturate(1.2)',
    borderBottom: '1px solid rgba(38,37,30,.1)',
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '0 20px', gap: 16,
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontFamily: 'var(--font-display)', fontSize: 13.5 }}>
      <span style={{ color: 'rgba(38,37,30,.55)' }}>Marcus K.</span>
      <Icon name="chevron" size={12} style={{ color: 'rgba(38,37,30,.4)' }} />
      <span style={{ color: 'rgba(38,37,30,.55)' }}>ZARIS landing</span>
      <Icon name="chevron" size={12} style={{ color: 'rgba(38,37,30,.4)' }} />
      <span style={{ color: '#26251e' }}>Hero</span>
      <ZBadge color="warn">draft</ZBadge>
    </div>
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <button onClick={onCmdK} style={{
        display: 'flex', alignItems: 'center', gap: 10,
        background: '#ebeae5', color: 'rgba(38,37,30,.55)',
        fontFamily: 'var(--font-display)', fontSize: 13, border: 'none',
        padding: '6px 8px 6px 12px', borderRadius: 8,
        boxShadow: '0 0 0 1px rgba(38,37,30,.1)', cursor: 'pointer', minWidth: 260,
      }}>
        <Icon name="search" size={13} /> <span style={{ flex: 1, textAlign: 'left' }}>Search or run command</span>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, background: '#e1e0db', padding: '2px 6px', borderRadius: 3 }}>⌘K</span>
      </button>
      <ZBtn variant="surface" icon={<Icon name="plus" size={13} />}>New</ZBtn>
    </div>
  </header>
);

Object.assign(window, { TopBar });
