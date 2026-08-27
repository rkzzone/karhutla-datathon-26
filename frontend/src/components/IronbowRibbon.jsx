import { TINGKAT } from '../lib/risk.js'
import { persen } from '../lib/format.js'

/**
 * "Ironbow Risk Ribbon" — elemen signature, DESIGN_BRIEF Bagian 2.3.
 *
 * Ramp yang sama dipakai identik di tiga tempat:
 *   (a) aksen tepi-kiri AlertCard  → <IronbowRibbon nilai={confidence} />
 *   (b) legenda peta               → <LegendaIronbow />
 *   (c) color ramp HeatmapOverlay  → gradien di public/media/heatmaps/*.svg
 *       dan di ramp legenda HeatmapOverlay
 *
 * Stop gradien di sini HARUS sama persis dengan `backgroundImage.ironbow` di
 * tailwind.config.js dan dengan stop di scripts/generate-media.mjs. Kalau salah
 * satu berubah, ubah ketiganya — kalau tidak, "elemen yang sama" jadi bohong.
 *
 * Tebal DAN tinggi isian mengikuti confidence: sekali lihat dari jauh, operator
 * tahu mana yang paling berat tanpa membaca angka.
 */

const TEBAL_MIN = 4
const TEBAL_MAKS = 10

export default function IronbowRibbon({
  nilai,
  keluarga = 'ember',
  tinggiPenuh = false,
  className = '',
}) {
  const terukur = typeof nilai === 'number' && !Number.isNaN(nilai)
  const isian = terukur ? Math.max(0.08, Math.min(1, nilai)) : 0
  const tebal = terukur ? TEBAL_MIN + (TEBAL_MAKS - TEBAL_MIN) * isian : TEBAL_MIN

  // Status aman sengaja keluar dari skala Ember sepenuhnya (brief Bagian 2.1) —
  // "aman" tidak boleh terbaca sebagai "risiko rendah".
  const latar =
    keluarga === 'canopy'
      ? 'linear-gradient(to top, #152A21 0%, #1F3A2E 45%, #4A7A5E 100%)'
      : undefined

  return (
    <div
      className={`relative shrink-0 overflow-hidden rounded-full bg-ash-800 ${className}`}
      style={{ width: `${tebal}px`, alignSelf: tinggiPenuh ? 'stretch' : undefined }}
      aria-hidden="true"
    >
      <div
        className={`absolute inset-x-0 bottom-0 ${latar ? '' : 'bg-ironbow'}`}
        style={{ height: `${isian * 100}%`, backgroundImage: latar }}
      />
      {/* Takik di batas isian. Tanpa ini selisih 94% vs 87% nyaris tak terbaca
          pada pita setipis ini — dan justru selisih itu yang dipakai operator
          untuk memilih mana yang dikejar duluan. */}
      {terukur && (
        <div
          className="absolute inset-x-0 h-[2px] bg-ash-950"
          style={{ bottom: `calc(${isian * 100}% - 1px)` }}
        />
      )}
    </div>
  )
}

/** Legenda peta — ramp identik, dibaca kiri→kanan. */
export function LegendaIronbow({ className = '' }) {
  return (
    <div className={className}>
      <div className="label-meta mb-2">Skala keparahan</div>
      <div
        className="h-2 w-full rounded-full bg-ironbow-x"
        role="img"
        aria-label="Skala keparahan dari rendah (abu bara) ke kritis (kuning terpanas)"
      />
      <div className="mt-1.5 flex justify-between font-mono text-[0.625rem] text-haze-500">
        <span>{TINGKAT[1].nama.replace('Risiko ', '')}</span>
        <span>{TINGKAT[4].nama.replace('Risiko ', '')}</span>
      </div>
    </div>
  )
}

/** Ramp berlabel angka — dipakai HeatmapOverlay di Halaman 3. */
export function RampHeatmap({ className = '' }) {
  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <span className="label-meta">Atensi</span>
      <div className="h-1.5 w-24 rounded-full bg-ironbow-x" aria-hidden="true" />
      <span className="font-mono text-[0.625rem] text-haze-500">
        {persen(0)} → {persen(1)}
      </span>
    </div>
  )
}
