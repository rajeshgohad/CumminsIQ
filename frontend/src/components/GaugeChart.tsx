interface GaugeChartProps {
  value: number
  max?: number
  size?: number
  label?: string
  colorClass?: string
}

function getColor(value: number, max: number): string {
  const pct = value / max
  if (pct >= 0.85) return '#10B981' // emerald
  if (pct >= 0.70) return '#F59E0B' // amber
  return '#EF4444'                   // red
}

export default function GaugeChart({ value, max = 100, size = 110, label, colorClass }: GaugeChartProps) {
  const radius = 38
  const cx = size / 2
  const cy = size / 2
  const strokeWidth = 8
  const gap = 60 // degrees gap at bottom

  const totalAngle = 360 - gap
  const startAngle = 90 + gap / 2
  const pct = Math.min(1, Math.max(0, value / max))
  const sweepAngle = totalAngle * pct

  function polarToCartesian(angle: number) {
    const rad = ((angle - 90) * Math.PI) / 180
    return {
      x: cx + radius * Math.cos(rad),
      y: cy + radius * Math.sin(rad),
    }
  }

  function describeArc(startDeg: number, endDeg: number) {
    const s = polarToCartesian(startDeg)
    const e = polarToCartesian(endDeg)
    const largeArc = endDeg - startDeg > 180 ? 1 : 0
    return `M ${s.x} ${s.y} A ${radius} ${radius} 0 ${largeArc} 1 ${e.x} ${e.y}`
  }

  const bgEnd = startAngle + totalAngle
  const fgEnd = startAngle + sweepAngle
  const color = colorClass || getColor(value, max)

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {/* Track */}
        <path
          d={describeArc(startAngle, bgEnd)}
          fill="none"
          stroke="#1F2937"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
        />
        {/* Value arc */}
        {pct > 0 && (
          <path
            d={describeArc(startAngle, fgEnd)}
            fill="none"
            stroke={typeof color === 'string' && color.startsWith('#') ? color : undefined}
            className={typeof color === 'string' && !color.startsWith('#') ? color : undefined}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            style={typeof color === 'string' && color.startsWith('#') ? { stroke: color } : {}}
          />
        )}
        {/* Center value */}
        <text
          x={cx}
          y={cy - 4}
          textAnchor="middle"
          dominantBaseline="middle"
          fill="white"
          fontSize="14"
          fontWeight="700"
          fontFamily="system-ui"
        >
          {value.toFixed(1)}
        </text>
        <text
          x={cx}
          y={cy + 12}
          textAnchor="middle"
          dominantBaseline="middle"
          fill="#6B7280"
          fontSize="8"
          fontFamily="system-ui"
        >
          {label || '%'}
        </text>
      </svg>
    </div>
  )
}
