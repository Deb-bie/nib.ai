/** Shared language metadata used across the app */

export const LANG_FLAGS = {
  spanish:    '🇪🇸',
  french:     '🇫🇷',
  german:     '🇩🇪',
  italian:    '🇮🇹',
  portuguese: '🇵🇹',
  mandarin:   '🇨🇳',
}

export const LANG_LABELS = {
  spanish:    'Spanish',
  french:     'French',
  german:     'German',
  italian:    'Italian',
  portuguese: 'Portuguese',
  mandarin:   'Mandarin',
}

/** Returns flag + capitalized name for any language key */
export function langDisplay(key) {
  if (!key) return '—'
  const flag  = LANG_FLAGS[key]  || '🌐'
  const label = LANG_LABELS[key] || (key.charAt(0).toUpperCase() + key.slice(1))
  return `${flag} ${label}`
}
