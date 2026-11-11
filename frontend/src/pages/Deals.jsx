import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { PayPalButtons, PayPalScriptProvider } from '@paypal/react-paypal-js'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Check, Play } from 'lucide-react'
import { api, useAsync } from '../api'
import { useBiz } from '../ctx.jsx'
import { Btn, Card, Empty, Err, PageHead, StatusBadge, money, pct } from '../components/ui.jsx'
import Grid from '../components/Grid.jsx'

export default function Deals() {
  const { biz } = useBiz()
  const nav = useNavigate()
  const { data, error } = useAsync(() => api.get(`/deals?business_id=${biz.id}`), [biz.id])
  return (
    <div className="rise">
      <PageHead title="Deals" sub="Every agreement your agents negotiate, from first offer to PayPal payment." />
      <Err e={error} />
      {data && !data.length && <Empty>No deals yet. {biz.kind === 'retailer' ? <Link className="font-semibold text-cobalt" to="/command">Ask the agents to restock something.</Link> : 'Buyers will negotiate with your Seller Agent through the network.'}</Empty>}
      {!!data?.length && (
        <Grid height={Math.min(520, 60 + 44 * data.length)} rows={data} onRowClicked={(e) => nav(`/deals/${e.data.id}`)} rowStyle={{ cursor: 'pointer' }} cols={[
          { field: 'id', headerName: '#', maxWidth: 80 }, { field: 'product_name', headerName: 'Product', minWidth: 170 },
          { field: 'buyer', headerName: 'Buyer' }, { field: 'seller', headerName: 'Seller' }, { field: 'qty', headerName: 'Units', maxWidth: 100 },
          { field: 'unit_price', headerName: 'Unit price', maxWidth: 120, valueFormatter: (p) => money(p.value) },
          { field: 'total', headerName: 'Total', maxWidth: 130, valueFormatter: (p) => money(p.value) },
          { field: 'status', headerName: 'Status', cellRenderer: (p) => <StatusBadge s={p.value} /> },
        ]} />
      )}
    </div>
  )
}

function Stepper({ status }) {
  const order = ['pending_approval', 'approved', 'paid']
  const idx = status === 'refunded' ? 3 : order.indexOf(status)
  const labels = ['Negotiated', 'Approved', 'Paid with PayPal']
  return (
    <ol className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
      {labels.map((l, i) => (
        <li key={l} className={`flex items-center gap-2 ${i <= idx ? 'font-semibold text-ink' : 'text-muted'}`}>
          <span className={`flex h-5 w-5 items-center justify-center rounded-full text-white ${i <= idx ? 'bg-gain' : 'bg-line'}`}>{i <= idx && <Check size={13} />}</span>{l}
        </li>
      ))}
      {status === 'refunded' && <li className="font-semibold text-muted">Refunded</li>}
      {status === 'rejected' && <li className="font-semibold text-loss">Declined</li>}
    </ol>
  )
}

function Replay({ deal }) {
  const rounds = deal.rounds
  const [shown, setShown] = useState(rounds.length)
  const timer = useRef()
  const play = () => { clearInterval(timer.current); let n = 0; setShown(0); timer.current = setInterval(() => { n += 1; setShown(n); if (n >= rounds.length) clearInterval(timer.current) }, 700) }
  useEffect(() => () => clearInterval(timer.current), [])
  const pts = {}
  rounds.slice(0, shown).forEach((r) => { const p = (pts[r.n] ||= { n: r.n }); if (r.agent === 'buyer') p.buyer = r.price; else if (r.action !== 'walk') p.seller = r.price })
  const data = Object.values(pts)
  return (
    <Card title="Negotiation replay" aside={<Btn kind="ghost" onClick={play}><Play size={14} /> Replay</Btn>}>
      <div className="h-[220px]">
        <ResponsiveContainer><LineChart data={data} margin={{ left: -5, right: 12, top: 8 }}>
          <CartesianGrid stroke="#e8ecf3" vertical={false} />
          <XAxis dataKey="n" type="number" domain={[0, 6]} ticks={[0, 1, 2, 3, 4, 5, 6]} tick={{ fontSize: 12, fill: '#5b6784' }} axisLine={false} tickLine={false} label={{ value: 'Round', position: 'insideBottom', offset: -2, fontSize: 12, fill: '#5b6784' }} />
          <YAxis domain={['auto', 'auto']} tickFormatter={(v) => `$${v}`} tick={{ fontSize: 12, fill: '#5b6784' }} axisLine={false} tickLine={false} />
          <Tooltip formatter={(v) => money(v)} />
          <ReferenceLine y={deal.ceiling} stroke="#0e8a5f" strokeDasharray="4 4" label={{ value: `Margin ceiling ${money(deal.ceiling)}`, fontSize: 12, fill: '#0e8a5f', position: 'insideTopRight' }} />
          <Line dataKey="seller" name="Seller" stroke="#c97800" strokeWidth={2.5} connectNulls />
          <Line dataKey="buyer" name="Buyer" stroke="#0b3d91" strokeWidth={2.5} connectNulls />
        </LineChart></ResponsiveContainer>
      </div>
      <ol className="mt-3 space-y-3">
        {rounds.slice(0, shown).map((r) => (
          <li key={r.id} className={`rise flex ${r.agent === 'buyer' ? 'justify-start' : 'justify-end'}`}>
            <div className={`max-w-[85%] rounded-xl px-4 py-3 ${r.agent === 'buyer' ? 'bg-tint' : 'bg-sand'}`}>
              <div className="flex items-center gap-2 text-sm"><b>{r.agent === 'buyer' ? 'Buyer Agent' : 'Seller Agent'}</b><span className="text-muted">{r.action}</span><b>{money(r.price)}</b></div>
              <p className="text-[15px]">{r.message}</p>
              <details className="text-sm text-muted"><summary className="cursor-pointer">Why</summary>{r.reasoning}</details>
            </div>
          </li>
        ))}
      </ol>
    </Card>
  )
}

function Pay({ deal, cfg, done }) {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const simulate = async () => {
    setBusy(true); setErr(null)
    try { const o = await api.post('/paypal/orders', { deal_id: deal.id }); await api.post(`/paypal/orders/${o.id}/capture`); done() } catch (e) { setErr(e) } finally { setBusy(false) }
  }
  if (!cfg.paypal.live)
    return <><Err e={err} /><Btn className="w-full" onClick={simulate} disabled={busy}>{busy ? 'Processing…' : `Pay ${money(deal.total)} with PayPal`}</Btn>
      <p className="mt-2 text-xs text-muted">Simulated checkout: add PayPal Sandbox keys to the backend to show the real PayPal buttons.</p></>
  return (
    <PayPalScriptProvider options={{ clientId: cfg.paypal.client_id, currency: 'USD', intent: 'capture' }}>
      <Err e={err} />
      <PayPalButtons style={{ layout: 'vertical', shape: 'rect' }}
        createOrder={async () => (await api.post('/paypal/orders', { deal_id: deal.id })).id}
        onApprove={async (d) => { await api.post(`/paypal/orders/${d.orderID}/capture`); done() }}
        onError={(e) => setErr(e)} />
    </PayPalScriptProvider>
  )
}

export function DealDetail() {
  const { id } = useParams()
  const { biz, cfg, refresh } = useBiz()
  const { data: d, error, reload } = useAsync(() => api.get(`/deals/${id}`), [id])
  const [busy, setBusy] = useState(false)
  const act = async (path) => { setBusy(true); try { await api.post(path); await reload(); refresh() } finally { setBusy(false) } }
  if (error) return <Err e={error} />
  if (!d) return <div className="text-muted">Loading…</div>
  const isBuyer = biz.id === d.buyer_id
  const f = d.finance || {}
  return (
    <div className="rise">
      <PageHead title={`${d.qty} × ${d.product_name}`} sub={`${d.buyer} buying from ${d.seller}`}><StatusBadge s={d.status} /></PageHead>
      <div className="mb-6 rounded-xl border border-line bg-white px-5 py-4"><Stepper status={d.status} /></div>
      <div className="grid gap-6 xl:grid-cols-3">
        <div className="xl:col-span-2"><Replay deal={d} /></div>
        <div className="space-y-6">
          <Card title="Agreed terms">
            <dl className="space-y-2 text-sm">
              {[['Unit price', money(d.unit_price)], ['Quantity', d.qty], ['Total', money(d.total)], ['Delivery', `${d.delivery_days} days`], ['Below list price', `${d.rationale.saving_vs_list_pct}%`]].map(([k, v]) => (
                <div key={k} className="flex justify-between"><dt className="text-muted">{k}</dt><dd className="font-semibold">{v}</dd></div>))}
            </dl>
          </Card>
          <Card title="Finance check">
            <p className="mb-3 text-sm">Resale margin <b>{pct(f.margin)}</b>, expected profit <b>{money(f.expected_profit, 0)}</b>.</p>
            <ul className="space-y-2 text-sm">{(f.checks || []).map((c) => <li key={c.name} className="flex gap-2"><span className={c.ok ? 'text-gain' : 'text-loss'}>{c.ok ? '✓' : '✕'}</span><span><b>{c.name}</b> <span className="text-muted">{c.detail}</span></span></li>)}</ul>
          </Card>
          <Card title="Next step">
            {d.status === 'pending_approval' && (isBuyer
              ? <div className="flex gap-2"><Btn className="flex-1" disabled={busy || !f.all_ok} onClick={() => act(`/deals/${d.id}/approve`)}>Approve deal</Btn><Btn kind="danger" disabled={busy} onClick={() => act(`/deals/${d.id}/reject`)}>Decline</Btn></div>
              : <p className="text-sm text-muted">Waiting for {d.buyer} to approve.</p>)}
            {['approved', 'payment_failed'].includes(d.status) && (isBuyer ? <Pay deal={d} cfg={cfg} done={() => { reload(); refresh() }} /> : <p className="text-sm text-muted">Approved. Waiting for {d.buyer} to pay.</p>)}
            {d.status === 'paid' && <div><p className="mb-3 text-sm">Paid. Stock and cash balances were updated for both businesses.<br /><span className="text-muted">Capture {d.capture_id}</span></p>{isBuyer && <Btn kind="ghost" disabled={busy} onClick={() => act(`/deals/${d.id}/refund`)}>Refund this payment</Btn>}</div>}
            {['refunded', 'rejected'].includes(d.status) && <p className="text-sm text-muted">This deal is closed.</p>}
          </Card>
        </div>
      </div>
      <Card title="Offers from competing suppliers" className="mt-6">
        <Grid height={60 + 44 * d.competing.length} rows={d.competing} cols={[
          { field: 'seller', headerName: 'Supplier', minWidth: 180 }, { field: 'unit_price', headerName: 'Final price', valueFormatter: (p) => money(p.value) },
          { field: 'delivery_days', headerName: 'Delivery (days)' }, { field: 'score', headerName: 'Agent score' },
          { field: 'status', headerName: 'Outcome', cellRenderer: (p) => <StatusBadge s={p.value} /> }]} />
      </Card>
    </div>
  )
}
