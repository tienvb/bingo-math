import type {
  ClientMessageMap,
  ClientMessageType,
  Role,
  ServerMessageMap,
  ServerMessageType,
} from './contract'
import { WsGameClient } from './wsClient'
import { MockGameClient } from './mock/mockClient'

export type ConnectionStatus = 'idle' | 'connecting' | 'open' | 'reconnecting' | 'closed'

export type ServerHandler<T extends ServerMessageType> = (data: ServerMessageMap[T]) => void

/**
 * Transport giữa FE và server. Bản thật: wsClient.ts; bản giả: mock/mockClient.ts.
 * `onStatus` là phần mở rộng nội bộ FE (không thuộc hợp đồng) để UI biết trạng thái kết nối
 * và mã đóng (4401, 4403, 4404, 4410).
 */
export interface GameClient {
  connect(pin: string, role: Role, token: string): void
  /** Đăng ký nghe một loại message; trả về hàm hủy đăng ký. */
  on<T extends ServerMessageType>(type: T, fn: ServerHandler<T>): () => void
  send<T extends ClientMessageType>(type: T, data: ClientMessageMap[T]): void
  close(): void
  onStatus(fn: (status: ConnectionStatus, closeCode?: number) => void): () => void
}

export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

export function createGameClient(): GameClient {
  return USE_MOCK ? new MockGameClient() : new WsGameClient()
}
