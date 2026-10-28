import type { ServerMessage, ServerMessageMap, ServerMessageType } from './contract'
import type { ConnectionStatus, ServerHandler } from './gameClient'

/** Bộ phát sự kiện dùng chung cho wsClient và mockClient. */
export class ServerEmitter {
  private handlers = new Map<ServerMessageType, Set<(data: unknown) => void>>()
  private statusHandlers = new Set<(s: ConnectionStatus, code?: number) => void>()

  on<T extends ServerMessageType>(type: T, fn: ServerHandler<T>): () => void {
    let set = this.handlers.get(type)
    if (!set) {
      set = new Set()
      this.handlers.set(type, set)
    }
    const h = fn as (data: unknown) => void
    set.add(h)
    return () => set!.delete(h)
  }

  emit<T extends ServerMessageType>(type: T, data: ServerMessageMap[T]): void {
    this.handlers.get(type)?.forEach((fn) => {
      try {
        fn(data)
      } catch (e) {
        console.error('[game] handler error', type, e)
      }
    })
  }

  emitMessage(msg: ServerMessage): void {
    this.emit(msg.type, msg.data as never)
  }

  onStatus(fn: (s: ConnectionStatus, code?: number) => void): () => void {
    this.statusHandlers.add(fn)
    return () => this.statusHandlers.delete(fn)
  }

  emitStatus(s: ConnectionStatus, code?: number): void {
    this.statusHandlers.forEach((fn) => fn(s, code))
  }
}
