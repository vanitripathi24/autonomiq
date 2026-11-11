import { useEffect, useState } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, useAsync } from '../api'
import { useBiz } from '../ctx.jsx'
import { Card, Err, PageHead, money } from '../components/ui.jsx'

function Slider({ label, value, set, min, max, unit = '%' }) {
  return (
    <label className="block">
      <div className="mb-1 flex justify-between text-sm"><span className="font-medium">{label}</span><b>{value > 0 ? '+' : ''}{value}{unit}</b></div>
      <input type="range" min={min} max={max} value={value} onChange={(e) => set(Number(e.target.value))} />
    </label>
  )
}

export default function Twin() {
  const { biz } = useBiz()
  const [p, setP] = useState({ price_change: -10, stock_change: 20, cost_change: 0, product_id: 0 })
  const [res, setRes] = useState(null)
  const [err, setErr] = useState(null)
  const prods = useAsync(() => api.get(`/products?business_id=${biz.id}`), [biz.id])
  useEffect(() => {
    if (biz.kind !== 'retailer') return
    const t = setTimeout(() => api.post('/twin', { business_id: biz.id, ...p, product_id: p.product_id || null, horizon: 30 }).then(setRes, setErr), 250)
    return () => clearTimeout(t)
  }, [p, biz.id])
  if (biz.kind !== 'retailer') return <Card>The digital twin is for retailer accounts.</Card>
  const series = res && res.baseline.cum_profit.map((v, i) => ({ day: i + 1, current: v, scenario: res.scenario.cum_profit[i] }))
  const Tile = ({ label, a, b, fmt = (v) => money(v, 0) }) => (
    <div className="rounded-lg border border-line p-4"><div className="text-sm text-muted">{label}</div>
      <div className="text-xl font-bold">{fmt(b)}</div><div className={`text-sm ${b - a >= 0 ? 'text-gain' : 'text-loss'}`}>{b - a >= 0 ? '+' : ''}{fmt(b - a)} vs now ({fmt(a)})</div></div>
  )
  return (
    <div className="rise">
      <PageHead title="Digital twin" sub="Try a decision on a simulated copy of your business before you make it. Demand comes from the forecast and reacts to price." />
      <Err e={err} />
      <div className="grid gap-6 xl:grid-cols-3">
        <Card title="Scenario">
          <div className="space-y-5">
            <label className="block text-sm"><span className="mb-1 block font-medium">Apply to</span>
              <select className="w-full rounded-lg border border-line p-2" value={p.product_id} onChange={(e) => setP({ ...p, product_id: Number(e.target.value) })}>
                <option value={0}>All products</option>{(prods.data || []).map((x) => <option key={x.product_id} value={x.product_id}>{x.name}</option>)}</select></label>
            <Slider label="Selling price" value={p.price_change} set={(v) => setP({ ...p, price_change: v })} min={-30} max={30} />
            <Slider label="Starting inventory" value={p.stock_change} set={(v) => setP({ ...p, stock_change: v })} min={-50} max={100} />
            <Slider label="Supplier cost (e.g. switching supplier)" value={p.cost_change} set={(v) => setP({ ...p, cost_change: v })} min={-20} max={20} />
          </div>
        </Card>
        <div className="space-y-6 xl:col-span-2">
          {res && (
            <>
              <div className="grid gap-4 sm:grid-cols-3">
                <Tile label="Revenue, 30 days" a={res.baseline.revenue} b={res.scenario.revenue} />
                <Tile label="Profit, 30 days" a={res.baseline.profit} b={res.scenario.profit} />
                <Tile label="Lost sales (units)" a={res.baseline.lost_units} b={res.scenario.lost_units} fmt={(v) => Math.round(v).toLocaleString()} />
              </div>
              <Card title="Cumulative profit">
                <div className="h-[260px]"><ResponsiveContainer><LineChart data={series} margin={{ left: -5 }}>
                  <CartesianGrid stroke="#e8ecf3" vertical={false} />
                  <XAxis dataKey="day" tick={{ fontSize: 12, fill: '#5b6784' }} axisLine={false} tickLine={false} />
                  <YAxis tickFormatter={(v) => `$${(v / 1000).toFixed(1)}k`} tick={{ fontSize: 12, fill: '#5b6784' }} axisLine={false} tickLine={false} />
                  <Tooltip formatter={(v) => money(v, 0)} />
                  <Line dataKey="current" name="Today's plan" stroke="#5b6784" strokeWidth={2} dot={false} strokeDasharray="5 4" />
                  <Line dataKey="scenario" name="Scenario" stroke="#0b3d91" strokeWidth={2.5} dot={false} />
                </LineChart></ResponsiveContainer></div>
              </Card>
              <Card title="What the agents notice"><ul className="list-disc space-y-1 pl-5 text-[15px]">{res.insights.map((i, n) => <li key={n}>{i}</li>)}</ul></Card>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
