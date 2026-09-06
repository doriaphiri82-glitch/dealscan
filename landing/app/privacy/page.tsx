import Link from 'next/link'
import { supportContact } from '@/lib/support'
export const dynamic = 'force-dynamic'

export default function PrivacyPage() {
  const contact=supportContact()
  return <main id="main-content" className="min-h-screen bg-[#f7f9f7] px-6 py-16 text-[#203029]"><article className="mx-auto max-w-3xl rounded-3xl border border-[#dfe7e2] bg-white p-7 sm:p-10">
    <Link href="/" className="text-sm font-bold text-[#176b45]">← DealScan</Link><h1 className="mt-8 text-3xl font-black">Privacy & data handling</h1>
    <div className="mt-8 space-y-7 text-sm leading-7 text-[#64716a]">
      <section><h2 className="text-lg font-bold text-[#203029]">Product-update requests</h2><p>If you explicitly consent, the site stores your email address, consent timestamp and signup channel in a private Supabase table. These requests are for DealScan product updates, not automatic deal alerts or a paid subscription. New and existing addresses receive the same public response.</p><p>Signups require a configured database and operator contact. No successful signup is claimed when durable storage is unavailable.</p></section>
      <section><h2 className="text-lg font-bold text-[#203029]">Browser research</h2><p>Saved parcels and recent research are kept in this browser profile, not a cloud-synced account. Anyone using the same browser profile may see them, even after signing out. Clear the saved list in the workspace or clear this site's browser storage to remove it.</p></section>
      <section><h2 className="text-lg font-bold text-[#203029]">Parcel data and providers</h2><p>Published opportunities contain parcel identifiers, location, source references and verified screening calculations. Owner names, mailing addresses and raw ingestion audits are not part of the public API. Source and map links lead to third-party websites with their own practices.</p><p>Supabase provides database and authentication services. The hosting provider may maintain operational request logs under its configured policies. Signup rate limiting stores a keyed request token, not a raw IP address; expired rate buckets are cleaned opportunistically.</p></section>
      <section><h2 className="text-lg font-bold text-[#203029]">Contact and removal</h2>{contact?<p>Contact the site operator at <a className="font-semibold text-[#176b45] underline" href={`mailto:${contact}`}>{contact}</a> to ask about your signup request or request its removal. Do not post email addresses or private research in public issue trackers.</p>:<p>An operator contact is not configured, so new signup requests are disabled. The operator must provide contact details before collection is enabled.</p>}<p>Signup records remain until removed by the operator or a configured retention process. This application does not claim an automatic email-retention schedule or legal certification.</p></section>
    </div>
  </article></main>
}
