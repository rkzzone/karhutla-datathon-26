import L from 'leaflet'
import { Fragment } from 'react'
import { Marker, Polyline, Popup, Tooltip } from 'react-leaflet'

import { jarak } from '../lib/sizeup.js'

/**
 * Rencana sapuan verifikasi drone di peta.
 *
 * ============================================================================
 *  YANG DIJAWAB LAPISAN INI
 * ============================================================================
 * FIRMS memberi puluhan titik CURIGA dalam satu wilayah. Drone tidak bisa
 * mendatangi semuanya — baterainya habis ~30 menit dan ia harus pulang. Jadi
 * pertanyaan operator bukan "terbang ke mana", melainkan "yang mana dulu, dan
 * mana yang terpaksa ditinggal".
 *
 * Lapisan ini menjawab keduanya secara harfiah: jalur yang direncanakan, dan
 * titik yang TIDAK masuk penerbangan ini. Yang kedua sama pentingnya dengan
 * yang pertama — peta yang cuma menggambar jalur terpilih akan menyiratkan
 * tidak ada yang tertinggal.
 *
 * ============================================================================
 *  GARIS LURUS, DAN ITU BUKAN KEMALASAN
 * ============================================================================
 * Drone terbang; jalan tidak relevan baginya. Ini berbeda dari rute pengerahan
 * regu darat, yang justru HARUS mengikuti jalan. Keduanya ada di peta ini
 * sebagai dua lapisan berbeda, dan mencampurnya pernah jadi kekeliruan nyata
 * di produk ini — jalur drone sempat dirutekan lewat jalan raya.
 */

/**
 * Pangkalan/posko — segitiga. Bentuknya sengaja tidak dipakai marker lain:
 * bulatan milik alert, belah ketupat milik hotspot, kotak milik sensor,
 * tetesan milik sumber air.
 */
const IKON_PANGKALAN = L.divIcon({
  className: '',
  iconSize: [18, 18],
  iconAnchor: [9, 9],
  html: `<span class="marker-peta block" style="width:0;height:0;border-left:9px solid transparent;border-right:9px solid transparent;border-bottom:16px solid var(--marker-halo);position:relative">
    <span style="position:absolute;left:-6px;top:4px;width:0;height:0;border-left:6px solid transparent;border-right:6px solid transparent;border-bottom:11px solid #F5C242"></span>
  </span>`,
})

/** Titik yang akan disinggahi — bulatan kecil bernomor urut. */
function ikonSinggah(urut) {
  return L.divIcon({
    className: '',
    iconSize: [16, 16],
    iconAnchor: [8, 8],
    html: `<span class="marker-peta flex items-center justify-center rounded-full" style="width:16px;height:16px;background:var(--marker-halo);border:1.5px solid #F5C242;font:600 9px/1 'IBM Plex Mono',monospace;color:#F5C242">${urut}</span>`,
  })
}

/** Titik yang TIDAK masuk penerbangan — cincin kosong, sengaja pudar. */
const IKON_TERLEWAT = L.divIcon({
  className: '',
  iconSize: [11, 11],
  iconAnchor: [5.5, 5.5],
  html: '<span class="marker-peta block rounded-full" style="width:11px;height:11px;border:1.5px dashed var(--marker-satelit);opacity:0.75"></span>',
})

export default function SapuanDrone({ sapuan, wilayah, tampilkanTerlewat = true }) {
  if (!sapuan) return null

  const pangkalan = sapuan.pangkalan
  const urutan = sapuan.urutan ?? []
  const terlewat = sapuan.di_luar_jangkauan ?? []

  return (
    <>
      {/* Jalur sapuan — garis lurus pangkalan → titik → pangkalan */}
      {Array.isArray(sapuan.jalur) && sapuan.jalur.length > 1 && (
        <Polyline
          positions={sapuan.jalur}
          pathOptions={{
            color: '#F5C242',
            weight: 1.6,
            opacity: 0.8,
            dashArray: '7 4',
          }}
        >
          <Tooltip sticky>
            <div className="font-display text-caption text-haze-100">
              Urutan prioritas verifikasi
            </div>
            <div className="mt-0.5 font-mono text-[0.6875rem] text-haze-300">
              {sapuan.jarak_km} km · {sapuan.durasi_menit} menit · {urutan.length} titik
            </div>
            <div className="mt-1 border-t border-ash-700 pt-1 text-[0.625rem] leading-relaxed text-haze-500">
              Urutan untuk patroli yang memang sudah dijadwalkan terbang — sistem
              ini tidak mengoperasikan drone. Anggaran {sapuan.anggaran_menit} menit
              dari daya tahan {sapuan.asumsi?.daya_tahan_menit} menit. Garis lurus
              karena patroli terbang; jalan tidak relevan baginya.
            </div>
          </Tooltip>
        </Polyline>
      )}

      {/* Titik yang tidak terjangkau penerbangan ini. Digambar SEBELUM titik
          singgah supaya tidak menutupinya, dan tetap digambar karena "apa yang
          ditinggal" adalah separuh dari keputusan operator. */}
      {tampilkanTerlewat &&
        terlewat.map((t) => (
          <Marker
            key={`lewat-${t.id}`}
            position={[t.lat, t.lon]}
            icon={IKON_TERLEWAT}
            alt={`Hotspot di luar jangkauan penerbangan, ${t.jarak_pangkalan_km} km dari pangkalan`}
          >
            <Tooltip>
              Di luar jangkauan penerbangan ini · {jarak(t.jarak_pangkalan_km)} ·
              FRP {t.frp_mw} MW
            </Tooltip>
          </Marker>
        ))}

      {urutan.map((t, i) => (
        <Fragment key={`singgah-${t.id}`}>
          <Marker
            position={[t.lat, t.lon]}
            icon={ikonSinggah(i + 1)}
            alt={`Singgah ${i + 1}, hotspot FRP ${t.frp_mw} megawatt`}
          >
            <Tooltip>
              Singgah {i + 1} · FRP {t.frp_mw} MW · {jarak(t.jarak_pangkalan_km)} dari
              pangkalan
            </Tooltip>
          </Marker>
        </Fragment>
      ))}

      {pangkalan && (
        <Marker
          position={[pangkalan.lat, pangkalan.lon]}
          icon={IKON_PANGKALAN}
          alt={`Pangkalan drone dan posko, ${pangkalan.nama}`}
        >
          <Popup>
            <div className="p-3">
              <div className="font-display text-heading text-haze-100">
                {pangkalan.nama}
              </div>
              <div className="mt-0.5 text-caption text-haze-400">
                Posko & titik lepas landas patroli
              </div>
              <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 font-mono text-mono-data text-haze-300">
                <div>
                  <dt className="label-meta">Jalur</dt>
                  <dd>{sapuan.jarak_km} km</dd>
                </div>
                <div>
                  <dt className="label-meta">Durasi</dt>
                  <dd>{sapuan.durasi_menit} mnt</dd>
                </div>
                <div>
                  <dt className="label-meta">Diverifikasi</dt>
                  <dd>{urutan.length} titik</dd>
                </div>
                <div>
                  <dt className="label-meta">Ditinggal</dt>
                  <dd>{terlewat.length} titik</dd>
                </div>
              </dl>

              {/* Asumsi ikut tampil, tidak disembunyikan. Dua dari tiga angka
                  ini TIDAK diukur tim ini, dan rencana yang tampak presisi
                  tanpa menyebut asumsinya lebih menyesatkan daripada rencana
                  kasar yang jujur. */}
              <div className="mt-2 border-t border-ash-700 pt-2 text-[0.625rem] leading-relaxed text-haze-500">
                Anggaran {sapuan.anggaran_menit} menit ={' '}
                {sapuan.asumsi?.daya_tahan_menit} menit daya tahan −{' '}
                {Math.round((sapuan.asumsi?.marjin_cadangan ?? 0) * 100)}% cadangan.
                Laju {sapuan.asumsi?.laju_mps} m/s dan hover{' '}
                {sapuan.asumsi?.hover_detik_per_titik} detik/titik adalah{' '}
                <span className="text-haze-400">asumsi tim ini, tidak diukur</span>.
              </div>
              {wilayah?.adalah_andaian && (
                <div className="mt-1.5 text-[0.625rem] leading-relaxed text-haze-500">
                  Posisi posko adalah <span className="text-haze-400">posisi
                  andaian</span> untuk demo — kami tidak memverifikasi Daops mana
                  yang membawahi koordinat ini.
                </div>
              )}
            </div>
          </Popup>
        </Marker>
      )}
    </>
  )
}
