import type { ErrorCode } from './contract'

/** Mã lỗi phía FE, không thuộc hợp đồng (mất mạng, phản hồi lạ). */
export type ClientErrorCode = 'network_error' | 'unknown_error'

/** Lỗi REST: `code` theo hợp đồng; FE dịch theo `code`, `message` chỉ là dự phòng. */
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: ErrorCode | ClientErrorCode,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}
