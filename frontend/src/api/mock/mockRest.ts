import type { RestApi } from '../rest'
import { getHostToken } from '@/stores/session'
import { MOCK_AVATARS } from './avatars'
import { mockServer, type MockServer } from './server'

const LATENCY_MS = 80

/** Gọi hàm của mock server với độ trễ nhỏ; lỗi ApiError được chuyển thành Promise reject. */
function call<T>(fn: () => T): Promise<T> {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      try {
        resolve(JSON.parse(JSON.stringify(fn())) as T)
      } catch (e) {
        reject(e)
      }
    }, LATENCY_MS)
  })
}

export function createMockRestApi(server: MockServer, hostToken: (pin: string) => string | undefined = getHostToken): RestApi {
  return {
    createRoom: (body) => call(() => server.createRoom(body)),
    getRoom: (pin) => call(() => server.getRoom(pin)),
    lookup: (pictures) => call(() => server.lookup(pictures)),
    closeRoom: (pin) => call(() => server.closeRoom(pin, hostToken(pin))),
    updateConfig: (pin, config) => call(() => server.updateConfig(pin, hostToken(pin), config)),
    updateJoinBaseUrl: (pin, url) => call(() => server.updateJoinBaseUrl(pin, hostToken(pin), url)),
    kickPlayer: (pin, id) => call(() => server.kickPlayer(pin, hostToken(pin), id)),
    start: (pin, body) => call(() => server.start(pin, hostToken(pin), body)),
    next: (pin) => call(() => server.next(pin, hostToken(pin))),
    skip: (pin) => call(() => server.skip(pin, hostToken(pin))),
    help: (pin) => call(() => server.help(pin, hostToken(pin))),
    end: (pin) => call(() => server.end(pin, hostToken(pin))),
    newRound: (pin, body) => call(() => server.newRound(pin, hostToken(pin), body?.join_base_url)),
    join: (pin, body) => call(() => server.join(pin, body)),
    avatars: () => call(() => MOCK_AVATARS),
    network: () => call(() => ({ ips: ['192.168.1.15'], port: 5173 })),
    health: () => call(() => ({ ok: true })),
  }
}

export const mockRestApi: RestApi = createMockRestApi(mockServer)
