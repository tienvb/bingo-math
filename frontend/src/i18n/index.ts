import { createI18n } from 'vue-i18n'
import vi from './locales/vi.json'
import en from './locales/en.json'
import { readString, writeString } from '@/utils/storage'

export type Lang = 'vi' | 'en'
export const LANGS: Lang[] = ['vi', 'en']
const KEY_LANG = 'bingo.lang'

const isLang = (v: unknown): v is Lang => v === 'vi' || v === 'en'

/** Ưu tiên ?lang= trên URL, rồi localStorage, mặc định vi. */
export function detectLang(): Lang {
  try {
    const q = new URLSearchParams(window.location.search).get('lang')
    if (isLang(q)) {
      writeString(KEY_LANG, q)
      return q
    }
  } catch {
    /* bỏ qua */
  }
  const saved = readString(KEY_LANG)
  return isLang(saved) ? saved : 'vi'
}

type Schema = typeof vi

export const i18n = createI18n<[Schema], Lang, false>({
  legacy: false,
  locale: detectLang(),
  fallbackLocale: 'vi',
  messages: { vi, en },
})

export function setLang(lang: Lang): void {
  i18n.global.locale.value = lang
  writeString(KEY_LANG, lang)
  try {
    document.documentElement.lang = lang
  } catch {
    /* bỏ qua */
  }
}

/** Khóa dịch cho mã lỗi từ server (hoặc lỗi phía client). */
export function errorKey(code: string): string {
  return `errors.${code in vi.errors ? code : 'unknown_error'}`
}
