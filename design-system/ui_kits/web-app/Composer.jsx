const Composer = ({ onSend }) => {
  const [val, setVal] = React.useState('');
  const [mode, setMode] = React.useState('edit');
  const send = () => { if (!val.trim()) return; onSend(val); setVal(''); };
  return (
    <div style={{
      background: '#f2f1ed', borderRadius: 10,
      boxShadow: 'rgba(0,0,0,.02) 0 0 16px, rgba(0,0,0,.008) 0 0 8px, 0 0 0 1px rgba(38,37,30,.1)',
      padding: 14, display: 'flex', flexDirection: 'column', gap: 10,
    }}>
      <textarea
        value={val}
        onChange={e => setVal(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) send(); }}
        placeholder="Describe the change. The composer will plan, grep, read, and edit."
        style={{
          fontFamily: 'var(--font-display)', fontSize: 15, lineHeight: 1.5, color: '#26251e',
          background: 'transparent', border: 'none', outline: 'none', resize: 'none',
          minHeight: 64, width: '100%', padding: 0,
        }}
      />
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
        <div style={{ display: 'flex', gap: 6 }}>
          <ZPill active={mode === 'edit'} onClick={() => setMode('edit')}>edit</ZPill>
          <ZPill active={mode === 'ask'} onClick={() => setMode('ask')}>ask</ZPill>
          <ZPill active={mode === 'plan'} onClick={() => setMode('plan')}>plan</ZPill>
          <ZPill>@ mention</ZPill>
          <ZPill>/ file</ZPill>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10.5, color: 'rgba(38,37,30,.55)' }}>⌘ ↵</span>
          <ZBtn variant="primary" icon={<Icon name="send" size={13} />} onClick={send}>Send</ZBtn>
        </div>
      </div>
    </div>
  );
};

Object.assign(window, { Composer });
