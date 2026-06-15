import './styles.css'
import Alpine from 'alpinejs'
import htmx from 'htmx.org'

// Alpine.js
window.Alpine = Alpine
Alpine.start()

// HTMX
window.htmx = htmx

// Injecte automatiquement le token CSRF Django dans tous les hx-post
document.addEventListener('htmx:configRequest', e => {
  const m = document.cookie.match(/csrftoken=([^;]+)/)
  if (m) e.detail.headers['X-CSRFToken'] = m[1]
})
