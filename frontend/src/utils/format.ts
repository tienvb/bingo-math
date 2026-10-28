import type { Operator, Question } from '@/api/contract'

/** Ký hiệu phép tính theo ngôn ngữ (spec *Song ngữ*): chia là ":" ở vi, "÷" ở en; nhân là "×". */
export function operatorSymbol(op: Operator, locale: string): string {
  switch (op) {
    case '+':
      return '+'
    case '-':
      return '−'
    case 'x':
      return '×'
    case ':':
      return locale === 'en' ? '÷' : ':'
  }
}

/** Phép tính do FE tự dựng từ operator, a, b; `text` chỉ dùng dự phòng. */
export function expression(q: Pick<Question, 'operator' | 'a' | 'b' | 'text'>, locale: string): string {
  if (!q || typeof q.a !== 'number' || typeof q.b !== 'number') return q?.text ?? ''
  return `${q.a} ${operatorSymbol(q.operator, locale)} ${q.b} = ?`
}

/** PIN hiển thị cách quãng: "4 7 2 9". */
export function spacedPin(pin: string): string {
  return pin.split('').join(' ')
}

/** Thêm ?lang=<ngôn ngữ> vào join_url để QR mở đúng ngôn ngữ. */
export function withLang(url: string, lang: string): string {
  if (!url) return ''
  try {
    const u = new URL(url)
    u.searchParams.set('lang', lang)
    return u.toString()
  } catch {
    return url
  }
}

export function isLocalHost(hostname: string): boolean {
  const h = hostname.toLowerCase()
  return h === 'localhost' || h === '127.0.0.1' || h === '[::1]' || h === '::1' || h.endsWith('.localhost')
}
