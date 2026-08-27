import { useState } from 'react'

import { LABEL_KEPUTUSAN } from '../lib/risk.js'
import Ikon from './Ikon.jsx'

/**
 * Log keputusan + tiga aksi operator.
 *
 * Warna tombol sengaja NETRAL (ash/haze), bukan skala Ember — Ember menyatakan
 * skor risiko sistem, sedangkan ini aksi manusia. Mencampurnya membuat operator
 * mengira tombol ikut "menilai" (DESIGN_BRIEF Bagian 4).
 *
 * Kosakata tombol dan konfirmasi memakai kata yang sama persis:
 *   "Tindak Lanjuti" → toast "Ditindaklanjuti"   (brief Bagian 6)
 */

const AKSI = [
  { nilai: 'ditindaklanjuti', tombol: 'Tindak Lanjuti', ikon: 'centang' },
  { nilai: 'ditunda', tombol: 'Tunda', ikon: 'jam' },
  { nilai: 'alarm_palsu', tombol: 'Tandai Alarm Palsu', ikon: 'tutup' },
]

/** Bilah aksi operator — melebar penuh di kaki Halaman 3. */
export default function DecisionLog({ alert, onPutuskan, mengirim = false }) {
  const [dikirimBarusan, setDikirimBarusan] = useState(null)
  const terpilih = alert.operator_decision

  async function pilih(nilai) {
    if (mengirim) return
    await onPutuskan(nilai === terpilih ? null : nilai)
    setDikirimBarusan(nilai === terpilih ? null : nilai)
  }

  return (
    <section
      className="permukaan flex flex-wrap items-center gap-x-6 gap-y-3 p-4"
      aria-label="Keputusan operator"
    >
      <div className="min-w-[200px] flex-1">
        <div className="label-meta">Keputusan operator</div>
        <p aria-live="polite" className="mt-1 min-h-[1.25rem] text-caption">
          {mengirim ? (
            <span className="text-haze-400">Menyimpan keputusan…</span>
          ) : dikirimBarusan ? (
            <span className="inline-flex items-center gap-1.5 text-canopy-300">
              <Ikon nama="centang" ukuran={13} />
              {LABEL_KEPUTUSAN[dikirimBarusan]} — tercatat di log alert ini.
            </span>
          ) : terpilih ? (
            <span className="text-haze-400">
              Tercatat {LABEL_KEPUTUSAN[terpilih].toLowerCase()}. Klik tombol yang sama
              untuk membatalkan.
            </span>
          ) : (
            <span className="text-haze-500">
              Keputusan tercatat bersama alert dan bisa diubah selama alert masih aktif.
            </span>
          )}
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {AKSI.map((aksi) => {
          const aktif = terpilih === aksi.nilai
          return (
            <button
              key={aksi.nilai}
              type="button"
              onClick={() => pilih(aksi.nilai)}
              disabled={mengirim}
              aria-pressed={aktif}
              className={`inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md border px-4 py-2.5 text-caption font-medium
                [transition:background-color_150ms_cubic-bezier(0.22,0.61,0.36,1),border-color_150ms_cubic-bezier(0.22,0.61,0.36,1),opacity_150ms_linear]
                active:translate-y-px disabled:opacity-50
                ${
                  aktif
                    ? 'border-haze-400 bg-haze-100 text-ash-950'
                    : 'border-ash-600 bg-ash-800 text-haze-200 hover:border-ash-500 hover:bg-ash-700'
                }`}
            >
              <Ikon nama={aksi.ikon} ukuran={14} />
              {aksi.tombol}
            </button>
          )
        })}
      </div>
    </section>
  )
}
