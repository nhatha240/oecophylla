/* Lightweight SVG charts: AreaChart, DonutChart, BarChart */

function AreaChart({ data, height = 180, color = 'var(--emerald-500)', fill = 'var(--emerald-50)', secondary }) {
  const w = 600;
  const max = Math.max(...data, ...(secondary || []));
  const stepX = w / (data.length - 1);
  const pts = data.map((v, i) => [i * stepX, height - (v / max) * (height - 30) - 10]);
  const path = pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' ');
  const area = path + ` L${pts[pts.length-1][0]} ${height} L0 ${height} Z`;

  let secPath = null;
  if (secondary) {
    const sp = secondary.map((v, i) => [i * stepX, height - (v / max) * (height - 30) - 10]);
    secPath = sp.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' ');
  }

  return (
    <svg viewBox={`0 0 ${w} ${height}`} width="100%" height={height} style={{ display: 'block' }}>
      <defs>
        <linearGradient id="ag1" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={fill} stopOpacity="0.9"/>
          <stop offset="100%" stopColor={fill} stopOpacity="0.1"/>
        </linearGradient>
      </defs>
      {[0.25, 0.5, 0.75].map((g, i) => (
        <line key={i} x1="0" x2={w} y1={height * g} y2={height * g} stroke="var(--hairline)" strokeDasharray="2 4"/>
      ))}
      <path d={area} fill="url(#ag1)" />
      <path d={path} fill="none" stroke={color} strokeWidth="2" />
      {secPath && <path d={secPath} fill="none" stroke="var(--muted-2)" strokeWidth="2" strokeDasharray="4 4"/>}
      {pts.map((p, i) => i % Math.ceil(pts.length / 8) === 0 && (
        <circle key={i} cx={p[0]} cy={p[1]} r="3" fill="var(--surface)" stroke={color} strokeWidth="1.6"/>
      ))}
    </svg>
  );
}

function Donut({ slices, size = 160, hole = 50, label }) {
  const total = slices.reduce((s, x) => s + x.value, 0);
  let acc = 0;
  const cx = size / 2, cy = size / 2;
  const R = size / 2 - 4;
  const arcs = slices.map((s, i) => {
    const start = acc / total * Math.PI * 2 - Math.PI / 2;
    acc += s.value;
    const end = acc / total * Math.PI * 2 - Math.PI / 2;
    const large = end - start > Math.PI ? 1 : 0;
    const x1 = cx + R * Math.cos(start);
    const y1 = cy + R * Math.sin(start);
    const x2 = cx + R * Math.cos(end);
    const y2 = cy + R * Math.sin(end);
    const xi1 = cx + hole * Math.cos(start);
    const yi1 = cy + hole * Math.sin(start);
    const xi2 = cx + hole * Math.cos(end);
    const yi2 = cy + hole * Math.sin(end);
    return (
      <path key={i}
        d={`M${x1} ${y1} A${R} ${R} 0 ${large} 1 ${x2} ${y2} L${xi2} ${yi2} A${hole} ${hole} 0 ${large} 0 ${xi1} ${yi1} Z`}
        fill={s.color} />
    );
  });
  return (
    <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size}>
      {arcs}
      {label && (
        <>
          <text x={cx} y={cy - 4} textAnchor="middle" fontFamily="var(--font-serif)" fontSize="22" fill="var(--ink)" fontWeight="500">{label.value}</text>
          <text x={cx} y={cy + 16} textAnchor="middle" fontSize="10" fill="var(--muted)">{label.sub}</text>
        </>
      )}
    </svg>
  );
}

function BarsHorizontal({ items, max }) {
  const mx = max || Math.max(...items.map(i => i.value));
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {items.map((it, i) => (
        <div key={i}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
            <span style={{ fontWeight: 500 }}>{it.label}</span>
            <span style={{ color: 'var(--muted)' }}>{it.display ?? it.value}</span>
          </div>
          <div style={{ height: 6, background: 'var(--surface-2)', borderRadius: 99, overflow: 'hidden' }}>
            <div style={{
              height: '100%',
              width: (it.value / mx * 100) + '%',
              background: it.color || 'var(--emerald-500)',
              borderRadius: 99,
              transition: 'width 0.4s ease'
            }} />
          </div>
        </div>
      ))}
    </div>
  );
}

Object.assign(window, { AreaChart, Donut, BarsHorizontal });
