import { useMemo, useState } from 'react'

import { ambilAlerts } from '../api/client.js'
import AlertCard, { AlertCardSkeleton } from '../components/AlertCard.jsx'
import Ikon from '../components/Ikon.jsx'
import { StateGalat, StateKosong } from '../components/StatePesan.jsx'
import { LABEL_PEMICU, URUTAN, adaApi, ringkasModalitas } from '../lib/risk.js'
import { useData } from '../lib/useData.js'

/**
 * HALAMAN 2 — Panel Alert.
 *
 * Daftar terurut risiko. Default pengurutan BUKAN confidence mentah: `no_fire`
 * dengan confidence 0.91 berarti "yakin tidak ada api", jadi menaruhnya di
 * puncak akan menyesatkan operator. Perhitungannya di lib/risk.js dan hanya
 * memakai field yang sudah ada di kontrak — tidak ada field baru.
 */

const SARINGAN = [
  { kunci: 'semua', nama: 'Semua' },
  { kunci: 'berapi', nama: 'Terindikasi api' },
  { kunci: 'belum', nama: 'Belum diputus' },
  { kunci: 'termal', nama: 'Bersandar pada termal' },
]

function cocokSaringan(alert, saringan) {
  if (saringan === 'berapi') return adaApi(alert.prediction.label)
  if (saringan === 'belum') return !alert.operator_decision
  if (saringan === 'termal') return ringkasModalitas(alert.modality_reliability).dominan === 'thermal'
  return true
}

export default function PanelAlert() {
  const [urutan, setUrutan] = useState('risiko')
  const [saringan, setSaringan] = useState('semua')
  const { data, galat, memuat, muatUlang } = useData(ambilAlerts)

  const daftar = useMemo(() => {
    if (!data) return []
    return data.filter((a) => cocokSaringan(a, saringan)).sort(URUTAN[urutan].bandingkan)
  }, [data, saringan, urutan])

  const belumDiukur = (data ?? []).filter(
    (a) => !ringkasModalitas(a.modality_reliability).terukur,
  ).length

  return (
    <div className="mx-auto w-full max-w-[1100px] px-4 py-6 sm:px-6 lg:py-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-display-lg text-haze-100">Panel Alert</h1>
          <p className="mt-1 text-caption text-haze-400">
            {memuat
              ? 'Memuat daftar alert…'
              : `${daftar.length} alert ditampilkan${
                  saringan === 'semua' ? '' : ` dari ${data?.length ?? 0} total`
                }.`}
          </p>
        </div>

        <label className="flex items-center gap-2 text-caption text-haze-400">
          Urutkan
          <select
            value={urutan}
            onChange={(e) => setUrutan(e.target.value)}
            className="rounded-md border border-ash-600 bg-ash-900 px-2.5 py-1.5 text-caption text-haze-100 [transition:border-color_140ms_cubic-bezier(0.22,0.61,0.36,1)] hover:border-ash-500"
          >
            {Object.entries(URUTAN).map(([kunci, o]) => (
              <option key={kunci} value={kunci}>
                {o.nama}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-1.5">
        {SARINGAN.map((s) => (
          <button
            key={s.kunci}
            type="button"
            aria-pressed={saringan === s.kunci}
            onClick={() => setSaringan(s.kunci)}
            className={`rounded-full border px-3 py-1 text-caption [transition:background-color_150ms_cubic-bezier(0.22,0.61,0.36,1),border-color_150ms_cubic-bezier(0.22,0.61,0.36,1),color_150ms_linear] ${
              saringan === s.kunci
                ? 'border-ash-500 bg-ash-800 text-haze-100'
                : 'border-ash-700 bg-ash-900 text-haze-500 hover:border-ash-600 hover:text-haze-300'
            }`}
          >
            {s.nama}
          </button>
        ))}
      </div>

      {belumDiukur > 0 && !memuat && !galat && (
        <p className="mt-4 flex items-start gap-2 rounded-md border border-ash-700 bg-ash-900 px-3 py-2.5 text-caption text-haze-400">
          <Ikon nama="info" ukuran={14} className="mt-0.5 shrink-0 text-haze-500" />
          <span>
            {belumDiukur} alert belum punya nilai keandalan modalitas. Badge alert
            tersebut menampilkan{' '}
            <span className="font-mono text-haze-300">—</span>, bukan angka —
            kalibrasi keandalan untuk alert itu belum selesai.
          </span>
        </p>
      )}

      <div className="mt-5 space-y-2.5">
        {memuat &&
          Array.from({ length: 5 }).map((_, i) => <AlertCardSkeleton key={i} />)}

        {galat && <StateGalat galat={galat} onCoba={muatUlang} judul="Daftar alert tidak bisa dimuat" />}

        {!memuat && !galat && daftar.length === 0 && (
          <StateKosong
            judul={
              saringan === 'semua'
                ? 'Belum ada alert.'
                : 'Tidak ada alert yang cocok dengan saringan ini.'
            }
            pesan={
              saringan === 'semua'
                ? 'Sistem akan menampilkan titik terdeteksi begitu patroli dimulai.'
                : 'Ubah saringan untuk melihat alert lain yang sedang aktif.'
            }
            aksi={
              saringan !== 'semua' && (
                <button
                  type="button"
                  onClick={() => setSaringan('semua')}
                  className="mt-4 rounded border border-ash-600 bg-ash-800 px-3 py-1.5 text-caption text-haze-200 [transition:background-color_140ms_cubic-bezier(0.22,0.61,0.36,1)] hover:bg-ash-700"
                >
                  Tampilkan semua alert
                </button>
              )
            }
          />
        )}

        {!memuat &&
          !galat &&
          daftar.map((alert) => <AlertCard key={alert.alert_id} alert={alert} />)}
      </div>

      {!memuat && !galat && daftar.length > 0 && (
        <p className="mt-6 border-t border-ash-800 pt-4 font-mono text-[0.6875rem] text-haze-500">
          Sumber pemicu: {[...new Set(daftar.map((a) => LABEL_PEMICU[a.source_trigger]))].join(' · ')}
        </p>
      )}
    </div>
  )
}
