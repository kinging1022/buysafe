// Route table, kept free of browser APIs so the prerender step
// (src/entry-server.js) can import it.
import LandingView from '@/views/LandingView.vue'
import { PAGE_META } from '@/config/landing'

// TODO: /vendors/apply, /terms and /privacy are linked from the landing page but
// don't exist yet; they fall through to the not-found route. /messages,
// /wallet, /profile/phone and the listing detail pages are placeholders.
export const routes = [
  {
    path: '/',
    name: 'landing',
    // Eager: this is the entry route, and prerendering needs it synchronously.
    component: LandingView,
    meta: PAGE_META,
  },
  // Auth: lazy-loaded so none of it ships with the landing page.
  // guestOnly: signed-in users are sent to /. requiresPending: /verify needs a
  // phone waiting for its code, otherwise it goes back to /signup.
  {
    path: '/signup',
    name: 'signup',
    component: () => import('@/views/auth/SignUpView.vue'),
    meta: { title: 'Create account', guestOnly: true },
  },
  {
    path: '/verify',
    name: 'verify',
    component: () => import('@/views/auth/VerifyPhoneView.vue'),
    meta: { title: 'Verify your phone', guestOnly: true, requiresPending: true },
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/auth/LoginView.vue'),
    meta: { title: 'Log in', guestOnly: true },
  },
  {
    // Open to everyone: signed-in users reach it from "Forgot it?" on /profile/password.
    path: '/reset-password',
    name: 'reset-password',
    component: () => import('@/views/auth/ResetPasswordView.vue'),
    meta: { title: 'Reset password' },
  },
  // Account: requiresAuth sends signed-out users to /login and back.
  {
    path: '/profile',
    name: 'profile',
    component: () => import('@/views/account/ProfileView.vue'),
    meta: { title: 'Your profile', requiresAuth: true },
  },
  {
    path: '/profile/edit',
    name: 'profile-edit',
    component: () => import('@/views/account/EditProfileView.vue'),
    meta: { title: 'Edit profile', requiresAuth: true },
  },
  {
    path: '/profile/password',
    name: 'profile-password',
    component: () => import('@/views/account/ChangePasswordView.vue'),
    meta: { title: 'Change password', requiresAuth: true },
  },
  // TODO placeholders until these pages are built.
  {
    // Will reuse the OTP flow (purpose change_phone).
    path: '/profile/phone',
    name: 'profile-phone',
    component: () => import('@/views/account/PlaceholderView.vue'),
    meta: { title: 'Change number', requiresAuth: true },
    props: { heading: 'Change number', back: '/profile/edit', backLabel: 'Back to edit profile' },
  },
  // Browse is public; posting needs a signed-in, phone-verified account.
  {
    path: '/listings',
    name: 'listings',
    component: () => import('@/views/listings/ListingsView.vue'),
    meta: { title: 'Browse' },
  },
  {
    path: '/sell',
    name: 'sell',
    component: () => import('@/views/sell/CreateListingView.vue'),
    meta: { title: 'Post an item', requiresAuth: true },
  },
  {
    path: '/sell/:id(\\d+)/edit',
    name: 'sell-edit',
    component: () => import('@/views/sell/CreateListingView.vue'),
    meta: { title: 'Edit your item', requiresAuth: true },
  },
  ...[
    ['/messages', 'Messages'],
    ['/wallet', 'Wallet'],
    // TODO: listing detail, deal and receipt pages.
    ['/listings/:id/:action?', 'Your listing'],
  ].map(([path, heading]) => ({
    path,
    component: () => import('@/views/account/PlaceholderView.vue'),
    meta: { title: heading },
    props: { heading },
  })),
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFoundView.vue'),
    meta: { title: 'Page not found' },
  },
]
