import { useEffect, useState, useCallback } from 'react'

const BASE = import.meta.env.VITE_API_URL || ''

async function req(path, method = 'GET', body) {
  const r = await fetch(`${BASE}/api${path}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!r.ok) {
    const j = await r.json().catch(() => ({}))
    throw new Error(j.detail || r.statusText)
  }
  return r.json()
}

export const api = {
  get: (p) => req(p),
  post: (p, b = {}) => req(p, 'POST', b),
  put: (p, b) => req(p, 'PUT', b),
}

export function useAsync(fn, deps = []) {
  const [state, set] = useState({ data: null, loading: true, error: null })
  const run = useCallback(() => {
    set((s) => ({ ...s, loading: true, error: null }))
    return fn().then((data) => set({ data, loading: false, error: null }), (error) => set({ data: null, loading: false, error }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  useEffect(() => { run() }, [run])
  return { ...state, reload: run }
}
