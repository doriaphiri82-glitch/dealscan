function checkPublicEnvironment(env) {
  for (const name of Object.keys(env)) {
    if (/^NEXT_PUBLIC_.*(?:SERVICE_ROLE|SECRET_KEY)/i.test(name) && env[name]) {
      throw new Error('A privileged credential is configured as a public environment variable. Remove it before building.')
    }
  }
  const key = env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  if (!key) return
  if (key.startsWith('sb_publishable_')) return
  try {
    const payload = JSON.parse(Buffer.from(key.split('.')[1], 'base64url').toString())
    if (payload.role === 'anon') return
  } catch {}
  throw new Error('NEXT_PUBLIC_SUPABASE_ANON_KEY must be an anon/publishable key, never a service-role or secret key.')
}
module.exports = { checkPublicEnvironment }
