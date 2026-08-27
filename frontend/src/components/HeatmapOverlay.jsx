import { useId, useState } from 'react'

import { urlMedia } from '../api/client.js'
import Ikon from './Ikon.jsx'
import { RampHeatmap } from './IronbowRibbon.jsx'

const NAMA_METODE = {
  attention_rollout: 'Attention rollout',
  segmentation_head: 'Segmentation head',
}

/**
 * Overlay lokalisasi di atas frame RGB.
 *
 * State `null` (Stage 6 tim model belum selesai): overlay DISEMBUNYIKAN rapi dan
 * frame dasar tetap tampil utuh — bukan kotak kosong/putih pecah
 * (DESIGN_BRIEF Bagian 4). Tidak ada heatmap rekaan yang digambar.
 *
 * Color ramp overlay adalah skala Ember yang sama dengan Ironbow Risk Ribbon.
 */
export default function HeatmapOverlay({ localization, images, label }) {
  const [tampil, setTampil] = useState(true)
  const [opasitas, setOpasitas] = useState(0.72)
  const idSlider = useId()

  const dasar = urlMedia(images?.rgb_url)
  const heatmap = urlMedia(localization?.heatmap_path)
  const adaHeatmap = Boolean(heatmap)

  return (
    <section className="permukaan overflow-hidden" aria-label="Lokalisasi titik panas">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-ash-700 px-4 py-3">
        <div className="flex items-center gap-2">
          <Ikon nama="mata" ukuran={16} className="text-haze-400" />
          <h2 className="font-display text-heading text-haze-100">Lokalisasi</h2>
          {adaHeatmap && localization.method && (
            <span className="rounded border border-ash-600 bg-ash-800 px-2 py-0.5 font-mono text-[0.6875rem] text-haze-400">
              {NAMA_METODE[localization.method] ?? localization.method}
            </span>
          )}
        </div>

        {adaHeatmap ? (
          <div className="flex flex-wrap items-center gap-4">
            <RampHeatmap />
            <label
              htmlFor={idSlider}
              className="flex items-center gap-2 font-mono text-[0.6875rem] text-haze-400"
            >
              Opasitas
              <input
                id={idSlider}
                type="range"
                min="0"
                max="1"
                step="0.02"
                value={opasitas}
                onChange={(e) => setOpasitas(Number(e.target.value))}
                className="h-1 w-24 cursor-pointer appearance-none rounded-full bg-ash-700 accent-flame"
              />
              <span className="w-8 tabular-nums text-haze-300">
                {Math.round(opasitas * 100)}%
              </span>
            </label>
            <button
              type="button"
              onClick={() => setTampil((v) => !v)}
              aria-pressed={tampil}
              className="rounded border border-ash-600 bg-ash-800 px-2.5 py-1 text-caption text-haze-200 [transition:background-color_140ms_cubic-bezier(0.22,0.61,0.36,1)] hover:bg-ash-700 active:translate-y-px"
            >
              {tampil ? 'Sembunyikan overlay' : 'Tampilkan overlay'}
            </button>
          </div>
        ) : (
          <span className="inline-flex items-center gap-2 rounded border border-dashed border-ash-600 px-2.5 py-1 text-caption text-haze-400">
            <Ikon nama="info" ukuran={13} />
            Peta atensi belum tersedia untuk alert ini
          </span>
        )}
      </header>

      <div className="relative h-[340px] bg-ash-950">
        <img
          src={dasar}
          alt={`Frame RGB ${label ?? 'lokasi alert'}`}
          className="h-full w-full object-cover"
        />
        {adaHeatmap && tampil && (
          <img
            src={heatmap}
            alt=""
            aria-hidden="true"
            // Komposit normal, BUKAN mix-blend-screen. Screen hanya mencerahkan,
            // jadi di atas bingkai berasap yang sudah terang ia praktis tidak
            // terlihat — persis kasus yang paling butuh overlay ini. PNG-nya
            // sudah membawa alpha per piksel (di bawah persentil 90 = transparan),
            // sehingga komposit normal sudah cukup dan terbaca di bingkai gelap
            // maupun terang.
            className="pointer-events-none absolute inset-0 h-full w-full object-cover"
            style={{ opacity: opasitas }}
          />
        )}
        <span className="pointer-events-none absolute bottom-2 right-2 rounded bg-ash-950/85 px-1.5 py-0.5 font-mono text-[0.625rem] text-haze-500">
          sampel FLAME2
        </span>
      </div>

      {!adaHeatmap && (
        <p className="border-t border-ash-700 px-4 py-3 text-caption text-haze-400">
          Model belum melaporkan peta atensi untuk alert ini. Frame RGB tetap
          ditampilkan utuh — tidak ada area yang ditandai sistem.
        </p>
      )}
    </section>
  )
}
