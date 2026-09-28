import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './style.css'

class AppErrorBoundary extends React.Component<{ children: React.ReactNode }, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError() { return { failed: true } }

  componentDidCatch(error: Error) { console.error('Clinical Review render failure:', error) }

  render() {
    if (this.state.failed) return <main role="alert" style={{ minHeight: '100vh', display: 'grid', placeContent: 'center', gap: 12, padding: 24, color: '#18352a', fontFamily: 'DM Sans, sans-serif' }}>
      <h1 style={{ margin: 0, fontFamily: 'Manrope, sans-serif' }}>This view could not be displayed</h1>
      <p style={{ margin: 0, color: '#5d7168' }}>Your saved review is unchanged. Reload the workspace or return to Documents to try again.</p>
      <button type="button" onClick={() => window.location.reload()} style={{ justifySelf: 'start', border: 0, borderRadius: 24, padding: '11px 16px', background: '#bdebd0', color: '#174f34', cursor: 'pointer' }}>Reload workspace</button>
    </main>
    return this.props.children
  }
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><AppErrorBoundary><App /></AppErrorBoundary></React.StrictMode>)
