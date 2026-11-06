import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it } from 'vitest'
import { buildRoutes } from '@/router/routes'

async function visit(prelaunch, url) {
  const router = createRouter({ history: createMemoryHistory(), routes: buildRoutes(prelaunch) })
  await router.push(url)
  return router.currentRoute.value
}

describe('routes', () => {
  it('serves the pre-launch page at / in pre-launch mode', async () => {
    const route = await visit(true, '/')
    expect(route.name).toBe('prelaunch')
    expect(route.meta.ogTitle).toBe('buysafe · Money that waits')
  })

  it.each(['/listings', '/sell', '/signup', '/deals/12', '/nope'])('redirects %s to / in pre-launch mode', async (url) => {
    expect((await visit(true, url)).path).toBe('/')
  })

  it('keeps utm params through the redirect', async () => {
    const route = await visit(true, '/listings?utm_source=ig&utm_campaign=launch')
    expect(route.path).toBe('/')
    expect(route.query).toEqual({ utm_source: 'ig', utm_campaign: 'launch' })
  })

  it.each(['/login', '/reset-password'])('keeps the staff auth page %s in pre-launch mode', async (url) => {
    expect((await visit(true, url)).path).toBe(url)
  })

  it('serves the normal landing page when pre-launch mode is off', async () => {
    expect((await visit(false, '/')).name).toBe('landing')
    expect((await visit(false, '/listings')).name).toBe('listings')
  })
})
