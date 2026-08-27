import L from 'leaflet'
import { Fragment, useEffect, useMemo } from 'react'
import { MapContainer, Marker, Polyline, Popup, TileLayer, Tooltip, useMap } from 'react-leaflet'
import { useNavigate } from 'react-router-dom'

import { angkaPersen, jam, koordinat } from '../lib/format.js'
import { LABEL_PEMICU, LABEL_PREDIKSI, adaApi, tingkatRisiko } from '../lib/risk.js'
import { WARNA_BAHAYA, jarak as jarakSizeUp } from '../lib/sizeup.js'
import { useTema } from '../lib/tema.js'
import Ikon from './Ikon.jsx'
import KerucutAngin from './KerucutAngin.jsx'
import SapuanDrone from './SapuanDrone.jsx'

/**
 * Peta operasi.
 *
 * Basemap memakai CARTO (gratis, tanpa API key) dan mengikuti tema aktif —
 * lihat catatan di konstanta `UBIN` di bawah soal hubungannya dengan larangan
 * basemap terang di DESIGN_BRIEF Bagian 8.
 *
 * Marker dibuat dari `L.divIcon`, bukan `CircleMarker`, supaya tiap marker jadi
 * elemen DOM yang bisa difokus keyboard — brief Bagian 5 mewajibkan focus-visible
 * sampai ke marker peta.
 */

/**
 * Basemap: CARTO Dark Matter kalau ada kunci, Esri Canvas kalau tidak.
 *
 * ============================================================================
 *  KENAPA DUA PENYEDIA, DAN KENAPA ITU BUKAN KERAGU-RAGUAN
 * ============================================================================
 * CARTO menutup basemap publiknya pada 2026: ubin masih membalas HTTP 200,
 * tetapi datang bertuliskan "API KEY REQUIRED" melintang di seluruh peta.
 * Karena statusnya 200, tidak ada penanganan galat yang bisa menangkapnya —
 * kerusakan senyap yang cuma ketahuan dengan melihat.
 *
 * DESIGN_BRIEF Bagian 2.1 menyebut CARTO Dark Matter sebagai spesifikasi, dan
 * dengan kunci ia kembali persis seperti yang dimaksud brief. Tetapi kunci itu
 * milik satu orang, sedangkan repo ini harus tetap jalan bagi siapa pun yang
 * meng-clone-nya — termasuk juri yang memeriksa reproduksibilitas. Karena itu
 * ketiadaan kunci BUKAN kegagalan: peta beralih ke Esri Canvas, yang gratis
 * tanpa kunci dan tetap memenuhi syarat "basemap gelap".
 *
 * PERINGATAN YANG TIDAK BOLEH DILUPAKAN: `import.meta.env` DITANAM Vite ke
 * bundle hasil build. Kunci ini akan terlihat publik di JavaScript yang
 * di-deploy. Itu sifat semua kunci ubin sisi-klien dan tidak bisa dihindari
 * dengan menyembunyikannya di berkas lain — satu-satunya perlindungan nyata
 * adalah membatasi kunci ke domain tertentu di dasbor CARTO. Ini BERBEDA dari
 * MAP_KEY milik FIRMS, yang tinggal di server dan tidak pernah masuk bundle.
 */
const KUNCI_CARTO = import.meta.env.VITE_CARTO_KEY || ''

// CARTO menyediakan gaya yang sudah memuat label, jadi satu permintaan per
// ubin — bukan dua. Penting untuk kuota: jatah gratis 5 juta ubin/bulan
// dihitung per permintaan, dan lapisan label terpisah akan melipatduakannya
// tanpa menambah apa pun yang tidak sudah ada di `*_all`.
const UBIN_CARTO = {
  gelap: {
    berlabel: 'https://{s}.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}{r}.png',
    polos: 'https://{s}.basemaps.cartocdn.com/rastertiles/dark_nolabels/{z}/{x}/{y}{r}.png',
  },
  terang: {
    berlabel: 'https://{s}.basemaps.cartocdn.com/rastertiles/light_all/{z}/{x}/{y}{r}.png',
    polos: 'https://{s}.basemaps.cartocdn.com/rastertiles/light_nolabels/{z}/{x}/{y}{r}.png',
  },
}

const UBIN_ESRI = {
  gelap: {
    dasar: 'https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
    label: 'https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}',
  },
  terang: {
    dasar: 'https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}',
    label: 'https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}',
  },
}

const PAKAI_CARTO = Boolean(KUNCI_CARTO)
const UBIN = PAKAI_CARTO ? UBIN_CARTO : UBIN_ESRI
const AKHIRAN_KUNCI = PAKAI_CARTO ? `?key=${KUNCI_CARTO}` : ''

const ATRIBUSI = PAKAI_CARTO
  ? '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>, &copy; <a href="https://carto.com/attributions">CARTO</a>'
  : 'Ubin &copy; <a href="https://www.esri.com/">Esri</a> &mdash; Esri, HERE, Garmin, &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'

const PUSAT = [-1.6, 108.6]
const ZOOM = 5

/**
 * Marker IoT SELALU mauve — warna menandakan SUMBER, bukan tingkat.
 * Sempat sekali dibuat mengikuti skala Ember menurut status sensor; itu keliru:
 * skala Ember milik skor risiko model, dan memakainya di sini membuat bacaan
 * sensor simulasi terlihat setara keputusan model (DESIGN_BRIEF Bagian 2.1).
 * Status sekarang di-encode lewat BENTUK — cincin luar & denyut, bukan hue.
 */
const CINCIN_STATUS_IOT = { kritis: 3, waspada: 2, normal: 0 }

/**
 * Marker alert: cincin + inti, bukan bulatan penuh.
 * Cincin memberi bentuk yang terbaca sebagai penanda instrumen dan tetap
 * terlihat saat marker menumpuk — bulatan penuh saling menutupi total.
 * Ukuran mengikuti tingkat keparahan sehingga hierarki terbaca dari zoom jauh.
 */
function ikonAlert(alert) {
  const tingkat = tingkatRisiko(alert)
  const kritis = tingkat.urut >= 4
  const d = 12 + tingkat.urut * 3
  const denyut = kritis
    ? `<span class="absolute inset-0 rounded-full animasi-denyut" style="box-shadow:0 0 0 2px ${tingkat.isi}"></span>`
    : ''
  // Halo ikut tema: di peta terang, cincin flare kuning butuh pemisah gelap
  // agar tetap terbaca; di peta gelap sebaliknya. Hue Ember-nya tidak diubah.
  return L.divIcon({
    className: '',
    iconSize: [d, d],
    iconAnchor: [d / 2, d / 2],
    html: `<span class="marker-peta relative block rounded-full" style="width:${d}px;height:${d}px;border:2px solid ${tingkat.isi};background:color-mix(in srgb, var(--marker-halo) 72%, transparent);box-shadow:0 0 0 1px color-mix(in srgb, var(--marker-kontras) 55%, transparent), 0 0 10px color-mix(in srgb, ${tingkat.isi} 40%, transparent)">
      <span class="absolute left-1/2 top-1/2 rounded-full" style="width:${Math.round(d * 0.34)}px;height:${Math.round(d * 0.34)}px;transform:translate(-50%,-50%);background:${tingkat.isi}"></span>
      ${denyut}
    </span>`,
  })
}

/**
 * Marker konteks size-up — bentuknya SENGAJA berbeda dari semua marker deteksi.
 *
 * Air memakai tetesan, akses memakai batang. Keduanya tidak pernah memakai
 * bulatan (alert), belah ketupat (FIRMS), atau kotak (sensor), karena bentuk
 * adalah cara pembaca membedakan "ini yang dideteksi model" dari "ini konteks
 * dari peta terbuka". Ukurannya juga lebih kecil: konteks tidak boleh menarik
 * mata lebih dulu daripada api.
 */
const IKON_AIR = L.divIcon({
  className: '',
  iconSize: [10, 10],
  iconAnchor: [5, 5],
  html: '<span class="marker-peta block" style="width:10px;height:10px;background:var(--marker-satelit);border-radius:50% 50% 50% 0;transform:rotate(-45deg);box-shadow:0 0 0 1.5px var(--marker-halo)"></span>',
})

const IKON_AKSES = L.divIcon({
  className: '',
  iconSize: [9, 9],
  iconAnchor: [4.5, 4.5],
  html: '<span class="marker-peta block" style="width:9px;height:3px;background:var(--marker-patroli);box-shadow:0 0 0 1.5px var(--marker-halo)"></span>',
})

const IKON_FIRMS = L.divIcon({
  className: '',
  iconSize: [11, 11],
  iconAnchor: [5.5, 5.5],
  html: '<span class="marker-peta block rotate-45" style="width:11px;height:11px;background:var(--marker-satelit);box-shadow:0 0 0 1.5px var(--marker-halo)"></span>',
})

function ikonIot(status) {
  const cincin = CINCIN_STATUS_IOT[status] ?? 0
  const denyut =
    status === 'kritis'
      ? '<span class="absolute inset-0 rounded-sm animasi-denyut" style="box-shadow:0 0 0 3px var(--marker-iot)"></span>'
      : ''
  return L.divIcon({
    className: '',
    iconSize: [13, 13],
    iconAnchor: [6.5, 6.5],
    html: `<span class="marker-peta relative block rounded-sm" style="width:13px;height:13px;background:var(--marker-iot);border:2px solid var(--marker-halo);box-shadow:0 0 0 ${cincin}px color-mix(in srgb, var(--marker-iot) 60%, transparent)">${denyut}</span>`,
  })
}

/** Menyesuaikan viewport ke titik yang sedang aktif tanpa mengubah zoom user. */
function IkutiFokus({ fokus }) {
  const peta = useMap()
  useEffect(() => {
    if (fokus) peta.flyTo(fokus, Math.max(peta.getZoom(), 9), { duration: 0.8 })
  }, [peta, fokus?.[0], fokus?.[1]]) // eslint-disable-line react-hooks/exhaustive-deps
  return null
}

/**
 * Sekali di awal, rapatkan viewport ke titik yang benar-benar ada datanya.
 * Zoom statis level 5 memperlihatkan separuh Asia Tenggara dan membuat marker
 * jadi debu — peta harus langsung berguna, bukan cantik dari luar angkasa.
 *
 * `maxZoom` dinaikkan dari 8 ke 11 sejak data dipusatkan ke satu wilayah
 * operasi: kesepuluh alert kini muat dalam ~18 km, dan batas 8 menyisakan
 * separuh Kalimantan kosong di sekelilingnya.
 */
function RapatkanKeData({ titik }) {
  const peta = useMap()
  const kunci = titik.length
  useEffect(() => {
    if (!kunci) return
    peta.fitBounds(L.latLngBounds(titik), { padding: [64, 64], maxZoom: 11, animate: false })
  }, [peta, kunci]) // eslint-disable-line react-hooks/exhaustive-deps
  return null
}

export default function MapView({
  alerts = [],
  hotspots = [],
  nodeIot = [],
  rutePatroli = [],
  sizeup = {},
  sapuan = null,
  wilayah = null,
  sorot = null,
  onSorot = () => {},
  lapisan = { alert: true, firms: true, iot: true, patroli: true, angin: true, konteks: true, sapuan: true },
  varian = 'berlabel',
  fokus = null,
  tinggi = '100%',
}) {
  const navigate = useNavigate()
  const { tema, terang } = useTema()
  // Leaflet menulis `color` polyline sebagai atribut SVG, dan `var()` tidak
  // resolve di atribut presentasi — jadi nilainya harus konkret di sini.
  const warnaPatroli = terang ? '#6A604F' : '#B8AFA0'
  // Alasan yang sama persis dengan `warnaPatroli` di atas: garis konteks juga
  // polyline, jadi warnanya juga harus konkret. Nilainya mengikuti token
  // satellite per tema (lihat src/index.css).
  const warnaAir = terang ? '#2F6180' : '#5B8AA6'
  const jalur = useMemo(
    () => rutePatroli.filter((r) => Array.isArray(r.jalur) && r.jalur.length > 1),
    [rutePatroli],
  )
  const titikData = useMemo(
    () => [
      ...alerts.map((a) => [a.location.lat, a.location.lon]),
      ...nodeIot.map((n) => [n.lat, n.lon]),
    ],
    [alerts, nodeIot],
  )

  return (
    <MapContainer
      center={PUSAT}
      zoom={ZOOM}
      minZoom={4}
      maxZoom={14}
      scrollWheelZoom
      zoomControl
      style={{ height: tinggi, width: '100%' }}
      attributionControl
    >
      {/* Dua penyedia, dua bentuk lapisan.
          CARTO punya gaya berlabel tunggal → satu TileLayer.
          Esri memisahkan label ke lapisan `Reference` → dua TileLayer.
          Peredupan CSS HANYA untuk Esri: daratannya jauh lebih terang daripada
          CARTO Dark Matter, dan menerapkannya ke CARTO akan membuat peta nyaris
          hitam pekat serta menelan sungai dan kanal yang justru perlu dilihat. */}
      {PAKAI_CARTO ? (
        <TileLayer
          key={`carto-${tema}-${varian}`}
          url={(UBIN[tema] ?? UBIN.gelap)[varian] + AKHIRAN_KUNCI}
          attribution={ATRIBUSI}
          subdomains="abcd"
          maxZoom={20}
        />
      ) : (
        <>
          <TileLayer
            key={`esri-dasar-${tema}`}
            className="ubin-dasar"
            url={(UBIN[tema] ?? UBIN.gelap).dasar}
            attribution={ATRIBUSI}
            maxZoom={16}
          />
          {varian === 'berlabel' && (
            <TileLayer
              key={`esri-label-${tema}`}
              className="ubin-label"
              url={(UBIN[tema] ?? UBIN.gelap).label}
              maxZoom={16}
            />
          )}
        </>
      )}

      <RapatkanKeData titik={titikData} />
      <IkutiFokus fokus={fokus} />

      {/* Sapuan drone + pangkalan. Digambar sebelum marker deteksi supaya
          nomor singgahnya tidak menutupi alert model. */}
      {lapisan.sapuan && (
        <SapuanDrone sapuan={sapuan} wilayah={wilayah} tampilkanTerlewat={lapisan.firms} />
      )}

      {/* Proyeksi angin — paling belakang. Lapisan konteks tidak boleh menutupi
          satu pun marker deteksi yang duduk di atasnya.

          Digambar untuk SETIAP alert yang punya data size-up. Di mode cuplikan
          itu berarti kesepuluhnya, dan pola anginnya yang berbeda-beda antar
          pulau justru jadi terbaca sekaligus — sesuatu yang tidak terlihat
          kalau hanya satu titik yang digambar. */}
      {lapisan.angin &&
        alerts.map((alert) => {
          const cuaca = sizeup[alert.alert_id]?.blok?.cuaca
          if (cuaca?.status !== 'ada' || cuaca.arah_rambatan_deg == null) return null
          return (
            <KerucutAngin
              key={`angin-${alert.alert_id}`}
              lat={alert.location.lat}
              lon={alert.location.lon}
              arahRambatanDeg={cuaca.arah_rambatan_deg}
              anginKmj={cuaca.angin_kmj}
            />
          )
        })}

      {/* Sumber air & akses — HANYA untuk titik yang sedang disorot.
          Menggambarnya untuk semua alert menghasilkan ratusan marker yang
          menenggelamkan deteksi model; dan size-up di lapangan memang
          dikerjakan satu titik pada satu waktu. */}
      {lapisan.konteks &&
        sorot &&
        (() => {
          const konteks = sizeup[sorot]
          const alert = alerts.find((a) => a.alert_id === sorot)
          if (!konteks || !alert) return null
          const asal = [alert.location.lat, alert.location.lon]
          const air = konteks.blok?.sumber_air?.daftar ?? []
          const akses = konteks.blok?.akses?.daftar ?? []
          return (
            <>
              {air.slice(0, 3).map((f, i) => (
                <Fragment key={`air-${i}-${f.lat}-${f.lon}`}>
                  {/* Garis penghubung: tanpa itu, marker air terbaca sebagai
                      titik lepas alih-alih "sumber air UNTUK alert ini". */}
                  <Polyline
                    positions={[asal, [f.lat, f.lon]]}
                    pathOptions={{
                      color: warnaAir,
                      weight: 1,
                      opacity: 0.45,
                      dashArray: '3 5',
                      interactive: false,
                    }}
                  />
                  <Marker position={[f.lat, f.lon]} icon={IKON_AIR} alt={`Sumber air ${f.jenis_nama}`}>
                    <Tooltip>
                      {f.nama || f.jenis_nama} · {f.jarak_km} km
                      {f.kanal_gambut ? ' · kanal gambut' : ''}
                    </Tooltip>
                  </Marker>
                </Fragment>
              ))}
              {akses.slice(0, 3).map((f, i) => (
                <Fragment key={`akses-${i}-${f.lat}-${f.lon}`}>
                  <Polyline
                    positions={[asal, [f.lat, f.lon]]}
                    pathOptions={{
                      color: warnaPatroli,
                      weight: 1,
                      opacity: 0.4,
                      dashArray: '2 6',
                      interactive: false,
                    }}
                  />
                  <Marker position={[f.lat, f.lon]} icon={IKON_AKSES} alt={`Akses ${f.jenis_nama}`}>
                    <Tooltip>
                      {f.nama || f.jenis_nama} · {f.jarak_km} km
                      {f.kendaraan_berat === false ? ' · roda dua' : ''}
                    </Tooltip>
                  </Marker>
                </Fragment>
              ))}
            </>
          )
        })()}

      {/* Rute patroli — garis putus-putus, paling belakang secara visual */}
      {lapisan.patroli &&
        jalur.map((rute) => (
          <Polyline
            key={rute.rute_id}
            positions={rute.jalur}
            pathOptions={{
              color: warnaPatroli,
              // Rute yang TIDAK tersambung jaringan jalan digambar lebih tipis
              // dan bertitik rapat. Bentuknya sengaja dibedakan: ia garis lurus
              // yang menandakan "belum ada jalan ke sana", bukan rute tempuh —
              // dan dua hal itu tidak boleh terlihat sama.
              weight: rute.tersambung_jalan === false ? 1 : 1.6,
              opacity: rute.status === 'berjalan' ? 0.75 : 0.4,
              dashArray:
                rute.tersambung_jalan === false
                  ? '1 5'
                  : rute.status === 'berjalan'
                    ? '6 5'
                    : '2 6',
            }}
          >
            <Tooltip sticky>
              <div className="font-display text-caption text-haze-100">{rute.nama}</div>
              <div className="text-[0.6875rem] text-haze-400">
                {rute.regu} · {rute.status}
              </div>
              {/* Jarak dan durasi TEMPUH, dihitung di atas jaringan jalan nyata
                  — bukan jarak lurus. Perbedaannya besar: rute Kalteng 49 km
                  lewat jalan padahal garis lurusnya jauh lebih pendek. */}
              {typeof rute.jarak_km === 'number' && (
                <div className="mt-1 font-mono text-[0.6875rem] text-haze-300">
                  {rute.jarak_km} km · {rute.durasi_menit} menit tempuh
                </div>
              )}
              {rute.tersambung_jalan === false && (
                // Temuan operasional, bukan kegagalan data: tidak ada jalan
                // terpetakan yang mencapai titik ini. Justru inilah alasan
                // terkuat kenapa verifikasi lewat drone berguna di gambut.
                <div className="mt-1 flex items-start gap-1.5 text-[0.6875rem] leading-relaxed text-aksen-kuat">
                  <span>
                    Tidak ada jalan terpetakan ke titik ini — jalan terdekat{' '}
                    <span className="font-mono">
                      {(rute.penempelan_terjauh_m / 1000).toFixed(1)} km
                    </span>
                    . Garis lurus, bukan rute tempuh.
                  </span>
                </div>
              )}
              <div className="mt-1 border-t border-ash-700 pt-1 text-[0.625rem] leading-relaxed text-haze-500">
                Rencana rute <span className="text-haze-400">contoh</span>
                {rute.tersambung_jalan === false
                  ? '. Nama regu dan jadwalnya karangan untuk demo.'
                  : '. Geometrinya jalan nyata dari OpenStreetMap; titik sektor, regu, dan jadwalnya karangan untuk demo.'}
              </div>
            </Tooltip>
          </Polyline>
        ))}

      {/* Hotspot FIRMS mentah */}
      {lapisan.firms &&
        hotspots.map((titik, i) => (
          <Marker
            key={`firms-${i}`}
            position={[titik.lat, titik.lon]}
            icon={IKON_FIRMS}
            alt={`Hotspot satelit ${koordinat(titik.lat, titik.lon)}`}
          >
            <Tooltip>
              {koordinat(titik.lat, titik.lon)} · {titik.kecerahan_k?.toFixed(1) ?? '—'} K ·
              FRP {titik.frp_mw?.toFixed(1) ?? '—'} MW
            </Tooltip>
          </Marker>
        ))}

      {/* Sensor darat simulasi */}
      {lapisan.iot &&
        nodeIot.map((node) => (
          <Marker
            key={node.node_id}
            position={[node.lat, node.lon]}
            icon={ikonIot(node.status)}
            alt={`Sensor simulasi ${node.nama}, status ${node.status}`}
          >
            <Popup>
              <div className="p-3">
                <div className="mb-1 flex items-center gap-1.5">
                  <span className="rounded-sm bg-iot/20 px-1.5 py-0.5 font-mono text-[0.5625rem] uppercase tracking-[0.12em] text-iot">
                    simulasi
                  </span>
                  <span className="font-mono text-[0.6875rem] text-haze-500">
                    {node.node_id}
                  </span>
                </div>
                <div className="font-display text-heading text-haze-100">{node.nama}</div>
                <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 font-mono text-mono-data">
                  {[
                    ['Suhu', `${node.bacaan.suhu_c} °C`, node.bacaan.suhu_c > node.ambang.suhu_c],
                    [
                      'Lembap udara',
                      `${node.bacaan.kelembapan_persen} %`,
                      node.bacaan.kelembapan_persen < node.ambang.kelembapan_persen,
                    ],
                    ['PM2.5', `${node.bacaan.pm25_ugm3} µg/m³`, node.bacaan.pm25_ugm3 > node.ambang.pm25_ugm3],
                    [
                      'Lembap gambut',
                      `${node.bacaan.kelembapan_gambut_persen} %`,
                      node.bacaan.kelembapan_gambut_persen < node.ambang.kelembapan_gambut_persen,
                    ],
                  ].map(([nama, nilai, lewatAmbang]) => (
                    <div key={nama}>
                      <dt className="text-[0.625rem] uppercase tracking-[0.1em] text-haze-500">
                        {nama}
                      </dt>
                      <dd className={lewatAmbang ? 'text-aksen' : 'text-haze-200'}>{nilai}</dd>
                    </div>
                  ))}
                </dl>
                <p className="mt-2 border-t border-ash-700 pt-2 text-caption text-haze-500">
                  Bacaan disimulasikan untuk demo — bukan sensor lapangan.
                </p>
              </div>
            </Popup>
          </Marker>
        ))}

      {/* Alert model — lapisan paling atas */}
      {lapisan.alert &&
        alerts.map((alert) => {
          const tingkat = tingkatRisiko(alert)
          return (
            <Marker
              key={alert.alert_id}
              position={[alert.location.lat, alert.location.lon]}
              icon={ikonAlert(alert)}
              alt={`Alert ${LABEL_PREDIKSI[alert.prediction.label]}, ${tingkat.nama}, keyakinan ${angkaPersen(alert.prediction.confidence)} persen`}
              eventHandlers={{
                // Klik menyorot, bukan membuka halaman. Membuka rincian sudah
                // disediakan tombol di dalam popup; menjadikan klik marker
                // sebagai navigasi akan membuat operator tidak punya cara
                // melihat konteks air/akses tanpa meninggalkan peta.
                click: () => onSorot(alert.alert_id),
                keydown: (e) => {
                  if (e.originalEvent.key === 'Enter') navigate(`/alert/${alert.alert_id}`)
                },
              }}
            >
              <Popup>
                <div className="p-3">
                  <div className="flex items-center gap-2">
                    <Ikon nama={tingkat.ikon} ukuran={14} style={{ color: tingkat.teks }} />
                    <span className="font-display text-heading text-haze-100">
                      {LABEL_PREDIKSI[alert.prediction.label]}
                    </span>
                  </div>
                  <div className="mt-0.5 text-caption" style={{ color: tingkat.teks }}>
                    {tingkat.nama} · keyakinan {angkaPersen(alert.prediction.confidence)}%
                  </div>
                  <dl className="mt-2 space-y-0.5 font-mono text-mono-data text-haze-400">
                    <div>{koordinat(alert.location.lat, alert.location.lon)}</div>
                    <div>
                      {jam(alert.timestamp)} WIB · {LABEL_PEMICU[alert.source_trigger]}
                    </div>
                  </dl>

                  {/* Ringkasan size-up di dalam popup. Batas model ↔ aturan
                      tetap dijaga lewat garis pemisah dan label sumbernya:
                      di atas garis keluaran model, di bawahnya aturan
                      deterministik atas data terbuka. */}
                  {(() => {
                    const k = sizeup[alert.alert_id]?.blok
                    if (!k) return null
                    const b = k.bahaya
                    const w = WARNA_BAHAYA[b?.tingkat] ?? WARNA_BAHAYA[1]
                    return (
                      <div className="mt-2 space-y-1 border-t border-ash-700 pt-2">
                        {b?.status === 'ada' && (
                          <div className="flex items-baseline gap-1.5">
                            <span className="label-meta">FWI</span>
                            <span
                              className="font-mono text-mono-data tabular-nums"
                              style={{ color: w.teks }}
                            >
                              {b.fwi}
                            </span>
                            <span className="text-caption" style={{ color: w.teks }}>
                              {b.nama}
                            </span>
                          </div>
                        )}
                        {k.bmkg?.status === 'ada' && (
                          <div className="text-[0.6875rem] text-haze-400">
                            BMKG {k.bmkg.desa}: {k.bmkg.cuaca} · {k.bmkg.suhu_c} °C · RH{' '}
                            {k.bmkg.kelembapan_persen}%
                          </div>
                        )}
                        {k.penutup_lahan?.status === 'ada' && (
                          <div className="text-[0.6875rem] text-haze-400">
                            BIG: {k.penutup_lahan.nama}
                          </div>
                        )}
                        {k.sumber_air?.daftar?.[0] && (
                          <div className="text-[0.6875rem] text-haze-400">
                            Air terdekat {jarakSizeUp(k.sumber_air.daftar[0].jarak_km)}
                            {k.peralatan?.status === 'ada' && ` · saran ${k.peralatan.nama}`}
                          </div>
                        )}
                      </div>
                    )
                  })()}
                  <button
                    type="button"
                    onClick={() => navigate(`/alert/${alert.alert_id}`)}
                    className="mt-3 inline-flex w-full items-center justify-center gap-1.5 rounded border border-ash-600 bg-ash-800 px-2.5 py-1.5 text-caption text-haze-200 [transition:background-color_140ms_cubic-bezier(0.22,0.61,0.36,1)] hover:bg-ash-700"
                  >
                    Buka rincian
                    <Ikon nama="panah" ukuran={13} />
                  </button>
                </div>
              </Popup>
            </Marker>
          )
        })}
    </MapContainer>
  )
}
