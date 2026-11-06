// What a profile card (desktop) or row (mobile) shows for each display status.
// Copy is from design/profile-tab-all-*.reference.html.
import { REVIEW_SLA, dealLinks, listingLinks } from '@/config/account'
import { dayTime, naira, relativeTime } from '@/utils/format'

const MUTED = '#5B5E55'
const AMBER = '#A86A0C'
const RED = '#A3361F'
const GREEN = '#1E6B45'

function interestNote(n) {
  if (!n) return ''
  return n === 1 ? '1 person asked about this' : `${n} people asked about this`
}

const withPeriod = (text) => (/[.!?]$/.test(text) ? text : `${text}.`)

// "Open deal" / "Receipt" go to the deal page; older sales without one fall
// back to the listing.
const dealOrListing = (item) => (item.deal_id ? dealLinks(item.deal_id).view : listingLinks(item.id).view)

/** Desktop card: meta line, note line and the primary action. */
export function cardDisplay(item) {
  const links = listingLinks(item.id)
  const posted = `Posted ${relativeTime(item.created_at)}`
  const meta = item.display_status === 'sold' ? `Sold ${relativeTime(item.sold_at)}` : [item.area, posted].filter(Boolean).join(' · ')

  switch (item.display_status) {
    case 'in_escrow':
      return {
        meta,
        note: item.meetup_at ? `Buyer paid. Meeting set for ${dayTime(item.meetup_at)}.` : 'Buyer paid. Deal in progress.',
        noteColor: AMBER,
        action: { label: 'Open deal', to: dealOrListing(item) },
      }
    case 'pending':
      return { meta, note: `Usually reviewed within ${REVIEW_SLA}`, noteColor: MUTED, action: { label: 'Edit', to: links.edit } }
    case 'rejected':
      return { meta, note: item.rejection_reason, noteColor: RED, action: { label: 'Fix & resubmit', to: links.edit } }
    case 'sold':
      return {
        meta,
        note: item.payout != null ? `You received ${naira(item.payout)}` : '',
        noteColor: GREEN,
        action: { label: 'Receipt', to: dealOrListing(item) },
      }
    default: // live
      return { meta, note: interestNote(item.interest_count), noteColor: MUTED, action: { label: 'Edit', to: links.edit } }
  }
}

/** Mobile row: the one line under the price, and where tapping the row goes. */
export function rowDisplay(item) {
  const links = listingLinks(item.id)
  switch (item.display_status) {
    case 'in_escrow':
      return {
        line: item.meetup_at ? `Meeting set for ${dayTime(item.meetup_at)}` : 'Buyer paid. Deal in progress.',
        color: AMBER,
        to: dealOrListing(item),
      }
    case 'pending':
      return { line: `Reviewed within ${REVIEW_SLA}`, color: MUTED, to: links.view }
    case 'rejected':
      return {
        line: item.rejection_reason ? `${withPeriod(item.rejection_reason)} Tap to fix.` : 'Tap to fix.',
        color: RED,
        to: links.edit,
      }
    case 'sold':
      return {
        line: item.payout != null ? `You received ${naira(item.payout)}` : `Sold ${relativeTime(item.sold_at)}`,
        color: GREEN,
        to: dealOrListing(item),
      }
    default: // live
      return {
        line: [item.area, relativeTime(item.created_at)].filter(Boolean).join(' · '),
        color: MUTED,
        to: links.view,
      }
  }
}
