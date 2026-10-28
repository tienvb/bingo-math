import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { GameConfig } from '@/api/contract'
import { readJson, readString, removeKey, writeJson, writeString } from '@/utils/storage'

/** Token và thông tin đã lưu cho một PIN. */
export type PinSession = {
  host_token?: string
  screen_token?: string
  player_token?: string
  player_id?: string
}

const KEY_SESSION = (pin: string) => `bingo.session.${pin}`
const KEY_LAST_CONFIG = 'bingo.lastConfig'
const KEY_JOIN_BASE = 'bingo.joinBaseUrl'
const KEY_LAST_PLAYER = 'bingo.lastPlayer'

// ---- Hàm thuần (dùng được cả ngoài Pinia, ví dụ trong api/rest.ts) ----

export function loadPinSession(pin: string): PinSession {
  return readJson<PinSession>(KEY_SESSION(pin)) ?? {}
}

export function savePinSession(pin: string, patch: Partial<PinSession>): PinSession {
  const next = { ...loadPinSession(pin), ...patch }
  writeJson(KEY_SESSION(pin), next)
  return next
}

export function clearPinSession(pin: string, keys?: (keyof PinSession)[]): void {
  if (!keys) {
    removeKey(KEY_SESSION(pin))
    return
  }
  const cur = loadPinSession(pin)
  for (const k of keys) delete cur[k]
  writeJson(KEY_SESSION(pin), cur)
}

export function getHostToken(pin: string): string | undefined {
  return loadPinSession(pin).host_token
}

export function loadLastConfig(): GameConfig | null {
  return readJson<GameConfig>(KEY_LAST_CONFIG)
}

export function saveLastConfig(config: GameConfig): void {
  writeJson(KEY_LAST_CONFIG, config)
}

/** Địa chỉ join đặt tay đã nhớ (null nếu chưa đặt). */
export function loadJoinBaseOverride(): string | null {
  return readString(KEY_JOIN_BASE)
}

export function saveJoinBaseOverride(url: string | null): void {
  if (url) writeString(KEY_JOIN_BASE, url)
  else removeKey(KEY_JOIN_BASE)
}

/** Thứ tự chọn join base URL theo spec: địa chỉ đặt tay → window.location.origin. */
export function resolveJoinBaseUrl(): string {
  return loadJoinBaseOverride() ?? window.location.origin
}

/** Đã lưu host token cho PIN này chưa (dùng cho trang chủ / điều hướng). */
export function hasHostToken(pin: string): boolean {
  return !!loadPinSession(pin).host_token
}

/** Tên và nhân vật lần trước của người chơi trên máy này (điền sẵn). */
export type LastPlayer = { nickname: string; avatar_id: string }

export function loadLastPlayer(): LastPlayer | null {
  const v = readJson<LastPlayer>(KEY_LAST_PLAYER)
  return v && typeof v.nickname === 'string' && typeof v.avatar_id === 'string' ? v : null
}

export function saveLastPlayer(v: LastPlayer): void {
  writeJson(KEY_LAST_PLAYER, v)
}

// ---- Pinia store ----

export const useSessionStore = defineStore('session', () => {
  const joinBaseOverride = ref<string | null>(loadJoinBaseOverride())

  function get(pin: string): PinSession {
    return loadPinSession(pin)
  }

  function set(pin: string, patch: Partial<PinSession>): PinSession {
    return savePinSession(pin, patch)
  }

  function clear(pin: string, keys?: (keyof PinSession)[]): void {
    clearPinSession(pin, keys)
  }

  function setJoinBaseOverride(url: string | null): void {
    saveJoinBaseOverride(url)
    joinBaseOverride.value = url
  }

  return {
    joinBaseOverride,
    get,
    set,
    clear,
    loadLastConfig,
    saveLastConfig,
    setJoinBaseOverride,
    resolveJoinBaseUrl,
  }
})
