import { createContext, useContext, useEffect, useState } from 'react'
import { api } from './api'

const Ctx = createContext(null)
export const useBiz = () => useContext(Ctx)

export function BizProvider({ children }) {
  const [businesses, setBusinesses] = useState([])
  const [cfg, setCfg] = useState(null)
  const [id, setId] = useState(() => Number(localStorage.getItem('aq-biz')) || 1)
  const refresh = () => api.get('/businesses').then(setBusinesses)
  useEffect(() => { refresh(); api.get('/config').then(setCfg) }, [])
  const biz = businesses.find((b) => b.id === id) || businesses[0]
  const choose = (v) => { setId(v); localStorage.setItem('aq-biz', v) }
  if (!biz || !cfg) return <div className="p-10 text-muted">Connecting to AUTONOMIQ…</div>
  return <Ctx.Provider value={{ biz, businesses, choose, cfg, refresh }}>{children}</Ctx.Provider>
}
