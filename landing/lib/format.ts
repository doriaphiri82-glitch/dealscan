const usd=new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',minimumFractionDigits:0,maximumFractionDigits:2})

/** Keep sourced cents visible; unavailable values are never formatted as zero. */
export function formatCurrency(value?:number|null,unknown='—'):string {
  return typeof value==='number'&&Number.isFinite(value)?usd.format(value):unknown
}
