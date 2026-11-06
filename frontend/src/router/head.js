import { PAGE_META, SITE_URL, OG_IMAGE } from '../config/landing.js'

// Tag list shared by the client (applyHead) and the static index.html
// (vite.config.js), so crawlers that don't run JS see the same tags.
export function headTags(meta = {}) {
  const title = meta.title ? withBrand(meta.title) : PAGE_META.title
  const description = meta.description ?? PAGE_META.description
  // Share cards can differ from the page's own title and description.
  const ogTitle = meta.ogTitle ?? title
  const ogDescription = meta.ogDescription ?? description
  const tags = [
    ['name', 'description', description],
    ['property', 'og:type', 'website'],
    ['property', 'og:site_name', 'buysafe'],
    ['property', 'og:locale', 'en_NG'],
    ['property', 'og:title', ogTitle],
    ['property', 'og:description', ogDescription],
    ['name', 'twitter:card', OG_IMAGE ? 'summary_large_image' : 'summary'],
  ]
  if (SITE_URL) tags.push(['property', 'og:url', SITE_URL])
  if (OG_IMAGE) tags.push(['property', 'og:image', OG_IMAGE])
  return { title, tags }
}

function withBrand(title) {
  return title.startsWith('buysafe') ? title : `${title} · buysafe`
}

export function applyHead(meta) {
  const { title, tags } = headTags(meta)
  document.title = title
  for (const [attr, key, content] of tags) {
    let el = document.head.querySelector(`meta[${attr}="${key}"]`)
    if (!el) {
      el = document.createElement('meta')
      el.setAttribute(attr, key)
      document.head.appendChild(el)
    }
    el.setAttribute('content', content)
  }
}
