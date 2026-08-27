import { TAHAP_PENGERAHAN } from '../api/client.js'
import { jam, tanggalJam } from '../lib/format.js'
import { LABEL_KEPUTUSAN, LABEL_PEMICU, LABEL_PREDIKSI, ringkasModalitas } from '../lib/risk.js'
import Ikon from './Ikon.jsx'

/**
 * Rantai alur satu alert — dari pemicu sampai tim tiba di lokasi.
 *
 * ============================================================================
 *  KENAPA KOMPONEN INI ADA
 * ============================================================================
 * Sebelumnya konsol menampilkan setiap TAHAP sebagai lapisan atau halaman
 * terpisah, tetapi tidak pernah menampilkan PANAH di antaranya. Akibatnya tiga
 * hal yang penting jadi tak terlihat:
 *
 *   1. Langkah verifikasi drone hilang sama sekali. Kata "drone" tidak muncul
 *      satu kali pun di seluruh kode, padahal pasangan RGB+termal yang dipakai
 *      model justru ITULAH yang dibawa pulang drone. Di mata pembaca, citra itu
 *      muncul entah dari mana.
 *   2. Waktu runtuh jadi satu titik. Jejak lama memakai `alert.timestamp` untuk
 *      "pemicu masuk" DAN "model memutuskan" — jam yang sama persis — sehingga
 *      menyiratkan verifikasi terjadi seketika, tanpa penerbangan.
 *   3. Rantainya berhenti di keputusan operator. Padahal tahap yang paling
 *      mahal justru sesudahnya: tim bergerak ke lokasi.
 *
 * ============================================================================
 *  ATURAN KEJUJURAN YANG MENGIKAT KOMPONEN INI
 * ============================================================================
 * Godaan terbesar di sini adalah MENGARANG mata rantainya supaya rapi: menarik
 * garis dari satu hotspot FIRMS ke satu alert, atau mengarang jam penerbangan
 * drone supaya ada jeda yang enak dilihat. Keduanya haram.
 *
 *   · Bingkai FLAME 2 direkam di Arizona 2021; hotspot FIRMS adalah deteksi
 *     Indonesia 2026 yang nyata. Menghubungkannya sebagai sebab-akibat berarti
 *     mengarang peristiwa yang tidak pernah terjadi.
 *   · `alert.timestamp` DISINTESIS untuk demo (`dasar - 17 menit x i`, lihat
 *     `backend/scripts/jalankan_inference.py`). Ia bukan waktu tangkap dan
 *     bukan waktu klasifikasi. Menyajikannya sebagai salah satunya = berbohong.
 *
 * Jadi rantai ini menampilkan TAHAPNYA, dan menyatakan untuk tiap tahap apakah
 * waktunya benar-benar tercatat. Tahap tanpa waktu menulis "belum tercatat",
 * bukan menampilkan jam karangan — disiplin yang sama persis dengan
 * `modality_reliability: null` yang merender "—" alih-alih 0%.
 *
 * Yang justru bermanfaat: dengan begitu rantai ini sekaligus menunjukkan kepada
 * pembaca APA yang akan dicatat sistem produksi di tiap tahap.
 */

/** Satu simpul rantai. `keadaan` menentukan bentuk penanda, bukan cuma warnanya. */
function Simpul({ keadaan, judul, waktu, catatanWaktu, isi, provenans, terakhir }) {
  const PENANDA = {
    selesai: 'bg-haze-500',
    aktif: 'bg-flame',
    menunggu: 'border border-ash-500 bg-ash-900',
  }
  return (
    <li className={`relative ${terakhir ? '' : 'pb-3'}`}>
      <span
        className={`absolute -left-[21px] top-1.5 h-2 w-2 rounded-full ${PENANDA[keadaan]}`}
      />
      <div className="flex flex-wrap items-baseline gap-x-2">
        <span className="label-meta">{judul}</span>
        {waktu ? (
          <span className="font-mono text-[0.6875rem] text-haze-300">{waktu}</span>
        ) : (
          // Kata "waktu" WAJIB ada. Tanpa itu, "KEPUTUSAN OPERATOR · belum
          // tercatat" di atas baris "Ditindaklanjuti" terbaca seolah
          // keputusannya yang belum terjadi — padahal yang belum ada hanya
          // stempel waktunya. Kekosongan ini sendiri bukan aib: ia menunjukkan
          // field mana yang akan diisi sistem produksi.
          <span className="font-mono text-[0.625rem] text-haze-500">
            waktu belum tercatat
          </span>
        )}
      </div>
      {isi && <div className="mt-0.5 text-caption text-haze-200">{isi}</div>}
      {catatanWaktu && (
        <div className="mt-0.5 text-[0.625rem] leading-relaxed text-haze-500">
          {catatanWaktu}
        </div>
      )}
      {provenans && (
        <div className="mt-1 text-[0.625rem] leading-relaxed text-haze-500">{provenans}</div>
      )}
    </li>
  )
}

const LABEL_TAHAP = {
  dikerahkan: 'Tim dikerahkan',
  berangkat: 'Dalam perjalanan',
  tiba: 'Tiba di lokasi',
}

export default function JejakAlur({ alert, pengerahan = [], onPengerahan, bisaKerahkan }) {
  const keputusan = alert.operator_decision
  const modalitas = ringkasModalitas(alert.modality_reliability)
  const tercatat = new Map(pengerahan.map((t) => [t.tahap, t.waktu]))

  return (
    <section className="permukaan p-4" aria-label="Jejak alur alert">
      <div className="label-meta mb-1">Jejak alur</div>
      <p className="mb-3 text-[0.625rem] leading-relaxed text-haze-500">
        Rantai dari pemicu sampai tim tiba. Tahap yang waktunya belum tercatat
        ditandai apa adanya — tidak diisi jam karangan.
      </p>

      <ol className="space-y-0 border-l border-ash-700 pl-4">
        <Simpul
          keadaan="selesai"
          judul="Pemicu"
          isi={LABEL_PEMICU[alert.source_trigger]}
          provenans={
            alert.source_trigger === 'satellite_firms'
              ? 'Jenis pemicu dinyatakan kontrak. Tautan ke satu rekaman hotspot tertentu belum ada — hotspot FIRMS di peta adalah deteksi nyata yang berdiri sendiri.'
              : 'Jenis pemicu dinyatakan kontrak; rekaman peristiwa pemicunya belum ditautkan.'
          }
        />

        {/* Simpul yang selama ini hilang sama sekali dari produk. */}
        <Simpul
          keadaan="selesai"
          judul="Verifikasi · patroli drone"
          isi="Pasangan bingkai RGB + termal"
          provenans="Citra udara nyata dari benchmark FLAME 2 (drone, hutan pinus Arizona). Koordinat pada alert adalah penempatan simulasi di lahan gambut Indonesia."
        />

        <Simpul
          keadaan="selesai"
          judul="Klasifikasi model"
          waktu={`${jam(alert.timestamp)} WIB`}
          catatanWaktu="Waktu alert ditetapkan untuk keperluan demo, bukan jam tangkap maupun jam inferensi sungguhan."
          isi={
            <>
              <span className="text-haze-100">{LABEL_PREDIKSI[alert.prediction.label]}</span>{' '}
              — {modalitas.terukur ? modalitas.ringkas.toLowerCase() : 'keandalan belum diukur'}
            </>
          }
          provenans="Keluaran model sungguhan atas bingkai tersebut."
        />

        {keputusan ? (
          <Simpul
            keadaan="selesai"
            judul="Keputusan operator"
            isi={<span className="text-haze-100">{LABEL_KEPUTUSAN[keputusan]}</span>}
          />
        ) : (
          <Simpul keadaan="menunggu" judul="Keputusan operator" isi="Menunggu" />
        )}

        {TAHAP_PENGERAHAN.map((tahap, i) => {
          const waktu = tercatat.get(tahap)
          return (
            <Simpul
              key={tahap}
              keadaan={waktu ? 'selesai' : 'menunggu'}
              judul={LABEL_TAHAP[tahap]}
              waktu={waktu ? tanggalJam(waktu) : null}
              catatanWaktu={
                // Satu-satunya waktu di seluruh rantai ini yang benar-benar
                // terjadi — dicatat saat tombolnya ditekan. Layak disebut.
                waktu ? 'Dicatat saat operator menandainya.' : null
              }
              // Catatan "tersedia setelah ditindaklanjuti" cukup sekali, di
              // tahap tertunda yang pertama. Mengulanginya di ketiga tahap
              // membuat kolom penuh kalimat identik tanpa menambah informasi.
              isi={!waktu && !bisaKerahkan && i === 0 ? 'Tersedia setelah alert ditindaklanjuti' : null}
              terakhir={i === TAHAP_PENGERAHAN.length - 1}
            />
          )
        })}
      </ol>

      {/* Tombol pengerahan hanya muncul setelah alert ditindaklanjuti. Menandai
          "tim berangkat" pada alert yang ditandai alarm palsu tidak punya arti,
          dan membiarkannya bisa diklik mengundang catatan yang saling
          bertentangan di jejak yang sama. */}
      {bisaKerahkan && (
        <div className="mt-3 border-t border-ash-700 pt-3">
          <div className="label-meta mb-2">Tandai kemajuan tim</div>
          <div className="flex flex-wrap gap-1.5">
            {TAHAP_PENGERAHAN.map((tahap) => {
              const aktif = tercatat.has(tahap)
              return (
                <button
                  key={tahap}
                  type="button"
                  aria-pressed={aktif}
                  onClick={() => onPengerahan(tahap)}
                  className={`inline-flex items-center gap-1.5 rounded border px-2.5 py-1.5 text-caption
                    [transition:background-color_140ms_cubic-bezier(0.22,0.61,0.36,1),color_140ms_linear,border-color_140ms_linear]
                    active:translate-y-px
                    ${
                      aktif
                        ? 'border-canopy-400 bg-canopy-600/25 text-canopy-300'
                        : 'border-ash-600 bg-ash-900 text-haze-300 hover:bg-ash-800 hover:text-haze-100'
                    }`}
                >
                  <Ikon nama={aktif ? 'centang' : 'panah'} ukuran={12} />
                  {LABEL_TAHAP[tahap]}
                </button>
              )
            })}
          </div>
          <p className="mt-2 text-[0.625rem] leading-relaxed text-haze-500">
            Dicatat oleh operator, bukan dilacak otomatis — konsol ini tidak
            terhubung ke perangkat atau kendaraan regu. Menekan tahap yang sudah
            tercatat membatalkannya beserta tahap sesudahnya.
          </p>
        </div>
      )}
    </section>
  )
}
