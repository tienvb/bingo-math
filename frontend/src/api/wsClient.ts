import {
  WS_CLOSE,
  type ClientMessageMap,
  type ClientMessageType,
  type Role,
  type ServerMessage,
  type ServerMessageType,
} from './contract'
import type { ConnectionStatus, GameClient, ServerHandler } from './gameClient'
import { ServerEmitter } from './emitter'

const PING_MS = 20_000
const BACKOFF_MIN_MS = 1_000
const BACKOFF_MAX_MS = 10_000

/** Mã đóng mà không nên kết nối lại. */
const FINAL_CODES: number[] = [WS_CLOSE.BAD_TOKEN, WS_CLOSE.ROOM_NOT_FOUND, WS_CLOSE.KICKED, WS_CLOSE.ROOM_CLOSED]

export function buildWsUrl(pin: string, role: Role, token: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const q = new URLSearchParams({ pin, role, token })
  return `${proto}//${window.location.host}/ws?${q.toString()}`
}

export class WsGameClient implements GameClient {
  private ws: WebSocket | null = null
  private emitter = new ServerEmitter()
  private params: { pin: string; role: Role; token: string } | null = null
  private backoff = BACKOFF_MIN_MS
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private pingTimer: ReturnType<typeof setInterval> | null = null
  private stopped = false

  connect(pin: string, role: Role, token: string): void {
    this.close()
    this.stopped = false
    this.params = { pin, role, token }
    this.backoff = BACKOFF_MIN_MS
    this.open('connecting')
  }

  on<T extends ServerMessageType>(type: T, fn: ServerHandler<T>): () => void {
    return this.emitter.on(type, fn)
  }

  onStatus(fn: (status: ConnectionStatus, closeCode?: number) => void): () => void {
    return this.emitter.onStatus(fn)
  }

  send<T extends ClientMessageType>(type: T, data: ClientMessageMap[T]): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type, data }))
    }
  }

  close(): void {
    this.stopped = true
    this.clearTimers()
    if (this.ws) {
      const ws = this.ws
      this.ws = null
      ws.onopen = ws.onmessage = ws.onclose = ws.onerror = null
      try {
        ws.close(1000)
      } catch {
        /* bỏ qua */
      }
    }
    this.emitter.emitStatus('closed')
  }

  private open(status: ConnectionStatus): void {
    if (!this.params) return
    this.emitter.emitStatus(status)
    const { pin, role, token } = this.params
    const ws = new WebSocket(buildWsUrl(pin, role, token))
    this.ws = ws

    ws.onopen = () => {
      this.backoff = BACKOFF_MIN_MS
      this.emitter.emitStatus('open')
      this.startPing()
    }
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(String(ev.data)) as ServerMessage
        if (msg && typeof msg.type === 'string') this.emitter.emitMessage(msg)
      } catch (e) {
        console.warn('[ws] bad message', e)
      }
    }
    ws.onclose = (ev) => {
      this.clearTimers()
      this.ws = null
      if (this.stopped || FINAL_CODES.includes(ev.code)) {
        this.stopped = true
        this.emitter.emitStatus('closed', ev.code)
        return
      }
      this.scheduleReconnect()
    }
    ws.onerror = () => {
      /* onclose sẽ xử lý */
    }
  }

  private scheduleReconnect(): void {
    this.emitter.emitStatus('reconnecting')
    const delay = this.backoff
    this.backoff = Math.min(this.backoff * 2, BACKOFF_MAX_MS)
    this.reconnectTimer = setTimeout(() => this.open('reconnecting'), delay)
  }

  private startPing(): void {
    this.pingTimer = setInterval(() => this.send('ping', {}), PING_MS)
  }

  private clearTimers(): void {
    if (this.pingTimer) clearInterval(this.pingTimer)
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    this.pingTimer = null
    this.reconnectTimer = null
  }
}
