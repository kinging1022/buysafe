import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

import { headTags } from './src/router/head.js'

// Writes the landing page's title, description and Open Graph tags into
// index.html so crawlers that don't run JavaScript still see them.
function staticHead() {
  const escape = (s) => s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;')
  return {
    name: 'static-head',
    transformIndexHtml(html) {
      const { title, tags } = headTags()
      const markup = [
        `<title>${escape(title)}</title>`,
        ...tags.map(([attr, key, content]) => `<meta ${attr}="${key}" content="${escape(content)}">`),
      ].join('\n    ')
      return html.replace(/<!-- head:meta[^>]*-->/, markup)
    },
  }
}

const apiTarget = process.env.API_PROXY_TARGET || 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
    staticHead(),
  ],
  // Same-origin API in dev/preview so the Django session + CSRF cookies just work.
  // /media is uploaded listing photos. Override the Django address with
  // API_PROXY_TARGET=http://127.0.0.1:8001 etc.
  server: { proxy: { '/api': apiTarget, '/media': apiTarget } },
  preview: { proxy: { '/api': apiTarget, '/media': apiTarget } },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
})
