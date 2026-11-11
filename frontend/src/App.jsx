import { NavLink, Route, Routes, Navigate } from 'react-router-dom'
import { LayoutDashboard, Terminal, Boxes, Tag, Handshake, FlaskConical, Network, ScrollText, CreditCard, RotateCcw } from 'lucide-react'
import { BizProvider, useBiz } from './ctx.jsx'
import { api } from './api'
import Dashboard from './pages/Dashboard.jsx'
import Command from './pages/Command.jsx'
import Inventory from './pages/Inventory.jsx'
import Pricing from './pages/Pricing.jsx'
import Deals, { DealDetail } from './pages/Deals.jsx'
import Twin from './pages/Twin.jsx'
import NetworkPage from './pages/Network.jsx'
import Trail from './pages/Trail.jsx'
import Payments from './pages/Payments.jsx'

const NAV = [
  ['/', 'Dashboard', LayoutDashboard, 'both'],
  ['/command', 'Command center', Terminal, 'retailer'],
  ['/inventory', 'Inventory & sales', Boxes, 'retailer'],
  ['/pricing', 'Smart pricing', Tag, 'retailer'],
  ['/twin', 'Digital twin', FlaskConical, 'retailer'],
  ['/deals', 'Deals', Handshake, 'both'],
  ['/network', 'Supplier network', Network, 'both'],
  ['/payments', 'Payments', CreditCard, 'both'],
  ['/trail', 'Decision trail', ScrollText, 'both'],
]

function Shell() {
  const { biz, businesses, choose, cfg } = useBiz()
  const reset = async () => {
    if (!confirm('Reset all demo data to the starting state?')) return
    await api.post('/reset'); location.reload()
  }
  return (
    <div className="flex min-h-full">
      <aside className="sticky top-0 flex h-screen w-64 shrink-0 flex-col bg-ink px-4 py-5 text-white">
        <div className="mb-6 px-2">
          <div className="text-xl font-extrabold tracking-tight">AUTONOMIQ</div>
          <div className="text-xs text-white/60">Your business, run by a team of agents</div>
        </div>
        <label className="mb-1 px-2 text-xs text-white/60" htmlFor="biz">Signed in as</label>
        <select id="biz" value={biz.id} onChange={(e) => choose(Number(e.target.value))}
          className="mb-5 rounded-lg border border-white/20 bg-white/10 px-3 py-2 text-sm text-white">
          {businesses.map((b) => <option key={b.id} value={b.id} className="text-ink">{b.name} ({b.kind})</option>)}
        </select>
        <nav className="flex-1 space-y-0.5 overflow-y-auto">
          {NAV.filter(([, , , k]) => k === 'both' || k === biz.kind).map(([to, label, Icon]) => (
            <NavLink key={to} to={to} end={to === '/'}
              className={({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${isActive ? 'bg-white text-ink' : 'text-white/75 hover:bg-white/10'}`}>
              <Icon size={17} /> {label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-4 space-y-1.5 border-t border-white/15 pt-4 text-xs text-white/70">
          <div>Payments: <b className="text-white">{cfg.paypal.live ? `PayPal ${cfg.paypal.mode}` : 'Simulated checkout'}</b></div>
          <div>Reasoning: <b className="text-white">{cfg.llm}</b></div>
          <button onClick={reset} className="mt-2 flex items-center gap-1.5 rounded-md px-1 py-1 text-white/70 hover:text-white"><RotateCcw size={13} /> Reset demo data</button>
        </div>
      </aside>
      <main className="min-w-0 flex-1 px-8 py-7">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/command" element={biz.kind === 'retailer' ? <Command /> : <Navigate to="/" />} />
          <Route path="/inventory" element={<Inventory />} />
          <Route path="/pricing" element={<Pricing />} />
          <Route path="/twin" element={<Twin />} />
          <Route path="/deals" element={<Deals />} />
          <Route path="/deals/:id" element={<DealDetail />} />
          <Route path="/network" element={<NetworkPage />} />
          <Route path="/payments" element={<Payments />} />
          <Route path="/trail" element={<Trail />} />
        </Routes>
      </main>
    </div>
  )
}

export default function App() {
  return <BizProvider><Shell /></BizProvider>
}
