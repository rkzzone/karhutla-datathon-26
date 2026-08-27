/**
 * Kosakata & format lapisan size-up — SATU tempat, dipakai identik di panel,
 * brief, dan kerucut peta.
 *
 * DESIGN_BRIEF Bagian 6: "kata yang sama selalu berarti hal yang sama di semua
 * tempat". Frasa di berkas ini termasuk yang tidak boleh diganti sinonim di
 * tengah jalan — beberapa di antaranya adalah pagar kejujuran, bukan gaya
 * bahasa. Lihat `SIZEUP_CONTRACT.md` "Aturan pelabelan UI".
 */

/** Label yang WAJIB menempel pada kerucut arah, di peta maupun di panel. */
export const LABEL_KERUCUT = 'Proyeksi arah angin'

/**
 * Indeks bahaya kebakaran memakai Sistem FWI Kanada (van Wagner 1987) — sistem
 * yang sama yang diadopsi SPBK BMKG. Judulnya menyebut sistemnya, bukan
 * lembaganya: angka ini dihitung sendiri dari persamaan terbit atas data
 * Open-Meteo, dan BUKAN keluaran BMKG.
 */
export const LABEL_BAHAYA = 'Indeks bahaya kebakaran (FWI)'

/** Nama panjang tiap komponen FWI — kode tiga huruf tidak berarti apa-apa bagi operator. */
export const KOMPONEN_FWI = [
  ['ffmc', 'FFMC', 'Kadar air bahan bakar halus permukaan'],
  ['dmc', 'DMC', 'Kadar air serasah agak dalam'],
  ['dc', 'DC', 'Kekeringan lapisan dalam — paling relevan untuk gambut'],
  ['isi', 'ISI', 'Laju penyebaran awal'],
  ['bui', 'BUI', 'Total bahan bakar tersedia'],
]

/** Tingkat bahaya meteorologis memakai skala Ember yang sama dengan risiko. */
export const WARNA_BAHAYA = {
  1: { isi: '#6B6259', teks: 'var(--tingkat-1-teks)' },
  2: { isi: '#C1392B', teks: 'var(--tingkat-2-teks)' },
  3: { isi: '#E8752C', teks: 'var(--tingkat-3-teks)' },
  4: { isi: '#F5C242', teks: 'var(--tingkat-4-teks)' },
}

export const LABEL_PERALATAN = {
  manual: 'Manual',
  semi_mekanis: 'Semi-mekanis',
  mekanis: 'Mekanis',
}

/** Jarak instrumen: di bawah 1 km lebih berguna dalam meter. */
export function jarak(km) {
  if (typeof km !== 'number' || Number.isNaN(km)) return '—'
  if (km < 1) return `${Math.round(km * 1000)} m`
  return `${km.toFixed(1)} km`
}

const MATA_ANGIN = [
  'utara', 'timur laut', 'timur', 'tenggara',
  'selatan', 'barat daya', 'barat', 'barat laut',
]

export function arahMata(derajat) {
  if (typeof derajat !== 'number' || Number.isNaN(derajat)) return null
  return MATA_ANGIN[Math.round(((derajat % 360) + 360) % 360 / 45) % 8]
}

/**
 * "≥ 8 hari" vs "2 hari".
 *
 * `terpotong_jendela` berarti SELURUH jendela pengamatan kering, jadi hitungan
 * sebenarnya bisa lebih panjang — kami cuma tidak melihatnya. Merendernya
 * sebagai angka bulat akan membuatnya terbaca sebagai batas atas yang
 * terkonfirmasi, padahal ia batas bawah.
 */
export function hariKering(riwayat) {
  const n = riwayat?.hari_kering_berturut
  if (typeof n !== 'number') return '—'
  return `${riwayat.terpotong_jendela ? '≥' : ''}${n}`
}

/** Nama fitur OSM: nama asli kalau ada, kalau tidak jenisnya. Tidak pernah dikarang. */
export function namaFitur(fitur) {
  if (!fitur) return '—'
  return fitur.nama || fitur.jenis_nama
}

/**
 * Label prakiraan BMKG: wilayah + jarak titik acuannya dari titik alert.
 *
 * Jaraknya WAJIB ikut. Prakiraan BMKG berlaku untuk desa, bukan untuk titik
 * alert; tanpa angka ini, dua tempat berbeda terbaca sebagai satu.
 */
export function wilayahBmkg(bmkg) {
  const bagian = [bmkg?.desa, bmkg?.kecamatan, bmkg?.kotkab].filter(Boolean)
  return bagian.length ? bagian.join(' · ') : '—'
}

/**
 * Titik ujung kerucut proyeksi angin, dihitung di sisi klien dari arah + jarak.
 *
 * Panjang kerucut TIDAK berarti "api akan sampai sejauh ini". Ia panjang tetap
 * yang dipilih supaya terbaca di zoom operasi — semata penanda arah. Kalau
 * suatu saat panjangnya dibuat mengikuti kecepatan angin, ia berubah menjadi
 * klaim jarak rambatan, dan itu persis larangan nomor 14.
 */
export function titikArah(lat, lon, derajat, km) {
  const R = 6371.0088
  const rad = (derajat * Math.PI) / 180
  const lat1 = (lat * Math.PI) / 180
  const lon1 = (lon * Math.PI) / 180
  const d = km / R
  const lat2 = Math.asin(
    Math.sin(lat1) * Math.cos(d) + Math.cos(lat1) * Math.sin(d) * Math.cos(rad),
  )
  const lon2 =
    lon1 +
    Math.atan2(
      Math.sin(rad) * Math.sin(d) * Math.cos(lat1),
      Math.cos(d) - Math.sin(lat1) * Math.sin(lat2),
    )
  return [(lat2 * 180) / Math.PI, (lon2 * 180) / Math.PI]
}

/** Sudut buka kerucut. Lebar karena ketidakpastiannya memang lebar — lihat catatan di komponen. */
export const BUKAAN_KERUCUT_DERAJAT = 34

/**
 * Panjang kerucut dalam PIKSEL LAYAR, bukan kilometer.
 *
 * Disengaja: panjang yang tetap dalam kilometer terbaca sebagai jangkauan,
 * sedangkan panjang yang tetap dalam piksel jelas cuma penunjuk arah karena ia
 * berubah artinya tiap kali peta di-zoom. Lihat catatan lengkap di
 * `components/KerucutAngin.jsx`.
 */
export const PANJANG_KERUCUT_PIKSEL = 108
