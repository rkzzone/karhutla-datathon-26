import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  adaLapisanLangsung,
  ambilAlerts,
  ambilHotspotFirms,
  ambilNodeIot,
  ambilRutePatroli,
  ambilSapuanDrone,
  ambilSizeUpBanyak,
  ambilWilayahOperasi,
} from '../api/client.js'
import Ikon from '../components/Ikon.jsx'
import IronbowRibbon, { LegendaIronbow } from '../components/IronbowRibbon.jsx'
import LayerToggle from '../components/LayerToggle.jsx'
import MapView from '../components/MapView.jsx'
import { StateGalat, StateMemuat } from '../components/StatePesan.jsx'
import { angkaPersen, jam, koordinat, tanggalJam, tanggalSingkat } from '../lib/format.js'
import { WARNA_BAHAYA } from '../lib/sizeup.js'
import { LABEL_PREDIKSI, URUTAN, adaApi, tingkatRisiko } from '../lib/risk.js'
import { useData } from '../lib/useData.js'

/**
 * HALAMAN 1 — Peta Operasi.
 *
 * Peta adalah elemen utama, bukan tabel (docs/DESIGN_BRIEF.md). Semua panel lain
 * mengambang di atasnya atau duduk di rail sempit; tidak ada yang boleh tumbuh
 * sampai mengalahkan peta secara visual.
 */

/**
 * Kontrol basemap. Wireframe brief menunjukkan tombol [◐] di kanan atas —
 * di sini artinya BUKAN terang/gelap (basemap terang dilarang, brief Bagian 8),
 * melainkan dua varian basemap gelap: berlabel vs polos. Varian polos dipakai
 * saat marker menumpuk supaya nama tempat tidak menambah kebisingan visual.
 */
const VARIAN_PETA = [
  { kunci: 'berlabel', nama: 'Berlabel' },
  { kunci: 'polos', nama: 'Polos' },
]

function Kpi({ label, nilai, satuan, warna = 'var(--haze-100-warna)', catatan }) {
  return (
    <div className="min-w-[104px]">
      <div className="label-meta">{label}</div>
      <div className="mt-0.5 flex items-baseline gap-1">
        <span className="font-display text-[1.75rem] leading-none tabular-nums" style={{ color: warna }}>
          {nilai}
        </span>
        {satuan && <span className="font-mono text-[0.6875rem] text-haze-500">{satuan}</span>}
      </div>
      {catatan && <div className="mt-0.5 text-[0.6875rem] text-haze-500">{catatan}</div>}
    </div>
  )
}

export default function PetaOperasi() {
  const [lapisan, setLapisan] = useState({
    alert: true,
    firms: true,
    iot: true,
    patroli: true,
    angin: true,
    konteks: true,
    sapuan: true,
  })
  const [varian, setVarian] = useState('berlabel')
  const [fokus, setFokus] = useState(null)
  const [sorot, setSorot] = useState(null)

  const alerts = useData(ambilAlerts)
  const firms = useData(ambilHotspotFirms)
  const iot = useData(ambilNodeIot)
  const patroli = useData(ambilRutePatroli)
  const sapuan = useData(ambilSapuanDrone)
  const wilayah = useData(ambilWilayahOperasi)

  const daftar = alerts.data ?? []
  const node = iot.data?.node ?? []
  const titikFirms = firms.data?.titik ?? []

  const teratas = useMemo(
    () => [...daftar].sort(URUTAN.risiko.bandingkan).slice(0, 5),
    [daftar],
  )
  /**
   * Konteks size-up untuk lapisan peta.
   *
   * Berapa banyak titik yang terisi berbeda menurut mode, dan perbedaan itu
   * DINYATAKAN di layar alih-alih disamarkan:
   *
   *   cuplikan → kesepuluhnya, karena semuanya sudah ada di dalam bundle dan
   *              menggambarnya tidak menambah satu pun panggilan jaringan
   *   langsung → hanya beberapa teratas, karena tiap titik berarti satu kueri
   *              Overpass dan dua kueri BIG; menarik sepuluh sekaligus adalah
   *              pola yang persis memicu blokir keduanya
   *
   * Lihat `ambilSizeUpBanyak` di api/client.js.
   */
  const konteks = useData(() => ambilSizeUpBanyak(daftar), [daftar.length])
  const sizeup = konteks.data?.menurutAlert ?? {}
  const konteksLengkap = konteks.data?.lengkap ?? true
  const konteksJumlah = konteks.data?.jumlah ?? 0

  const berapi = daftar.filter((a) => adaApi(a.prediction.label))
  const belumDiputus = daftar.filter((a) => !a.operator_decision).length
  const nodeKritis = node.filter((n) => n.status === 'kritis').length

  return (
    <div className="flex flex-1 flex-col">
      {/* Strip kendali + ringkasan */}
      <div className="border-b border-ash-700 bg-ash-950/70">
        <div className="mx-auto flex max-w-[1800px] flex-wrap items-center gap-x-8 gap-y-4 px-4 py-3 sm:px-6">
          <div>
            <h1 className="font-display text-display-lg text-haze-100">Peta Operasi</h1>
            <p className="text-caption text-haze-400">
              {wilayah.data?.wilayah
                ? `Satu wilayah operasi — ${wilayah.data.wilayah}`
                : 'Pemicu satelit, sensor darat, dan prioritas patroli dalam satu tampilan.'}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-x-7 gap-y-3">
            <Kpi
              label="Titik berapi"
              nilai={berapi.length}
              satuan={`/ ${daftar.length}`}
              warna="var(--tingkat-3-teks)"
              catatan="alert aktif"
            />
            <Kpi label="Belum diputus" nilai={belumDiputus} catatan="menunggu operator" />
            <Kpi
              label="Sensor kritis"
              nilai={nodeKritis}
              satuan={`/ ${node.length}`}
              warna="var(--marker-iot)"
              catatan="jaringan simulasi"
            />
          </div>

          <div className="ml-auto flex flex-wrap items-center gap-3">
            <LayerToggle
              nilai={lapisan}
              onUbah={setLapisan}
              jumlah={{
                sapuan: sapuan.data?.urutan?.length ?? 0,
                alert: daftar.length,
                firms: titikFirms.length,
                iot: node.length,
                patroli: patroli.data?.rute?.length ?? 0,
              }}
            />
            <div
              role="group"
              aria-label="Varian basemap gelap"
              className="flex overflow-hidden rounded-md border border-ash-700"
            >
              {VARIAN_PETA.map((v) => (
                <button
                  key={v.kunci}
                  type="button"
                  aria-pressed={varian === v.kunci}
                  onClick={() => setVarian(v.kunci)}
                  className={`px-2.5 py-1.5 text-caption [transition:background-color_150ms_cubic-bezier(0.22,0.61,0.36,1),color_150ms_linear] ${
                    varian === v.kunci
                      ? 'bg-ash-800 text-haze-100'
                      : 'bg-ash-900 text-haze-500 hover:text-haze-300'
                  }`}
                >
                  {v.nama}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Peta + rail */}
      <div className="flex flex-1 flex-col lg:flex-row">
        <div className="relative min-h-[420px] flex-1 lg:min-h-0">
          <MapView
            key={varian}
            alerts={daftar}
            hotspots={titikFirms}
            nodeIot={node}
            rutePatroli={patroli.data?.rute ?? []}
            sizeup={sizeup}
            sapuan={sapuan.data}
            wilayah={wilayah.data}
            sorot={sorot}
            onSorot={setSorot}
            lapisan={lapisan}
            varian={varian}
            fokus={fokus}
            tinggi="100%"
          />

          {/* Legenda mengambang — ramp Ironbow yang sama dengan AlertCard */}
          <div className="pointer-events-none absolute bottom-6 left-3 z-[400] w-[210px] rounded-lg border border-ash-700 bg-ash-950/92 p-3 shadow-ash-lg backdrop-blur">
            <LegendaIronbow />
            <ul className="mt-3 space-y-1.5 border-t border-ash-700 pt-3">
              {/* Kolom `bentuk` bukan hiasan. Sumber air dan hotspot satelit
                  memakai token warna yang sama, dan di peta keduanya dipisahkan
                  oleh BENTUK — tetesan lawan belah ketupat. Legenda yang
                  menggambar keduanya sebagai kotak polos justru membuang
                  satu-satunya pembeda yang dipakai peta, dan melanggar aturan
                  brief Bagian 5: makna tidak boleh di-encode lewat warna saja. */}
              {[
                ['var(--marker-satelit)', 'Hotspot satelit', null, 'ketupat'],
                ['var(--marker-iot)', 'Sensor darat', 'simulasi', 'kotak'],
                ['var(--marker-patroli)', 'Pengerahan regu', 'contoh', 'garis'],
                ['#F5C242', 'Prioritas patroli', 'urutan', 'garis'],
                ['#F5C242', 'Posko / titik lepas landas', 'andaian', 'segitiga'],
                ['#E8752C', 'Proyeksi angin', 'proyeksi', 'kotak'],
                ['var(--marker-satelit)', 'Sumber air (OSM)', null, 'tetes'],
                ['var(--marker-patroli)', 'Akses jalan (OSM)', null, 'batang'],
              ].map(([warna, nama, tanda, bentuk]) => (
                <li key={nama} className="flex items-center gap-2 text-caption text-haze-400">
                  <span className="flex h-2.5 w-2.5 shrink-0 items-center justify-center">
                    <span
                      style={{
                        backgroundColor: warna,
                        ...(bentuk === 'ketupat'
                          ? { width: 8, height: 8, transform: 'rotate(45deg)' }
                          : bentuk === 'tetes'
                            ? {
                                width: 9,
                                height: 9,
                                borderRadius: '50% 50% 50% 0',
                                transform: 'rotate(-45deg)',
                              }
                            : bentuk === 'batang'
                              ? { width: 10, height: 3 }
                              : bentuk === 'garis'
                                ? { width: 10, height: 2 }
                                : bentuk === 'segitiga'
                                  ? {
                                      width: 0,
                                      height: 0,
                                      backgroundColor: 'transparent',
                                      borderLeft: '5px solid transparent',
                                      borderRight: '5px solid transparent',
                                      borderBottom: `9px solid ${warna}`,
                                    }
                                  : { width: 10, height: 10, borderRadius: 2 }),
                      }}
                    />
                  </span>
                  {nama}
                  {tanda && (
                    <span
                      className="rounded-sm px-1 font-mono text-[0.5625rem] uppercase tracking-[0.12em]"
                      style={{
                        color: warna,
                        backgroundColor: `color-mix(in srgb, ${warna} 20%, transparent)`,
                      }}
                    >
                      {tanda}
                    </span>
                  )}
                </li>
              ))}
            </ul>
            {/* Cakupan lapisan konteks dinyatakan apa adanya. Kalau hanya
                sebagian titik yang punya konteks, operator harus tahu — peta
                yang diam soal itu akan terbaca seolah titik lain tidak punya
                sumber air sama sekali. */}
            {konteksJumlah > 0 && (
              <p className="mt-3 border-t border-ash-700 pt-2.5 text-[0.625rem] leading-relaxed text-haze-500">
                Konteks size-up terisi untuk{' '}
                <span className="font-mono text-haze-400">{konteksJumlah}</span> dari{' '}
                <span className="font-mono text-haze-400">{daftar.length}</span> titik
                {!konteksLengkap && ' — sisanya butuh layanan langsung'}. Sorot satu
                titik untuk melihat sumber air dan aksesnya.
              </p>
            )}
          </div>

          {/* Galat FIRMS: banner di atas peta, peta tetap bisa dipakai */}
          {firms.galat && (
            <div className="absolute right-3 top-3 z-[400] max-w-sm">
              <StateGalat
                galat={firms.galat}
                onCoba={firms.muatUlang}
                judul="Hotspot satelit tidak tersedia"
              />
            </div>
          )}
          {/* Backend free-tier bisa spin-down; bangun lagi butuh ~50 detik.
              Tanpa penanda ini, lapisan FIRMS yang kosong sementara terbaca
              seperti kerusakan, padahal sedang menunggu. */}
          {firms.memuat && adaLapisanLangsung && (
            <div className="absolute right-3 top-3 z-[400] flex items-center gap-2 rounded-md border border-ash-600 bg-ash-950/92 px-2.5 py-1.5 text-caption text-haze-400 shadow-ash-md backdrop-blur">
              <span className="h-1.5 w-1.5 rounded-full bg-satellite animasi-denyut" />
              Menghubungi layanan hotspot satelit…
            </div>
          )}
          {firms.data?.is_fixture && (
            <div className="absolute right-3 top-3 z-[400] flex items-center gap-2 rounded-md border border-satellite/45 bg-ash-950/92 px-2.5 py-1.5 text-caption text-satellite shadow-ash-md backdrop-blur">
              <Ikon nama="info" ukuran={13} />
              Hotspot satelit: berkas contoh (MAP_KEY belum dipasang)
            </div>
          )}
          {/* Cuplikan: data satelit NYATA tapi beku. Titiknya tidak berdenyut —
              denyut menandakan aliran langsung, dan memakainya di sini akan
              menyiratkan kebaruan yang tidak dimiliki cuplikan. */}
          {/* DUA WAKTU YANG BERBEDA, DAN KEDUANYA HARUS TAMPIL.
              Versi sebelumnya hanya menampilkan `diambil` — kapan berkasnya
              dibekukan — sehingga banner berbunyi "diambil 27 Agu" untuk data
              satelit yang sebenarnya terekam 19-20 Agu. Pembaca wajar mengira
              hotspotnya dari hari itu. Tanggal DATA yang lebih penting, jadi ia
              yang tampil lebih dulu; waktu pembekuan menyusul sebagai metadata.

              Penyebutan jumlah juga dikoreksi: sejak penyaringnya diubah dari
              FRP ke jarak, 462 titik itu "dalam radius", bukan "terkuat". */}
          {firms.data?.is_cuplikan && (
            <div className="absolute right-3 top-3 z-[400] max-w-md rounded-md border border-satellite/45 bg-ash-950/92 px-2.5 py-1.5 text-caption text-satellite shadow-ash-md backdrop-blur">
              <div className="flex items-center gap-2">
                <Ikon nama="jam" ukuran={13} className="shrink-0" />
                <span>
                  Cuplikan hotspot satelit —{' '}
                  {firms.data.tanggal_arsip ? (
                    <>
                      data{' '}
                      <span className="font-mono text-haze-200">
                        {tanggalSingkat(firms.data.tanggal_arsip)}
                      </span>
                      {firms.data.rentang_hari > 1 && (
                        <span className="font-mono text-haze-200">
                          {' '}+{firms.data.rentang_hari - 1} hari
                        </span>
                      )}
                    </>
                  ) : (
                    <>terekam 24 jam sebelum dibekukan</>
                  )}
                </span>
              </div>
            </div>
          )}
          {firms.data && !firms.data.is_fixture && !firms.data.is_cuplikan && (
            <div className="absolute right-3 top-3 z-[400] flex items-center gap-2 rounded-md border border-satellite/45 bg-ash-950/92 px-2.5 py-1.5 text-caption text-satellite shadow-ash-md backdrop-blur">
              <span className="h-1.5 w-1.5 rounded-full bg-satellite animasi-denyut" />
              {firms.data.dipangkas ? (
                <>
                  Hotspot satelit langsung —{' '}
                  <span className="font-mono">{firms.data.jumlah}</span> terkuat dari{' '}
                  <span className="font-mono">{firms.data.jumlah_total}</span> terdeteksi
                </>
              ) : (
                <>
                  Hotspot satelit langsung —{' '}
                  <span className="font-mono">{firms.data.jumlah}</span> terdeteksi 24 jam
                  terakhir
                </>
              )}
            </div>
          )}
        </div>

        {/* Rail alert prioritas — sempit, peta tetap dominan */}
        <aside className="w-full shrink-0 border-t border-ash-700 bg-ash-950/60 lg:w-[336px] lg:border-l lg:border-t-0">
          <div className="flex items-center justify-between border-b border-ash-700 px-4 py-3">
            <h2 className="font-display text-heading text-haze-100">Prioritas tertinggi</h2>
            <Link
              to="/alert"
              className="inline-flex items-center gap-1 text-caption text-haze-400 hover:text-haze-200"
            >
              Semua alert
              <Ikon nama="panah" ukuran={13} />
            </Link>
          </div>

          {alerts.memuat && <StateMemuat pesan="Memuat titik patroli…" />}
          {alerts.galat && (
            <div className="p-3">
              <StateGalat galat={alerts.galat} onCoba={alerts.muatUlang} />
            </div>
          )}

          {!alerts.memuat && !alerts.galat && teratas.length === 0 && (
            <p className="px-4 py-8 text-center text-caption text-haze-400">
              Belum ada alert. Sistem akan menampilkan titik terdeteksi begitu patroli
              dimulai.
            </p>
          )}

          <ul className="divide-y divide-ash-800">
            {teratas.map((alert) => {
              const tingkat = tingkatRisiko(alert)
              return (
                <li key={alert.alert_id}>
                  <Link
                    to={`/alert/${alert.alert_id}`}
                    onMouseEnter={() => {
                      setFokus([alert.location.lat, alert.location.lon])
                      setSorot(alert.alert_id)
                    }}
                    onFocus={() => {
                      setFokus([alert.location.lat, alert.location.lon])
                      setSorot(alert.alert_id)
                    }}
                    className="flex items-center gap-3 px-4 py-3 [transition:background-color_150ms_cubic-bezier(0.22,0.61,0.36,1)] hover:bg-ash-900"
                  >
                    {/* Ribbon yang sama dengan AlertCard — bukan bar polos,
                        supaya bahasa visualnya konsisten lintas halaman */}
                    <IronbowRibbon
                      nilai={alert.prediction.confidence}
                      keluarga={adaApi(alert.prediction.label) ? 'ember' : 'canopy'}
                      className="h-9"
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5">
                        <Ikon nama={tingkat.ikon} ukuran={12} style={{ color: tingkat.teks }} />
                        <span className="truncate text-caption text-haze-100">
                          {LABEL_PREDIKSI[alert.prediction.label]}
                        </span>
                      </div>
                      <div className="mt-0.5 font-mono text-[0.6875rem] text-haze-500">
                        {koordinat(alert.location.lat, alert.location.lon)}
                      </div>
                      {/* FWI di samping keyakinan model, dan keduanya sengaja
                          dibedakan: keyakinan adalah keluaran MODEL atas citra,
                          FWI adalah cuaca kebakaran yang dihitung aturan. Dua
                          titik bisa sama-sama 100% yakin berapi tapi berbeda
                          jauh mendesaknya. */}
                      {(() => {
                        const b = sizeup[alert.alert_id]?.blok?.bahaya
                        if (b?.status !== 'ada') return null
                        const w = WARNA_BAHAYA[b.tingkat] ?? WARNA_BAHAYA[1]
                        return (
                          <div className="mt-1 flex items-baseline gap-1.5">
                            <span className="label-meta">FWI</span>
                            <span
                              className="font-mono text-[0.6875rem] tabular-nums"
                              style={{ color: w.teks }}
                            >
                              {b.fwi}
                            </span>
                            <span className="text-[0.625rem]" style={{ color: w.teks }}>
                              {b.nama}
                            </span>
                          </div>
                        )
                      })()}
                    </div>
                    <div className="text-right">
                      <div
                        className="font-display text-heading tabular-nums"
                        style={{ color: tingkat.teks }}
                      >
                        {angkaPersen(alert.prediction.confidence)}%
                      </div>
                      <div className="font-mono text-[0.6875rem] text-haze-500">
                        {jam(alert.timestamp)}
                      </div>
                    </div>
                  </Link>
                </li>
              )
            })}
          </ul>

          {iot.data?.simulasi && (
            <p className="border-t border-ash-700 px-4 py-3 text-[0.6875rem] leading-relaxed text-haze-500">
              Lapisan sensor darat berisi{' '}
              <span className="text-iot">data simulasi</span> untuk keperluan demo. Bacaan
              bukan berasal dari perangkat lapangan.
            </p>
          )}

          {/* Catatan patroli sejajar dengan catatan sensor di atas. Sempat tidak
              ada sama sekali: berkas datanya memuat catatan "bukan keluaran
              model, ganti dengan rencana posko", tapi catatan itu tidak pernah
              dirender — sehingga nama regu sungguhan tampil menyusuri rute
              karangan tanpa satu pun label, di peta yang sama dengan sensor
              berlabel SIMULASI. */}
          {(patroli.data?.rute?.length ?? 0) > 0 && (
            <p className="border-t border-ash-700 px-4 py-3 text-[0.6875rem] leading-relaxed text-haze-500">
              Rute pengerahan regu darat adalah{' '}
              <span className="text-haze-300">contoh</span> — nama regu dan jadwalnya
              karangan. Geometrinya nyata: jalan dari OpenStreetMap, dengan jarak dan
              durasi tempuh dihitung di atasnya. Berbeda dari prioritas patroli, yang
              lurus karena drone terbang.
            </p>
          )}
        </aside>
      </div>
    </div>
  )
}
