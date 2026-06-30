import './styles.css'
import Alpine from 'alpinejs'
import htmx from 'htmx.org'
import Sortable from 'sortablejs'

// Composant SVG Editor — enregistré avant Alpine.start() pour être disponible
// après chaque swap HTMX
Alpine.data('svgEditor', ({ densities: d = {} } = {}) => ({
  scale: 1,
  tx: 0,
  ty: 0,
  drag: false,
  sx: 0,
  sy: 0,
  selectedForMerge: null,
  pickerOpen: false,
  pickerTargetHex: null,
  pickerFilter: '',
  densities: { ...d },

  init() {
    const viewer = this.$refs.svgViewer
    if (viewer) {
      viewer.addEventListener('wheel', (e) => {
        e.preventDefault()
        const factor = e.deltaY > 0 ? 0.85 : 1.15
        this.scale = Math.min(Math.max(this.scale * factor, 0.2), 8)
      }, { passive: false })
    }

    const list = this.$el.querySelector('.color-list')
    if (list) {
      Sortable.create(list, {
        handle: '.drag-handle',
        animation: 150,
        ghostClass: 'sortable-ghost',
        chosenClass: 'sortable-chosen',
        dragClass: 'sortable-drag',
        onEnd: (evt) => {
          if (evt.oldIndex === evt.newIndex) return
          const items = Array.from(list.querySelectorAll('[data-color-hex]'))
          const hexes = items.map(el => el.dataset.colorHex)
          const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1] ?? ''
          htmx.ajax('POST', list.dataset.reorderUrl, {
            headers: { 'X-CSRFToken': csrf },
            values: { colors: JSON.stringify(hexes) },
            target: '#conversion-status',
            swap: 'outerHTML',
          })
        },
      })
    }
  },

  down(e) {
    this.drag = true
    this.sx = e.clientX - this.tx
    this.sy = e.clientY - this.ty
  },
  move(e) {
    if (!this.drag) return
    this.tx = e.clientX - this.sx
    this.ty = e.clientY - this.sy
  },
  up() {
    this.drag = false
  },
  reset() {
    this.scale = 1
    this.tx = 0
    this.ty = 0
  },
  openPicker(hex) {
    this.pickerTargetHex = hex
    this.pickerFilter = ''
    this.pickerOpen = true
  },
  closePicker() {
    this.pickerOpen = false
    this.pickerTargetHex = null
  },
  changeColor(newHex, url) {
    const oldHex = this.pickerTargetHex
    this.closePicker()
    const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1] ?? ''
    htmx.ajax('POST', url, {
      headers: { 'X-CSRFToken': csrf },
      values: { old_color: oldHex, new_color: newHex },
      target: '#conversion-status',
      swap: 'outerHTML',
    })
  },
  changeColorFree(newHex, oldHex, url) {
    const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1] ?? ''
    htmx.ajax('POST', url, {
      headers: { 'X-CSRFToken': csrf },
      values: { old_color: oldHex, new_color: newHex },
      target: '#conversion-status',
      swap: 'outerHTML',
    })
  },
}))

window.Alpine = Alpine
Alpine.start()

window.htmx = htmx

document.addEventListener('htmx:configRequest', e => {
  const m = document.cookie.match(/csrftoken=([^;]+)/)
  if (m) e.detail.headers['X-CSRFToken'] = m[1]
})

// Réinitialise Alpine sur les éléments non encore initialisés après chaque swap HTMX.
// Alpine.js v3 utilise MutationObserver mais peut rater les swaps outerHTML
// dans certaines configurations HTMX 2.x.
document.addEventListener('htmx:afterSettle', () => {
  const el = document.getElementById('conversion-status')
  if (el && !el._x_dataStack) Alpine.initTree(el)
})
