import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, useAsync } from '../api'
import { useBiz } from '../ctx.jsx'
import { Btn, Card, Empty, Err, PageHead, money, pct } from '../components/ui.jsx'

export default function Pricing() {
  const { biz } = useBiz()
  const nav = useNavigate()
  const { data, error, reload } = useAsync(() => api.get(`/pricing?business_id=${biz.id}`), [biz.id])
  const [pick, setPick] = useState({})
  useEffect(() => { setPick(Object.fromEntries((data || []).map((r) => [r.product_id, true]))) }, [data])
  if (biz.kind !== 'retailer') return <Card>Smart pricing is for retailer accounts.</Card>
  const apply = async () => {
    const items = (data || []).filter((r) => pick[r.product_id]).map((r) => ({ product_id: r.product_id, price: r.suggested_price }))
    await api.post('/pricing/apply', { items }); reload()
  }
  return (
    <div className="rise">
      <PageHead title="Smart pricing" sub={`Prices that respond to stock cover and demand, and never fall below your ${pct(biz.target_margin, 0)} margin target.`}>
        <Btn onClick={apply} disabled={!Object.values(pick).some(Boolean)}>Apply selected prices</Btn>
      </PageHead>
      <Err e={error} />
      {data && !data.length && <Empty>Current prices already fit demand and your margin target.</Empty>}
      {!!data?.length && (
        <div className="overflow-hidden rounded-xl border border-line bg-white">
          <table className="w-full text-left text-sm">
            <thead className="bg-[#f4f6fb] text-muted"><tr>
              <th className="w-10 p-3" /><th className="p-3">Product</th><th className="p-3">Now</th><th className="p-3">Suggested</th><th className="p-3">Margin after</th><th className="p-3">Why</th></tr></thead>
            <tbody>
              {data.map((r) => (
                <tr key={r.product_id} className="border-t border-line">
                  <td className="p-3"><input type="checkbox" aria-label={`Apply ${r.name}`} checked={!!pick[r.product_id]} onChange={(e) => setPick({ ...pick, [r.product_id]: e.target.checked })} /></td>
                  <td className="p-3 font-semibold">{r.name}</td>
                  <td className="p-3">{money(r.current_price)}</td>
                  <td className="p-3 font-semibold">{money(r.suggested_price)} <span className={r.change_pct >= 0 ? 'text-gain' : 'text-loss'}>({r.change_pct >= 0 ? '+' : ''}{r.change_pct}%)</span></td>
                  <td className="p-3">{pct(r.current_margin, 0)} → {pct(r.new_margin, 0)}</td>
                  <td className="p-3 text-muted">{r.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="mt-4"><Btn kind="ghost" onClick={() => nav('/twin')}>Test a price change in the digital twin first</Btn></div>
    </div>
  )
}
