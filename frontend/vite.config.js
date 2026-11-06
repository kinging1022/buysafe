import { fileURLToPath, URL } from 'node:url'

import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

import { headTags } from './src/router/head.js'
import { PRELAUNCH_META } from './src/config/prelaunch.js'

// Writes the landing page's title, description and Open Graph tags into
// index.html so crawlers that don't run JavaScript still see them. In
// pre-launch mode (VITE_PRELAUNCH=true) they're the pre-launch page's.
function staticHead(meta) {
  const escape = (s) => s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;')
  return {
    name: 'static-head',
    transformIndexHtml(html) {
      const { title, tags } = headTags(meta)
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
export default defineConfig(({ mode }) => ({
  plugins: [
    vue(),
    vueDevTools(),
    staticHead(loadEnv(mode, process.cwd()).VITE_PRELAUNCH === 'true' ? PRELAUNCH_META : undefined),
  ],
  // Same-origin API in dev/preview so the Django session + CSRF cookies just work.
  // /media is uploaded listing photos. Override the Django address with
  // API_PROXY_TARGET=http://127.0.0.1:8001 etc.
  // allowedHosts: a Cloudflare quick tunnel (any *.trycloudflare.com) for phone/webhook testing.
  server: { proxy: { '/api': apiTarget, '/media': apiTarget }, allowedHosts: ['.trycloudflare.com'] },
  preview: { proxy: { '/api': apiTarget, '/media': apiTarget } },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
}))
