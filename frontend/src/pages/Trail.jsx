import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, useAsync } from '../api'
import { useBiz } from '../ctx.jsx'
import { AgentDot, Empty, PageHead } from '../components/ui.jsx'

export default function Trail() {
  const { biz } = useBiz()
  const { data } = useAsync(() => api.get(`/decisions?business_id=${biz.id}`), [biz.id])
  const [agent, setAgent] = useState('all')
  const agents = [...new Set((data || []).map((d) => d.agent))]
  const rows = (data || []).filter((d) => agent === 'all' || d.agent === agent)
  return (
    <div className="rise mx-auto max-w-4xl">
      <PageHead title="Decision trail" sub="Every important agent decision with its reasoning, newest first. Open a deal to replay its negotiation.">
        <select aria-label="Filter by agent" className="rounded-lg border border-line bg-white p-2 text-sm" value={agent} onChange={(e) => setAgent(e.target.value)}>
          <option value="all">All agents</option>{agents.map((a) => <option key={a}>{a}</option>)}</select>
      </PageHead>
      {!rows.length && <Empty>No decisions recorded yet. Run a command to see the agents' reasoning here.</Empty>}
      <ol className="space-y-3">
        {rows.map((d) => (
          <li key={d.id} className="flex gap-3 rounded-xl border border-line bg-white p-4">
            <AgentDot name={d.agent} />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline gap-x-2"><b>{d.agent}</b><span>{d.action}</span>
                <span className="text-xs text-muted">{new Date(d.created_at + 'Z').toLocaleString()}</span></div>
              <p className="mt-1 text-[15px] text-muted">{d.reasoning}</p>
              {d.deal_id && <Link className="text-sm font-semibold text-cobalt" to={`/deals/${d.deal_id}`}>Open deal #{d.deal_id}</Link>}
            </div>
          </li>
        ))}
      </ol>
    </div>
  )
}
