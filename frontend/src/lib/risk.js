/**
 * Kosakata & pemetaan risiko — SATU tempat, dipakai identik di 4 halaman.
 *
 * DESIGN_BRIEF Bagian 6: "kata yang sama selalu berarti hal yang sama di semua
 * tempat". Kalau sebuah istilah perlu berubah, ubah di sini saja.
 *
 * Aturan warna (lihat audit kontras di src/index.css):
 *   `isi`  → boleh untuk fill/stroke/latar (ribbon, marker, bar). Hex Ember
 *            APA ADANYA, identik di tema gelap maupun terang — ramp Ironbow
 *            adalah elemen signature dan tidak boleh berubah antar tema.
 *   `teks` → satu-satunya yang boleh dipakai untuk teks. Berupa CSS variable
 *            karena nilainya harus berbeda per tema: di gelap `smoke` (2.93:1)
 *            dan `ember` (3.24:1) gagal, di terang `flare` (1.56:1) dan `flame`
 *            (2.83:1) yang gagal. Nilai per tema ada di src/index.css.
 */

/** Label prediksi — string di kiri harus persis sama dengan API_CONTRACT.md. */
export const LABEL_PREDIKSI = {
  fire_smoke: 'Api + asap',
  fire_no_smoke: 'Api tanpa asap',
  no_fire: 'Tidak ada api',
}

export const LABEL_PEMICU = {
  satellite_firms: 'Hotspot satelit',
  iot_ground: 'Sensor darat',
  patrol_scheduled: 'Patroli terjadwal',
}

/** Warna sumber pemicu — ikut tema, sama persis dengan marker peta. */
export const WARNA_PEMICU = {
  satellite_firms: 'var(--marker-satelit)',
  iot_ground: 'var(--marker-iot)',
  patrol_scheduled: 'var(--marker-patroli)',
}

export const LABEL_KEPUTUSAN = {
  ditindaklanjuti: 'Ditindaklanjuti',
  ditunda: 'Ditunda',
  alarm_palsu: 'Alarm palsu',
}

/** Empat tingkat skala Ember + satu status aman di keluarga hue terpisah. */
export const TINGKAT = {
  1: {
    nama: 'Risiko rendah',
    isi: '#6B6259',
    teks: 'var(--tingkat-1-teks)',
    ikon: 'bara',
    urut: 1,
  },
  2: {
    nama: 'Risiko sedang',
    isi: '#C1392B',
    teks: 'var(--tingkat-2-teks)',
    ikon: 'bara',
    urut: 2,
  },
  3: {
    nama: 'Risiko tinggi',
    isi: '#E8752C',
    teks: 'var(--tingkat-3-teks)',
    ikon: 'api',
    urut: 3,
  },
  4: {
    nama: 'Risiko kritis',
    isi: '#F5C242',
    teks: 'var(--tingkat-4-teks)',
    ikon: 'api',
    urut: 4,
  },
  aman: {
    nama: 'Terkonfirmasi bersih',
    isi: '#4A7A5E',
    teks: 'var(--tingkat-aman-teks)',
    ikon: 'centang',
    urut: 0,
  },
}

export const adaApi = (label) => label === 'fire_smoke' || label === 'fire_no_smoke'

/**
 * Tingkat keparahan dari satu alert.
 * `no_fire` SELALU jatuh ke keluarga Canopy — tidak pernah masuk skala Ember,
 * supaya "aman" tidak pernah tertukar dengan "risiko rendah" (brief Bagian 2.1).
 */
export function tingkatRisiko(alert) {
  if (!alert || !adaApi(alert.prediction?.label)) return TINGKAT.aman
  const c = alert.prediction.confidence
  if (c >= 0.85) return TINGKAT[4]
  if (c >= 0.7) return TINGKAT[3]
  if (c >= 0.5) return TINGKAT[2]
  return TINGKAT[1]
}

/**
 * Skor pengurutan "risiko" untuk Panel Alert.
 *
 * API mengirim daftar terurut `confidence` menurun (API_CONTRACT.md) — tapi
 * `no_fire 0.91` berarti "yakin TIDAK ada api", jadi menaruhnya di puncak daftar
 * operator justru menyesatkan. Pengurutan risiko dihitung di sisi klien dari
 * field yang sudah ada; TIDAK ada field baru yang ditambahkan ke kontrak.
 */
export function skorRisiko(alert) {
  const c = alert.prediction?.confidence ?? 0
  if (!adaApi(alert.prediction?.label)) return -c
  const bobotLabel = alert.prediction.label === 'fire_smoke' ? 1.0 : 0.94
  return c * bobotLabel
}

export const URUTAN = {
  risiko: { nama: 'Risiko tertinggi', bandingkan: (a, b) => skorRisiko(b) - skorRisiko(a) },
  keyakinan: {
    nama: 'Keyakinan model',
    bandingkan: (a, b) => b.prediction.confidence - a.prediction.confidence,
  },
  terbaru: {
    nama: 'Paling baru',
    bandingkan: (a, b) => new Date(b.timestamp) - new Date(a.timestamp),
  },
  belum_diputus: {
    nama: 'Belum diputuskan',
    bandingkan: (a, b) =>
      (a.operator_decision ? 1 : 0) - (b.operator_decision ? 1 : 0) ||
      skorRisiko(b) - skorRisiko(a),
  },
}

/**
 * Ringkasan keandalan modalitas.
 *
 * Frasa "Bersandar pada termal" dipakai persis sama di badge maupun rincian —
 * jangan diganti sinonim (brief Bagian 6).
 * Kalau `modality_reliability` masih null (Stage 5 belum selesai) fungsi ini
 * mengembalikan `terukur: false` dan UI menampilkan "—", bukan angka rekaan.
 */
export function ringkasModalitas(modality) {
  const rgb = modality?.rgb
  const thermal = modality?.thermal
  const terukur = typeof rgb === 'number' && typeof thermal === 'number'

  if (!terukur) {
    return {
      terukur: false,
      ringkas: 'Keandalan belum diukur',
      penjelasan:
        'Model belum melaporkan keandalan per modalitas untuk alert ini. Nilai akan terisi setelah tahap kalibrasi keandalan selesai.',
      dominan: null,
      rgb: null,
      thermal: null,
    }
  }

  const selisih = thermal - rgb
  let ringkas = 'Dua modalitas seimbang'
  let dominan = null
  if (selisih >= 0.15) {
    ringkas = 'Bersandar pada termal'
    dominan = 'thermal'
  } else if (selisih <= -0.15) {
    ringkas = 'Bersandar pada RGB'
    dominan = 'rgb'
  }

  const lemah = Math.max(rgb, thermal) < 0.45
  return {
    terukur: true,
    ringkas: lemah ? 'Dua modalitas lemah' : ringkas,
    penjelasan: lemah
      ? 'Kedua modalitas di bawah ambang andal — perlakukan keputusan model sebagai indikasi awal, bukan konfirmasi.'
      : dominan === 'thermal'
        ? 'Kanal RGB terdegradasi (asap/kabut). Keputusan model didominasi kanal termal.'
        : dominan === 'rgb'
          ? 'Kanal termal terdegradasi. Keputusan model didominasi kanal RGB.'
          : 'Kedua kanal andal dan saling menguatkan.',
    dominan,
    rgb,
    thermal,
  }
}
