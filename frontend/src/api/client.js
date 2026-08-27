/**
 * Satu-satunya lapisan yang tahu dari mana data datang.
 *
 * DUA MODE (lihat README.md "Menjalankan konsol"):
 *   1. Styling murni — `VITE_API_BASE` kosong → baca /mock/*.json dari public/.
 *      Backend tidak perlu menyala. Ini mode default `npm run dev`.
 *   2. Integrasi   — isi `VITE_API_BASE` di .env.local, mis.
 *      VITE_API_BASE=http://127.0.0.1:8000
 *
 * Bentuk objek yang dikembalikan IDENTIK di kedua mode — persis skema
 * API_CONTRACT.md. Tidak ada field tambahan yang disuntikkan di sini.
 */

const API_BASE = (import.meta.env.VITE_API_BASE || '').replace(/\/$/, '')

/**
 * Basis untuk lapisan yang HARUS hidup: hotspot FIRMS dan sensor IoT.
 *
 * Dipisah dari `VITE_API_BASE` dengan sengaja. Alert dan metrik sudah berupa
 * keluaran batch yang ikut ter-bundle — menariknya lewat server cuma menambah
 * perantara tanpa menambah kebaruan. Di deployment statis (Vercel + backend
 * terpisah), backend free-tier bisa spin-down dan butuh ~50 detik untuk bangun;
 * kalau seluruh halaman menunggu itu, pengunjung pertama melihat layar kosong
 * hampir semenit. Dengan pemisahan ini, halaman tampil seketika dan hanya
 * lapisan FIRMS yang menyusul.
 *
 *   VITE_API_BASE   → integrasi penuh (dipakai saat uji lokal backend+frontend)
 *   VITE_LIVE_BASE  → hanya lapisan langsung (dipakai di Vercel)
 */
const LIVE_BASE = (import.meta.env.VITE_LIVE_BASE || '').replace(/\/$/, '') || API_BASE

/** Basis untuk `images.rgb_url` / `localization.heatmap_path` yang berupa path relatif. */
const MEDIA_BASE = (import.meta.env.VITE_MEDIA_BASE || '/media/').replace(/\/?$/, '/')

export const modeIntegrasi = Boolean(API_BASE)
/** True kalau FIRMS/IoT ditarik dari backend, walau alert tetap statis. */
export const adaLapisanLangsung = Boolean(LIVE_BASE)

/**
 * Override state untuk screenshot & latihan demo — `?demo=kosong`, dst.
 * Ini scaffolding UI, bukan data: tidak pernah mengarang nilai numerik, hanya
 * memilih jalur render mana yang ditampilkan.
 */
export function demoState() {
  if (typeof window === 'undefined') return null
  return new URLSearchParams(window.location.search).get('demo')
}

export class GalatApi extends Error {
  constructor(pesan, { alasan = 'tidak_diketahui', status = 0 } = {}) {
    super(pesan)
    this.alasan = alasan
    this.status = status
  }
}

const PESAN_JARINGAN =
  'Tidak bisa menghubungi server. Periksa koneksi, lalu muat ulang halaman.'

async function ambilJson(path, opsi = {}) {
  let respons
  try {
    respons = await fetch(path, opsi)
  } catch {
    throw new GalatApi(PESAN_JARINGAN, { alasan: 'jaringan' })
  }
  if (!respons.ok) {
    let detail = {}
    try {
      detail = (await respons.json())?.detail ?? {}
    } catch {
      /* badan bukan JSON — pakai pesan default di bawah */
    }
    throw new GalatApi(detail.pesan || PESAN_JARINGAN, {
      alasan: detail.alasan || 'galat_server',
      status: respons.status,
    })
  }

  // Status 200 belum menjamin isinya JSON. Kalau `VITE_LIVE_BASE` salah tunjuk
  // — mis. ke domain frontend, yang me-rewrite semua path ke index.html —
  // server membalas HTML dengan status 200 dan `respons.json()` melempar
  // "Unexpected token '<'". Pesan itu tidak boleh sampai ke layar operator:
  // DESIGN_BRIEF Bagian 6 mewajibkan copy fungsional berbahasa Indonesia,
  // bukan galat mentah runtime.
  try {
    return await respons.json()
  } catch {
    throw new GalatApi(
      'Alamat layanan membalas halaman web, bukan data. Konfigurasi alamat perlu diperiksa admin sistem.',
      { alasan: 'respons_bukan_json', status: respons.status },
    )
  }
}

/** Resolusi path media relatif dari kontrak ke URL yang bisa dirender. */
export function urlMedia(path) {
  if (!path) return null
  if (/^(https?:)?\/\//.test(path) || path.startsWith('/')) return path
  return MEDIA_BASE + path
}

/* -------------------------------------------------------------------------- */
/* Alert                                                                       */
/* -------------------------------------------------------------------------- */

/** Keputusan operator saat mode styling murni — hanya hidup di memori tab. */
const keputusanLokal = new Map()

export async function ambilAlerts() {
  const demo = demoState()
  if (demo === 'kosong') return []
  if (demo === 'error-alerts') {
    throw new GalatApi(
      'Daftar alert tidak bisa dimuat. Coba muat ulang dalam beberapa menit, atau hubungi posko pusat.',
      { alasan: 'galat_server', status: 503 },
    )
  }

  const data = modeIntegrasi
    ? await ambilJson(`${API_BASE}/api/alerts`)
    : await ambilJson('/mock/sample_predictions.json')

  return data
    .map((alert) =>
      keputusanLokal.has(alert.alert_id)
        ? { ...alert, operator_decision: keputusanLokal.get(alert.alert_id) }
        : alert,
    )
    .sort((a, b) => b.prediction.confidence - a.prediction.confidence)
}

export async function ambilAlert(alertId) {
  if (modeIntegrasi && !demoState()) {
    return ambilJson(`${API_BASE}/api/alerts/${encodeURIComponent(alertId)}`)
  }
  const semua = await ambilAlerts()
  const alert = semua.find((a) => a.alert_id === alertId)
  if (!alert) {
    throw new GalatApi(`Alert ${alertId} tidak ada dalam daftar aktif.`, {
      alasan: 'alert_tidak_ditemukan',
      status: 404,
    })
  }
  return alert
}

export async function kirimKeputusan(alertId, keputusan) {
  if (modeIntegrasi && !demoState()) {
    return ambilJson(`${API_BASE}/api/alerts/${encodeURIComponent(alertId)}/decision`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ operator_decision: keputusan }),
    })
  }
  keputusanLokal.set(alertId, keputusan)
  return ambilAlert(alertId)
}

/* -------------------------------------------------------------------------- */
/* FIRMS (Stage 11)                                                            */
/* -------------------------------------------------------------------------- */

export async function ambilHotspotFirms() {
  const demo = demoState()
  if (demo === 'error-firms') {
    throw new GalatApi(
      'Data hotspot satelit tidak bisa dimuat. Coba lagi dalam beberapa menit, atau lanjutkan dengan sumber pemicu lain.',
      { alasan: 'upstream_error', status: 503 },
    )
  }
  if (LIVE_BASE) return ambilJson(`${LIVE_BASE}/api/firms/hotspots`)

  // Tanpa backend, TIGA keadaan yang tidak boleh disamakan:
  //
  //   langsung  → ditarik saat halaman dibuka          (butuh backend)
  //   cuplikan  → hotspot NYATA, beku pada waktu tercatat
  //   contoh    → titik karangan, tidak pernah terjadi
  //
  // Cuplikan diutamakan karena datanya sungguhan; berkas contoh hanya dipakai
  // kalau cuplikan belum pernah dibuat. MAP_KEY tidak boleh masuk bundle
  // frontend, jadi memanggil NASA langsung dari sini bukan pilihan.
  try {
    return await ambilJson('/mock/firms_snapshot.json')
  } catch {
    const titik = await ambilJson('/mock/firms_fixture.json')
    return {
      is_fixture: true,
      is_cuplikan: false,
      sumber: 'VIIRS_SNPP_NRT',
      rentang_hari: 1,
      jumlah: titik.length,
      jumlah_total: titik.length,
      dipangkas: false,
      titik,
    }
  }
}

/* -------------------------------------------------------------------------- */
/* IoT simulasi (Stage 12)                                                     */
/* -------------------------------------------------------------------------- */

export async function ambilNodeIot() {
  if (LIVE_BASE) return ambilJson(`${LIVE_BASE}/api/iot/nodes`)
  return ambilJson('/mock/iot_nodes.json')
}

/* -------------------------------------------------------------------------- */
/* Size-up — lapisan keputusan deterministik setelah deteksi                   */
/* -------------------------------------------------------------------------- */

/**
 * Konteks size-up untuk satu alert: cuaca, kekeringan, sumber air, akses,
 * saran tingkat peralatan, dan brief siap tempel.
 *
 * Bentuknya dikunci `SIZEUP_CONTRACT.md` — BUKAN `API_CONTRACT.md`. Objek alert
 * tidak bertambah satu field pun karena fungsi ini ada; size-up adalah objek
 * terpisah di endpoint terpisah, karena ia lapisan SETELAH model, bukan bagian
 * dari keluaran model.
 *
 * Tiga keadaan, sama persis dengan lapisan FIRMS dan sama-sama tidak boleh
 * disamakan satu sama lain:
 *
 *   langsung  → ditarik saat panel dibuka        (butuh backend)
 *   cuplikan  → cuaca & geografi NYATA, beku pada waktu tercatat
 *   —         → tidak ada backend dan belum pernah dibekukan
 *
 * Tidak ada keadaan keempat berupa "contoh": tidak seperti hotspot, tidak ada
 * berkas cuaca karangan di proyek ini, dan tidak boleh ada.
 */
export async function ambilSizeUp(alert) {
  if (!alert) return null
  const { lat, lon } = alert.location

  if (demoState() === 'error-sizeup') {
    throw new GalatApi(
      'Konteks size-up tidak bisa dimuat. Lanjutkan dengan peta cetak posko, atau coba lagi dalam beberapa menit.',
      { alasan: 'upstream_error', status: 503 },
    )
  }

  if (LIVE_BASE) {
    const parameter = new URLSearchParams({
      lat: String(lat),
      lon: String(lon),
      alert_id: alert.alert_id,
    })
    return ambilJson(`${LIVE_BASE}/api/sizeup?${parameter}`)
  }

  // Berkas cuplikan yang BELUM ADA dan berkas yang ADA tapi tidak memuat alert
  // ini harus menghasilkan pesan yang sama, dan pesan itu harus menyebut
  // penyebab sebenarnya.
  //
  // Sebelumnya tidak begitu: server statis membalas index.html dengan status
  // 200 untuk berkas yang tidak ada, sehingga `ambilJson` melempar
  // "respons_bukan_json" dan operator melihat "Alamat layanan membalas halaman
  // web — konfigurasi perlu diperiksa admin sistem". Itu menuduh konfigurasi
  // untuk masalah yang sebenarnya cuma "cuplikan belum pernah dibekukan", dan
  // mengirim orang memburu kesalahan yang tidak ada.
  let beku = null
  try {
    beku = await ambilJson('/mock/sizeup_snapshot.json')
  } catch {
    beku = null
  }
  const tersimpan = beku?.sizeup?.[alert.alert_id]
  if (!tersimpan) {
    throw new GalatApi(
      'Konteks size-up untuk alert ini belum pernah dibekukan. Jalankan ' +
        'backend/scripts/bekukan_sizeup.py, atau hubungkan konsol ke layanan langsung.',
      { alasan: 'cuplikan_tidak_ada', status: 404 },
    )
  }
  // `dibekukan` milik berkas, `diambil` milik tiap alert — waktu yang ditampilkan
  // harus yang kedua, karena itulah kapan cuacanya benar-benar diukur.
  return { ...tersimpan, is_cuplikan: true, dibekukan: beku.dibekukan }
}

/* -------------------------------------------------------------------------- */
/* Pengerahan tim — tahap SETELAH keputusan operator                           */
/* -------------------------------------------------------------------------- */

/**
 * Tahap pengerahan tim, disimpan TERPISAH dari objek alert.
 *
 * ============================================================================
 *  KENAPA TERPISAH, DAN KENAPA ITU BUKAN SEKADAR SELERA PENATAAN
 * ============================================================================
 * `API_CONTRACT.md` mengunci bentuk objek alert dan wajib identik byte-per-byte
 * dengan salinan tim model. Menempelkan `status_pengerahan` ke dalamnya berarti
 * memaksa perubahan kontrak untuk data yang tim model tidak menghasilkan dan
 * tidak mengonsumsi. Skema `extra="forbid"` di sisi backend juga akan MENOLAK
 * objek alert yang membawa field asing — jadi ini bukan pilihan gaya, melainkan
 * satu-satunya bentuk yang lolos pagar kontrak.
 *
 * Konsekuensinya: pengerahan hidup di memori tab, sama seperti keputusan
 * operator selama Stage 9. Di deployment nyata ia milik basis data posko.
 *
 * WAKTUNYA NYATA. Berbeda dari `alert.timestamp` yang disintesis untuk demo
 * (lihat `backend/scripts/jalankan_inference.py`), stempel waktu di sini
 * dicatat saat operator benar-benar menekan tombolnya. Itu satu-satunya waktu
 * di seluruh rantai yang benar-benar terjadi, dan UI menyebutkannya begitu.
 */
export const TAHAP_PENGERAHAN = ['dikerahkan', 'berangkat', 'tiba']

const pengerahanLokal = new Map()

export function ambilPengerahan(alertId) {
  return pengerahanLokal.get(alertId) ?? []
}

/**
 * Catat satu tahap. Menekan tahap yang sudah tercatat akan MEMBATALKANNYA
 * beserta seluruh tahap sesudahnya — regu tidak bisa "tiba" lalu kembali jadi
 * "berangkat" tanpa membatalkan kedatangannya juga.
 */
export function simpanPengerahan(alertId, tahap) {
  const urut = TAHAP_PENGERAHAN.indexOf(tahap)
  if (urut < 0) return ambilPengerahan(alertId)

  const sekarang = ambilPengerahan(alertId)
  const sudahAda = sekarang.some((t) => t.tahap === tahap)
  const berikutnya = sudahAda
    ? sekarang.filter((t) => TAHAP_PENGERAHAN.indexOf(t.tahap) < urut)
    : [
        ...sekarang.filter((t) => TAHAP_PENGERAHAN.indexOf(t.tahap) < urut),
        { tahap, waktu: new Date().toISOString() },
      ]

  pengerahanLokal.set(alertId, berikutnya)
  return berikutnya
}

/**
 * Size-up untuk BANYAK alert sekaligus — dipakai lapisan konteks di peta.
 *
 * ============================================================================
 *  KENAPA HASILNYA BERBEDA ANTARA DUA MODE, DAN KENAPA ITU BUKAN CACAT
 * ============================================================================
 * Cuplikan  → kesepuluh alert SUDAH ada di dalam satu berkas yang ikut ter-bundle.
 *             Menampilkan semuanya tidak menambah satu pun panggilan jaringan.
 * Langsung  → tiap alert berarti satu panggilan cuaca, satu kueri Overpass, dan
 *             dua kueri geoportal BIG. Menariknya untuk sepuluh alert sekaligus
 *             adalah pola yang persis memicu blokir Overpass dan BIG — keduanya
 *             infrastruktur gratis, dan membanjirinya demi lapisan konteks
 *             adalah cara buruk memakainya.
 *
 * Jadi mode langsung hanya menarik `batas` alert teratas, dan mengembalikan
 * `lengkap: false` supaya UI bisa menyatakan apa adanya bahwa sebagian titik
 * belum punya konteks — bukan menyembunyikan perbedaannya.
 */
export async function ambilSizeUpBanyak(alerts, batas = 3) {
  const kosong = { menurutAlert: {}, lengkap: true, jumlah: 0, sumber: 'kosong' }
  if (!alerts?.length || demoState() === 'error-sizeup') return kosong

  if (!LIVE_BASE) {
    let beku
    try {
      beku = await ambilJson('/mock/sizeup_snapshot.json')
    } catch {
      // Cuplikan belum pernah dibuat. Lapisan konteks tidak tampil, dan itu
      // keadaan yang sah — bukan galat yang perlu menghentikan peta.
      return { ...kosong, sumber: 'tidak_tersedia' }
    }
    const menurutAlert = {}
    for (const alert of alerts) {
      const isi = beku?.sizeup?.[alert.alert_id]
      if (isi) menurutAlert[alert.alert_id] = { ...isi, is_cuplikan: true }
    }
    const jumlah = Object.keys(menurutAlert).length
    return {
      menurutAlert,
      jumlah,
      lengkap: jumlah === alerts.length,
      sumber: 'cuplikan',
      dibekukan: beku?.dibekukan ?? null,
    }
  }

  const dipilih = alerts.slice(0, batas)
  const menurutAlert = {}
  // Berurutan, bukan Promise.all: paralel akan menembakkan tiga kueri Overpass
  // dan enam kueri BIG dalam satu tarikan napas, yang justru bentuk beban yang
  // paling cepat diblokir kedua layanan itu.
  for (const alert of dipilih) {
    try {
      menurutAlert[alert.alert_id] = await ambilSizeUp(alert)
    } catch {
      /* satu titik gagal tidak boleh menjatuhkan lapisan konteks seluruhnya */
    }
  }
  const jumlah = Object.keys(menurutAlert).length
  return {
    menurutAlert,
    jumlah,
    lengkap: jumlah === alerts.length,
    sumber: 'langsung',
  }
}

/* -------------------------------------------------------------------------- */
/* Patroli & metrik                                                            */
/* -------------------------------------------------------------------------- */

export async function ambilRutePatroli() {
  return ambilJson('/mock/patrol_routes.json')
}

/**
 * Rencana sapuan verifikasi drone + posisi pangkalan.
 *
 * Dihitung `backend/scripts/rencanakan_sapuan.py` (Orienteering Problem di atas
 * hotspot FIRMS nyata) dan dibekukan sebagai berkas statis — bukan dihitung di
 * peramban. Perencanaannya deterministik, jadi menghitungnya sekali lalu
 * menyimpannya menghasilkan angka yang identik dan membuat halaman terbuka
 * seketika.
 */
export async function ambilSapuanDrone() {
  try {
    return await ambilJson('/mock/sapuan_drone.json')
  } catch {
    // Belum pernah direncanakan. Lapisan sapuan tidak tampil, dan itu keadaan
    // yang sah — bukan galat yang perlu menghentikan peta.
    return null
  }
}

/** Wilayah operasi: posko/pangkalan berikut penegasan bahwa posisinya andaian. */
export async function ambilWilayahOperasi() {
  try {
    return await ambilJson('/mock/wilayah_operasi.json')
  } catch {
    return null
  }
}

export async function ambilMetrikModel() {
  if (modeIntegrasi) return ambilJson(`${API_BASE}/api/inference/metrics`)
  return ambilJson('/mock/model_metrics.json')
}

export async function ambilStatusSumber() {
  if (modeIntegrasi) return ambilJson(`${API_BASE}/api/inference/status`)

  // Deployment statis (Vercel) tidak punya backend untuk ditanyai. Penanda
  // ditulis oleh backend/scripts/jalankan_inference.py bersama data yang
  // dihasilkannya, jadi ia otomatis benar: kalau berkasnya tidak ada, artinya
  // data yang tersaji memang belum pernah lewat model.
  try {
    return await ambilJson('/mock/status_sumber.json')
  } catch {
    return { sumber: 'mock', model_service_url: null, berkas_mock: '/mock/sample_predictions.json' }
  }
}
