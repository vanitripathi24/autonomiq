import { useState } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, useAsync } from '../api'
import { useBiz } from '../ctx.jsx'
import { Card, Err, PageHead, StatusBadge, money, pct } from '../components/ui.jsx'
import Grid from '../components/Grid.jsx'

export default function Inventory() {
  const { biz } = useBiz()
  const [tab, setTab] = useState('inventory')
  const [sel, setSel] = useState(null)
  const inv = useAsync(() => api.get(`/products?business_id=${biz.id}`), [biz.id])
  const sales = useAsync(() => (tab === 'sales' ? api.get(`/sales?business_id=${biz.id}`) : Promise.resolve([])), [biz.id, tab])
  const fc = useAsync(() => (sel ? api.get(`/forecast?business_id=${biz.id}&product_id=${sel.product_id}`) : Promise.resolve(null)), [sel?.product_id])
  if (biz.kind !== 'retailer') return <Card>Inventory and sales analytics are for retailer accounts.</Card>

  const chart = fc.data && [
    ...fc.data.history_dates.map((d, i) => ({ d, actual: fc.data.history[i] })),
    ...fc.data.dates.map((d, i) => ({ d, forecast: fc.data.forecast[i] })),
  ]
  return (
    <div className="rise">
      <PageHead title="Inventory and sales" sub="Coverage and shortfalls come from a demand forecast (trend plus day-of-week model). Select a product to see it. Edit a price to update it live.">
        <div className="flex rounded-lg border border-line bg-white p-0.5 text-sm font-semibold">
          {['inventory', 'sales'].map((t) => <button key={t} onClick={() => setTab(t)} className={`rounded-md px-4 py-1.5 capitalize ${tab === t ? 'bg-ink text-white' : 'text-muted'}`}>{t}</button>)}
        </div>
      </PageHead>
      <Err e={inv.error} />
      {tab === 'inventory' ? (
        <>
          <Grid height={330} rows={inv.data || []} rowSelection={{ mode: 'singleRow', checkboxes: false, enableClickSelection: true }}
            onRowSelected={(e) => e.node.isSelected() && setSel(e.data)}
            onCellValueChanged={async (e) => { await api.put(`/products/${e.data.product_id}`, { price: Number(e.newValue) }); inv.reload() }}
            cols={[
              { field: 'sku', headerName: 'SKU', maxWidth: 100 }, { field: 'name', headerName: 'Product', minWidth: 170 },
              { field: 'stock', headerName: 'Stock', maxWidth: 100 },
              { field: 'cost', headerName: 'Avg cost', maxWidth: 110, valueFormatter: (p) => money(p.value) },
              { field: 'price', headerName: 'Price (editable)', editable: true, maxWidth: 150, valueFormatter: (p) => money(p.value) },
              { field: 'margin', headerName: 'Margin', maxWidth: 110, valueFormatter: (p) => pct(p.value, 0), cellStyle: (p) => (p.value < biz.target_margin ? { color: '#c2362b', fontWeight: 600 } : null) },
              { field: 'avg_daily', headerName: 'Demand/day', maxWidth: 130 },
              { field: 'coverage_days', headerName: 'Days of cover', maxWidth: 140 },
              { field: 'shortage', headerName: 'Shortfall (14d)', maxWidth: 140 },
              { field: 'status', headerName: 'Status', maxWidth: 130, cellRenderer: (p) => <StatusBadge s={p.value} /> },
            ]} />
          <Card title={sel ? `${sel.name}: last 30 days and 14-day forecast` : 'Forecast'} className="mt-6"
            aside={fc.data && <span className="text-sm text-muted">Backtest error {fc.data.mape}% · trend {fc.data.trend_pct >= 0 ? '+' : ''}{fc.data.trend_pct}%</span>}>
            {!sel && <p className="text-muted">Select a product row above.</p>}
            {chart && (
              <div className="h-[260px]"><ResponsiveContainer><LineChart data={chart} margin={{ left: -15 }}>
                <CartesianGrid stroke="#e8ecf3" vertical={false} />
                <XAxis dataKey="d" tickFormatter={(d) => d.slice(5)} interval={6} tick={{ fontSize: 12, fill: '#5b6784' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 12, fill: '#5b6784' }} axisLine={false} tickLine={false} />
                <Tooltip />
                <Line dataKey="actual" name="Units sold" stroke="#0b3d91" dot={false} strokeWidth={2} />
                <Line dataKey="forecast" name="Forecast" stroke="#c97800" dot={false} strokeWidth={2} strokeDasharray="5 4" />
              </LineChart></ResponsiveContainer></div>
            )}
          </Card>
        </>
      ) : (
        <Grid height={520} rows={sales.data || []} cols={[
          { field: 'day', headerName: 'Date', maxWidth: 130 }, { field: 'product', headerName: 'Product', minWidth: 180 }, { field: 'qty', headerName: 'Units', maxWidth: 100 },
          { field: 'unit_price', headerName: 'Unit price', valueFormatter: (p) => money(p.value) },
          { field: 'revenue', headerName: 'Revenue', valueFormatter: (p) => money(p.value) }, { field: 'profit', headerName: 'Profit', valueFormatter: (p) => money(p.value) }]} />
      )}
    </div>
  )
}
