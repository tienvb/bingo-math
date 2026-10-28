import type {
  ClientMessage,
  ClientMessageMap,
  ClientMessageType,
  Role,
  ServerMessageMap,
  ServerMessageType,
} from '../contract'
import type { ConnectionStatus, GameClient, ServerHandler } from '../gameClient'
import { ServerEmitter } from '../emitter'
import { mockServer, type MockConnection, type MockServer } from './server'

const PING_MS = 20_000

/** GameClient giả: nói chuyện với MockServer trong cùng tab, message đi bất đồng bộ như mạng thật. */
export class MockGameClient implements GameClient {
  private emitter = new ServerEmitter()
  private conn: MockConnection | null = null
  private handler: ((msg: ClientMessage) => void) | null = null
  private pin: string | null = null
  private pingTimer: ReturnType<typeof setInterval> | null = null
  private kill: (() => void) | null = null

  constructor(private server: MockServer = mockServer) {}

  connect(pin: string, role: Role, token: string): void {
    this.close()
    this.pin = pin
    this.emitter.emitStatus('connecting')
    let alive = true
    const conn: MockConnection = {
      role,
      deliver: <T extends ServerMessageType>(type: T, data: ServerMessageMap[T]) => {
        // Sao chép như qua JSON, giao bất đồng bộ nhưng giữ thứ tự.
        const copy = JSON.parse(JSON.stringify(data)) as ServerMessageMap[T]
        queueMicrotask(() => {
          if (alive) this.emitter.emit(type, copy)
        })
      },
      terminate: (code: number) => {
        queueMicrotask(() => {
          if (!alive) return
          alive = false
          this.stopPing()
          this.conn = null
          this.handler = null
          this.emitter.emitStatus('closed', code)
        })
      },
    }
    this.conn = conn
    this.kill = () => {
      alive = false
    }
    queueMicrotask(() => {
      if (!alive) return
      this.emitter.emitStatus('open')
      this.handler = this.server.connect(pin, role, token, conn)
      if (this.handler) this.pingTimer = setInterval(() => this.send('ping', {}), PING_MS)
    })
  }

  on<T extends ServerMessageType>(type: T, fn: ServerHandler<T>): () => void {
    return this.emitter.on(type, fn)
  }

  onStatus(fn: (status: ConnectionStatus, closeCode?: number) => void): () => void {
    return this.emitter.onStatus(fn)
  }

  send<T extends ClientMessageType>(type: T, data: ClientMessageMap[T]): void {
    const h = this.handler
    if (!h) return
    const msg = JSON.parse(JSON.stringify({ type, data })) as ClientMessage
    queueMicrotask(() => h(msg))
  }

  close(): void {
    this.stopPing()
    if (this.conn && this.pin) {
      this.kill?.()
      this.server.disconnect(this.pin, this.conn)
      this.emitter.emitStatus('closed')
    }
    this.conn = null
    this.handler = null
    this.kill = null
  }

  private stopPing(): void {
    if (this.pingTimer) clearInterval(this.pingTimer)
    this.pingTimer = null
  }
}
