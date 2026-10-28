import type { ClientMessageMap, ClientMessageType, Role, ServerMessageType } from '../contract'
import { WS_CLOSE } from '../contract'
import type { ConnectionStatus, GameClient, ServerHandler } from '../gameClient'
import { ServerEmitter } from '../emitter'
import { MockServer } from './server'
import { LocalTransport, type ConnHandle, type MockTransport } from './transport'
import { lazyHub } from './hub'

const PING_MS = 20_000
const RECONNECT_MS = 1000
/** Mã đóng không kết nối lại (CHANGELOG 2026-10-28: 4401, 4403, 4404, 4409, 4410). */
const FINAL_CODES: number[] = [1000, WS_CLOSE.BAD_TOKEN, WS_CLOSE.ROOM_NOT_FOUND, WS_CLOSE.KICKED, WS_CLOSE.REPLACED, WS_CLOSE.ROOM_CLOSED]

/**
 * GameClient giả: nói chuyện với MockServer qua MockTransport (cùng tab hoặc qua BroadcastChannel).
 * Tự kết nối lại khi kết nối bị cắt không phải vì lý do cuối (ví dụ đổi tab giữ engine).
 */
export class MockGameClient implements GameClient {
  private emitter = new ServerEmitter()
  private transport: MockTransport
  private handle: ConnHandle | null = null
  private params: { pin: string; role: Role; token: string } | null = null
  private pingTimer: ReturnType<typeof setInterval> | null = null
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private generation = 0

  constructor(target: MockServer | MockTransport = lazyHub) {
    this.transport = target instanceof MockServer ? new LocalTransport(target) : target
  }

  connect(pin: string, role: Role, token: string): void {
    this.close()
    this.params = { pin, role, token }
    this.open('connecting')
  }

  on<T extends ServerMessageType>(type: T, fn: ServerHandler<T>): () => void {
    return this.emitter.on(type, fn)
  }

  onStatus(fn: (status: ConnectionStatus, closeCode?: number) => void): () => void {
    return this.emitter.onStatus(fn)
  }

  send<T extends ClientMessageType>(type: T, data: ClientMessageMap[T]): void {
    this.handle?.send(JSON.parse(JSON.stringify({ type, data })) as never)
  }

  close(): void {
    this.generation++
    this.stopTimers()
    if (this.handle) {
      this.handle.close()
      this.handle = null
      this.emitter.emitStatus('closed')
    }
    this.params = null
  }

  private open(status: ConnectionStatus): void {
    const p = this.params
    if (!p) return
    const gen = ++this.generation
    this.emitter.emitStatus(status)
    this.handle = this.transport.open(p.pin, p.role, p.token, {
      opened: () => {
        if (gen !== this.generation) return
        this.emitter.emitStatus('open')
        this.pingTimer = setInterval(() => this.send('ping', {}), PING_MS)
      },
      deliver: (type, data) => {
        if (gen === this.generation) this.emitter.emit(type, data)
      },
      terminate: (code) => {
        if (gen !== this.generation) return
        this.stopTimers()
        this.handle = null
        if (FINAL_CODES.includes(code)) {
          this.generation++
          this.emitter.emitStatus('closed', code)
          return
        }
        this.emitter.emitStatus('reconnecting')
        this.reconnectTimer = setTimeout(() => this.open('reconnecting'), RECONNECT_MS)
      },
    })
  }

  private stopTimers(): void {
    if (this.pingTimer) clearInterval(this.pingTimer)
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    this.pingTimer = null
    this.reconnectTimer = null
  }
}
