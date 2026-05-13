import type { WebSocketMessage } from '../types'

type MessageHandler = (msg: WebSocketMessage) => void

class WebSocketService {
  private connections: Map<string, WebSocket> = new Map()
  private handlers: Map<string, Set<MessageHandler>> = new Map()
  private retryTimeouts: Map<string, ReturnType<typeof setTimeout>> = new Map()
  private maxRetries = 5
  private retryCount: Map<string, number> = new Map()

  connect(runId: string): Promise<void> {
    return new Promise((resolve, reject) => {
      if (this.connections.has(runId)) {
        resolve()
        return
      }

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${window.location.host}/api/v1/runs/${runId}/ws`
      const ws = new WebSocket(wsUrl)
      const token = localStorage.getItem('proteus_access_token')

      ws.onopen = () => {
        this.retryCount.set(runId, 0)
        if (token) {
          ws.send(JSON.stringify({ type: 'auth', token }))
        }
        resolve()
      }

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data) as WebSocketMessage
          const runHandlers = this.handlers.get(runId)
          if (runHandlers) {
            runHandlers.forEach((handler) => handler(msg))
          }
        } catch { }
      }

      ws.onclose = () => {
        this.connections.delete(runId)
        this.attemptReconnect(runId)
      }

      ws.onerror = () => {
        reject(new Error(`WebSocket connection failed for run ${runId}`))
      }

      this.connections.set(runId, ws)
    })
  }

  private attemptReconnect(runId: string) {
    const count = this.retryCount.get(runId) || 0
    if (count >= this.maxRetries) return

    this.retryCount.set(runId, count + 1)
    const delay = Math.min(1000 * Math.pow(2, count), 30000)

    const timeout = setTimeout(() => {
      this.connect(runId).catch(() => { })
    }, delay)
    this.retryTimeouts.set(runId, timeout)
  }

  subscribe(runId: string, handler: MessageHandler) {
    if (!this.handlers.has(runId)) {
      this.handlers.set(runId, new Set())
    }
    this.handlers.get(runId)!.add(handler)
  }

  unsubscribe(runId: string, handler: MessageHandler) {
    const runHandlers = this.handlers.get(runId)
    if (runHandlers) {
      runHandlers.delete(handler)
      if (runHandlers.size === 0) {
        this.disconnect(runId)
      }
    }
  }

  disconnect(runId: string) {
    const ws = this.connections.get(runId)
    if (ws) {
      ws.close()
      this.connections.delete(runId)
    }
    const timeout = this.retryTimeouts.get(runId)
    if (timeout) {
      clearTimeout(timeout)
      this.retryTimeouts.delete(runId)
    }
    this.handlers.delete(runId)
    this.retryCount.delete(runId)
  }

  disconnectAll() {
    this.connections.forEach((ws) => ws.close())
    this.connections.clear()
    this.retryTimeouts.forEach((t) => clearTimeout(t))
    this.retryTimeouts.clear()
    this.handlers.clear()
    this.retryCount.clear()
  }
}

export const wsService = new WebSocketService()
