import process from 'node:process'
import { URL } from 'node:url'

// Vercel embeds this public API origin into the static bundle.
// Local builds may omit it; hosted builds must point to the HTTPS API.
if (process.env.VERCEL) {
  const raw = (process.env.VITE_API_URL ?? '').trim()
  let url
  try { url = new URL(raw) } catch { url = null }
  if (!url || url.protocol !== 'https:' || /^(localhost|127\.|0\.0\.0\.0|\[::1\])$/i.test(url.hostname)) {
    process.stderr.write('Set VITE_API_URL to the HTTPS origin of the deployed FastAPI service in Vercel project settings.\n')
    process.exit(1)
  }
}
