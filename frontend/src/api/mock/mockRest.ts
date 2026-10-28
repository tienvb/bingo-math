import type { RestApi } from '../rest'
import { getHostToken } from '@/stores/session'
import { MOCK_AVATARS } from './avatars'
import { MockServer } from './server'
import { LATENCY_MS, LocalTransport, cloneArgs, type MockTransport, type ServerMethod } from './transport'
import { lazyHub } from './hub'

const later = <T>(v: T): Promise<T> => new Promise((r) => setTimeout(() => r(JSON.parse(JSON.stringify(v)) as T), LATENCY_MS))

/**
 * REST giả theo đúng bảng endpoint. Lời gọi đi qua MockTransport (cùng tab hoặc qua tab giữ engine);
 * host token đọc từ localStorage của tab gọi, như header Bearer của bản thật.
 */
export function createMockRestApi(
  target: MockServer | MockTransport,
  hostToken: (pin: string) => string | undefined = getHostToken,
): RestApi {
  const t = target instanceof MockServer ? new LocalTransport(target) : target
  const call = <R>(method: ServerMethod, ...args: unknown[]) => t.invoke(method, cloneArgs(args)) as Promise<R>
  return {
    createRoom: (body) => call('createRoom', body),
    getRoom: (pin) => call('getRoom', pin),
    lookup: (pictures) => call('lookup', pictures),
    closeRoom: (pin) => call('closeRoom', pin, hostToken(pin)),
    updateConfig: (pin, config) => call('updateConfig', pin, hostToken(pin), config),
    updateJoinBaseUrl: (pin, url) => call('updateJoinBaseUrl', pin, hostToken(pin), url),
    kickPlayer: (pin, id) => call('kickPlayer', pin, hostToken(pin), id),
    start: (pin, body) => call('start', pin, hostToken(pin), body),
    next: (pin) => call('next', pin, hostToken(pin)),
    skip: (pin) => call('skip', pin, hostToken(pin)),
    help: (pin) => call('help', pin, hostToken(pin)),
    end: (pin) => call('end', pin, hostToken(pin)),
    newRound: (pin, body) => call('newRound', pin, hostToken(pin), body?.join_base_url),
    join: (pin, body) => call('join', pin, body),
    avatars: () => later(MOCK_AVATARS),
    network: () => later({ ips: ['192.168.1.15'], port: Number(window.location.port) || 80 }),
    health: () => later({ ok: true }),
  }
}

export const mockRestApi: RestApi = createMockRestApi(lazyHub)
