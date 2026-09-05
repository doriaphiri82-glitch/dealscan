const usd=new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',minimumFractionDigits:0,maximumFractionDigits:2})

/** Keep sourced cents visible; unavailable values are never formatted as zero. */
export function formatCurrency(value?:number|null,unknown='—'):string {
  if(typeof value!=='number'||!Number.isFinite(value))return unknown
  if(value>0&&value<.01)return '<$0.01'
  if(value<0&&value>-.01)return '>-$0.01'
  return usd.format(value)
}
