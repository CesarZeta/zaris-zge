const Hero = () => (
  <MSection bg="#f2f1ed" style={{ padding: '112px 32px 80px' }}>
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 22, textAlign: 'center' }}>
      <span style={{ fontFamily: 'var(--font-system)', fontSize: 11, letterSpacing: '.08em', textTransform: 'uppercase', color: 'rgba(38,37,30,.55)', fontWeight: 500, padding: '4px 10px', background: '#e6e5e0', borderRadius: 9999 }}>
        NEW · Timeline view, in beta
      </span>
      <h1 style={{ margin: 0, fontFamily: 'var(--font-display)', fontSize: 72, lineHeight: 1.05, letterSpacing: '-2.16px', color: '#26251e', fontWeight: 400, maxWidth: 900 }}>
        Ship the thing you meant to make.
      </h1>
      <p style={{ margin: 0, fontFamily: 'var(--font-serif)', fontSize: 19.2, lineHeight: 1.5, fontWeight: 500, color: 'rgba(38,37,30,.7)', maxWidth: 620, fontFeatureSettings: "'ss01' on, 'ss02' on" }}>
        ZARIS is a workspace for web apps, not a form-builder with opinions. Start a project, describe the change, and the composer plans, greps, reads, and edits — without losing the cursor.
      </p>
      <div style={{ display: 'flex', gap: 12, marginTop: 6 }}>
        <MBtn variant="primary">Start a project</MBtn>
        <MBtn variant="surface">Read the docs →</MBtn>
      </div>
    </div>

    {/* Editor mockup */}
    <div style={{ marginTop: 72, maxWidth: 980, margin: '72px auto 0', borderRadius: 10, overflow: 'hidden', boxShadow: 'rgba(0,0,0,.14) 0 28px 70px, rgba(0,0,0,.1) 0 14px 32px, 0 0 0 1px rgba(38,37,30,.1)' }}>
      <div style={{ background: '#1b1a15', padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ width: 10, height: 10, borderRadius: 9999, background: '#cf2d56' }}/>
        <span style={{ width: 10, height: 10, borderRadius: 9999, background: '#c08532' }}/>
        <span style={{ width: 10, height: 10, borderRadius: 9999, background: '#1f8a65' }}/>
        <span style={{ marginLeft: 14, fontFamily: 'var(--font-mono)', fontSize: 11.5, color: 'rgba(242,241,237,.55)' }}>src/hero.tsx · ZARIS landing</span>
      </div>
      <div style={{ background: '#26251e', padding: '28px 32px', display: 'grid', gridTemplateColumns: '1fr 280px', gap: 32 }}>
        <pre style={{ margin: 0, fontFamily: 'var(--font-mono)', fontSize: 13, lineHeight: 1.7, color: '#f2f1ed' }}>
<span style={{ color: 'rgba(242,241,237,.4)' }}>  1  </span><span style={{ color: '#c0a8dd' }}>export</span> <span style={{ color: '#c0a8dd' }}>const</span> <span style={{ color: '#9fbbe0' }}>Hero</span> = () =&gt; (<br/>
<span style={{ color: 'rgba(242,241,237,.4)' }}>  2  </span>  &lt;<span style={{ color: '#9fc9a2' }}>section</span> <span style={{ color: '#dfa88f' }}>className</span>=<span style={{ color: '#f2f1ed' }}>"hero"</span>&gt;<br/>
<span style={{ color: 'rgba(242,241,237,.4)' }}>  3  </span>    &lt;<span style={{ color: '#9fc9a2' }}>h1</span>&gt;Ship the thing.&lt;/<span style={{ color: '#9fc9a2' }}>h1</span>&gt;<br/>
<span style={{ color: 'rgba(242,241,237,.4)' }}>  4  </span>    &lt;<span style={{ color: '#9fc9a2' }}>p</span>&gt;A workspace...&lt;/<span style={{ color: '#9fc9a2' }}>p</span>&gt;<br/>
<span style={{ color: 'rgba(242,241,237,.4)' }}>  5  </span>  &lt;/<span style={{ color: '#9fc9a2' }}>section</span>&gt;<br/>
<span style={{ color: 'rgba(242,241,237,.4)' }}>  6  </span>);
        </pre>
        <div style={{ background: 'rgba(242,241,237,.04)', borderRadius: 8, padding: 14, display: 'flex', flexDirection: 'column', gap: 12, boxShadow: '0 0 0 1px rgba(242,241,237,.08)' }}>
          <div style={{ fontFamily: 'var(--font-system)', fontSize: 10, letterSpacing: '.08em', textTransform: 'uppercase', color: 'rgba(242,241,237,.5)', fontWeight: 500 }}>AI Timeline</div>
          {[
            { c: '#dfa88f', l: 'Thinking', d: 'Plan rewrite' },
            { c: '#9fc9a2', l: 'Grep', d: "'hero-title'" },
            { c: '#9fbbe0', l: 'Read', d: 'hero.tsx' },
            { c: '#c0a8dd', l: 'Edit', d: '3 edits' },
          ].map((s, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ width: 10, height: 10, borderRadius: 9999, background: s.c }}/>
              <span style={{ fontFamily: 'var(--font-system)', fontSize: 10.5, letterSpacing: '.05em', textTransform: 'uppercase', color: 'rgba(242,241,237,.55)', minWidth: 60 }}>{s.l}</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5, color: '#f2f1ed' }}>{s.d}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  </MSection>
);

Object.assign(window, { Hero });
