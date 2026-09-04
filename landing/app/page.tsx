'use client'

import Navbar from '@/components/Navbar'
import ScrollReveal from '@/components/ScrollReveal'
import Hero from '@/components/Hero'
import Problem from '@/components/Problem'
import Audience from '@/components/Audience'
import Solution from '@/components/Solution'
import HowItWorks from '@/components/HowItWorks'
import SampleDeal from '@/components/SampleDeal'
import Pricing from '@/components/Pricing'
import FAQ from '@/components/FAQ'
import FinalCTA from '@/components/FinalCTA'
import Footer from '@/components/Footer'

export default function Home() {
  return (
    <>
      <ScrollReveal />
      <Navbar />
      <main id="main-content" className="min-h-screen bg-[#f7f9f7] text-[#15211b] selection:bg-[#dceee3] selection:text-[#153025]">
        <Hero />
        <Problem />
        <Audience />
        <Solution />
        <HowItWorks />
        <SampleDeal />
        <Pricing />
        <FAQ />
        <FinalCTA />
      </main>
      <Footer />
    </>
  )
}
