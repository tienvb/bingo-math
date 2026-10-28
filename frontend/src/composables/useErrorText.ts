import { useI18n } from 'vue-i18n'
import { ApiError } from '@/api/errors'
import { errorKey } from '@/i18n'

/** Dịch lỗi theo `code` (REST: ApiError, WS: ErrorBody); `message` chỉ là dự phòng. */
export function useErrorText() {
  const { t } = useI18n()
  return (e: unknown): string => {
    if (e instanceof ApiError) return t(errorKey(e.code))
    if (e && typeof e === 'object' && 'code' in e) return t(errorKey(String((e as { code: unknown }).code)))
    return t(errorKey('unknown_error'))
  }
}

export function errorCode(e: unknown): string | null {
  if (e && typeof e === 'object' && 'code' in e) return String((e as { code: unknown }).code)
  return null
}
