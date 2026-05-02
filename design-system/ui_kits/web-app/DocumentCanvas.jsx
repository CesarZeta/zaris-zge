const DocumentCanvas = ({ children }) => (
  <div style={{
    background: '#f7f7f4', borderRadius: 10,
    boxShadow: '0 0 0 1px rgba(38,37,30,.1)',
    padding: '28px 36px', minHeight: 220,
    display: 'flex', flexDirection: 'column', gap: 14,
  }}>
    <div style={{ fontFamily: 'var(--font-system)', fontSize: 10.5, letterSpacing: '.05em', textTransform: 'uppercase', color: 'rgba(38,37,30,.55)', fontWeight: 500 }}>Hero · draft</div>
    <h1 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 44, lineHeight: 1.1, letterSpacing: '-1.3px', color: '#26251e', fontWeight: 400 }}>Ship the thing you meant to make.</h1>
    <p style={{ margin: 0, fontFamily: 'var(--font-serif)', fontSize: 17.28, lineHeight: 1.5, fontWeight: 400, color: 'rgba(38,37,30,.55)', fontFeatureSettings: "'ss01' on" }}>
      ZARIS is a workspace for web apps, not a form-builder with opinions. Start a project, describe the change, and watch the composer plan, grep, read, and edit on your behalf — without losing the cursor.
    </p>
    <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
      <ZBtn variant="primary">Start a project</ZBtn>
      <ZBtn variant="surface" icon={<Icon name="arrow" size={13} />}>Read the docs</ZBtn>
    </div>
    {children}
  </div>
);

const ProjectCard = ({ name, meta, status }) => (
  <ZCard variant="ring" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 8, cursor: 'pointer' }}>
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <Icon name="folder" size={16} style={{ color: 'rgba(38,37,30,.55)' }}/>
      <ZBadge color={status === 'live' ? 'success' : status === 'draft' ? 'warn' : 'neutral'} dot={status === 'live'}>{status}</ZBadge>
    </div>
    <div style={{ fontFamily: 'var(--font-display)', fontSize: 17, letterSpacing: '-0.15px', color: '#26251e', fontWeight: 500 }}>{name}</div>
    <div style={{ fontFamily: 'var(--font-serif)', fontSize: 13.5, color: 'rgba(38,37,30,.55)', lineHeight: 1.4 }}>{meta}</div>
  </ZCard>
);

Object.assign(window, { DocumentCanvas, ProjectCard });
