import type { Avatar } from '../contract'
// Lottie mẫu để thử nhánh win_animation_url (.json) trong mock.
import winDemoUrl from './win-demo.json?url'

// Ảnh tạm cho mock: hình tròn màu kèm chữ cái đầu, cùng dạng dữ liệu Avatar.
const RAW: { id: string; vi: string; en: string; color: string }[] = [
  { id: 'capybara', vi: 'Chuột lang nước', en: 'Capybara', color: '#C08A5B' },
  { id: 'cat', vi: 'Mèo', en: 'Cat', color: '#F4A261' },
  { id: 'rabbit', vi: 'Thỏ', en: 'Rabbit', color: '#E98FB3' },
  { id: 'bear', vi: 'Gấu', en: 'Bear', color: '#8D6E63' },
  { id: 'panda', vi: 'Gấu trúc', en: 'Panda', color: '#455A64' },
  { id: 'fox', vi: 'Cáo', en: 'Fox', color: '#EF6C00' },
  { id: 'penguin', vi: 'Chim cánh cụt', en: 'Penguin', color: '#3F51B5' },
  { id: 'frog', vi: 'Ếch', en: 'Frog', color: '#43A047' },
  { id: 'duck', vi: 'Vịt', en: 'Duck', color: '#FBC02D' },
  { id: 'unicorn', vi: 'Kỳ lân', en: 'Unicorn', color: '#AB47BC' },
  { id: 'dinosaur', vi: 'Khủng long', en: 'Dinosaur', color: '#26A69A' },
  { id: 'owl', vi: 'Cú', en: 'Owl', color: '#795548' },
]

function placeholder(letter: string, color: string): string {
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">` +
    `<circle cx="128" cy="128" r="120" fill="${color}"/>` +
    `<text x="128" y="160" font-family="Arial,sans-serif" font-size="110" font-weight="bold" text-anchor="middle" fill="#fff">${letter}</text>` +
    `</svg>`
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
}

export const MOCK_AVATARS: Avatar[] = RAW.map((r) => ({
  id: r.id,
  name: { vi: r.vi, en: r.en },
  image_url: placeholder(r.en[0], r.color),
  win_animation_url: r.id === 'unicorn' ? winDemoUrl : null,
  color: r.color,
}))
