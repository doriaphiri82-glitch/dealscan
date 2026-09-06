function roleOf(token) {
  try {
    const parts=token.split('.')
    if(parts.length!==3||!parts.every(part=>/^[A-Za-z0-9_-]+$/.test(part)))return null
    return JSON.parse(Buffer.from(parts[1],'base64url').toString())?.role ?? null
  } catch { return null }
}

function privilegedValue(value) {
  if(typeof value!=='string')return false
  if(/sb_secret_|-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----/.test(value))return true
  return (value.match(/[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g)||[])
    .some(token=>{const role=roleOf(token);return typeof role==='string'&&role!=='anon'})
}

function checkPublicEnvironment(env) {
  for(const [name,value] of Object.entries(env)) {
    if(/^NEXT_PUBLIC_/i.test(name)&&value&&(
      /(?:SERVICE_ROLE|SECRET_KEY|PRIVATE_KEY)/i.test(name)||privilegedValue(value))) {
      // Names/values are deliberately omitted from build logs.
      throw new Error('A privileged credential is configured as a public environment variable. Remove it before building.')
    }
  }
  const key=env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  if(!key)return
  if(/^sb_publishable_[A-Za-z0-9_-]+$/.test(key)||roleOf(key)==='anon')return
  throw new Error('NEXT_PUBLIC_SUPABASE_ANON_KEY must be an anon/publishable key, never a service-role or secret key.')
}
module.exports={checkPublicEnvironment}
