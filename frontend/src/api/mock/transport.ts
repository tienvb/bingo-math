// Lớp vận chuyển giữa "client" và MockServer.
// - LocalTransport: gọi thẳng MockServer trong cùng tab (test, hoặc tab đang giữ engine).
// - TabHub (hub.ts): đồng bộ nhiều tab qua BroadcastChannel, một tab giữ engine.

import type { ClientMessage, Role, ServerMessageMap, ServerMessageType } from '../contract'
import { ApiError } from '../errors'
import type { MockConnection, MockServer } from './server'

/** Các hàm REST của MockServer mà client được gọi. */
export type ServerMethod =
  | 'createRoom' | 'getRoom' | 'lookup' | 'closeRoom' | 'updateConfig' | 'updateJoinBaseUrl'
  | 'kickPlayer' | 'start' | 'next' | 'skip' | 'help' | 'end' | 'newRound' | 'join'

/** Nơi nhận dữ liệu của một kết nối WS giả. */
export interface ConnSink {
  opened(): void
  deliver<T extends ServerMessageType>(type: T, data: ServerMessageMap[T]): void
  terminate(code: number): void
}

export interface ConnHandle {
  send(msg: ClientMessage): void
  close(): void
}

export interface MockTransport {
  invoke(method: ServerMethod, args: unknown[]): Promise<unknown>
  open(pin: string, role: Role, token: string, sink: ConnSink): ConnHandle
}

export const LATENCY_MS = 80

const clone = <T>(v: T): T => (v === undefined ? v : (JSON.parse(JSON.stringify(v)) as T))
/** Sao chép tham số như qua mạng; giữ `undefined` (tham số tùy chọn) và bỏ Proxy reactive của Vue. */
export const cloneArgs = (args: unknown[]): unknown[] => args.map((a) => clone(a))

export class LocalTransport implements MockTransport {
  constructor(readonly server: MockServer) {}

  invoke(method: ServerMethod, args: unknown[]): Promise<unknown> {
    return new Promise((resolve, reject) => {
      setTimeout(() => {
        try {
          const fn = this.server[method] as (...a: unknown[]) => unknown
          resolve(clone(fn.apply(this.server, cloneArgs(args))))
        } catch (e) {
          reject(e instanceof ApiError ? e : new ApiError(500, 'unknown_error', String(e)))
        }
      }, LATENCY_MS)
    })
  }

  open(pin: string, role: Role, token: string, sink: ConnSink): ConnHandle {
    let alive = true
    let handler: ((msg: ClientMessage) => void) | null = null
    const conn: MockConnection = {
      role,
      // Sao chép như qua JSON, giao bất đồng bộ nhưng giữ thứ tự.
      deliver: (type, data) => {
        const copy = clone(data)
        queueMicrotask(() => alive && sink.deliver(type, copy))
      },
      terminate: (code) => {
        queueMicrotask(() => {
          if (!alive) return
          alive = false
          handler = null
          sink.terminate(code)
        })
      },
    }
    queueMicrotask(() => {
      if (!alive) return
      sink.opened()
      handler = this.server.connect(pin, role, token, conn)
    })
    return {
      send: (msg) => {
        const copy = clone(msg)
        queueMicrotask(() => alive && handler?.(copy))
      },
      close: () => {
        if (!alive) return
        alive = false
        handler = null
        this.server.disconnect(pin, conn)
      },
    }
  }
}
