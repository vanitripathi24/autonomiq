export const money = (v, d = 2) => (v == null ? '—' : Number(v).toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: d, maximumFractionDigits: d }))
export const pct = (v, d = 1) => (v == null ? '—' : `${(v * 100).toFixed(d)}%`)

export function PageHead({ title, sub, children }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-[26px] font-bold leading-tight tracking-tight">{title}</h1>
        {sub && <p className="mt-1 max-w-2xl text-[15px] text-muted">{sub}</p>}
      </div>
      <div className="flex items-center gap-2">{children}</div>
    </div>
  )
}

export function Card({ title, aside, children, className = '' }) {
  return (
    <section className={`rounded-xl border border-line bg-white ${className}`}>
      {(title || aside) && (
        <header className="flex items-center justify-between border-b border-line px-5 py-3">
          <h2 className="text-[15px] font-semibold">{title}</h2>
          {aside}
        </header>
      )}
      <div className="p-5">{children}</div>
    </section>
  )
}

const TONES = {
  neutral: 'bg-paper text-muted', blue: 'bg-tint text-cobalt', green: 'bg-mint text-gain',
  amber: 'bg-sand text-amber', red: 'bg-rose text-loss',
}
export function Badge({ tone = 'neutral', children }) {
  return <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${TONES[tone]}`}>{children}</span>
}

export const STATUS = {
  pending_approval: ['amber', 'Needs approval'], approved: ['blue', 'Approved'], paid: ['green', 'Paid'],
  refunded: ['neutral', 'Refunded'], rejected: ['red', 'Declined'], payment_failed: ['red', 'Payment failed'],
  critical: ['red', 'Critical'], low: ['amber', 'Low'], healthy: ['green', 'Healthy'], overstock: ['blue', 'Overstock'],
  failed: ['red', 'No deal'], not_selected: ['neutral', 'Not selected'],
}
export function StatusBadge({ s }) {
  const [tone, label] = STATUS[s] || ['neutral', s]
  return <Badge tone={tone}>{label}</Badge>
}

export function Btn({ kind = 'primary', className = '', ...p }) {
  const k = {
    primary: 'bg-cobalt text-white hover:bg-[#0a3278]', ghost: 'border border-line bg-white text-ink hover:bg-paper',
    danger: 'border border-line bg-white text-loss hover:bg-rose',
  }[kind]
  return <button {...p} className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${k} ${className}`} />
}

export function Empty({ children }) {
  return <div className="rounded-xl border border-dashed border-line bg-white/60 p-8 text-center text-muted">{children}</div>
}

export function Err({ e }) {
  return e ? <div className="mb-4 rounded-lg bg-rose px-4 py-3 text-sm text-loss">{e.message || String(e)}</div> : null
}

const AGENT_COLORS = {
  Orchestrator: '#101b33', Inventory: '#0e8a5f', Supplier: '#0a7f94', Buyer: '#0b3d91', Seller: '#c97800',
  Finance: '#6b4bb8', 'Smart Pricing': '#b4458f', 'Sales Intelligence': '#3b7a1f', 'Business Analyst': '#4b5d85',
  'Digital Twin': '#8a5a00', Owner: '#101b33',
}
export function agentColor(name = '') {
  const k = Object.keys(AGENT_COLORS).find((x) => name.startsWith(x))
  return AGENT_COLORS[k] || '#5b6784'
}
export function AgentDot({ name }) {
  return <span className="mt-1.5 inline-block h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: agentColor(name) }} />
}
