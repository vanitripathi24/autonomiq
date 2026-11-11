import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { api } from '../api'
import { useBiz } from '../ctx.jsx'
import { AgentDot, Btn, Card, Err, PageHead, money, pct } from '../components/ui.jsx'
import Grid from '../components/Grid.jsx'

const EXAMPLES = [
  'My inventory is running low. Find the best supplier, negotiate a good deal, maintain at least a 25% profit margin and prepare the payment.',
  'Find products with low profit margins and suggest a better supplier.',
  'What happens if we reduce prices by 10% and increase inventory by 20%?',
  'Suggest better prices for my products.',
  'Forecast demand for the next two weeks.',
  'How is my business performing?',
]

function Result({ r, run }) {
  if (r.type === 'restock' && r.deal_id)
    return (
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="text-lg font-bold">{r.supplier}: {r.qty} units at {money(r.unit_price)}</div>
          <div className="text-muted">{money(r.total)} total · {pct(r.margin)} margin on resale</div>
        </div>
        <Link to={`/deals/${r.deal_id}`}><Btn>Review and approve</Btn></Link>
      </div>
    )
  if (r.type === 'margin_review')
    return <Grid height={Math.max(140, 52 + 42 * r.items.length)} rows={r.items} cols={[
      { field: 'name', headerName: 'Product' }, { field: 'margin', headerName: 'Margin', maxWidth: 110, valueFormatter: (p) => pct(p.value, 0) },
      { field: 'cost', headerName: 'Cost', maxWidth: 100, valueFormatter: (p) => money(p.value) },
      { field: 'target_cost', headerName: 'Cost needed', maxWidth: 130, valueFormatter: (p) => money(p.value) },
      { field: 'best_supplier', headerName: 'Best supplier' },
      { headerName: '', maxWidth: 150, sortable: false, cellRenderer: (p) => <button className="font-semibold text-cobalt" onClick={() => run(p.data.command)}>Negotiate</button> },
    ]} />
  if (r.type === 'pricing')
    return <div className="flex items-center justify-between"><span>{r.recommendations.length} recommendation(s) are ready.</span><Link to="/pricing"><Btn kind="ghost">Open smart pricing</Btn></Link></div>
  if (r.type === 'twin')
    return <div className="flex items-center justify-between"><span>Profit {money(r.sim.delta.profit, 0)}, revenue {money(r.sim.delta.revenue, 0)} over 30 days.</span><Link to="/twin"><Btn kind="ghost">Explore in digital twin</Btn></Link></div>
  if (r.type === 'forecast')
    return <Grid height={Math.max(140, 52 + 42 * r.rows.length)} rows={r.rows} cols={[
      { field: 'name', headerName: 'Product' }, { field: 'next_14d', headerName: 'Units, next 14 days' },
      { field: 'avg_daily', headerName: 'Per day' }, { field: 'trend_pct', headerName: 'Trend %' }, { field: 'mape', headerName: 'Backtest error %' }]} />
  if (r.type === 'analyze')
    return <ul className="list-disc pl-5 text-sm">{r.issues.map((i, n) => <li key={n}>{i.title}</li>)}{!r.issues.length && <li>No issues found.</li>}</ul>
  return <p>{r.message}</p>
}

export default function Command() {
  const { biz } = useBiz()
  const loc = useLocation()
  const [text, setText] = useState(loc.state?.text || '')
  const [out, setOut] = useState(null)
  const [shown, setShown] = useState(0)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const timer = useRef()

  const run = async (t = text) => {
    if (!t.trim()) return
    setText(t); setBusy(true); setErr(null); setOut(null); setShown(0)
    try {
      const res = await api.post('/command', { business_id: biz.id, text: t })
      setOut(res)
      let n = 0
      clearInterval(timer.current)
      timer.current = setInterval(() => { n += 1; setShown(n); if (n >= res.steps.length) clearInterval(timer.current) }, 420)
    } catch (e) { setErr(e) } finally { setBusy(false) }
  }
  useEffect(() => { if (loc.state?.run) { window.history.replaceState({}, ''); run(loc.state.text) } return () => clearInterval(timer.current) }, [])

  return (
    <div className="rise mx-auto max-w-4xl">
      <PageHead title="Command center" sub="Tell AUTONOMIQ what you want in plain language. The orchestrator picks the agents and shows its work." />
      <Err e={err} />
      <div className="rounded-xl border border-line bg-white p-4">
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={3} placeholder="e.g. Find products with low profit margins and suggest a better supplier"
          className="w-full resize-none rounded-lg border border-line p-3 text-[15px]" onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) run() }} />
        <div className="mt-3 flex items-center justify-between gap-3">
          <span className="text-xs text-muted">Ctrl or ⌘ + Enter to send</span>
          <Btn onClick={() => run()} disabled={busy || !text.trim()}>{busy ? 'Agents are working…' : 'Run with agents'}</Btn>
        </div>
      </div>
      {!out && !busy && (
        <div className="mt-4 flex flex-wrap gap-2">
          {EXAMPLES.map((e) => <button key={e} onClick={() => run(e)} className="rounded-full border border-line bg-white px-3 py-1.5 text-left text-sm text-muted hover:text-ink">{e.length > 70 ? e.slice(0, 68) + '…' : e}</button>)}
        </div>
      )}
      {out && (
        <div className="mt-6 grid gap-6">
          <Card title="Agent activity">
            <ol className="space-y-4">
              {out.steps.slice(0, shown).map((s, i) => (
                <li key={i} className="rise flex gap-3">
                  <AgentDot name={s.agent} />
                  <div><div className="text-sm"><b>{s.agent}</b> <span className="text-muted">{s.title}</span></div><p className="text-[15px]">{s.detail}</p></div>
                </li>
              ))}
              {shown < out.steps.length && <li className="text-sm text-muted">Working…</li>}
            </ol>
          </Card>
          {shown >= out.steps.length && (
            <Card title="Outcome" className="rise">
              <p className="mb-4 text-[15px]">{out.summary}</p>
              <Result r={out.result} run={run} />
            </Card>
          )}
        </div>
      )}
    </div>
  )
}
