// What one row on the deals list says: design/deals-1…3-*. The pill tone
// decides its colours: turn (marigold, your turn), wait (grey outline),
// meetup (green outline), done (green tint), refunded (red tint).
// TODO: pills for states the references don't show (the seller waiting for a
// rating or a decision, the buyer with no meetup set) reuse nearby wording.
import { naira } from '@/utils/format'
import { REFUND_REASONS, ago, hoursMinutes, meetupShort, personName } from '@/utils/deals'

export function rowPill(row, mobile) {
  const seller = row.role === 'seller'
  const n = row.video_count + 1
  switch (row.state) {
    case 'awaiting_video':
      return seller
        ? { tone: 'turn', text: 'YOUR TURN · RECORD VIDEO' }
        : { tone: 'wait', text: mobile ? `WAITING · VIDEO ${n} OF 3` : `WAITING FOR SELLER · VIDEO ${n} OF 3` }
    case 'video_to_rate':
      return seller
        ? { tone: 'wait', text: mobile ? 'WAITING · BUYER TO RATE' : 'WAITING FOR BUYER · RATING' }
        : { tone: 'turn', text: 'YOUR TURN · RATE VIDEO' }
    case 'awaiting_decision':
      return seller
        ? { tone: 'wait', text: mobile ? 'WAITING · BUYER TO DECIDE' : 'WAITING FOR BUYER · DECISION' }
        : { tone: 'turn', text: 'YOUR TURN · REFUND OR CONTINUE' }
    case 'chat_open': {
      const meetup = row.meetup
      if (meetup && meetup.status === 'confirmed' && new Date(meetup.when) > new Date()) {
        return { tone: 'meetup', text: `MEETUP · ${meetupShort(meetup.when).toUpperCase()}` }
      }
      return seller
        ? { tone: 'wait', text: mobile ? 'WAITING · BUYER TO CONFIRM' : 'WAITING FOR BUYER · CONFIRM' }
        : { tone: 'meetup', text: 'NEXT · MEET, THEN CONFIRM' }
    }
    case 'released':
      if (!seller) return { tone: 'done', text: 'RELEASED TO SELLER' }
      if (mobile) return { tone: 'done', text: `RELEASED · ${naira(row.payout)} SENT` }
      return row.payout_account
        ? { tone: 'done', text: `RELEASED · SENT TO ${row.payout_account.bank_short.toUpperCase()} ····${row.payout_account.last4}` }
        : { tone: 'done', text: 'RELEASED' }
    default: {
      const reason = REFUND_REASONS[row.refund?.reason]
      return { tone: 'refunded', text: reason ? `REFUNDED · ${mobile ? reason.short : reason.pill}` : 'REFUNDED' }
    }
  }
}

export function rowWho(row) {
  const name = personName(row.other)
  const closed = row.state === 'released' || row.state === 'refunded'
  if (row.role === 'seller') return { verb: closed ? 'Sold to' : 'Selling to', name }
  return { verb: closed ? 'Bought from' : 'Buying from', name }
}

/** The deadline / time column. */
export function rowTime(row, mobile) {
  if (row.state === 'released') return { text: ago(row.released_at, { short: mobile }), urgent: false }
  if (row.state === 'refunded') return { text: ago(row.refund?.at || row.created_at, { short: mobile }), urgent: false }
  const mine = row.turn === 'me'
  if (row.seconds_left == null) return { text: mobile ? '' : '—', urgent: false }
  const left = hoursMinutes(row.seconds_left)
  return { text: mine || !mobile ? `${left} LEFT` : left, urgent: mine }
}

/** The amount and its label (desktop). */
export function rowMoney(row) {
  if (row.state === 'released') {
    return row.role === 'seller'
      ? { amount: row.payout, label: 'YOU RECEIVED', tone: 'muted' }
      : { amount: row.amount, label: 'YOU PAID', tone: 'muted' }
  }
  if (row.state === 'refunded') {
    const r = row.refund
    const label = r?.bank ? `BACK TO ${r.bank.toUpperCase()} ····${r.last4}` : 'REFUNDED TO BUYER'
    return { amount: row.amount, label, tone: 'muted' }
  }
  return { amount: row.amount, label: 'HELD', tone: 'amber' }
}
