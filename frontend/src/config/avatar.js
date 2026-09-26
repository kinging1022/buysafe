// Avatar colours. The API stores the key; the hex lives only here.
export const AVATAR_COLORS = [
  { key: 'marigold', label: 'Marigold', hex: '#F5B82E' },
  { key: 'lime', label: 'Lime', hex: '#B6E36B' },
  { key: 'sky', label: 'Sky', hex: '#7FD1FF' },
  { key: 'coral', label: 'Coral', hex: '#FF8A65' },
  { key: 'paper', label: 'Paper', hex: '#F3EDE0' },
]

export const avatarHex = (key) => (AVATAR_COLORS.find((c) => c.key === key) || AVATAR_COLORS[0]).hex
