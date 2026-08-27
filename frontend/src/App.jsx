import { useEffect, useState } from 'react'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'

import { adaLapisanLangsung, ambilStatusSumber, modeIntegrasi } from './api/client.js'
import { useTema } from './lib/tema.js'
import Ikon from './components/Ikon.jsx'
import InfoModel from './pages/InfoModel.jsx'
import PanelAlert from './pages/PanelAlert.jsx'
import PetaOperasi from './pages/PetaOperasi.jsx'
import RincianAlert from './pages/RincianAlert.jsx'

const NAV = [
  { ke: '/peta', nama: 'Peta Operasi', ikon: 'peta' },
  { ke: '/alert', nama: 'Panel Alert', ikon: 'daftar' },
  { ke: '/model', nama: 'Info Model', ikon: 'bagan' },
]

/**
 * Penanda sumber data — sengaja permanen di header.
 * Saat demo di depan juri harus selalu jelas apakah yang tampil berasal dari
 * mock Stage 9 atau dari inference service sungguhan (Stage 10). Menyembunyikan
 * ini akan membuat demo tidak jujur.
 */
function PenandaSumber() {
  const [sumber, setSumber] = useState(null)
  useEffect(() => {
    ambilStatusSumber()
      .then(setSumber)
      .catch(() => setSumber({ sumber: 'tidak diketahui' }))
  }, [])

  // Tiga keadaan, bukan dua. "mock" untuk data karangan sangat berbeda artinya
  // dari "batch" — keluaran model sungguhan yang dihitung sekali lalu disimpan.
  const jenis = sumber?.sumber ?? 'mock'
  const TAMPILAN = {
    model_service: {
      teks: 'model',
      titik: 'bg-canopy-400',
      judul: `Inference service hidup: ${sumber?.model_service_url ?? ''}`,
    },
    batch: {
      teks: 'model · batch',
      titik: 'bg-canopy-400',
      judul: sumber?.batch
        ? `Keluaran ${sumber.batch.checkpoint} atas ${sumber.batch.jumlah_bingkai} bingkai ${sumber.batch.dataset}. Dihitung sekali lalu disimpan — bukan layanan hidup.`
        : 'Keluaran model sungguhan, dihitung batch.',
      judulPendek: 'dihitung sekali, bukan layanan hidup',
    },
    mock: {
      teks: 'mock',
      titik: 'bg-flare',
      judul: 'Data contoh — belum ada model yang terlibat.',
    },
  }
  const t = TAMPILAN[jenis] ?? TAMPILAN.mock

  return (
    <span
      className="inline-flex items-center gap-1.5 rounded border border-ash-600 bg-ash-900 px-2 py-1 font-mono text-[0.6875rem]"
      title={t.judul}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${t.titik}`} />
      <span className="text-haze-500">sumber</span>
      <span className="text-haze-200">{t.teks}</span>
    </span>
  )
}

/**
 * Peralih tema. Ditaruh di header dan bukan di menu tersembunyi karena kondisi
 * cahaya posko berubah sepanjang hari — siang di ruang berjendela, malam saat
 * jaga. Ini setelan yang diganti berulang, bukan sekali seumur pemakaian.
 */
function PeralihTema() {
  const { terang, balik } = useTema()
  return (
    <button
      type="button"
      onClick={balik}
      aria-pressed={terang}
      title={terang ? 'Beralih ke tampilan gelap' : 'Beralih ke tampilan terang'}
      className="inline-flex items-center gap-1.5 rounded border border-ash-600 bg-ash-900 px-2 py-1 text-caption text-haze-400
        [transition:background-color_150ms_cubic-bezier(0.22,0.61,0.36,1),color_150ms_linear]
        hover:bg-ash-800 hover:text-haze-200 active:translate-y-px"
    >
      <Ikon nama={terang ? 'matahari' : 'bulan'} ukuran={14} />
      <span className="hidden font-mono text-[0.6875rem] sm:inline">
        {terang ? 'terang' : 'gelap'}
      </span>
      <span className="sr-only">
        Tampilan saat ini {terang ? 'terang' : 'gelap'}. Klik untuk menukar.
      </span>
    </button>
  )
}

function Kepala() {
  return (
    <header className="sticky top-0 z-[500] border-b border-ash-700 bg-ash-950/92 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-[1800px] items-center gap-4 px-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-2.5">
          {/* Wordmark: ramp Ember dipakai lagi sebagai tanda identitas */}
          <span className="h-6 w-1.5 shrink-0 rounded-full bg-ironbow" aria-hidden="true" />
          <div className="min-w-0 leading-tight">
            <div className="truncate font-display text-[0.9375rem] font-bold tracking-tight text-haze-100">
              Deteksi Dini Karhutla Gambut
            </div>
            <div className="label-meta">Konsol operator</div>
          </div>
        </div>

        <nav className="ml-2 flex items-center gap-1" aria-label="Navigasi utama">
          {NAV.map((item) => (
            <NavLink
              key={item.ke}
              to={item.ke}
              className={({ isActive }) =>
                `inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-caption
                 [transition:background-color_150ms_cubic-bezier(0.22,0.61,0.36,1),color_150ms_linear]
                 ${
                   isActive
                     ? 'bg-ash-800 text-haze-100'
                     : 'text-haze-400 hover:bg-ash-900 hover:text-haze-200'
                 }`
              }
            >
              <Ikon nama={item.ikon} ukuran={14} />
              <span className="hidden sm:inline">{item.nama}</span>
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          {!modeIntegrasi && (
            // Tiga situasi berbeda, jangan disamakan:
            //   integrasi penuh      → tidak ada label (semuanya lewat backend)
            //   statis + lapisan live → alert dari bundle, FIRMS/IoT dari backend
            //   statis murni          → tidak ada backend sama sekali
            <span className="hidden font-mono text-[0.6875rem] text-haze-500 lg:inline">
              {adaLapisanLangsung
                ? 'alert statis · lapisan langsung aktif'
                : 'data statis · tanpa backend'}
            </span>
          )}
          <PenandaSumber />
          <PeralihTema />
        </div>
      </div>
    </header>
  )
}

export default function App() {
  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#konten"
        className="sr-only rounded bg-haze-100 px-3 py-2 text-caption text-ash-950 focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-[600]"
      >
        Lompat ke konten
      </a>
      <Kepala />
      <main id="konten" className="flex flex-1 flex-col">
        <Routes>
          <Route path="/" element={<Navigate to="/peta" replace />} />
          <Route path="/peta" element={<PetaOperasi />} />
          <Route path="/alert" element={<PanelAlert />} />
          <Route path="/alert/:alertId" element={<RincianAlert />} />
          <Route path="/model" element={<InfoModel />} />
          <Route
            path="*"
            element={
              <div className="mx-auto max-w-md px-6 py-24 text-center">
                <p className="font-display text-display-lg text-haze-100">
                  Halaman tidak ada
                </p>
                <p className="mt-2 text-caption text-haze-400">
                  Periksa alamat yang dibuka, atau kembali ke peta operasi.
                </p>
              </div>
            }
          />
        </Routes>
      </main>
    </div>
  )
}
