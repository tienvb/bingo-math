// Đồng bộ mock giữa nhiều tab (CHANGELOG 2026-10-28): một tab giữ engine (leader), các tab khác
// (follower) chuyển REST và WS giả qua BroadcastChannel. Leader được bầu bằng Web Locks; leader đóng
// hoặc tải lại thì tab kế tiếp trong hàng đợi lên thay, khôi phục state đã lưu trong localStorage,
// và mọi kết nối tự kết nối lại (mã đóng 1012).
// Không có BroadcastChannel / Web Locks (ví dụ http qua IP LAN): mỗi tab tự giữ engine riêng.

import type { ClientMessage, Role, ServerMessageMap, ServerMessageType } from '../contract'
import { ApiError } from '../errors'
import { readJson, writeJson } from '@/utils/storage'
import { randomId } from './algorithms'
import { mockServer, type ServerState } from './server'
import { LocalTransport, type ConnHandle, type ConnSink, type MockTransport, type ServerMethod } from './transport'

const CHANNEL = 'bingo-mock-v1'
const LOCK = 'bingo-mock-leader-v1'
const STATE_KEY = 'bingo.mock.state'
const STATE_MAX_AGE_MS = 30 * 60_000
const REST_TIMEOUT_MS = 8000
const OPEN_TIMEOUT_MS = 4000
/** Mã đóng khi leader đổi: client giả sẽ tự kết nối lại. */
export const CLOSE_LEADER_CHANGED = 1012

type Wire =
  | { k: 'leader'; from: string }
  | { k: 'bye'; from: string }
  | { k: 'rest'; from: string; id: string; method: ServerMethod; args: unknown[] }
  | { k: 'rest-res'; to: string; id: string; ok: true; value: unknown }
  | { k: 'rest-res'; to: string; id: string; ok: false; status: number; code: string; message: string }
  | { k: 'open'; from: string; connId: string; pin: string; role: Role; token: string }
  | { k: 'opened'; to: string; connId: string }
  | { k: 'msg'; to: string; connId: string; type: ServerMessageType; data: unknown }
  | { k: 'term'; to: string; connId: string; code: number }
  | { k: 'send'; from: string; connId: string; msg: ClientMessage }
  | { k: 'close'; from: string; connId: string }

type HubConn = {
  id: string
  pin: string
  role: Role
  token: string
  sink: ConnSink
  local: ConnHandle | null
  openTimer: ReturnType<typeof setTimeout> | null
  dead: boolean
}

type Pending = { resolve: (v: unknown) => void; reject: (e: unknown) => void; timer: ReturnType<typeof setTimeout> }

class TabHub implements MockTransport {
  private readonly tabId = randomId(10)
  private readonly local = new LocalTransport(mockServer)
  private channel: BroadcastChannel | null = null
  private mode: 'pending' | 'leader' | 'follower' = 'pending'
  private readyResolve!: () => void
  private readonly readyP = new Promise<void>((r) => (this.readyResolve = r))
  private readonly own = new Map<string, HubConn>()
  private readonly pending = new Map<string, Pending>()
  /** Leader: kết nối của các tab khác. */
  private readonly remote = new Map<string, { from: string; handle: ConnHandle }>()
  private persistTimer: ReturnType<typeof setInterval> | null = null

  constructor() {
    const hasBC = typeof BroadcastChannel !== 'undefined'
    const locks = typeof navigator !== 'undefined' ? navigator.locks : undefined
    if (!hasBC || !locks) {
      this.becomeLeader(false)
      return
    }
    this.channel = new BroadcastChannel(CHANNEL)
    this.channel.onmessage = (ev: MessageEvent<Wire>) => this.onWire(ev.data)
    window.addEventListener('pagehide', () => this.onPageHide())
    const hold = () => new Promise<void>(() => {})
    locks
      .request(LOCK, { ifAvailable: true }, (lock) => {
        if (lock) {
          this.becomeLeader(false)
          return hold()
        }
        this.mode = 'follower'
        this.readyResolve()
        void locks.request(LOCK, () => {
          this.becomeLeader(true)
          return hold()
        })
        return undefined
      })
      .catch(() => this.becomeLeader(false))
  }

  // ---------------- MockTransport ----------------

  async invoke(method: ServerMethod, args: unknown[]): Promise<unknown> {
    await this.readyP
    if (this.mode === 'leader') return this.local.invoke(method, args)
    const id = randomId(12)
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id)
        reject(new ApiError(0, 'network_error', 'mock leader timeout'))
      }, REST_TIMEOUT_MS)
      this.pending.set(id, { resolve, reject, timer })
      this.post({ k: 'rest', from: this.tabId, id, method, args })
    })
  }

  open(pin: string, role: Role, token: string, sink: ConnSink): ConnHandle {
    const c: HubConn = { id: randomId(12), pin, role, token, sink, local: null, openTimer: null, dead: false }
    this.own.set(c.id, c)
    void this.readyP.then(() => !c.dead && this.attach(c))
    return {
      send: (msg) => {
        if (c.dead) return
        if (c.local) c.local.send(msg)
        else if (this.mode === 'follower') this.post({ k: 'send', from: this.tabId, connId: c.id, msg })
      },
      close: () => {
        if (c.dead) return
        c.dead = true
        this.own.delete(c.id)
        if (c.openTimer) clearTimeout(c.openTimer)
        if (c.local) c.local.close()
        else if (this.mode === 'follower') this.post({ k: 'close', from: this.tabId, connId: c.id })
      },
    }
  }

  // ---------------- nội bộ ----------------

  private attach(c: HubConn): void {
    if (this.mode === 'leader') {
      c.local = this.local.open(c.pin, c.role, c.token, {
        opened: () => c.sink.opened(),
        deliver: (t, d) => c.sink.deliver(t, d),
        terminate: (code) => this.killOwn(c, code, false),
      })
      return
    }
    c.openTimer = setTimeout(() => this.killOwn(c, 1006, true), OPEN_TIMEOUT_MS)
    this.post({ k: 'open', from: this.tabId, connId: c.id, pin: c.pin, role: c.role, token: c.token })
  }

  /** Kết nối của tab này bị đóng; `notify` thì báo leader (nếu là follower). */
  private killOwn(c: HubConn, code: number, notify: boolean): void {
    if (c.dead) return
    c.dead = true
    this.own.delete(c.id)
    if (c.openTimer) clearTimeout(c.openTimer)
    if (notify && !c.local && this.mode === 'follower') this.post({ k: 'close', from: this.tabId, connId: c.id })
    c.local = null
    c.sink.terminate(code)
  }

  private dropAllOwn(): void {
    ;[...this.own.values()].forEach((c) => {
      if (c.local) c.local.close()
      this.killOwn(c, CLOSE_LEADER_CHANGED, false)
    })
    this.pending.forEach((p) => {
      clearTimeout(p.timer)
      p.reject(new ApiError(0, 'network_error', 'mock leader changed'))
    })
    this.pending.clear()
  }

  private becomeLeader(takeover: boolean): void {
    const st = readJson<{ savedAt: number; state: ServerState }>(STATE_KEY)
    if (st && Date.now() - st.savedAt < STATE_MAX_AGE_MS) {
      try {
        mockServer.importState(st.state)
      } catch (e) {
        console.warn('[mock] cannot restore state', e)
      }
    }
    if (takeover) this.dropAllOwn()
    this.mode = 'leader'
    this.persistTimer = setInterval(() => this.persist(), 1000)
    this.post({ k: 'leader', from: this.tabId })
    this.readyResolve()
  }

  private persist(): void {
    if (this.mode !== 'leader') return
    writeJson(STATE_KEY, { savedAt: Date.now(), state: mockServer.exportState() })
  }

  private onPageHide(): void {
    if (this.mode === 'leader') {
      this.persist()
      if (this.persistTimer) clearInterval(this.persistTimer)
    } else {
      this.post({ k: 'bye', from: this.tabId })
    }
  }

  private post(m: Wire): void {
    try {
      this.channel?.postMessage(m)
    } catch (e) {
      console.warn('[mock] postMessage failed', e)
    }
  }

  private onWire(m: Wire): void {
    if ('to' in m && m.to !== this.tabId) return
    if ('from' in m && m.from === this.tabId) return
    switch (m.k) {
      case 'leader':
        // Tab khác vừa lên làm leader: mọi kết nối của tab này phải kết nối lại.
        if (this.mode === 'follower') this.dropAllOwn()
        return
      case 'rest-res': {
        const p = this.pending.get(m.id)
        if (!p) return
        this.pending.delete(m.id)
        clearTimeout(p.timer)
        if (m.ok) p.resolve(m.value)
        else p.reject(new ApiError(m.status, m.code as never, m.message))
        return
      }
      case 'opened': {
        const c = this.own.get(m.connId)
        if (!c) return
        if (c.openTimer) clearTimeout(c.openTimer)
        c.openTimer = null
        c.sink.opened()
        return
      }
      case 'msg': {
        const c = this.own.get(m.connId)
        if (c) c.sink.deliver(m.type, m.data as ServerMessageMap[typeof m.type])
        return
      }
      case 'term': {
        const c = this.own.get(m.connId)
        if (c) this.killOwn(c, m.code, false)
        return
      }
    }
    if (this.mode !== 'leader') return
    switch (m.k) {
      case 'rest':
        this.local.invoke(m.method, m.args).then(
          (value) => this.post({ k: 'rest-res', to: m.from, id: m.id, ok: true, value }),
          (e: unknown) => {
            const err = e instanceof ApiError ? e : new ApiError(500, 'unknown_error', String(e))
            this.post({ k: 'rest-res', to: m.from, id: m.id, ok: false, status: err.status, code: err.code, message: err.message })
          },
        )
        return
      case 'open': {
        const { connId, from } = m
        const handle = this.local.open(m.pin, m.role, m.token, {
          opened: () => this.post({ k: 'opened', to: from, connId }),
          deliver: (type, data) => this.post({ k: 'msg', to: from, connId, type, data }),
          terminate: (code) => {
            this.remote.delete(connId)
            this.post({ k: 'term', to: from, connId, code })
          },
        })
        this.remote.set(connId, { from, handle })
        return
      }
      case 'send':
        this.remote.get(m.connId)?.handle.send(m.msg)
        return
      case 'close': {
        const r = this.remote.get(m.connId)
        if (r) {
          this.remote.delete(m.connId)
          r.handle.close()
        }
        return
      }
      case 'bye':
        this.remote.forEach((r, id) => {
          if (r.from !== m.from) return
          this.remote.delete(id)
          r.handle.close()
        })
        return
    }
  }
}

let hub: TabHub | null = null

/** Hub dùng chung cho cả tab, tạo khi cần lần đầu. */
export function getHub(): MockTransport {
  if (!hub) hub = new TabHub()
  return hub
}

/** Transport trì hoãn: chỉ tạo hub khi thật sự gọi (để import trong test không mở BroadcastChannel). */
export const lazyHub: MockTransport = {
  invoke: (m, a) => getHub().invoke(m, a),
  open: (p, r, t, s) => getHub().open(p, r, t, s),
}

export type { ConnSink }
