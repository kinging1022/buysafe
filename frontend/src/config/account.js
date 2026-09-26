// Routes the signed-in pages link to. Messages, Wallet, Change number and the
// listing detail/deal/receipt pages are still TODO placeholders.
export const ROUTES = {
  browse: '/listings',
  messages: '/messages',
  wallet: '/wallet',
  sell: '/sell',
  changePhone: '/profile/phone',
}

export const listingLinks = (id) => ({
  view: `/listings/${id}`,
  edit: `/sell/${id}/edit`,
  deal: `/listings/${id}/deal`, // TODO
  receipt: `/listings/${id}/receipt`, // TODO
})

// TODO: the review SLA. Keep the placeholder until it's confirmed.
export const REVIEW_SLA = '[X HOURS]'
