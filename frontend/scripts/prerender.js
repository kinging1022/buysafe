// Prerenders the landing route (/) into dist/index.html.
// Run via `npm run build`, after the client and SSR builds.
import { readFile, rm, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('..', import.meta.url))
const ssrDir = `${root}dist-ssr`
const indexPath = `${root}dist/index.html`

const { render } = await import(`${ssrDir}/entry-server.js`)
const appHtml = await render('/')

const template = await readFile(indexPath, 'utf8')
const marker = '<div id="app"></div>'
if (!template.includes(marker)) throw new Error(`prerender: ${marker} not found in dist/index.html`)

await writeFile(indexPath, template.replace(marker, `<div id="app">${appHtml}</div>`))
await rm(ssrDir, { recursive: true, force: true })

console.log(`prerender: wrote / (${(appHtml.length / 1024).toFixed(1)} KB of HTML)`)
