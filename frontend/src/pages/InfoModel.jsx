import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { ambilMetrikModel } from '../api/client.js'
import Ikon from '../components/Ikon.jsx'
import { StateGalat, StateMemuat } from '../components/StatePesan.jsx'
import { angka, persen } from '../lib/format.js'
import { PALET_SERI, useTema } from '../lib/tema.js'
import { useData } from '../lib/useData.js'

/**
 * HALAMAN 4 — Info Model. Audiensnya JURI, bukan operator.
 *
 * Gaya sengaja berbeda dari Halaman 1-3: grid lebih padat, mono-data dominan,
 * terasa seperti laporan teknis (brief Bagian 3). Token warna/tipe tetap sama —
 * yang berubah kepadatan dan hierarki, bukan palet.
 *
 * Sel bertanda "—" berarti metrik itu TIDAK PERNAH diukur/dilaporkan, bukan
 * nol dan bukan lupa diisi. Mengisi angka rekaan supaya tabel terlihat penuh
 * dilarang keras (brief Bagian 8), dan di depan juri itu jauh lebih berisiko
 * daripada kolom kosong yang jujur.
 */

/**
 * Seri kurva degradasi. Warna diambil dari `PALET_SERI` menurut tema
 * (Recharts menulis `stroke` sebagai atribut SVG — `var()` tidak resolve di
 * sana). `pola` adalah encoding kedua: identitas seri tidak boleh bergantung
 * pada warna saja (brief Bagian 5).
 */
const SERI = [
  { kunci: 'fusi', nama: 'Fusi RGB+termal', pola: null, tebal: 2.4 },
  { kunci: 'thermal_only', nama: 'Termal saja', pola: '6 3', tebal: 1.7 },
  { kunci: 'rgb_only', nama: 'RGB saja', pola: '2 3', tebal: 1.7 },
]

function Panel({ judul, catatan, anak }) {
  return (
    <section className="permukaan">
      <header className="flex flex-wrap items-baseline justify-between gap-2 border-b border-ash-700 px-4 py-2.5">
        <h2 className="font-display text-[1.0625rem] leading-tight tracking-[-0.01em] text-haze-100">
          {judul}
        </h2>
        {catatan && <span className="label-meta">{catatan}</span>}
      </header>
      {anak}
    </section>
  )
}

/**
 * Temuan utama proyek ini, dan satu-satunya angka yang benar-benar membedakan
 * fusi dari baseline — jadi ia jadi angka besar, bukan baris tabel. Di data
 * bersih fusi SERI dengan RGB-saja (0.9833 keduanya); keunggulannya baru
 * terlihat saat modalitas terdegradasi.
 */
function Ketahanan({ penurunan, palet }) {
  if (!penurunan) return null
  const baris = [
    { nama: 'Fusi RGB+termal', nilai: penurunan.fusi, warna: palet.fusi, unggul: true },
    { nama: 'Termal saja', nilai: penurunan.thermal_only, warna: palet.thermal_only },
    { nama: 'RGB saja', nilai: penurunan.rgb_only, warna: palet.rgb_only },
  ].filter((b) => typeof b.nilai === 'number')
  if (!baris.length) return null

  return (
    <section className="permukaan px-4 py-4">
      <div className="label-meta mb-1">
        Penurunan akurasi saat modalitas terdegradasi penuh (tau 0 → 100%)
      </div>
      <p className="mb-4 max-w-2xl text-caption text-haze-400">
        Lebih kecil lebih baik. Di data bersih, fusi dan RGB-saja sama-sama
        0,9833 — keunggulan fusi baru terbukti di sini.
      </p>
      <div className="grid gap-4 sm:grid-cols-3">
        {baris.map((b) => (
          <div key={b.nama}>
            <div className="flex items-baseline gap-1.5">
              <span
                className="font-display text-display-lg tabular-nums"
                style={{ color: b.unggul ? b.warna : undefined }}
              >
                {b.nilai.toFixed(2)}
              </span>
              <span className="font-mono text-[0.6875rem] text-haze-500">poin</span>
              {b.unggul && (
                <span className="ml-0.5 rounded border border-ash-600 bg-ash-800 px-1.5 py-0.5 text-[0.625rem] text-haze-300">
                  paling tahan
                </span>
              )}
            </div>
            <div className="mt-1 flex items-center gap-2">
              <span
                className="h-0.5 w-5 shrink-0 rounded-full"
                style={{ backgroundColor: b.warna }}
              />
              <span className="text-caption text-haze-300">{b.nama}</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

function TabelBaseline({ baris }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[480px] border-collapse text-left">
        <thead>
          <tr className="border-b border-ash-700">
            {['Model', 'Modalitas', 'Akurasi', 'Δ vs fusi'].map((h, i) => (
              <th key={h} scope="col" className={`label-meta px-4 py-2 ${i >= 2 ? 'text-right' : ''}`}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="font-mono text-mono-data">
          {baris.map((b, i) => (
            <tr
              key={b.model}
              className={`border-b border-ash-800 last:border-0 ${
                b.acuan ? 'bg-flare/[0.05]' : i % 2 ? 'bg-ash-950/30' : ''
              }`}
            >
              <th
                scope="row"
                className={`px-4 py-1.5 font-sans text-caption font-normal ${
                  b.acuan ? 'text-aksen-kuat' : 'text-haze-200'
                }`}
              >
                {b.model}
                {b.acuan && <span className="ml-1.5 text-haze-500">· acuan</span>}
              </th>
              <td className="px-4 py-1.5 text-haze-500">{b.modalitas}</td>
              <td className="px-4 py-1.5 text-right text-haze-200">{persen(b.akurasi, 2)}</td>
              <td className="px-4 py-1.5 text-right text-haze-400">
                {typeof b.delta_vs_fusi === 'number'
                  ? b.delta_vs_fusi === 0
                    ? 'seri'
                    : `−${(b.delta_vs_fusi * 100).toFixed(2)}%`
                  : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="border-t border-ash-800 px-4 py-2.5 text-[0.6875rem] leading-relaxed text-haze-500">
        F1-makro, AUROC, dan jumlah parameter tidak masuk lingkup evaluasi tim model
        dan karena itu tidak ditampilkan — bukan disembunyikan.
      </p>
    </div>
  )
}

function KurvaDegradasi({ degradasi }) {
  const { tema } = useTema()
  const palet = PALET_SERI[tema] ?? PALET_SERI.gelap
  const titik = degradasi?.titik ?? []
  const adaData = titik.some((t) => SERI.some((s) => typeof t[s.kunci] === 'number'))

  if (!adaData) {
    return (
      <div className="px-4 py-4">
        <div className="kisi-instrumen flex h-[190px] flex-col items-center justify-center rounded-md border border-dashed border-ash-600">
          <Ikon nama="bagan" ukuran={22} className="text-haze-500" />
          <p className="mt-3 text-caption text-haze-300">Belum ada titik pengukuran.</p>
        </div>
      </div>
    )
  }

  const nilai = titik.flatMap((t) => SERI.map((s) => t[s.kunci]).filter((v) => typeof v === 'number'))
  const min = Math.max(0, Math.floor(Math.min(...nilai) * 50) / 50 - 0.01)

  return (
    <div className="px-2 pb-3 pt-4">
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={titik} margin={{ top: 4, right: 88, bottom: 26, left: 4 }}>
          <CartesianGrid stroke={palet.kisi} strokeDasharray="2 4" vertical={false} />
          <XAxis
            dataKey="degradasi"
            stroke={palet.sumbu}
            tick={{ fill: palet.tik, fontSize: 11, fontFamily: 'IBM Plex Mono' }}
            tickLine={false}
            tickFormatter={(v) => `${v}%`}
            label={{
              value: degradasi.sumbu_x,
              position: 'insideBottom',
              offset: -16,
              fill: palet.tik,
              fontSize: 11,
            }}
          />
          <YAxis
            domain={[min, 1]}
            stroke={palet.sumbu}
            tick={{ fill: palet.tik, fontSize: 11, fontFamily: 'IBM Plex Mono' }}
            tickLine={false}
            tickFormatter={(v) => persen(v)}
            width={52}
          />
          <Tooltip
            cursor={{ stroke: palet.sumbu, strokeDasharray: '3 3' }}
            contentStyle={{
              background: palet.latarTooltip,
              border: `1px solid ${palet.garisTooltip}`,
              borderRadius: 8,
              fontFamily: 'IBM Plex Mono',
              fontSize: 12,
            }}
            labelStyle={{ color: palet.tekstTooltip }}
            labelFormatter={(v) => `Degradasi ${v}%`}
            formatter={(v, n) => [persen(v, 2), n]}
          />
          <Legend verticalAlign="top" height={30} wrapperStyle={{ fontSize: 12 }} />
          {SERI.map((s) => (
            <Line
              key={s.kunci}
              type="monotone"
              dataKey={s.kunci}
              name={s.nama}
              stroke={palet[s.kunci]}
              strokeWidth={s.tebal}
              strokeDasharray={s.pola ?? undefined}
              dot={{ r: 2.5, fill: palet[s.kunci], strokeWidth: 0 }}
              activeDot={{ r: 5, stroke: palet.latarTooltip, strokeWidth: 2 }}
              connectNulls={false}
              isAnimationActive={false}
              label={({ x, y, index }) =>
                index === titik.length - 1 ? (
                  <text
                    x={x + 8}
                    y={y}
                    dy={4}
                    fill={palet[s.kunci]}
                    fontSize={11}
                    fontFamily="IBM Plex Mono"
                  >
                    {s.nama.replace('Fusi RGB+termal', 'Fusi').replace(' saja', '')}
                  </text>
                ) : null
              }
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

function TabelGating({ baris }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[380px] border-collapse text-left">
        <thead>
          <tr className="border-b border-ash-700">
            {['Degradasi', 'Tanpa gate', 'Dengan gate'].map((h, i) => (
              <th key={h} scope="col" className={`label-meta px-4 py-2 ${i ? 'text-right' : ''}`}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="font-mono text-mono-data">
          {baris.map((b, i) => (
            <tr key={b.degradasi} className={`border-b border-ash-800 last:border-0 ${i % 2 ? 'bg-ash-950/30' : ''}`}>
              <th scope="row" className="px-4 py-1.5 font-normal text-haze-300">{b.degradasi}%</th>
              <td className="px-4 py-1.5 text-right text-haze-200">{persen(b.tanpa_gate, 2)}</td>
              <td className="px-4 py-1.5 text-right text-haze-200">{persen(b.dengan_gate, 2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="border-t border-ash-800 px-4 py-2.5 text-[0.6875rem] leading-relaxed text-haze-500">
        Gating tidak menaikkan akurasi klasifikasi pada split ini — akurasinya sudah
        mendekati 100% tanpa gating, sehingga tidak tersisa ruang untuk menunjukkan
        manfaatnya. Dicatat apa adanya. Nilai keandalan yang dihasilkan gate tetap
        dipakai di Panel Alert dan Rincian Alert.
      </p>
    </div>
  )
}

function TabelLokalisasi({ baris }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[420px] border-collapse text-left">
        <thead>
          <tr className="border-b border-ash-700">
            {['Metode', 'Pointing game', 'mIoU'].map((h, i) => (
              <th key={h} scope="col" className={`label-meta px-4 py-2 ${i ? 'text-right' : ''}`}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="font-mono text-mono-data">
          {baris.map((b, i) => (
            <tr
              key={b.metode}
              className={`border-b border-ash-800 last:border-0 ${
                b.disarankan ? 'bg-flare/[0.05]' : i % 2 ? 'bg-ash-950/30' : ''
              }`}
            >
              <th
                scope="row"
                className={`px-4 py-1.5 font-sans text-caption font-normal ${
                  b.disarankan ? 'text-aksen-kuat' : 'text-haze-200'
                }`}
              >
                {b.metode}
                {b.disarankan && <span className="ml-1.5 text-haze-500">· dipakai di produksi</span>}
              </th>
              <td className="px-4 py-1.5 text-right text-haze-200">{angka(b.pointing_game, 4)}</td>
              <td className="px-4 py-1.5 text-right text-haze-200">{angka(b.miou, 4)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TabelEdge({ baris, sumber }) {
  const adaData = baris.some((b) => typeof b.latensi_p50_ms === 'number')
  return (
    <div className="overflow-x-auto">
      {!adaData && (
        <p className="flex items-start gap-2 border-b border-ash-800 px-4 py-2.5 text-caption text-haze-400">
          <Ikon nama="info" ukuran={14} className="mt-0.5 shrink-0 text-haze-500" />
          <span>
            Belum diukur — menunggu tolok ukur perangkat dari {sumber ?? 'Stage 8'}.
            Perangkat di bawah adalah target yang direncanakan, bukan hasil.
          </span>
        </p>
      )}
      <table className="w-full min-w-[520px] border-collapse text-left">
        <thead>
          <tr className="border-b border-ash-700">
            {['Perangkat', 'Presisi', 'p50', 'p95', 'Throughput', 'Daya'].map((h, i) => (
              <th key={h} scope="col" className={`label-meta px-4 py-2 ${i >= 2 ? 'text-right' : ''}`}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="font-mono text-mono-data">
          {baris.map((b, i) => (
            <tr
              key={`${b.perangkat}-${b.presisi}`}
              className={`border-b border-ash-800 last:border-0 ${i % 2 ? 'bg-ash-950/30' : ''}`}
            >
              <th scope="row" className="px-4 py-1.5 font-sans text-caption font-normal text-haze-200">
                {b.perangkat}
              </th>
              <td className="px-4 py-1.5 text-haze-500">{b.presisi}</td>
              <td className="px-4 py-1.5 text-right text-haze-200">{angka(b.latensi_p50_ms, 0, 'ms')}</td>
              <td className="px-4 py-1.5 text-right text-haze-200">{angka(b.latensi_p95_ms, 0, 'ms')}</td>
              <td className="px-4 py-1.5 text-right text-haze-200">{angka(b.throughput_fps, 1, 'fps')}</td>
              <td className="px-4 py-1.5 text-right text-haze-400">{angka(b.daya_watt, 1, 'W')}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function InfoModel() {
  const { data, galat, memuat, muatUlang } = useData(ambilMetrikModel)
  const { tema } = useTema()
  const palet = PALET_SERI[tema] ?? PALET_SERI.gelap

  if (memuat) {
    return (
      <div className="mx-auto w-full max-w-[1000px] px-4 py-8 sm:px-6">
        <StateMemuat pesan="Memuat hasil evaluasi model…" />
      </div>
    )
  }
  if (galat) {
    return (
      <div className="mx-auto w-full max-w-[640px] px-4 py-10 sm:px-6">
        <StateGalat galat={galat} onCoba={muatUlang} judul="Hasil evaluasi tidak bisa dimuat" />
      </div>
    )
  }

  const terukur = data.status === 'terukur'

  return (
    <div className="mx-auto w-full max-w-[1000px] px-4 py-6 sm:px-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-display-lg text-haze-100">Info Model</h1>
          <p className="mt-1 max-w-2xl text-caption text-haze-400">
            Ringkasan evaluasi untuk penilaian teknis: perbandingan baseline, ketahanan
            saat satu modalitas terdegradasi, dan biaya inferensi di perangkat edge.
          </p>
        </div>
        <dl className="flex gap-6 font-mono text-mono-data">
          <div>
            <dt className="label-meta">Status data</dt>
            <dd className={terukur ? 'text-canopy-300' : 'text-aksen-kuat'}>
              {terukur ? 'terukur' : 'belum diukur'}
            </dd>
          </div>
          <div>
            <dt className="label-meta">Diperbarui</dt>
            <dd className="text-haze-400">{data.diperbarui ?? '—'}</dd>
          </div>
        </dl>
      </div>

      {data.evaluasi && (
        <p className="mt-3 border-t border-ash-800 pt-3 font-mono text-[0.6875rem] text-haze-500">
          Split evaluasi: {data.evaluasi.split}
          {data.evaluasi.split_lokalisasi ? ` · lokalisasi: ${data.evaluasi.split_lokalisasi}` : ''}
        </p>
      )}

      <div className="mt-4 space-y-3">
        <Ketahanan penurunan={data.degradasi?.penurunan_poin} palet={palet} />

        <Panel
          judul="Perbandingan baseline"
          catatan={data.sumber?.baseline}
          anak={<TabelBaseline baris={data.baseline ?? []} />}
        />

        <Panel
          judul="Ketahanan terhadap degradasi modalitas"
          catatan={data.sumber?.degradasi}
          anak={<KurvaDegradasi degradasi={data.degradasi} />}
        />

        {data.gating?.length > 0 && (
          <Panel
            judul="Ablation: reliability gating"
            catatan={data.sumber?.gating}
            anak={<TabelGating baris={data.gating} />}
          />
        )}

        {data.lokalisasi?.length > 0 && (
          <Panel
            judul="Lokalisasi titik panas"
            catatan={data.sumber?.lokalisasi}
            anak={<TabelLokalisasi baris={data.lokalisasi} />}
          />
        )}

        <Panel
          judul="Latensi inferensi di perangkat edge"
          catatan={data.sumber?.edge}
          anak={<TabelEdge baris={data.edge ?? []} sumber={data.sumber?.edge} />}
        />
      </div>

      <p className="mt-6 border-t border-ash-800 pt-4 text-[0.6875rem] leading-relaxed text-haze-500">
        Halaman ini sengaja lebih padat dan bergaya laporan teknis dibanding Halaman
        1–3 — audiensnya penilai, bukan operator di posko. Token warna dan tipografi
        tetap sama; yang berbeda kepadatan dan hierarkinya.
      </p>
    </div>
  )
}
