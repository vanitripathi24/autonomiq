import { api, useAsync } from '../api'
import { useBiz } from '../ctx.jsx'
import { Badge, Card, PageHead, money } from '../components/ui.jsx'
import Grid from '../components/Grid.jsx'

export default function Payments() {
  const { biz, cfg } = useBiz()
  const tx = useAsync(() => api.get(`/transactions?business_id=${biz.id}`), [biz.id])
  const wh = useAsync(() => api.get('/webhooks'), [biz.id])
  return (
    <div className="rise">
      <PageHead title="Payments" sub="Payments and refunds through PayPal Orders API v2. Webhooks confirm each payment and are checked against PayPal's signature service when a webhook ID is configured.">
        <Badge tone={cfg.paypal.live ? 'green' : 'amber'}>{cfg.paypal.live ? `PayPal ${cfg.paypal.mode}` : 'Simulated checkout'}</Badge>
      </PageHead>
      <Card title="Transactions" className="mb-6">
        <Grid height={Math.max(160, 60 + 44 * (tx.data?.length || 1))} rows={tx.data || []} cols={[
          { field: 'created_at', headerName: 'Time', valueFormatter: (p) => new Date(p.value + 'Z').toLocaleString(), minWidth: 170 },
          { field: 'kind', headerName: 'Type', maxWidth: 110 }, { field: 'product', headerName: 'Product', minWidth: 160 },
          { field: 'buyer', headerName: 'From' }, { field: 'seller', headerName: 'To' },
          { field: 'amount', headerName: 'Amount', valueFormatter: (p) => money(p.value) }, { field: 'capture_id', headerName: 'PayPal capture', minWidth: 190 },
          { field: 'source', headerName: 'Source', maxWidth: 120 }]} />
      </Card>
      <Card title="Webhook events received">
        <Grid height={Math.max(160, 60 + 44 * (wh.data?.length || 1))} rows={wh.data || []} cols={[
          { field: 'created_at', headerName: 'Time', valueFormatter: (p) => new Date(p.value + 'Z').toLocaleString(), minWidth: 170 },
          { field: 'event_type', headerName: 'Event', minWidth: 230 }, { field: 'event_id', headerName: 'Event ID', minWidth: 190 },
          { field: 'verified', headerName: 'Signature', valueFormatter: (p) => (p.value ? 'Verified by PayPal' : 'Not verified (simulated or no webhook ID)') , minWidth: 260 }]} />
      </Card>
    </div>
  )
}
