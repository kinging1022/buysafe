// What the deal page's escrow card says in each state: design/deal-00…11-*.
// Everything here is derived from GET /api/deals/:id/ for the viewer.
// TODO: states the references don't show (the seller while the buyer rates
// or decides, the seller at the meetup, the refunded deal from the seller's
// side, a no-show refund) reuse the nearest designed wording.
import { naira } from '@/utils/format'
import { REFUND_REASONS, clock, dayClock, meetupShort, meetupWhen, shortDayClock, shortTitle, stamp } from '@/utils/deals'

const up = (s) => (s || '').toUpperCase()
const lowerFirst = (s) => (s ? s.charAt(0).toLowerCase() + s.slice(1) : s)

export const nextVideo = (d) => (d.state === 'awaiting_video' ? d.video_count + 1 : d.video_count)

/** "show the back, closer, and the dent up close" */
export function askSentence(instructions) {
  if (!instructions) return ''
  const parts = [...(instructions.chips || []).map(lowerFirst)]
  if (instructions.note) parts.push(lowerFirst(instructions.note).replace(/[.!\s]+$/, ''))
  if (parts.length <= 1) return parts.join('')
  if (parts.length === 2) return `${parts[0]} and ${parts[1]}`
  return `${parts.slice(0, -1).join(', ')}, and ${parts[parts.length - 1]}`
}

export function cardLabel(d) {
  const role = d.role === 'seller' ? 'SELLING' : 'BUYING'
  return `DEAL ${d.id} · ${up(shortTitle(d.listing.title))} · ${up(d.seller_first_name)} → ${up(d.buyer_first_name)} · YOU’RE ${role}`
}

export function escrowStamp(d) {
  if (d.state === 'released') return { text: 'RELEASED', color: '#B6E36B', sub: `released to ${d.seller_first_name}`, short: 'released' }
  if (d.state === 'refunded') return { text: 'REFUNDED', color: '#FF8A65', sub: `refunded to ${d.buyer_first_name}`, short: 'refunded' }
  return { text: 'HELD SAFE', color: '#F5B82E', sub: 'held in escrow', short: 'held in escrow' }
}

/** The 5 steps: [{ label, meta, status: done | current | todo | failed | refunded }] */
export function timeline(d, { mobile = false } = {}) {
  const meetup = d.meetup && d.meetup.status === 'confirmed' ? d.meetup : null
  const met = meetup && new Date(meetup.when) <= new Date()
  const video = { label: 'Seller’s live video', meta: '—', status: 'current' }
  const meet = { label: 'Meet', meta: meetup ? up(mobile ? meetupShort(meetup.when) : meetupWhen(meetup.when)) : '—', status: 'todo' }
  const confirm = { label: 'Buyer confirms', meta: d.confirmed_at ? up(shortDayClock(d.confirmed_at)) : '—', status: 'todo' }
  const last = { label: 'Released', meta: d.released_at ? up(shortDayClock(d.released_at)) : '—', status: 'todo' }

  if (d.state === 'awaiting_video') {
    video.meta = d.video_count ? `VIDEO ${d.video_count + 1} OF 3` : `DUE ${clock(d.deadline)}`
  } else if (d.state === 'video_to_rate') {
    video.meta = `DUE ${clock(d.deadline)}`
  } else if (d.state === 'awaiting_decision') {
    video.meta = '3 OF 3 · BAD'
  } else {
    video.status = 'done'
    video.meta = d.video_accepted_at ? `ACCEPTED ${clock(d.video_accepted_at)}` : d.video_count ? `${d.video_count} OF 3` : '—'
  }

  if (d.state === 'chat_open') {
    if (met) {
      meet.status = 'done'
      meet.meta = `${up(meetupShort(meetup.when))} · DONE`
      confirm.status = 'current'
    } else {
      meet.status = 'current'
    }
  } else if (d.state === 'released') {
    meet.status = confirm.status = last.status = 'done'
    if (meetup) meet.meta = `${up(meetupShort(meetup.when))} · DONE`
  } else if (d.state === 'refunded') {
    const reason = d.refund?.reason
    if (reason === 'seller_missed_video' || reason === 'cancelled_after_3_bad') {
      video.status = 'failed'
      if (reason === 'seller_missed_video') video.meta = `DUE ${clock(d.refunded_at)}`
    } else {
      meet.status = 'failed'
    }
    last.label = 'Refunded'
    last.status = 'refunded'
    last.meta = d.refunded_at ? up(stamp(d.refunded_at)).replace(/^(\d)/, 'TODAY $1') : '—'
  }
  return [{ label: 'Paid', meta: up(stamp(d.paid_at)), status: 'done' }, video, meet, confirm, last]
}

/** The turn banner under the card. tone: turn | wait | next | done | refunded. */
export function banner(d, { mobile = false, picking = false } = {}) {
  const buyer = d.buyer_first_name
  const seller = d.seller_first_name
  const item = shortTitle(d.listing.title)
  const n = nextVideo(d)
  const mine = d.role
  const refundTo = d.refund?.bank ? `${up(d.refund.bank)} ····${d.refund.last4}` : up(buyer)

  switch (d.state) {
    case 'awaiting_video':
      if (mine === 'seller') {
        if (d.video_count === 0) {
          return {
            tone: 'turn',
            eyebrow: mobile ? 'YOUR TURN · RECORD LIVE VIDEO' : 'YOUR TURN · RECORD YOUR LIVE VIDEO',
            text: `${buyer} has paid. Show the ${item} working, from every side. Your chat unlocks after ${buyer} rates it.`,
            countdown: true,
            action: 'record',
          }
        }
        return {
          tone: 'turn',
          eyebrow: mobile ? `YOUR TURN · VIDEO ${n} OF 3` : `YOUR TURN · RE-RECORD · VIDEO ${n} OF 3`,
          text: `${buyer} asked: ${askSentence(d.requested)}.`,
          countdown: true,
          action: 'record',
        }
      }
      return {
        tone: 'wait',
        eyebrow: mobile ? `WAITING FOR ${up(seller)}’S VIDEO` : `WAITING FOR ${up(seller)} · LIVE VIDEO ${n} OF 3`,
        text: 'If no video arrives in time, the deal is cancelled and you’re refunded in full.',
        countdown: true,
      }
    case 'video_to_rate':
      if (mine === 'buyer') {
        if (picking) {
          return {
            tone: 'turn',
            eyebrow: mobile ? 'YOUR TURN · SAY WHAT TO SHOW' : `YOUR TURN · TELL ${up(seller)} WHAT TO SHOW`,
            text: `Pick what’s missing. ${seller} gets a new 4-hour window for video ${d.video_count + 1} of 3.`,
            countdown: true,
          }
        }
        return {
          tone: 'turn',
          eyebrow: 'YOUR TURN · RATE THE VIDEO',
          text: 'Watch it, then tap Good or Bad below. No rating in time counts as Good.',
          countdown: true,
        }
      }
      return {
        tone: 'wait',
        eyebrow: `WAITING FOR ${up(buyer)} · RATING VIDEO ${d.video_count} OF 3`,
        text: 'No rating in time counts as Good, and your chat unlocks.',
        countdown: true,
      }
    case 'awaiting_decision':
      if (mine === 'buyer') {
        return {
          tone: 'turn',
          eyebrow: mobile ? 'YOUR TURN · REFUND OR CONTINUE' : 'YOUR TURN · DECIDE',
          text: 'All 3 videos were rated bad. Cancel for a full refund, or continue to the meetup.',
        }
      }
      return {
        tone: 'wait',
        eyebrow: `WAITING FOR ${up(buyer)} · REFUND OR CONTINUE`,
        text: `All 3 videos were rated bad. ${buyer} chooses a refund or the meetup.`,
      }
    case 'chat_open': {
      const meetup = d.meetup && d.meetup.status === 'confirmed' ? d.meetup : null
      if (mine === 'buyer') {
        return {
          tone: 'next',
          eyebrow: mobile
            ? `NEXT · ${meetup ? `MEET ${up(meetupShort(meetup.when))}` : 'MEET'}, THEN CONFIRM`
            : `NEXT · MEET AND CHECK${meetup ? ` · ${up(meetupWhen(meetup.when))}` : ''}`,
          text: `Confirm only with the ${item} in your hands. The money is released when you do.`,
          action: 'confirm',
        }
      }
      return {
        tone: 'next',
        eyebrow: mobile
          ? `NEXT · ${meetup ? `MEET ${up(meetupShort(meetup.when))}` : 'MEET'}, THEN ${up(buyer)} CONFIRMS`
          : `NEXT · MEET${meetup ? ` · ${up(meetupWhen(meetup.when))}` : ''}`,
        text: `${buyer} confirms with the ${item} in hand, and the money is released to you.`,
      }
    }
    case 'released':
      if (mine === 'seller') {
        const acct = d.payout_account
        const where = acct ? `${up(mobile ? acct.bank_short : acct.bank_name)} ····${acct.last4}` : ''
        return {
          tone: 'done',
          eyebrow: mobile ? `COMPLETE · ${naira(d.payout)} SENT TO ${where}` : `COMPLETE · ${naira(d.payout)} SENT TO YOUR ${where}`,
          text: `${buyer} confirmed the ${item}. Thanks for selling safe.`,
        }
      }
      return {
        tone: 'done',
        eyebrow: mobile ? `COMPLETE · RELEASED TO ${up(seller)}` : `COMPLETE · ${naira(d.amount)} RELEASED TO ${up(seller)}`,
        text: `Deal closed ${dayClock(d.released_at)}. The chat stays readable.`,
      }
    default: {
      const reason = d.refund?.reason
      let text = 'The deal was cancelled and the money went back to the paying account.'
      if (reason === 'seller_missed_video') text = `${seller} didn’t send a live video within 4 hours, so the deal was cancelled.`
      else if (reason === 'cancelled_after_3_bad') text = 'All 3 videos were rated bad, so the deal was cancelled.'
      else if (reason === 'no_show') text = 'The deal was cancelled after a no-show was reported.'
      return {
        tone: 'refunded',
        eyebrow: mobile ? `REFUNDED · BACK TO ${refundTo}` : `REFUNDED · ${naira(d.amount)} BACK TO ${refundTo}`,
        text,
      }
    }
  }
}

export const refundReason = (d) => REFUND_REASONS[d.refund?.reason]?.long || ''
