import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import {
  ambilAlert,
  ambilPengerahan,
  ambilSizeUp,
  kirimKeputusan,
  simpanPengerahan,
  urlMedia,
} from '../api/client.js'
import DecisionLog from '../components/DecisionLog.jsx'
import JejakAlur from '../components/JejakAlur.jsx'
import HeatmapOverlay from '../components/HeatmapOverlay.jsx'
import Ikon from '../components/Ikon.jsx'
import IronbowRibbon from '../components/IronbowRibbon.jsx'
import ModalityBadge from '../components/ModalityBadge.jsx'
import PanelSizeUp from '../components/PanelSizeUp.jsx'
import SourceBadge from '../components/SourceBadge.jsx'
import TombolSalin from '../components/TombolSalin.jsx'
import { StateGalat, StateMemuat } from '../components/StatePesan.jsx'
import { angkaPersen, idPendek, koordinat, tanggalJam } from '../lib/format.js'
import { LABEL_PREDIKSI, adaApi, tingkatRisiko } from '../lib/risk.js'
import { useData } from '../lib/useData.js'

/**
 * HALAMAN 3 — Rincian Alert.
 *
 * Susunan mengikuti wireframe brief Bagian 3: baris citra RGB | Termal, badge
 * modalitas di kolom kanan, overlay heatmap di bawah citra, lalu tiga tombol
 * keputusan operator melebar penuh di kaki halaman.
 *
 * LAPISAN SIZE-UP ditambahkan DI BAWAH bilah keputusan, bukan di atasnya, dan
 * urutan itu disengaja. Alur kerja nyata yang diceritakan praktisi berjalan
 * begini: alert masuk → operator memutuskan tindak lanjut → tim size-up
 * berangkat menggambar situasi → tim pemadam bergerak. Menaruh panel size-up
 * sebelum tombol keputusan akan membalik urutan itu di layar dan mendorong
 * operator menimbang logistik sebelum menimbang apakah ini benar-benar api.
 */

/**
 * Bingkai citra dengan rasio tetap 5:4 (rasio sensor termal umum).
 * `object-cover` dipakai supaya tidak muncul pita hitam kiri-kanan — pita itu
 * membuat panel terlihat rusak, bukan terlihat seperti umpan kamera.
 */
function Citra({ judul, src, alt, catatan }) {
  return (
    <figure className="permukaan overflow-hidden">
      <figcaption className="flex items-center justify-between border-b border-ash-700 px-3 py-2">
        <span className="label-meta">{judul}</span>
        {catatan && <span className="font-mono text-[0.625rem] text-haze-500">{catatan}</span>}
      </figcaption>
      {/* Tinggi tetap + object-cover. `aspect-[5/4]` + `max-h` sempat dipakai,
          tapi kombinasi itu membuat LEBAR ikut menyusut demi menjaga rasio dan
          menyisakan pita kosong di kanan — persis cacat yang mau dihindari. */}
      <div className="h-[288px] bg-ash-950">
        <img src={src} alt={alt} className="h-full w-full object-cover" />
      </div>
    </figure>
  )
}

export default function RincianAlert() {
  const { alertId } = useParams()
  const { data: alert, galat, memuat, muatUlang, setData } = useData(
    () => ambilAlert(alertId),
    [alertId],
  )
  const [mengirim, setMengirim] = useState(false)
  const [pengerahan, setPengerahan] = useState([])

  // Pengerahan hidup terpisah dari objek alert dan direset saat berpindah alert.
  // Menyatukannya ke dalam alert akan ditolak skema kontrak (`extra="forbid"`).
  useEffect(() => {
    setPengerahan(ambilPengerahan(alertId))
  }, [alertId])

  // Size-up ditarik TERPISAH dari alert, dan sengaja tidak menahan render
  // halaman. Ia memanggil dua layanan luar (cuaca + Overpass) yang bisa lambat
  // atau memblokir; kalau citra dan tombol keputusan ikut menunggu keduanya,
  // pekerjaan inti operator tersandera oleh lapisan konteks.
  const sizeup = useData(() => (alert ? ambilSizeUp(alert) : null), [alert?.alert_id])

  async function putuskan(nilai) {
    setMengirim(true)
    try {
      setData(await kirimKeputusan(alertId, nilai))
    } finally {
      setMengirim(false)
    }
  }

  if (memuat) {
    return (
      <div className="mx-auto w-full max-w-[1280px] px-4 py-8 sm:px-6">
        <StateMemuat pesan="Memuat rincian alert…" />
      </div>
    )
  }

  if (galat) {
    return (
      <div className="mx-auto w-full max-w-[640px] px-4 py-10 sm:px-6">
        <StateGalat galat={galat} onCoba={muatUlang} judul="Rincian alert tidak bisa dimuat" />
        <Link
          to="/alert"
          className="mt-4 inline-flex items-center gap-1.5 text-caption text-haze-400 hover:text-haze-200"
        >
          <Ikon nama="daftar" ukuran={13} />
          Kembali ke panel alert
        </Link>
      </div>
    )
  }

  const tingkat = tingkatRisiko(alert)
  const berapi = adaApi(alert.prediction.label)

  return (
    <div className="mx-auto w-full max-w-[1280px] px-4 py-6 sm:px-6 lg:py-8">
      <Link
        to="/alert"
        className="inline-flex items-center gap-1.5 text-caption text-haze-400 hover:text-haze-200"
      >
        <Ikon nama="panah" ukuran={13} className="rotate-180" />
        Panel alert
      </Link>

      {/* Kepala: skor risiko hero + identitas alert */}
      <header className="mt-3 flex flex-wrap items-stretch gap-5 border-b border-ash-700 pb-6">
        <IronbowRibbon
          nilai={alert.prediction.confidence}
          keluarga={berapi ? 'ember' : 'canopy'}
          tinggiPenuh
          className="!w-[6px]"
        />

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <Ikon nama={tingkat.ikon} ukuran={18} style={{ color: tingkat.teks }} />
            <h1 className="font-display text-display-lg text-haze-100">
              {LABEL_PREDIKSI[alert.prediction.label]}
            </h1>
          </div>
          <p className="mt-1 text-caption" style={{ color: tingkat.teks }}>
            {tingkat.nama}
          </p>
          <dl className="mt-3 flex flex-wrap gap-x-7 gap-y-2 font-mono text-mono-data">
            <div>
              <dt className="label-meta">Koordinat</dt>
              {/* Nilai desimal mentah ikut disalin, bukan bentuk berhemisfer.
                  Yang menerima teks ini menempelkannya ke aplikasi peta atau
                  GPS genggam, dan format itulah yang mereka terima langsung. */}
              <dd className="flex items-center gap-2 text-haze-200">
                {koordinat(alert.location.lat, alert.location.lon)}
                <TombolSalin
                  teks={`${alert.location.lat}, ${alert.location.lon}`}
                  label="Salin"
                  labelBerhasil="Tersalin"
                  judul="Salin koordinat desimal untuk aplikasi peta atau GPS"
                />
              </dd>
            </div>
            <div>
              <dt className="label-meta">Waktu deteksi</dt>
              <dd className="text-haze-200">{tanggalJam(alert.timestamp)}</dd>
            </div>
            <div>
              <dt className="label-meta">ID alert</dt>
              <dd className="text-haze-400">{idPendek(alert.alert_id)}</dd>
            </div>
          </dl>
          <div className="mt-3">
            <SourceBadge pemicu={alert.source_trigger} />
          </div>
        </div>

        <div className="flex flex-col items-end justify-center pl-2">
          <div className="label-meta">Keyakinan model</div>
          <div className="flex items-baseline">
            <span
              className="font-display text-display-xl tabular-nums"
              style={{ color: tingkat.teks }}
            >
              {angkaPersen(alert.prediction.confidence)}
            </span>
            <span className="ml-1 font-display text-heading" style={{ color: tingkat.teks }}>
              %
            </span>
          </div>
        </div>
      </header>

      {/* Kolom kiri: citra + heatmap · Kolom kanan: badge modalitas + log */}
      <div className="mt-6 grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-5">
          <div className="grid gap-5 sm:grid-cols-2">
            <Citra
              judul="Citra RGB — patroli drone"
              src={urlMedia(alert.images.rgb_url)}
              alt={`Frame RGB pada ${koordinat(alert.location.lat, alert.location.lon)}`}
              catatan="FLAME 2"
            />
            <Citra
              judul="Citra termal — patroli drone"
              src={urlMedia(alert.images.thermal_url)}
              alt={`Frame termal pada ${koordinat(alert.location.lat, alert.location.lon)}`}
              catatan="FLAME 2"
            />
          </div>

          <HeatmapOverlay
            localization={alert.localization}
            images={alert.images}
            label={koordinat(alert.location.lat, alert.location.lon)}
          />

          {/* Provenans citra. Wajib eksplisit: modelnya nyata dan angkanya nyata,
              tapi bingkainya berasal dari benchmark publik yang direkam di
              Arizona — bukan citra lapangan gambut Indonesia. Menyamarkan ini
              akan membuat seluruh demo tidak jujur. */}
          <p className="flex items-start gap-2 rounded-md border border-ash-700 bg-ash-900 px-3 py-2.5 text-[0.6875rem] leading-relaxed text-haze-500">
            <Ikon nama="info" ukuran={13} className="mt-0.5 shrink-0" />
            <span>
              Kedua bingkai adalah <span className="text-haze-400">citra udara
              drone</span> — inilah yang dibawa pulang penerbangan verifikasi, dan
              yang dikonsumsi model. Sumbernya benchmark publik{' '}
              <span className="text-haze-400">FLAME 2</span> (hutan pinus Arizona),
              split RFFNet val — split yang sama dengan angka evaluasi di Info
              Model. Prediksi, keandalan modalitas, dan peta atensi di halaman ini
              adalah keluaran model sungguhan atas bingkai tersebut. Koordinat
              menunjukkan lokasi penempatan yang disimulasikan di lahan gambut
              Indonesia. Sistem ini <span className="text-haze-400">tidak
              mengoperasikan drone</span>: ia mengonsumsi citra dari penerbangan
              yang memang sudah berlangsung di bawah izin yang ada.
            </span>
          </p>
        </div>

        <div className="space-y-5 lg:sticky lg:top-[4.5rem] lg:self-start">
          <ModalityBadge modality={alert.modality_reliability} variasi="penuh" />
          <JejakAlur
            alert={alert}
            pengerahan={pengerahan}
            bisaKerahkan={alert.operator_decision === 'ditindaklanjuti'}
            onPengerahan={(tahap) => setPengerahan(simpanPengerahan(alertId, tahap))}
          />
        </div>
      </div>

      {/* Bilah aksi melebar penuh di kaki halaman — wireframe brief Bagian 3 */}
      <div className="mt-5">
        <DecisionLog alert={alert} onPutuskan={putuskan} mengirim={mengirim} />
      </div>

      {/* Lapisan size-up — tahap kerja berikutnya, setelah keputusan diambil */}
      <div id="size-up" className="mt-5 scroll-mt-20">
        <PanelSizeUp
          sizeup={sizeup.data}
          galat={sizeup.galat}
          memuat={sizeup.memuat}
          onCoba={sizeup.muatUlang}
        />
      </div>
    </div>
  )
}
