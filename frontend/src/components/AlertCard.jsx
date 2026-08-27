import { Link } from 'react-router-dom'

import { angkaPersen, idPendek, jam, koordinat, selangWaktu } from '../lib/format.js'
import { LABEL_KEPUTUSAN, LABEL_PEMICU, LABEL_PREDIKSI, adaApi, tingkatRisiko } from '../lib/risk.js'
import { urlMedia } from '../api/client.js'
import Ikon from './Ikon.jsx'
import IronbowRibbon from './IronbowRibbon.jsx'
import ModalityBadge from './ModalityBadge.jsx'
import SourceBadge from './SourceBadge.jsx'

/**
 * Kartu satu alert — DESIGN_BRIEF Bagian 4.
 * State wajib: default, hover (elevasi ke ash-800), selected, skeleton-loading.
 *
 * Hierarki dibaca dalam ~1 detik: ribbon (seberapa berat) → label + tingkat
 * (apa) → angka besar (seberapa yakin) → badge modalitas (kenapa boleh percaya).
 */
export default function AlertCard({ alert, terpilih = false, ke }) {
  const tingkat = tingkatRisiko(alert)
  const berapi = adaApi(alert.prediction.label)
  const sudahDiputus = Boolean(alert.operator_decision)
  // Selalu RGB di kartu. Sempat memakai termal untuk alert berapi, tapi bingkai
  // termal FLAME2 sudah ber-false-color (ungu/magenta/kuning) dan pada 72px ia
  // beradu dengan skala Ember di ribbon dan badge — dua sistem warna berbeda
  // berebut arti di satu kartu. Termal tetap tampil penuh di Rincian Alert,
  // tempat ia punya ruang dan keterangan.
  const pratinjau = urlMedia(alert.images.rgb_url)

  return (
    <Link
      to={ke ?? `/alert/${alert.alert_id}`}
      aria-current={terpilih ? 'true' : undefined}
      className={`group flex items-stretch gap-3 rounded-lg border p-3 shadow-ash-sm outline-offset-2
        [transition:background-color_160ms_cubic-bezier(0.22,0.61,0.36,1),border-color_160ms_cubic-bezier(0.22,0.61,0.36,1)]
        hover:bg-ash-800 hover:shadow-ash-md
        ${
          terpilih
            ? 'border-flame/55 bg-ash-800 shadow-ember-glow'
            : 'border-ash-700 bg-ash-900'
        }`}
    >
      {/* (a) Ironbow ribbon di tepi kiri — tebal & isian mengikuti confidence */}
      <IronbowRibbon
        nilai={alert.prediction.confidence}
        keluarga={berapi ? 'ember' : 'canopy'}
        tinggiPenuh
      />

      <img
        src={pratinjau}
        alt={
          berapi
            ? 'Pratinjau frame termal lokasi alert'
            : 'Pratinjau frame RGB lokasi alert'
        }
        width={72}
        height={58}
        loading="lazy"
        className="hidden h-[58px] w-[72px] shrink-0 rounded border border-ash-700 object-cover sm:block"
      />

      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <Ikon
            nama={tingkat.ikon}
            ukuran={14}
            className="shrink-0 translate-y-0.5"
            style={{ color: tingkat.teks }}
          />
          <span className="truncate font-display text-heading text-haze-100">
            {LABEL_PREDIKSI[alert.prediction.label]}
          </span>
          <span className="shrink-0 text-caption" style={{ color: tingkat.teks }}>
            {tingkat.nama}
          </span>
        </div>

        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-mono-data text-haze-400">
          <span>{koordinat(alert.location.lat, alert.location.lon)}</span>
          <span className="text-haze-500">{idPendek(alert.alert_id)}</span>
        </div>

        <div className="mt-2 flex flex-wrap items-center gap-2">
          <SourceBadge pemicu={alert.source_trigger} />
          {/* Badge modalitas WAJIB ada di setiap kartu */}
          <ModalityBadge modality={alert.modality_reliability} variasi="ringkas" />
          {sudahDiputus && (
            <span className="inline-flex items-center gap-1.5 rounded border border-ash-600 bg-ash-800 px-2 py-0.5 text-caption text-haze-300">
              <Ikon nama="centang" ukuran={12} className="text-canopy-300" />
              {LABEL_KEPUTUSAN[alert.operator_decision]}
            </span>
          )}
        </div>
      </div>

      <div className="flex shrink-0 flex-col items-end justify-between pl-1 text-right">
        <div>
          <span
            className="font-display text-display-lg tabular-nums"
            style={{ color: tingkat.teks }}
          >
            {angkaPersen(alert.prediction.confidence)}
          </span>
          <span className="ml-0.5 font-display text-caption" style={{ color: tingkat.teks }}>
            %
          </span>
          <div className="label-meta text-right">keyakinan</div>
        </div>
        <div className="mt-2 font-mono text-mono-data text-haze-400">
          <span className="text-haze-200">{jam(alert.timestamp)}</span>
          <span className="ml-1.5 text-[0.6875rem] text-haze-500">
            {selangWaktu(alert.timestamp)}
          </span>
        </div>
      </div>
    </Link>
  )
}

/** State skeleton-loading — struktur sama supaya tidak ada lompatan layout. */
export function AlertCardSkeleton() {
  return (
    <div
      className="flex items-stretch gap-3 rounded-lg border border-ash-700 bg-ash-900 p-3"
      aria-hidden="true"
    >
      <div className="w-[3px] shrink-0 rounded-full bg-ash-800" />
      <div className="hidden h-[58px] w-[72px] shrink-0 overflow-hidden rounded bg-ash-800 sm:block">
        <div className="h-full w-full bg-gradient-to-r from-transparent via-ash-700 to-transparent animasi-kilau" />
      </div>
      <div className="flex-1 space-y-2 py-1">
        <div className="h-4 w-40 rounded bg-ash-800" />
        <div className="h-3 w-56 rounded bg-ash-800/70" />
        <div className="h-5 w-48 rounded bg-ash-800/70" />
      </div>
      <div className="space-y-2 py-1">
        <div className="ml-auto h-7 w-14 rounded bg-ash-800" />
        <div className="ml-auto h-3 w-16 rounded bg-ash-800/70" />
      </div>
    </div>
  )
}
