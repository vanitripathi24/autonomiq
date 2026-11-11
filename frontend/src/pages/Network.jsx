import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, useAsync } from '../api'
import { useBiz } from '../ctx.jsx'
import { Btn, Card, PageHead, money, pct } from '../components/ui.jsx'
import Grid from '../components/Grid.jsx'

function SellerSettings({ biz }) {
  const { data, reload } = useAsync(() => api.get(`/listings?business_id=${biz.id}`), [biz.id])
  const edit = async (e) => { await api.put(`/listings/${e.data.id}`, { [e.colDef.field]: Number(e.newValue) }); reload() }
  return (
    <div className="rise">
      <PageHead title="Seller Agent settings" sub="Your Seller Agent negotiates with buyers on your behalf. It quotes your list price, concedes step by step, and never accepts less than your floor price. Buyers cannot see the floor." />
      <Grid height={60 + 44 * (data?.length || 3)} rows={data || []} onCellValueChanged={edit} cols={[
        { field: 'sku', headerName: 'SKU', maxWidth: 110 }, { field: 'name', headerName: 'Product', minWidth: 180 },
        { field: 'list_price', headerName: 'List price (editable)', editable: true, valueFormatter: (p) => money(p.value) },
        { field: 'floor_price', headerName: 'Floor price (private, editable)', editable: true, valueFormatter: (p) => money(p.value) },
        { field: 'stock', headerName: 'Stock (editable)', editable: true }, { field: 'delivery_days', headerName: 'Delivery (days)' }]} />
    </div>
  )
}

export default function NetworkPage() {
  const { biz } = useBiz()
  const nav = useNavigate()
  const all = useAsync(() => api.get('/listings'), [biz.id])
  const mine = useAsync(() => (biz.kind === 'retailer' ? api.get(`/products?business_id=${biz.id}`) : Promise.resolve([])), [biz.id])
  const [sku, setSku] = useState('HP-100')
  const rank = useAsync(() => (biz.kind === 'retailer' ? api.get(`/suppliers/rank?sku=${sku}&qty=100&max_price=${((mine.data || []).find((p) => p.sku === sku)?.price || 60) * 0.75}&exclude=${biz.id}`) : Promise.resolve([])), [sku, mine.data, biz.id])
  if (biz.kind === 'supplier') return <SellerSettings biz={biz} />
  const name = (mine.data || []).find((p) => p.sku === sku)?.name || sku
  return (
    <div className="rise">
      <PageHead title="Supplier network" sub="Registered suppliers and the Supplier Intelligence Agent's ranking. Scores weigh price against your margin limit, on-time record, delivery speed and stock." />
      <Card title="Rank suppliers for" className="mb-6" aside={
        <div className="flex items-center gap-2">
          <select className="rounded-lg border border-line p-2 text-sm" value={sku} onChange={(e) => setSku(e.target.value)}>{(mine.data || []).map((p) => <option key={p.sku} value={p.sku}>{p.name}</option>)}</select>
          <Btn onClick={() => nav('/command', { state: { text: `Negotiate 100 units of ${name} with at least ${pct(biz.target_margin, 0)} profit margin.`, run: true } })}>Negotiate with the top three</Btn>
        </div>}>
        <Grid height={60 + 44 * Math.max(1, rank.data?.length || 1)} rows={rank.data || []} cols={[
          { field: 'supplier', headerName: 'Supplier', minWidth: 180 }, { field: 'list_price', headerName: 'List price', valueFormatter: (p) => money(p.value) },
          { field: 'reliability', headerName: 'On time', valueFormatter: (p) => pct(p.value, 0) }, { field: 'delivery_days', headerName: 'Delivery (days)' },
          { field: 'stock', headerName: 'Stock' }, { field: 'score', headerName: 'Score' }]} />
      </Card>
      <Card title="All supplier listings">
        <Grid height={420} rows={all.data || []} cols={[
          { field: 'sku', headerName: 'SKU', maxWidth: 110 }, { field: 'name', headerName: 'Product', minWidth: 170 }, { field: 'supplier', headerName: 'Supplier', minWidth: 170 },
          { field: 'list_price', headerName: 'List price', valueFormatter: (p) => money(p.value) }, { field: 'stock', headerName: 'Stock' },
          { field: 'reliability', headerName: 'On time', valueFormatter: (p) => pct(p.value, 0) }, { field: 'delivery_days', headerName: 'Delivery (days)' }]} />
      </Card>
    </div>
  )
}
