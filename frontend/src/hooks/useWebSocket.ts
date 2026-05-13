import { useEffect, useCallback, useRef } from 'react'
import { wsService } from '../services/websocket'
import type { WebSocketMessage } from '../types'

export function useWebSocket(
  runId: string | null,
  onMessage: (msg: WebSocketMessage) => void
) {
  const handlerRef = useRef(onMessage)
  handlerRef.current = onMessage

  const stableHandler = useCallback((msg: WebSocketMessage) => {
    handlerRef.current(msg)
  }, [])

  useEffect(() => {
    if (!runId) return

    wsService.connect(runId).catch(() => {})
    wsService.subscribe(runId, stableHandler)

    return () => {
      wsService.unsubscribe(runId, stableHandler)
    }
  }, [runId, stableHandler])
}
