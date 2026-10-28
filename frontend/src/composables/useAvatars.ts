import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Avatar } from '@/api/contract'
import { api } from '@/api/rest'
import { useGameStore } from '@/stores/game'

let loading: Promise<void> | null = null

/** Danh sách nhân vật từ GET /api/avatars (tải một lần, lưu trong game store). */
export function useAvatars() {
  const game = useGameStore()
  const { locale } = useI18n()

  function load(force = false): Promise<void> {
    if (!force && (game.avatars.length || loading)) return loading ?? Promise.resolve()
    loading = api
      .avatars()
      .then((list) => game.setAvatars(list))
      .catch((e) => {
        console.warn('[avatars] load failed', e)
      })
      .finally(() => (loading = null))
    return loading
  }
  void load()

  const byId = (id: string | null | undefined): Avatar | undefined => (id ? game.avatarMap.get(id) : undefined)
  const nameOf = (a: Avatar | undefined): string => (a ? (locale.value === 'en' ? a.name.en : a.name.vi) : '')

  return { avatars: computed(() => game.avatars), byId, nameOf, load }
}
