import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'

class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { error: Error | null }
> {
  state = { error: null }
  static getDerivedStateFromError(error: Error) { return { error } }
  render() {
    if (this.state.error) {
      const err = this.state.error as Error
      return (
        <div style={{ background: '#000', color: '#fff', minHeight: '100vh', padding: 40, fontFamily: 'monospace' }}>
          <div style={{ color: '#f44336', fontSize: 14, marginBottom: 8 }}>React render error:</div>
          <div style={{ color: '#ff9800', fontSize: 13, marginBottom: 16 }}>{err.message}</div>
          <pre style={{ color: '#888', fontSize: 11, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
            {err.stack}
          </pre>
        </div>
      )
    }
    return this.props.children
  }
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <ErrorBoundary>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </ErrorBoundary>,
)
