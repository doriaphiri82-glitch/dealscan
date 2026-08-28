# DealScan AI

**AI-Powered Vacant Land Deal Finder**

Find profitable land deals while you sleep. Our AI scans county records daily,
identifies motivated sellers, calculates profit potential, and delivers the
top 5-10 deals to your inbox every morning.

## Project Structure

```
dealscan/
├── landing/          # Next.js landing page + waitlist
│   ├── app/          # App router (pages, API routes)
│   ├── components/   # React components
│   └── data/         # Waitlist email storage
├── pipeline/         # Python data pipeline (core engine)
│   ├── config/       # County configs + settings
│   ├── scrapers/     # County data collection
│   ├── scoring/      # Deal scoring algorithm
│   ├── delivery/     # Email delivery system
│   ├── data/         # SQLite database
│   └── main.py       # Pipeline orchestrator
└── dashboard/        # Web dashboard (future)
```

## Quick Start

### Landing Page
```bash
cd landing
npm install
npm run dev
# Visit http://localhost:3000
```

### Data Pipeline
```bash
cd pipeline
python3 main.py --setup-db   # Initialize database
python3 main.py --demo       # Run with demo data
python3 main.py --deliver    # Send deals to subscribers
```

## Pricing Model

| Tier | Price | Features |
|------|-------|----------|
| Free | $0/mo | 3 deals/week (48hr delay), community read-only |
| Pro | $297/mo | 5-10 deals daily, full analysis, all tools |
| Elite | $697/mo | Everything + 1-on-1 coaching, priority alerts |

**Founding Members:** $197/mo locked forever (first 20 members)

## Tech Stack

- **Landing:** Next.js 14, Tailwind CSS, TypeScript
- **Pipeline:** Python 3.11, SQLite, Requests, BeautifulSoup
- **Email:** Resend/SendGrid
- **Deployment:** Vercel (landing), Railway/Render (pipeline)
- **Store:** Whop.com
- **Community:** Discord

## Status

- [x] Landing page built
- [x] Waitlist email collection
- [x] Deal scoring algorithm
- [x] Profit estimation engine
- [x] Motivated seller detection
- [x] Email delivery system
- [x] Demo pipeline (3 test deals)
- [ ] County scrapers (real data)
- [ ] Whop store setup
- [ ] Discord community
- [ ] Deploy to production
