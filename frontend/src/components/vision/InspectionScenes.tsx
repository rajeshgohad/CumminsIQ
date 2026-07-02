import type { Inspection, InspectionState } from './CameraFeed'

// ── Helper drawing primitives ─────────────────────────────────────────────────

function DetectionBox({ x, y, w, h, state, label }: {
  x: number; y: number; w: number; h: number
  state: InspectionState; label: string
}) {
  const color = state === 'pass' ? '#4ade80' : state === 'fail' ? '#f87171' : '#fbbf24'
  return (
    <g>
      <rect x={x} y={y} width={w} height={h}
        fill="none" stroke={color} strokeWidth="1.5" strokeDasharray="4 2"
        style={{ filter: `drop-shadow(0 0 3px ${color}60)` }} />
      <rect x={x} y={y - 11} width={label.length * 5.5 + 6} height={11} fill={color} rx="2" />
      <text x={x + 3} y={y - 2} fontSize="7" fontFamily="monospace" fill="black" fontWeight="bold">{label}</text>
    </g>
  )
}

// ── Scene 1: Cylinder Head Bolt Pattern ──────────────────────────────────────

function BoltPatternScene({ state }: { state: InspectionState }) {
  const cx = 160; const cy = 110; const r = 62
  const bolts = Array.from({ length: 6 }, (_, i) => {
    const angle = (i * 60 - 90) * (Math.PI / 180)
    return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle), ok: state !== 'fail' || i !== 2 }
  })

  return (
    <svg viewBox="0 0 320 220" width="100%" height="100%" className="absolute inset-0">
      {/* Background grid */}
      <defs>
        <pattern id="grid1" width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#1a2035" strokeWidth="0.5" />
        </pattern>
      </defs>
      <rect width="320" height="220" fill="url(#grid1)" />

      {/* Cylinder head body */}
      <rect x={60} y={30} width={200} height={160} rx="8" fill="#0f1929" stroke="#1e3a5f" strokeWidth="1.5" />
      <rect x={70} y={40} width={180} height={140} rx="6" fill="#0a1220" stroke="#162d4a" strokeWidth="1" />

      {/* Centre bore */}
      <ellipse cx={cx} cy={cy} rx={38} ry={38} fill="#060c16" stroke="#1e3a5f" strokeWidth="1.5" />
      <ellipse cx={cx} cy={cy} rx={30} ry={30} fill="#040810" stroke="#0d2040" strokeWidth="1" />
      <text x={cx} y={cy + 4} fontSize="8" fill="#1e4080" textAnchor="middle" fontFamily="monospace">BORE</text>

      {/* Bolt circle guide */}
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="#1e3a5f" strokeWidth="0.5" strokeDasharray="3 3" />

      {/* Bolts */}
      {bolts.map((b, i) => (
        <g key={i}>
          <circle cx={b.x} cy={b.y} r={9} fill="#0d1e30" stroke={b.ok ? '#2d5a8e' : '#5a1010'} strokeWidth="1.5" />
          <circle cx={b.x} cy={b.y} r={5} fill={b.ok ? '#1a3a5f' : '#3a0d0d'} />
          {/* Torque angle mark */}
          {b.ok ? (
            <line x1={b.x} y1={b.y}
              x2={b.x + 7 * Math.cos((-30 + i * 60) * Math.PI / 180)}
              y2={b.y + 7 * Math.sin((-30 + i * 60) * Math.PI / 180)}
              stroke="#4ade80" strokeWidth="1.5" />
          ) : (
            <text x={b.x} y={b.y + 3} fontSize="7" fill="#f87171" textAnchor="middle">✕</text>
          )}
          <text x={b.x + 13} y={b.y + 3} fontSize="7" fontFamily="monospace"
            fill={b.ok ? '#3a7a5a' : '#7a3a3a'}>B{i + 1}</text>
        </g>
      ))}

      {/* Detection boxes */}
      {state !== 'scanning' && bolts.map((b, i) => (
        b.ok
          ? <DetectionBox key={i} x={b.x - 12} y={b.y - 12} w={24} h={24}
              state="pass" label="TORQUE ✓" />
          : <DetectionBox key={i} x={b.x - 14} y={b.y - 14} w={28} h={28}
              state="fail" label="NO MARK" />
      ))}

      {/* Measurement overlay */}
      {state !== 'scanning' && (
        <g>
          <line x1={cx - r} y1={cy} x2={cx + r} y2={cy} stroke="#1e6060" strokeWidth="0.5" strokeDasharray="2 2" />
          <text x={cx + r + 4} y={cy + 3} fontSize="7" fill="#2a8080" fontFamily="monospace">Ø{(r * 2 * 0.22).toFixed(1)}mm</text>
        </g>
      )}
    </svg>
  )
}

// ── Scene 2: ECM Connector Pin Inspection ────────────────────────────────────

function ECMPinScene({ state }: { state: InspectionState }) {
  const cols = 10; const rows = 5
  const sx = 40; const sy = 50; const px = 22; const py = 20
  const bentPin = { col: 6, row: 2 }

  return (
    <svg viewBox="0 0 320 220" width="100%" height="100%" className="absolute inset-0">
      <defs>
        <pattern id="grid2" width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#1a2035" strokeWidth="0.5" />
        </pattern>
      </defs>
      <rect width="320" height="220" fill="url(#grid2)" />

      {/* Connector housing */}
      <rect x={28} y={35} width={264} height={135} rx="4" fill="#0c1525" stroke="#2a4060" strokeWidth="2" />
      <rect x={35} y={42} width={250} height={121} rx="3" fill="#060e1a" stroke="#1a2e48" strokeWidth="1" />

      {/* Connector label */}
      <text x={160} y={186} fontSize="8" fill="#1e3a5f" textAnchor="middle" fontFamily="monospace">ECM-J1 · 50-PIN · ISO 6722</text>

      {/* Pin grid */}
      {Array.from({ length: rows }, (_, row) =>
        Array.from({ length: cols }, (_, col) => {
          const x = sx + col * px; const y = sy + row * py
          const isBent = state === 'fail' && col === bentPin.col && row === bentPin.row
          const isMissing = false
          return (
            <g key={`${row}-${col}`}>
              {isBent ? (
                <g>
                  <rect x={x - 3} y={y - 7} width={6} height={14} rx="1"
                    fill="#3a0d0d" stroke="#9a2020" strokeWidth="1"
                    transform={`rotate(18, ${x}, ${y})`} />
                  <circle cx={x} cy={y} r={3} fill="#9a2020" />
                </g>
              ) : (
                <g>
                  <rect x={x - 3} y={y - 7} width={6} height={14} rx="1"
                    fill="#0f2540" stroke="#2d5a8e" strokeWidth="1" />
                  <circle cx={x} cy={y} r={2.5} fill="#1a4070" />
                </g>
              )}
              <text x={x} y={y + 16} fontSize="5" fill="#0d2040" textAnchor="middle" fontFamily="monospace">
                {row * cols + col + 1}
              </text>
            </g>
          )
        })
      )}

      {/* Detection boxes */}
      {state === 'pass' && (
        <DetectionBox x={28} y={35} w={264} h={135} state="pass" label={`ALL ${rows * cols} PINS OK`} />
      )}
      {state === 'fail' && (
        <DetectionBox
          x={sx + bentPin.col * px - 12} y={sy + bentPin.row * py - 14}
          w={24} h={24} state="fail" label="BENT PIN" />
      )}

      {/* Measurement line */}
      {state !== 'scanning' && (
        <g>
          <line x1={35} y1={172} x2={285} y2={172} stroke="#1e4060" strokeWidth="0.5" />
          <text x={160} y={170} fontSize="7" fill="#2060a0" textAnchor="middle" fontFamily="monospace">
            PITCH: 2.2mm · HEIGHT SPEC: 12.0±0.3mm
          </text>
        </g>
      )}
    </svg>
  )
}

// ── Scene 3: Piston Ring Gap Measurement ─────────────────────────────────────

function PistonRingScene({ state }: { state: InspectionState }) {
  const cx = 160; const cy = 115; const rOuter = 80; const rInner = 60
  const gapPass = 0.28; const gapFail = 0.51
  const gap = state === 'fail' ? gapFail : gapPass
  const gapOk = gap >= 0.20 && gap <= 0.40
  const gapAngle = 0   // gap at top

  return (
    <svg viewBox="0 0 320 230" width="100%" height="100%" className="absolute inset-0">
      <defs>
        <pattern id="grid3" width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#1a2035" strokeWidth="0.5" />
        </pattern>
        <radialGradient id="bore">
          <stop offset="0%" stopColor="#0a1020" />
          <stop offset="100%" stopColor="#060c18" />
        </radialGradient>
      </defs>
      <rect width="320" height="230" fill="url(#grid3)" />

      {/* Bore wall */}
      <circle cx={cx} cy={cy} r={rOuter + 8} fill="#0c1830" stroke="#1a3a60" strokeWidth="2" />
      <circle cx={cx} cy={cy} r={rOuter + 4} fill="#060e1a" />

      {/* Piston ring — gap at top */}
      <path
        d={`M ${cx} ${cy - rOuter} A ${rOuter} ${rOuter} 0 1 1 ${cx - 1} ${cy - rOuter}`}
        fill="none" stroke={gapOk ? '#4a8aaf' : '#8a3030'} strokeWidth="8"
        strokeLinecap="round" />

      {/* Inner ring edge */}
      <path
        d={`M ${cx} ${cy - rInner} A ${rInner} ${rInner} 0 1 1 ${cx - 1} ${cy - rInner}`}
        fill="none" stroke={gapOk ? '#2a5a7f' : '#5a2020'} strokeWidth="2" />

      {/* Bore centre */}
      <circle cx={cx} cy={cy} r={rInner - 10} fill="url(#bore)" stroke="#0d2040" strokeWidth="1" />
      <circle cx={cx} cy={cy} r={3} fill={gapOk ? '#4ade80' : '#f87171'} />

      {/* Gap measurement */}
      {state !== 'scanning' && (
        <g>
          {/* Gap highlight */}
          <line x1={cx - 6} y1={cy - rOuter - 2} x2={cx + 6} y2={cy - rOuter - 2}
            stroke={gapOk ? '#4ade80' : '#f87171'} strokeWidth="2" />
          {/* Measurement callout */}
          <line x1={cx} y1={cy - rOuter - 10} x2={cx} y2={cy - rOuter - 30}
            stroke={gapOk ? '#4ade80' : '#f87171'} strokeWidth="0.75" />
          <rect x={cx - 28} y={cy - rOuter - 48} width={56} height={16} rx="3"
            fill={gapOk ? '#0d2a1a' : '#2a0d0d'} stroke={gapOk ? '#4ade80' : '#f87171'} strokeWidth="1" />
          <text x={cx} y={cy - rOuter - 36} fontSize="8" fontFamily="monospace"
            fill={gapOk ? '#4ade80' : '#f87171'} textAnchor="middle" fontWeight="bold">
            GAP: {gap.toFixed(2)}mm
          </text>

          <DetectionBox x={cx - 14} y={cy - rOuter - 14} w={28} h={12}
            state={gapOk ? 'pass' : 'fail'} label={gapOk ? 'IN SPEC' : 'GAP HIGH'} />

          {/* Diameter */}
          <line x1={cx - rOuter} y1={cy} x2={cx + rOuter} y2={cy} stroke="#1a4060" strokeWidth="0.5" strokeDasharray="3 2" />
          <text x={cx} y={cy - 4} fontSize="7" fill="#2060a0" textAnchor="middle" fontFamily="monospace">
            Ø{(rOuter * 2 * 0.27).toFixed(1)}mm
          </text>
          <text x={cx} y={cy + 195} fontSize="7" fill="#2a5070" textAnchor="middle" fontFamily="monospace">
            SPEC: 0.20 – 0.40mm END GAP
          </text>
        </g>
      )}
    </svg>
  )
}

// ── Scene 4: Surface Finish / Bore Burr Detection ────────────────────────────

function SurfaceFinishScene({ state }: { state: InspectionState }) {
  const burr = state === 'fail'
  return (
    <svg viewBox="0 0 320 220" width="100%" height="100%" className="absolute inset-0">
      <defs>
        <pattern id="grid4" width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#1a2035" strokeWidth="0.5" />
        </pattern>
        <pattern id="surface" width="4" height="8" patternUnits="userSpaceOnUse">
          <line x1="2" y1="0" x2="2" y2="8" stroke="#1a3050" strokeWidth="0.5" />
        </pattern>
      </defs>
      <rect width="320" height="220" fill="url(#grid4)" />

      {/* Bore cross-section — viewed from side */}
      <rect x={40} y={30} width={240} height={160} rx="4" fill="#060e1a" stroke="#1a3050" strokeWidth="1.5" />

      {/* Machined surface texture */}
      <rect x={44} y={34} width={232} height={152} fill="url(#surface)" />

      {/* Surface profile line */}
      <polyline
        points={Array.from({ length: 120 }, (_, i) => {
          const x = 44 + i * 2
          const noise = Math.sin(i * 0.8) * 1.5 + Math.cos(i * 2.1) * 0.8
          const bump = burr && i > 70 && i < 85 ? (i - 70) * 0.8 - 8 : 0
          return `${x},${110 + noise + bump}`
        }).join(' ')}
        fill="none" stroke="#3a7aaf" strokeWidth="1.5" />

      {/* Reference lines */}
      <line x1={44} y1={106} x2={276} y2={106} stroke="#1e4060" strokeWidth="0.5" strokeDasharray="4 3" />
      <line x1={44} y1={114} x2={276} y2={114} stroke="#1e4060" strokeWidth="0.5" strokeDasharray="4 3" />
      <text x={280} y={109} fontSize="7" fill="#2060a0" fontFamily="monospace">Ra upper</text>
      <text x={280} y={117} fontSize="7" fill="#2060a0" fontFamily="monospace">Ra lower</text>

      {/* Burr anomaly highlight */}
      {burr && (state === 'fail' || state === 'warn' || state === 'pass') && (
        <g>
          <ellipse cx={192} cy={104} rx={18} ry={10}
            fill="#f8717120" stroke="#f87171" strokeWidth="1" />
          <DetectionBox x={175} y={88} w={36} h={28} state="fail" label="BURR DETECTED" />
          <text x={192} y={142} fontSize="8" fill="#f87171" textAnchor="middle" fontFamily="monospace">
            HEIGHT: +0.42mm (LIMIT: 0.15mm)
          </text>
        </g>
      )}

      {state === 'pass' && (
        <g>
          <DetectionBox x={44} y={30} w={232} h={152} state="pass" label="SURFACE OK" />
          <text x={160} y={168} fontSize="8" fill="#4ade80" textAnchor="middle" fontFamily="monospace">
            Ra 0.8μm · NO BURRS · WITHIN SPEC
          </text>
        </g>
      )}

      {/* Measurement scale */}
      <line x1={44} y1={195} x2={276} y2={195} stroke="#1a3050" strokeWidth="0.5" />
      {[0, 25, 50, 75, 100].map((p, i) => (
        <g key={i}>
          <line x1={44 + i * 58} y1={193} x2={44 + i * 58} y2={197} stroke="#2a4060" strokeWidth="0.5" />
          <text x={44 + i * 58} y={205} fontSize="6" fill="#2a4060" textAnchor="middle" fontFamily="monospace">
            {p}mm
          </text>
        </g>
      ))}
    </svg>
  )
}

// ── Scene 5: Gasket Presence & Seating ───────────────────────────────────────

function GasketScene({ state }: { state: InspectionState }) {
  const missing = state === 'fail'
  const bores = [
    { cx: 100, cy: 90 }, { cx: 180, cy: 90 },
    { cx: 100, cy: 150 }, { cx: 180, cy: 150 },
  ]

  return (
    <svg viewBox="0 0 280 220" width="100%" height="100%" className="absolute inset-0">
      <defs>
        <pattern id="grid5" width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#1a2035" strokeWidth="0.5" />
        </pattern>
      </defs>
      <rect width="280" height="220" fill="url(#grid5)" />

      {/* Block top surface */}
      <rect x={30} y={30} width={220} height={160} rx="6" fill="#0a1525" stroke="#1a3050" strokeWidth="2" />

      {/* Gasket outline (if present) */}
      {!missing && (
        <rect x={38} y={38} width={204} height={144} rx="5" fill="none"
          stroke="#5a9a5a" strokeWidth="3" strokeDasharray="6 3" opacity="0.8" />
      )}

      {/* Cylinder bores */}
      {bores.map((b, i) => (
        <g key={i}>
          <circle cx={b.cx} cy={b.cy} r={36} fill="#060c16" stroke="#1a3050" strokeWidth="1.5" />
          <circle cx={b.cx} cy={b.cy} r={28} fill="#040810" stroke="#0d2040" strokeWidth="1" />
          <text x={b.cx} y={b.cy + 4} fontSize="8" fill="#1a3a6a" textAnchor="middle" fontFamily="monospace">
            CYL {i + 1}
          </text>
          {/* Gasket ring around each bore */}
          {!missing && (
            <circle cx={b.cx} cy={b.cy} r={34} fill="none" stroke="#3a7a3a" strokeWidth="2" opacity="0.6" />
          )}
        </g>
      ))}

      {/* Detection */}
      {state !== 'scanning' && (
        missing ? (
          <g>
            <DetectionBox x={30} y={30} w={220} h={160} state="fail" label="GASKET MISSING" />
            <text x={140} y={195} fontSize="8" fill="#f87171" textAnchor="middle" fontFamily="monospace">
              HEAD GASKET NOT DETECTED — HOLD LINE
            </text>
          </g>
        ) : (
          <g>
            <DetectionBox x={30} y={30} w={220} h={160} state="pass" label="GASKET PRESENT" />
            <text x={140} y={195} fontSize="8" fill="#4ade80" textAnchor="middle" fontFamily="monospace">
              4-CYL GASKET SEATED · ALIGNMENT OK
            </text>
          </g>
        )
      )}
    </svg>
  )
}

// ── Scene 6: Weld Seam / Torque Angle ────────────────────────────────────────

function TorqueAngleScene({ state }: { state: InspectionState }) {
  const targetAngle = 90
  const measuredAngle = state === 'fail' ? 67 : 91
  const angleOk = Math.abs(measuredAngle - targetAngle) <= 5
  const cx = 160; const cy = 115; const r = 75

  return (
    <svg viewBox="0 0 320 230" width="100%" height="100%" className="absolute inset-0">
      <defs>
        <pattern id="grid6" width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#1a2035" strokeWidth="0.5" />
        </pattern>
      </defs>
      <rect width="320" height="230" fill="url(#grid6)" />

      {/* Protractor arc */}
      <circle cx={cx} cy={cy} r={r + 10} fill="none" stroke="#1a2a40" strokeWidth="1" />
      <circle cx={cx} cy={cy} r={r} fill="#060e1a" stroke="#1a3050" strokeWidth="1.5" />
      <circle cx={cx} cy={cy} r={20} fill="#0a1830" stroke="#1a3050" strokeWidth="1" />

      {/* Degree ticks */}
      {Array.from({ length: 36 }, (_, i) => {
        const a = (i * 10 - 90) * Math.PI / 180
        const r1 = i % 3 === 0 ? r - 10 : r - 5
        return (
          <line key={i}
            x1={cx + r * Math.cos(a)} y1={cy + r * Math.sin(a)}
            x2={cx + r1 * Math.cos(a)} y2={cy + r1 * Math.sin(a)}
            stroke="#1e3a5f" strokeWidth={i % 3 === 0 ? 1 : 0.5} />
        )
      })}
      {[0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330].map((deg) => {
        const a = (deg - 90) * Math.PI / 180
        return (
          <text key={deg} x={cx + (r - 18) * Math.cos(a)} y={cy + (r - 18) * Math.sin(a) + 3}
            fontSize="6" fill="#1e3a5f" textAnchor="middle" fontFamily="monospace">{deg}</text>
        )
      })}

      {/* Target zone (85–95°) */}
      <path
        d={`M ${cx} ${cy}
           L ${cx + r * Math.cos((85 - 90) * Math.PI / 180)} ${cy + r * Math.sin((85 - 90) * Math.PI / 180)}
           A ${r} ${r} 0 0 1 ${cx + r * Math.cos((95 - 90) * Math.PI / 180)} ${cy + r * Math.sin((95 - 90) * Math.PI / 180)}
           Z`}
        fill="#4ade8018" stroke="#4ade8040" strokeWidth="1" />

      {/* Measured angle needle */}
      {state !== 'scanning' && (
        <line
          x1={cx} y1={cy}
          x2={cx + r * 0.9 * Math.cos((measuredAngle - 90) * Math.PI / 180)}
          y2={cy + r * 0.9 * Math.sin((measuredAngle - 90) * Math.PI / 180)}
          stroke={angleOk ? '#4ade80' : '#f87171'} strokeWidth="2"
          style={{ filter: `drop-shadow(0 0 4px ${angleOk ? '#4ade80' : '#f87171'})` }} />
      )}

      {/* Bolt head */}
      <polygon
        points={Array.from({ length: 6 }, (_, i) => {
          const a = i * 60 * Math.PI / 180
          return `${cx + 16 * Math.cos(a)},${cy + 16 * Math.sin(a)}`
        }).join(' ')}
        fill="#0d2040" stroke="#2d5a8e" strokeWidth="1.5" />
      <circle cx={cx} cy={cy} r={8} fill="#1a3a6a" />

      {/* Readout */}
      {state !== 'scanning' && (
        <g>
          <rect x={cx - 45} y={cy + r + 12} width={90} height={28} rx="4"
            fill={angleOk ? '#0d2a1a' : '#2a0d0d'} stroke={angleOk ? '#4ade80' : '#f87171'} strokeWidth="1" />
          <text x={cx} y={cy + r + 24} fontSize="8" fontFamily="monospace"
            fill={angleOk ? '#4ade80' : '#f87171'} textAnchor="middle">
            MEAS: {measuredAngle}° / TARGET: {targetAngle}°
          </text>
          <text x={cx} y={cy + r + 34} fontSize="7" fontFamily="monospace"
            fill={angleOk ? '#4ade80' : '#f87171'} textAnchor="middle">
            {angleOk ? '✓ WITHIN ±5° TOLERANCE' : '✗ UNDER-TORQUED — REWORK'}
          </text>
        </g>
      )}
    </svg>
  )
}

// ── Exported inspection definitions ─────────────────────────────────────────

let _failCycle = 0

function coinFlip(weight = 0.82): boolean {
  _failCycle++
  return (_failCycle % 7 !== 0) && Math.random() < weight
}

export const INSPECTIONS: Inspection[] = [
  {
    id: 'bolt-pattern',
    station: 'STN-05 · Cylinder Head Torque',
    title: 'Bolt Torque Angle Verification',
    spec: '6-bolt pattern · M12 · 90° torque angle · AI visual confirmation',
    render: (s) => <BoltPatternScene state={s} />,
    passCondition: () => coinFlip(0.85),
  },
  {
    id: 'ecm-pins',
    station: 'STN-09 · ECM & Electrical',
    title: 'ECM Connector Pin Inspection',
    spec: '50-pin connector · pitch 2.2mm · height 12.0±0.3mm · bent/missing pin detection',
    render: (s) => <ECMPinScene state={s} />,
    passCondition: () => coinFlip(0.88),
  },
  {
    id: 'ring-gap',
    station: 'STN-03 · Piston & Con-Rod Assy',
    title: 'Piston Ring End Gap',
    spec: 'Ring gap spec: 0.20–0.40mm · bore Ø107.2mm · laser micrometer measurement',
    render: (s) => <PistonRingScene state={s} />,
    passCondition: () => coinFlip(0.80),
  },
  {
    id: 'surface-finish',
    station: 'STN-01 · Cylinder Block Prep',
    title: 'Bore Surface Finish & Burr Detection',
    spec: 'Ra ≤ 1.6μm · burr height limit 0.15mm · structured light profilometry',
    render: (s) => <SurfaceFinishScene state={s} />,
    passCondition: () => coinFlip(0.83),
  },
  {
    id: 'gasket',
    station: 'STN-05 · Cylinder Head Torque',
    title: 'Head Gasket Presence & Seating',
    spec: '4-cylinder MLS gasket · bore alignment ±0.1mm · infrared + visible detection',
    render: (s) => <GasketScene state={s} />,
    passCondition: () => coinFlip(0.92),
  },
  {
    id: 'torque-angle',
    station: 'STN-04 · Final Torque & Check',
    title: 'Rotational Torque Angle',
    spec: 'Target 90° ± 5° · torque-to-yield fastener · AI protractor overlay',
    render: (s) => <TorqueAngleScene state={s} />,
    passCondition: () => coinFlip(0.87),
  },
]
