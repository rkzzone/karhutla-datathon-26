import { useState } from 'react'
import { Polygon, Polyline, Tooltip, useMap, useMapEvent } from 'react-leaflet'

import {
  BUKAAN_KERUCUT_DERAJAT,
  LABEL_KERUCUT,
  PANJANG_KERUCUT_PIKSEL,
  arahMata,
  titikArah,
} from '../lib/sizeup.js'

/**
 * Proyeksi arah angin di peta — kerucut, bukan panah tunggal.
 *
 * ============================================================================
 *  KENAPA KERUCUT DAN BUKAN PANAH
 * ============================================================================
 * Panah tunggal membaca sebagai lintasan: "api akan bergerak ke sana, sejauh
 * ini". Yang sebenarnya kita punya jauh lebih sedikit dari itu — satu bacaan
 * arah angin sesaat pada satu titik, tanpa bahan bakar, tanpa kelerengan, tanpa
 * kelembapan gambut. Kerucut yang melebar menggambarkan ketidakpastian itu
 * dalam bentuk, sehingga bentuknya sendiri sudah menyampaikan batasnya sebelum
 * ada yang membaca labelnya.
 *
 * Ini larangan nomor 14 diterjemahkan menjadi keputusan visual, bukan cuma
 * menjadi teks penyangkalan di bawah peta.
 *
 * PANJANG KERUCUT TETAP DI RUANG LAYAR, bukan di ruang bumi — ia selalu
 * kira-kira sekian piksel, berapa pun zoom-nya. Dua alasan, dan keduanya
 * berujung ke hal yang sama:
 *
 *   1. Kejujuran. Panjang yang tetap dalam kilometer akan terbaca sebagai
 *      jangkauan; panjang yang tetap dalam piksel jelas-jelas cuma penunjuk
 *      arah, karena ia berubah maknanya setiap kali peta di-zoom. Begitu
 *      panjangnya dibuat proporsional terhadap kecepatan angin, ia berubah
 *      menjadi klaim jarak rambatan — persis larangan nomor 14.
 *   2. Keterbacaan. Kerucut 6 km sepanjang apa pun tidak terlihat di zoom 5,
 *      yang justru zoom bawaan halaman peta operasi. Lapisan yang menyala tapi
 *      tak tampak akan terbaca sebagai kerusakan.
 *
 * Isian sengaja sangat tipis: lapisan ini konteks, dan tidak boleh mengalahkan
 * marker alert yang duduk di atasnya.
 */
export default function KerucutAngin({ lat, lon, arahRambatanDeg, anginKmj }) {
  const peta = useMap()
  const [zoom, setZoom] = useState(() => peta.getZoom())
  useMapEvent('zoomend', () => setZoom(peta.getZoom()))

  if (
    typeof lat !== 'number' ||
    typeof lon !== 'number' ||
    typeof arahRambatanDeg !== 'number'
  ) {
    return null
  }

  // Meter per piksel pada Web Mercator di lintang & zoom ini. Dari sini,
  // panjang kerucut dalam kilometer dihitung mundur dari panjang layar yang
  // diinginkan — bukan sebaliknya.
  const meterPerPiksel =
    (156543.03392 * Math.cos((lat * Math.PI) / 180)) / Math.pow(2, zoom)
  const panjangKm = (PANJANG_KERUCUT_PIKSEL * meterPerPiksel) / 1000

  const setengah = BUKAAN_KERUCUT_DERAJAT / 2
  const kiri = titikArah(lat, lon, arahRambatanDeg - setengah, panjangKm)
  const kanan = titikArah(lat, lon, arahRambatanDeg + setengah, panjangKm)
  const tengah = titikArah(lat, lon, arahRambatanDeg, panjangKm * 0.82)

  // Busur tepi supaya kerucut tidak berujung runcing seperti panah. Sepuluh
  // segmen sudah mulus pada zoom operasi tanpa membebani render.
  const busur = Array.from({ length: 11 }, (_, i) =>
    titikArah(
      lat,
      lon,
      arahRambatanDeg - setengah + (BUKAAN_KERUCUT_DERAJAT * i) / 10,
      panjangKm,
    ),
  )

  const keterangan = [
    LABEL_KERUCUT,
    arahMata(arahRambatanDeg) ? `dorongan ke ${arahMata(arahRambatanDeg)}` : null,
    typeof anginKmj === 'number' ? `${anginKmj} km/j` : null,
  ]
    .filter(Boolean)
    .join(' · ')

  return (
    <>
      <Polygon
        positions={[[lat, lon], ...busur]}
        pathOptions={{
          color: '#E8752C',
          weight: 1,
          opacity: 0.5,
          fillColor: '#E8752C',
          fillOpacity: 0.1,
          // Lapisan konteks: tidak boleh menangkap klik yang ditujukan ke
          // marker alert di bawah kursor.
          interactive: true,
        }}
      >
        <Tooltip sticky>{keterangan}. Bukan prediksi rambatan model.</Tooltip>
      </Polygon>
      {/* Garis sumbu — arah utamanya tetap terbaca saat isian nyaris tak terlihat */}
      <Polyline
        positions={[[lat, lon], tengah]}
        pathOptions={{
          color: '#E8752C',
          weight: 1.4,
          opacity: 0.7,
          dashArray: '5 4',
          interactive: false,
        }}
      />
      <Polyline
        positions={[kiri, [lat, lon], kanan]}
        pathOptions={{ color: '#E8752C', weight: 1, opacity: 0.35, interactive: false }}
      />
    </>
  )
}
