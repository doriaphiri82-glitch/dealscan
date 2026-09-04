import type { Metadata, Viewport } from 'next'
import './globals.css'
import CommandPalette from '@/components/CommandPalette'

export const metadata: Metadata = {
  title: 'DealScan — Land Deal Intelligence',
  description: 'DealScan screens property data, comparable sales, seller signals, and market context to help land investors identify parcels worth investigating.',
  keywords: ['land investing', 'property data', 'deal screening', 'comparable sales', 'land deals'],
  openGraph: {
    title: 'DealScan — Land Deal Intelligence',
    description: 'Screen property data, compare sales, and identify parcels worth investigating.',
    type: 'website',
  },
}

export const viewport: Viewport = {
  themeColor: '#F7F9F7',
  width: 'device-width',
  initialScale: 1,
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased">
        <a href="#main-content" className="skip-link">Skip to content</a>
        {children}
        <CommandPalette />
      </body>
    </html>
  )
}
