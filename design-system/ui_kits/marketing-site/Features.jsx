const Features = () => {
  const items = [
    { icon: 'sparkles', title: 'A composer that plans',    body: "Describe the change. ZARIS decomposes it into atomic edits — plan, grep, read, edit — so you review, not reinvent." },
    { icon: 'layers',   title: 'Timeline, not a transcript', body: "Every AI operation is a typed step: Thinking, Grep, Read, Edit. Skim the timeline; rewind to any step; diff what changed." },
    { icon: 'zap',      title: 'Ship from the editor',     body: "Preview, commit, and deploy without leaving the canvas. Not everything needs AI — the cursor still belongs to you." },
  ];
  return (
    <MSection bg="#ebeae5">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 44 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14, maxWidth: 680 }}>
          <span style={{ fontFamily: 'var(--font-system)', fontSize: 11, letterSpacing: '.08em', textTransform: 'uppercase', color: 'rgba(38,37,30,.55)', fontWeight: 500 }}>What ZARIS does</span>
          <h2 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 36, lineHeight: 1.2, letterSpacing: '-0.72px', color: '#26251e', fontWeight: 400 }}>
            Built for teams that ship — a workspace, not a form-builder.
          </h2>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 18 }}>
          {items.map((it, i) => (
            <article key={i} style={{
              background: '#f2f1ed', borderRadius: 10, padding: '24px 22px',
              boxShadow: '0 0 0 1px rgba(38,37,30,.1)',
              display: 'flex', flexDirection: 'column', gap: 12,
            }}>
              <span style={{ color: '#f54e00' }}><MIcon name={it.icon} size={22}/></span>
              <h3 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 22, lineHeight: 1.3, letterSpacing: '-0.11px', color: '#26251e', fontWeight: 400 }}>{it.title}</h3>
              <p style={{ margin: 0, fontFamily: 'var(--font-serif)', fontSize: 17.28, lineHeight: 1.45, color: 'rgba(38,37,30,.7)', fontFeatureSettings: "'ss01' on" }}>{it.body}</p>
            </article>
          ))}
        </div>
      </div>
    </MSection>
  );
};

Object.assign(window, { Features });
