import { useNavigate } from 'react-router-dom'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, useAsync } from '../api'
import { useBiz } from '../ctx.jsx'
import { Badge, Btn, Card, Err, PageHead, agentColor, money, pct } from '../components/ui.jsx'
import Grid from '../components/Grid.jsx'

const SEV = { high: 'red', medium: 'amber', low: 'blue' }

function Figure({ label, value, note, tone }) {
  return (
    <div className="min-w-[150px] flex-1 border-l-2 border-line pl-4 first:border-l-0 first:pl-0">
      <div className="text-sm text-muted">{label}</div>
      <div className="text-[28px] font-bold leading-tight tracking-tight">{value}</div>
      {note && <div className={`text-sm ${tone === 'bad' ? 'text-loss' : tone === 'good' ? 'text-gain' : 'text-muted'}`}>{note}</div>}
    </div>
  )
}

export default function Dashboard() {
  const { biz } = useBiz()
  const nav = useNavigate()
  const { data, error } = useAsync(() => api.get(`/dashboard?business_id=${biz.id}`), [biz.id])
  const deals = useAsync(() => api.get(`/deals?business_id=${biz.id}`), [biz.id])
  if (error) return <Err e={error} />
  if (!data) return <div className="text-muted">Loading…</div>
  const k = data.kpis

  if (data.kind === 'supplier') {
    return (
      <div className="rise">
        <PageHead title={biz.name} sub="Your Seller Agent answers buyer offers using the price floors you set under Supplier network. Payments land here after PayPal confirms them." />
        <div className="mb-6 flex flex-wrap gap-5 rounded-xl border border-line bg-white p-5">
          <Figure label="Cash" value={money(k.cash, 0)} />
          <Figure label="Revenue from deals" value={money(k.revenue, 0)} note={`${k.units_sold} units sold`} />
          <Figure label="Open deals" value={k.open_deals} note="waiting on buyers" />
          <Figure label="Stock at floor value" value={money(k.stock_value, 0)} />
        </div>
        <Card title="Your listings">
          <Grid height={300} rows={data.listings} cols={[
            { field: 'sku', headerName: 'SKU', maxWidth: 110 }, { field: 'name', headerName: 'Product', minWidth: 180 },
            { field: 'list_price', headerName: 'List price', valueFormatter: (p) => money(p.value) },
            { field: 'stock', headerName: 'In stock' }, { field: 'delivery_days', headerName: 'Delivery (days)' },
          ]} />
        </Card>
        <div className="mt-6"><Card title="Recent deals" aside={<Btn kind="ghost" onClick={() => nav('/deals')}>All deals</Btn>}>
          {(deals.data || []).slice(0, 4).map((d) => (
            <div key={d.id} className="flex justify-between border-b border-line py-2 last:border-0 text-sm"><span>{d.qty} × {d.product_name} to {d.buyer}</span><b>{money(d.total)}</b></div>
          ))}
          {!deals.data?.length && <span className="text-muted">No deals yet. Buyers will find your listings through the network.</span>}
        </Card></div>
      </div>
    )
  }

  return (
    <div className="rise">
      <PageHead title={biz.name} sub={data.narrative} />
      <div className="mb-6 flex flex-wrap gap-5 rounded-xl border border-line bg-white p-5">
        <Figure label="Revenue, last 30 days" value={money(k.revenue_30d, 0)} note={`${k.revenue_delta_pct >= 0 ? '+' : ''}${k.revenue_delta_pct}% vs previous 30`} tone={k.revenue_delta_pct >= 0 ? 'good' : 'bad'} />
        <Figure label="Profit" value={money(k.profit_30d, 0)} note={`${pct(k.margin_30d)} margin`} />
        <Figure label="Cash" value={money(k.cash, 0)} note={`${money(k.stock_value, 0)} in stock`} />
        <Figure label="Units sold" value={k.units_30d.toLocaleString()} />
      </div>
      <div className="grid gap-6 xl:grid-cols-5">
        <Card title="What needs your attention" className="xl:col-span-3" aside={<Badge tone={data.issues.length ? 'amber' : 'green'}>{data.issues.length} open</Badge>}>
          {data.issues.length === 0 && <p className="text-muted">Nothing needs attention. Stock, margins and demand look healthy.</p>}
          <div className="space-y-3">
            {data.issues.map((i, n) => (
              <div key={n} className="flex items-start gap-4 rounded-lg border border-line p-4">
                <span className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: agentColor(i.agent) }} />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2"><b>{i.title}</b><Badge tone={SEV[i.severity]}>{i.severity}</Badge></div>
                  <p className="mt-0.5 text-sm text-muted">{i.detail}</p>
                  <p className="text-xs text-muted">Spotted by the {i.agent}</p>
                </div>
                <Btn kind="ghost" onClick={() => nav('/command', { state: { text: i.action, run: true } })}>Hand to agents</Btn>
              </div>
            ))}
          </div>
        </Card>
        <Card title="Revenue and profit, 60 days" className="xl:col-span-2">
          <div className="h-[300px]">
            <ResponsiveContainer>
              <AreaChart data={data.series} margin={{ left: -10, right: 4, top: 4 }}>
                <CartesianGrid stroke="#e8ecf3" vertical={false} />
                <XAxis dataKey="day" tickFormatter={(d) => d.slice(5)} interval={9} tick={{ fontSize: 12, fill: '#5b6784' }} axisLine={false} tickLine={false} />
                <YAxis tickFormatter={(v) => `$${(v / 1000).toFixed(1)}k`} tick={{ fontSize: 12, fill: '#5b6784' }} axisLine={false} tickLine={false} />
                <Tooltip formatter={(v) => money(v, 0)} />
                <Area dataKey="revenue" name="Revenue" stroke="#0b3d91" fill="#0b3d91" fillOpacity={0.12} strokeWidth={2} />
                <Area dataKey="profit" name="Profit" stroke="#0e8a5f" fill="#0e8a5f" fillOpacity={0.12} strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>
    </div>
  )
}
