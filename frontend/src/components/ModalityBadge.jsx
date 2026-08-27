import { persen } from '../lib/format.js'
import { ringkasModalitas } from '../lib/risk.js'
import Ikon from './Ikon.jsx'

/**
 * Badge keandalan modalitas — WAJIB tampil di setiap kartu alert.
 *
 * Alasannya bukan hiasan: ini bukti visual bahwa reliability gating benar-benar
 * dipakai saat inferensi, bukan sekadar dilatih lalu dilupakan.
 *
 * Saat `modality_reliability` masih null (Stage 5 tim model belum selesai):
 * tampilkan "—" dengan warna netral haze-400 — JANGAN 0%, jangan bar kosong
 * yang terbaca sebagai "keandalan nol" (DESIGN_BRIEF Bagian 4 & 8).
 */

const AMBANG_LEMAH = 0.45

function BarModalitas({ label, nilai, dominan }) {
  const terukur = typeof nilai === 'number'
  const lemah = terukur && nilai < AMBANG_LEMAH
  return (
    <div className="flex items-center gap-2">
      <span className="w-8 font-mono text-[0.625rem] uppercase tracking-[0.1em] text-haze-500">
        {label}
      </span>
      <div className="h-1 w-14 overflow-hidden rounded-full bg-ash-800">
        {terukur && (
          <div
            className="h-full rounded-full"
            style={{
              width: `${Math.max(3, nilai * 100)}%`,
              // Bar adalah fill, bukan teks — aman memakai ember/smoke di sini.
              // Yang netral memakai token haze supaya ikut bertukar tema; hex
              // mentah akan jadi bar terang nyaris tak terlihat di mode terang.
              backgroundColor: lemah
                ? '#6B6259'
                : dominan
                  ? '#E8752C'
                  : 'rgb(var(--haze-400))',
            }}
          />
        )}
      </div>
      <span
        className={`w-9 text-right font-mono text-mono-data ${
          terukur ? (lemah ? 'text-haze-500' : 'text-haze-200') : 'text-haze-500'
        }`}
      >
        {persen(nilai)}
      </span>
    </div>
  )
}

export default function ModalityBadge({ modality, variasi = 'ringkas', memuat = false }) {
  if (memuat) {
    return (
      <div
        className="inline-flex items-center gap-2 rounded border border-ash-700 bg-ash-800/60 px-2 py-1"
        aria-busy="true"
      >
        <span className="h-1.5 w-1.5 rounded-full bg-haze-500 animasi-denyut" />
        <span className="font-mono text-mono-data text-haze-500">Membaca keandalan…</span>
      </div>
    )
  }

  const r = ringkasModalitas(modality)

  /* ---- Ringkas: dipakai di AlertCard (Halaman 2) ---- */
  if (variasi === 'ringkas') {
    if (!r.terukur) {
      return (
        <span
          className="inline-flex items-center gap-1.5 rounded border border-dashed border-ash-600 px-2 py-0.5 text-haze-400"
          title={r.penjelasan}
        >
          <span className="font-mono text-mono-data">—</span>
          <span className="text-caption">{r.ringkas}</span>
        </span>
      )
    }
    const menonjol = r.dominan !== null
    return (
      <span
        className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 ${
          menonjol ? 'border-flame/40 bg-flame/10' : 'border-ash-600 bg-ash-800/70'
        }`}
        title={r.penjelasan}
      >
        <Ikon
          nama="gelombang"
          ukuran={12}
          className={menonjol ? 'text-aksen' : 'text-haze-400'}
        />
        <span className={`text-caption ${menonjol ? 'text-aksen' : 'text-haze-300'}`}>
          {r.ringkas}
        </span>
        <span className="font-mono text-mono-data text-haze-400">
          {persen(r.rgb)}/{persen(r.thermal)}
        </span>
      </span>
    )
  }

  /* ---- Penuh: dipakai di RincianAlert (Halaman 3) ---- */
  return (
    <div className="permukaan p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <div className="label-meta">Keandalan modalitas</div>
          <div
            className={`mt-1 font-display text-heading ${
              r.terukur ? (r.dominan ? 'text-aksen' : 'text-haze-100') : 'text-haze-400'
            }`}
          >
            {r.ringkas}
          </div>
        </div>
        <Ikon
          nama={r.terukur ? 'gelombang' : 'info'}
          ukuran={18}
          className={r.terukur ? 'mt-1 text-haze-400' : 'mt-1 text-haze-500'}
        />
      </div>

      <div className="space-y-2 border-t border-ash-700 pt-3">
        <BarModalitas label="RGB" nilai={r.rgb} dominan={r.dominan === 'rgb'} />
        <BarModalitas label="TRM" nilai={r.thermal} dominan={r.dominan === 'thermal'} />
      </div>

      <p className="mt-3 border-t border-ash-700 pt-3 text-caption text-haze-400">
        {r.penjelasan}
      </p>
    </div>
  )
}
