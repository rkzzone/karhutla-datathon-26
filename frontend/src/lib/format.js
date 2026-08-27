/** Pemformatan angka & waktu. Semua keluaran ditujukan untuk kelas `font-mono`. */

const ZONA = 'Asia/Jakarta'

/** 0.92 → "92%". Kembalikan "—" untuk null, JANGAN "0%". */
export function persen(nilai, digit = 0) {
  if (typeof nilai !== 'number' || Number.isNaN(nilai)) return '—'
  return `${(nilai * 100).toFixed(digit)}%`
}

/** Angka mentah untuk skor hero, tanpa simbol. */
export function angkaPersen(nilai) {
  if (typeof nilai !== 'number' || Number.isNaN(nilai)) return '—'
  return Math.round(nilai * 100).toString()
}

export function jam(iso) {
  if (!iso) return '—'
  return new Intl.DateTimeFormat('id-ID', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: ZONA,
  }).format(new Date(iso))
}

export function tanggalJam(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  const tanggal = new Intl.DateTimeFormat('id-ID', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    timeZone: ZONA,
  }).format(d)
  return `${tanggal} · ${jam(iso)} WIB`
}

/** "12 menit lalu" — relatif terhadap `sekarang` supaya bisa dites. */
export function selangWaktu(iso, sekarang = Date.now()) {
  if (!iso) return '—'
  const menit = Math.round((sekarang - new Date(iso).getTime()) / 60000)
  if (menit < 1) return 'baru saja'
  if (menit < 60) return `${menit} menit lalu`
  const jamLalu = Math.floor(menit / 60)
  if (jamLalu < 24) return `${jamLalu} jam lalu`
  return `${Math.floor(jamLalu / 24)} hari lalu`
}

/** Koordinat gaya instrumen: 4 desimal + hemisfer. */
export function koordinat(lat, lon) {
  if (typeof lat !== 'number' || typeof lon !== 'number') return '—'
  const ns = lat >= 0 ? 'N' : 'S'
  const ew = lon >= 0 ? 'E' : 'W'
  return `${Math.abs(lat).toFixed(4)}°${ns} ${Math.abs(lon).toFixed(4)}°${ew}`
}

/** ID panjang dipendekkan tapi tetap bisa dicocokkan dengan log. */
export function idPendek(alertId) {
  if (!alertId) return '—'
  const potongan = alertId.split('-')
  return `${potongan[0]}…${potongan[potongan.length - 1].slice(-6)}`.toUpperCase()
}

/** Angka teknis Halaman 4 — "—" kalau belum diukur, bukan 0. */
export function angka(nilai, digit = 1, satuan = '') {
  if (typeof nilai !== 'number' || Number.isNaN(nilai)) return '—'
  return `${nilai.toFixed(digit)}${satuan ? ` ${satuan}` : ''}`
}

/**
 * Tanggal saja, tanpa jam — untuk menyebut TANGGAL DATA, bukan waktu proses.
 *
 * Dipisahkan dari `tanggalJam` dengan sengaja. Banner cuplikan hotspot pernah
 * hanya menampilkan waktu pembekuan, sehingga data satelit 19 Agustus terbaca
 * "diambil 27 Agustus". Dua waktu yang berbeda butuh dua pemformat yang
 * berbeda, supaya tidak ada yang tergoda memakai satu untuk keduanya.
 */
export function tanggalSingkat(iso) {
  if (!iso) return '—'
  return new Intl.DateTimeFormat('id-ID', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    timeZone: ZONA,
  }).format(new Date(iso))
}
