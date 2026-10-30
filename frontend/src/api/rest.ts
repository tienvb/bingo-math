import type {
  AvatarsResponse,
  CreateRoomRequest,
  CreateRoomResponse,
  ErrorBody,
  ErrorCode,
  GameConfig,
  HealthResponse,
  JoinBaseUrlResponse,
  JoinRequest,
  JoinResponse,
  LookupResponse,
  NetworkResponse,
  NewRoundRequest,
  OkResponse,
  RoomIcon,
  RoomInfoResponse,
  StartRequest,
} from './contract'
import { getHostToken } from '@/stores/session'
import { USE_MOCK } from './gameClient'
import { mockRestApi } from './mock/mockRest'
import { ApiError } from './errors'

export { ApiError }

/** Bảng endpoint trong "Hợp đồng REST API". Các hàm host tự gắn Bearer host token theo PIN. */
export interface RestApi {
  createRoom(body: CreateRoomRequest): Promise<CreateRoomResponse>
  getRoom(pin: string): Promise<RoomInfoResponse>
  lookup(pictures: RoomIcon[]): Promise<LookupResponse>
  closeRoom(pin: string): Promise<OkResponse>
  updateConfig(pin: string, config: GameConfig): Promise<GameConfig>
  updateJoinBaseUrl(pin: string, join_base_url: string): Promise<JoinBaseUrlResponse>
  kickPlayer(pin: string, playerId: string): Promise<OkResponse>
  start(pin: string, body: StartRequest): Promise<OkResponse>
  next(pin: string): Promise<OkResponse>
  skip(pin: string): Promise<OkResponse>
  help(pin: string): Promise<OkResponse>
  end(pin: string): Promise<OkResponse>
  newRound(pin: string, body?: NewRoundRequest): Promise<OkResponse>
  join(pin: string, body: JoinRequest): Promise<JoinResponse>
  avatars(): Promise<AvatarsResponse>
  network(): Promise<NetworkResponse>
  health(): Promise<HealthResponse>
}

type Method = 'GET' | 'POST' | 'PUT' | 'DELETE'

async function request<T>(method: Method, path: string, opts: { body?: unknown; hostPin?: string } = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json'
  if (opts.hostPin) {
    const token = getHostToken(opts.hostPin)
    if (token) headers.Authorization = `Bearer ${token}`
  }
  let res: Response
  try {
    res = await fetch(path, {
      method,
      headers,
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
    })
  } catch (e) {
    throw new ApiError(0, 'network_error', String(e))
  }
  const text = await res.text()
  let json: unknown = null
  try {
    json = text ? JSON.parse(text) : null
  } catch {
    json = null
  }
  if (!res.ok) {
    const err = json as Partial<ErrorBody> | null
    throw new ApiError(res.status, (err?.code as ErrorCode) ?? 'unknown_error', err?.message ?? res.statusText)
  }
  return json as T
}

const p = (pin: string) => `/api/rooms/${encodeURIComponent(pin)}`

export const httpRestApi: RestApi = {
  createRoom: (body) => request('POST', '/api/rooms', { body }),
  getRoom: (pin) => request('GET', p(pin)),
  lookup: (pictures) => request('GET', `/api/rooms/lookup?pictures=${pictures.join(',')}`),
  closeRoom: (pin) => request('DELETE', p(pin), { hostPin: pin }),
  updateConfig: (pin, config) => request('PUT', `${p(pin)}/config`, { body: config, hostPin: pin }),
  updateJoinBaseUrl: (pin, join_base_url) =>
    request('PUT', `${p(pin)}/join-base-url`, { body: { join_base_url }, hostPin: pin }),
  kickPlayer: (pin, playerId) =>
    request('DELETE', `${p(pin)}/players/${encodeURIComponent(playerId)}`, { hostPin: pin }),
  start: (pin, body) => request('POST', `${p(pin)}/start`, { body, hostPin: pin }),
  next: (pin) => request('POST', `${p(pin)}/next`, { hostPin: pin }),
  skip: (pin) => request('POST', `${p(pin)}/skip`, { hostPin: pin }),
  help: (pin) => request('POST', `${p(pin)}/help`, { hostPin: pin }),
  end: (pin) => request('POST', `${p(pin)}/end`, { hostPin: pin }),
  newRound: (pin, body) => request('POST', `${p(pin)}/new-round`, { body: body ?? {}, hostPin: pin }),
  join: (pin, body) => request('POST', `${p(pin)}/join`, { body }),
  avatars: () => request('GET', '/api/avatars'),
  network: () => request('GET', '/api/network'),
  health: () => request('GET', '/api/health'),
}

export const api: RestApi = USE_MOCK ? mockRestApi : httpRestApi
