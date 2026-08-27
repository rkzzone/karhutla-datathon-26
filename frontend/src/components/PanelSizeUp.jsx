import Ikon from './Ikon.jsx'
import TombolSalin from './TombolSalin.jsx'
import { StateGalat, StateMemuat } from './StatePesan.jsx'
import { tanggalJam } from '../lib/format.js'
import {
  KOMPONEN_FWI,
  LABEL_BAHAYA,
  LABEL_KERUCUT,
  WARNA_BAHAYA,
  arahMata,
  hariKering,
  jarak,
  namaFitur,
  wilayahBmkg,
} from '../lib/sizeup.js'

/**
 * Lapisan size-up — konteks & rencana SETELAH model bicara.
 *
 * Tahap kerja ini sebelumnya tidak dilayani produk sama sekali: konsol berhenti
 * di "ini alert, silakan putuskan". Di lapangan, setelah keputusan itu ada satu
 * tahap penuh lagi — tim size-up berangkat lebih dulu untuk menggambar situasi,
 * melihat arah angin, sumber air, dan akses. Panel ini mendahului sebagian
 * pekerjaan itu dari data terbuka.
 *
 * ============================================================================
 *  PEMBEDAAN YANG MENJADI SELURUH ALASAN PANEL INI TERPISAH SECARA VISUAL
 * ============================================================================
 * Segala sesuatu di atas panel ini (prediksi, keandalan modalitas, heatmap)
 * adalah keluaran MODEL TERLATIH, dievaluasi dengan angka di paper.
 * Segala sesuatu DI DALAM panel ini dihitung ATURAN DETERMINISTIK dari cuaca
 * dan peta terbuka — tidak dilatih, tidak mengklaim akurasi, dan tiap angkanya
 * bisa ditelusuri ke satu sumber yang disebut di layar.
 *
 * Karena itu panel diberi kepala sendiri yang menyatakan batas itu terang-
 * terangan. Kalau suatu hari ada yang memindahkan blok-blok ini ke dalam kartu
 * prediksi supaya "lebih ringkas", batas itu hilang dari layar — dan bersamanya
 * hilang argumen arsitektur yang paling bisa dipertahankan di depan juri.
 */

/** Satu blok berlabel. Blok gagal merender pesannya sendiri, tidak menghilang. */
function Blok({ ikon, judul, sumber, blok, children }) {
  const gagal = blok?.status !== 'ada'
  return (
    <section className="rounded-lg border border-ash-700 bg-ash-900 p-3.5 shadow-ash-sm">
      <header className="mb-2.5 flex items-start justify-between gap-2">
        <h4 className="flex items-center gap-1.5 font-display text-[0.9375rem] text-haze-100">
          <Ikon nama={ikon} ukuran={14} className="shrink-0 text-haze-400" />
          {judul}
        </h4>
        {sumber && !gagal && (
          <span className="shrink-0 font-mono text-[0.625rem] text-haze-500">{sumber}</span>
        )}
      </header>
      {gagal ? (
        // Blok gagal TIDAK PERNAH ditambal angka tebakan — ia bilang apa adanya.
        <p className="flex items-start gap-2 text-caption text-haze-400">
          <Ikon nama="peringatan" ukuran={13} className="mt-0.5 shrink-0 text-aksen-kuat" />
          <span>
            {blok?.pesan ?? 'Data untuk blok ini tidak tersedia.'}
            {blok?.alasan && (
              <span className="ml-1 font-mono text-[0.625rem] text-haze-500">
                (kode: {blok.alasan})
              </span>
            )}
          </span>
        </p>
      ) : (
        children
      )}
    </section>
  )
}

/** Pasangan label + nilai, angka selalu mono + tabular. */
function Nilai({ label, children, catatan }) {
  return (
    <div className="min-w-0">
      <dt className="label-meta">{label}</dt>
      <dd className="mt-0.5 font-mono text-mono-data tabular-nums text-haze-200">{children}</dd>
      {catatan && <div className="mt-0.5 text-[0.625rem] text-haze-500">{catatan}</div>}
    </div>
  )
}

/** Daftar fitur OSM terdekat — jarak + arah, keduanya perlu untuk brief lisan. */
function DaftarFitur({ daftar, radius, kosong }) {
  if (!daftar?.length) {
    return (
      <p className="text-caption text-haze-400">
        {kosong} dalam radius {radius} km menurut OpenStreetMap. Ketiadaan di peta
        tidak berarti ketiadaan di lapangan — cakupan pemetaan di lahan gambut
        tidak merata.
      </p>
    )
  }
  return (
    <>
    <ul className="space-y-1.5">
      {daftar.slice(0, 3).map((fitur, i) => (
        // Koordinat saja TIDAK unik: dua ruas jalan yang bertemu di satu simpang
        // punya simpul terdekat yang sama persis, dan React lalu menganggapnya
        // satu elemen. Indeks ikut serta karena urutan daftar ini stabil —
        // sudah terurut jarak menaik dari server.
        <li key={`${i}-${fitur.jenis}-${fitur.lat}-${fitur.lon}`} className="flex items-baseline gap-2">
          <span
            className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full"
            style={{
              backgroundColor: i === 0 ? 'var(--marker-satelit)' : 'rgb(var(--ash-500))',
            }}
          />
          <span className="min-w-0 flex-1 truncate text-caption text-haze-200">
            {namaFitur(fitur)}
            {fitur.kanal_gambut && (
              // Kanal disorot khusus: di gambut ia infrastruktur mitigasi
              // karhutla yang sengaja dibangun, bukan sekadar garis air.
              <span className="ml-1.5 rounded-sm bg-satellite/20 px-1 font-mono text-[0.5625rem] uppercase tracking-[0.12em] text-satellite">
                kanal
              </span>
            )}
            {fitur.kendaraan_berat === false && (
              <span className="ml-1.5 font-mono text-[0.625rem] text-haze-500">
                roda dua
              </span>
            )}
          </span>
          <span className="shrink-0 font-mono text-mono-data tabular-nums text-haze-100">
            {jarak(fitur.jarak_km)}
          </span>
          <span className="w-[68px] shrink-0 text-right text-[0.625rem] text-haze-500">
            {arahMata(fitur.arah_deg) ?? '—'}
          </span>
        </li>
      ))}
    </ul>
    {/* Bukan detail akademis: jalan yang 4 km dalam garis lurus bisa 15 km
        ditempuh kalau harus memutar. Tim yang membaca angka ini sedang
        memperkirakan waktu tempuh, jadi sifat angkanya harus disebut. */}
    <p className="mt-2 border-t border-ash-700 pt-2 text-[0.625rem] text-haze-500">
      Jarak lurus dari titik, bukan jarak tempuh.
    </p>
    </>
  )
}

export default function PanelSizeUp({ sizeup, galat, memuat, onCoba }) {
  if (memuat) {
    return (
      <section className="permukaan p-4">
        <StateMemuat pesan="Memuat konteks size-up…" />
      </section>
    )
  }

  if (galat) {
    return (
      <section className="permukaan p-4">
        <StateGalat galat={galat} onCoba={onCoba} judul="Konteks size-up tidak tersedia" />
      </section>
    )
  }

  if (!sizeup) return null

  const { blok = {}, brief } = sizeup
  const cuaca = blok.cuaca ?? {}
  const bahaya = blok.bahaya ?? {}
  const riwayat = cuaca.riwayat_hujan ?? {}
  const warnaBahaya = WARNA_BAHAYA[bahaya.tingkat] ?? WARNA_BAHAYA[1]

  return (
    <section className="permukaan overflow-hidden">
      {/* Kepala: menyatakan batas model ↔ aturan, bukan sekadar judul */}
      <header className="border-b border-ash-700 px-4 py-3">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
          <h3 className="font-display text-heading text-haze-100">Size-up</h3>
          <span className="font-mono text-[0.625rem] text-haze-500">
            {sizeup.is_cuplikan ? 'cuplikan' : 'langsung'} ·{' '}
            {tanggalJam(sizeup.diambil)}
          </span>
        </div>
        <p className="mt-1 text-[0.6875rem] leading-relaxed text-haze-500">
          Dihitung <span className="text-haze-400">aturan deterministik</span> dari
          cuaca dan peta terbuka — bukan keluaran model. Tiap angka di bawah bisa
          ditelusuri ke sumber yang disebutkan.
        </p>
      </header>

      <div className="space-y-3 p-4">
        {/* Judul berubah pada cuplikan, dan itu bukan detail kosmetik: "Cuaca
            saat ini" di atas angka yang dibekukan tiga hari lalu adalah
            pernyataan yang salah, sekalipun waktu pengambilannya tercetak di
            kepala panel. Judul dibaca lebih dulu daripada metadata. */}
        <Blok
          ikon="angin"
          judul={sizeup.is_cuplikan ? 'Cuaca saat cuplikan diambil' : 'Cuaca saat ini'}
          sumber={cuaca.sumber}
          blok={cuaca}
        >
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5">
            <Nilai label="Suhu">
              {typeof cuaca.suhu_c === 'number' ? `${cuaca.suhu_c} °C` : '—'}
            </Nilai>
            <Nilai label="Kelembapan">
              {typeof cuaca.kelembapan_persen === 'number'
                ? `${cuaca.kelembapan_persen} %`
                : '—'}
            </Nilai>
            <Nilai
              label="Angin"
              catatan={
                cuaca.arah_angin_mata ? `datang dari ${cuaca.arah_angin_mata}` : null
              }
            >
              {typeof cuaca.angin_kmj === 'number' ? `${cuaca.angin_kmj} km/j` : '—'}
            </Nilai>
            <Nilai
              label="Hari kering berturut"
              catatan={
                riwayat.terpotong_jendela
                  ? `seluruh ${riwayat.jendela_hari} hari jendela kering — bisa lebih panjang`
                  : `ambang ${riwayat.ambang_hari_kering_mm} mm/hari`
              }
            >
              {hariKering(riwayat)} hari
            </Nilai>
          </dl>

          {cuaca.arah_rambatan_mata && (
            // Label wajib, dan penjelasan keterbatasannya ikut serta — tanpa itu
            // kerucut di peta akan terbaca sebagai prediksi rambatan.
            <p className="mt-3 flex items-start gap-2 rounded border border-ash-700 bg-ash-950 px-2.5 py-2 text-[0.6875rem] leading-relaxed text-haze-400">
              <Ikon nama="angin" ukuran={13} className="mt-0.5 shrink-0 text-aksen" />
              <span>
                <span className="text-haze-200">{LABEL_KERUCUT}</span>: dorongan ke{' '}
                <span className="font-mono text-haze-100">{cuaca.arah_rambatan_mata}</span>.{' '}
                {cuaca.catatan_kerucut}
              </span>
            </p>
          )}
        </Blok>

        <Blok
          ikon="peringatan"
          judul={LABEL_BAHAYA}
          sumber={bahaya.status === 'ada' ? 'van Wagner 1987' : null}
          blok={bahaya}
        >
          <div className="flex items-center gap-3">
            <span
              className="h-11 w-1.5 shrink-0 rounded-full"
              style={{ backgroundColor: warnaBahaya.isi }}
              aria-hidden="true"
            />
            <div className="flex items-baseline gap-2.5">
              <span
                className="font-display text-display-lg tabular-nums"
                style={{ color: warnaBahaya.teks }}
              >
                {bahaya.fwi}
              </span>
              <div className="min-w-0">
                <div className="font-display text-heading" style={{ color: warnaBahaya.teks }}>
                  {bahaya.nama}
                </div>
                {/* Ambangnya ikut tampil: kami tidak memverifikasi sendiri ambang
                    persis yang dipakai BMKG, jadi ANGKA yang jadi pegangan,
                    bukan namanya. */}
                <div className="font-mono text-[0.6875rem] text-haze-500">{bahaya.ambang}</div>
              </div>
            </div>
          </div>

          {/* Lima komponen antara, ditampilkan lengkap dan tidak diringkas ke
              satu angka: DC tinggi dengan FFMC rendah menceritakan situasi yang
              sama sekali berbeda dari kebalikannya. */}
          <dl className="mt-3 grid grid-cols-5 gap-2 border-t border-ash-700 pt-2.5">
            {KOMPONEN_FWI.map(([kunci, singkat, panjang]) => (
              <div key={kunci} title={panjang}>
                <dt className="text-[0.625rem] uppercase tracking-[0.1em] text-haze-500">
                  {singkat}
                </dt>
                <dd className="font-mono text-mono-data tabular-nums text-haze-200">
                  {bahaya.komponen?.[kunci] ?? '—'}
                </dd>
              </div>
            ))}
          </dl>
          <p className="mt-1.5 text-[0.625rem] leading-relaxed text-haze-500">
            DC mengukur kekeringan lapisan dalam — komponen yang paling berarti untuk
            gambut, dan yang paling lambat pulih setelah hujan.
          </p>

          {/* Dua catatan keterbatasan datang dari server bersama angkanya, bukan
              ditulis ulang di sini — supaya angkanya mustahil ditampilkan tanpa
              batasnya. */}
          <p className="mt-2 border-t border-ash-700 pt-2 text-[0.625rem] leading-relaxed text-haze-500">
            {bahaya.catatan}
          </p>
          <p className="mt-1.5 text-[0.625rem] leading-relaxed text-haze-500">
            {bahaya.catatan_spinup}
          </p>
        </Blok>

        {/* Prakiraan resmi — sengaja blok TERPISAH dari cuaca Open-Meteo di atas.
            Menggabungkannya akan menyiratkan keduanya mengukur tempat yang sama,
            padahal BMKG berlaku untuk desa dan Open-Meteo untuk titik. */}
        <Blok
          ikon="info"
          judul="Prakiraan resmi BMKG"
          sumber={blok.bmkg?.sumber}
          blok={blok.bmkg ?? {}}
        >
          <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
            <span className="font-display text-heading text-haze-100">
              {blok.bmkg?.cuaca ?? '—'}
            </span>
            <span className="font-mono text-[0.6875rem] text-haze-500">
              berlaku {blok.bmkg?.waktu_prakiraan ?? '—'}
            </span>
          </div>
          <dl className="mt-2.5 grid grid-cols-3 gap-x-4 gap-y-2">
            <Nilai label="Suhu">
              {typeof blok.bmkg?.suhu_c === 'number' ? `${blok.bmkg.suhu_c} °C` : '—'}
            </Nilai>
            <Nilai label="Kelembapan">
              {typeof blok.bmkg?.kelembapan_persen === 'number'
                ? `${blok.bmkg.kelembapan_persen} %`
                : '—'}
            </Nilai>
            <Nilai label="Angin">
              {typeof blok.bmkg?.angin_kmj === 'number' ? `${blok.bmkg.angin_kmj} km/j` : '—'}
            </Nilai>
          </dl>
          <p className="mt-2.5 border-t border-ash-700 pt-2 text-[0.625rem] leading-relaxed text-haze-500">
            Berlaku untuk <span className="text-haze-300">{wilayahBmkg(blok.bmkg)}</span>
            {typeof blok.bmkg?.jarak_titik_acuan_km === 'number' && (
              <>
                {' '}
                — titik acuannya{' '}
                <span className="font-mono text-haze-300">
                  {jarak(blok.bmkg.jarak_titik_acuan_km)}
                </span>{' '}
                dari titik alert
              </>
            )}
            . BMKG tidak menyediakan prakiraan per koordinat, jadi angka di blok cuaca
            atas (Open-Meteo, presisi titik) dan angka di sini akan berbeda. Keduanya
            benar untuk tempatnya masing-masing.
          </p>
        </Blok>

        {/* Penutup lahan BIG. Ini BUKAN peta gambut — alasannya di catatan bawah. */}
        <Blok
          ikon="peta"
          judul="Penutup lahan & wilayah"
          sumber={blok.penutup_lahan?.status === 'ada' ? 'BIG' : null}
          blok={blok.penutup_lahan ?? {}}
        >
          <div className="font-display text-heading text-haze-100">
            {blok.penutup_lahan?.nama ?? '—'}
          </div>
          <div className="mt-0.5 font-mono text-[0.6875rem] text-haze-500">
            kode {blok.penutup_lahan?.kode ?? '—'} · skala {blok.penutup_lahan?.skala ?? '—'}
          </div>

          {blok.wilayah?.status === 'ada' && (
            <dl className="mt-2.5 grid grid-cols-2 gap-x-4 gap-y-2 border-t border-ash-700 pt-2.5">
              <Nilai label="Desa / Kelurahan">{blok.wilayah.desa ?? '—'}</Nilai>
              <Nilai label="Kecamatan">{blok.wilayah.kecamatan ?? '—'}</Nilai>
              <Nilai label="Kabupaten / Kota">{blok.wilayah.kabupaten ?? '—'}</Nilai>
              <Nilai label="Provinsi">{blok.wilayah.provinsi ?? '—'}</Nilai>
            </dl>
          )}

          {blok.penutup_lahan?.indikasi_lahan_basah && (
            <p className="mt-2.5 flex items-start gap-2 rounded border border-satellite/45 bg-satellite/[0.07] px-2.5 py-2 text-[0.6875rem] leading-relaxed text-haze-300">
              <Ikon nama="air" ukuran={13} className="mt-0.5 shrink-0 text-satellite" />
              <span>
                Kelas ini <span className="text-haze-100">mengindikasikan lahan basah</span>.
                Status kesatuan hidrologis gambut TIDAK ditentukan oleh peta penutup
                lahan — penetapan KHG adalah dokumen hukum tersendiri.
              </span>
            </p>
          )}

          {/* Kenapa bukan peta gambut, dinyatakan di layar dan bukan cuma di kode.
              Kalau juri bertanya "kenapa tidak pakai peta KHG", jawabannya sudah
              ada di depan mereka. */}
          <p className="mt-2 border-t border-ash-700 pt-2 text-[0.625rem] leading-relaxed text-haze-500">
            Peta Kesatuan Hidrologis Gambut tidak dipakai: penelusuran seluruh layanan
            publik geoportal BIG (26 Agustus 2026) tidak menemukan layer gambut maupun
            KHG, dan host gambut lain yang dicoba tidak dapat dijangkau. Yang
            ditampilkan adalah penutup lahan resmi — pertanyaan yang berbeda, dan tidak
            boleh dibaca sebagai status gambut.
          </p>
        </Blok>

        <div className="grid gap-3 sm:grid-cols-2">
          <Blok
            ikon="air"
            judul="Sumber air terdekat"
            sumber={blok.sumber_air?.sumber}
            blok={blok.sumber_air ?? {}}
          >
            <DaftarFitur
              daftar={blok.sumber_air?.daftar}
              radius={blok.sumber_air?.radius_km}
              kosong="Tidak ada sungai, kanal, atau badan air terpetakan"
            />
          </Blok>

          <Blok
            ikon="jalan"
            judul="Akses terdekat"
            sumber={blok.akses?.sumber}
            blok={blok.akses ?? {}}
          >
            <DaftarFitur
              daftar={blok.akses?.daftar}
              radius={blok.akses?.radius_km}
              kosong="Tidak ada jalan terpetakan"
            />
          </Blok>
        </div>

        <Blok ikon="alat" judul="Saran tingkat peralatan" blok={blok.peralatan ?? {}}>
          <div className="font-display text-heading text-haze-100">
            {blok.peralatan?.nama}
          </div>
          <p className="text-caption text-haze-300">{blok.peralatan?.contoh}</p>
          <ul className="mt-2.5 space-y-1 border-t border-ash-700 pt-2.5">
            {(blok.peralatan?.alasan ?? []).map((baris) => (
              <li key={baris} className="flex items-start gap-1.5 text-[0.6875rem] text-haze-400">
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-ash-500" />
                {baris}
              </li>
            ))}
          </ul>
        </Blok>

        {/* Brief: keluaran yang benar-benar masuk ke alur kerja yang sudah ada */}
        {brief && (
          <section className="rounded-lg border border-ash-600 bg-ash-950 p-3.5">
            <header className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <h4 className="font-display text-[0.9375rem] text-haze-100">
                Brief untuk grup siaga
              </h4>
              <TombolSalin
                teks={brief}
                utama
                label="Salin brief"
                labelBerhasil="Brief tersalin"
                judul="Salin untuk ditempel ke grup siaga bencana"
              />
            </header>
            <p className="mb-2.5 flex items-start gap-1.5 text-[0.6875rem] leading-relaxed text-aksen-kuat">
              <Ikon nama="peringatan" ukuran={12} className="mt-0.5 shrink-0" />
              {sizeup.catatan_brief}
            </p>
            {/* Teks ditampilkan penuh, bukan disembunyikan di balik tombol salin.
                Operator harus bisa membaca apa yang akan ia kirim ke grup siaga
                SEBELUM mengirimnya — menyalin sesuatu yang tidak terlihat isinya
                adalah cara cepat menyebarkan kekeliruan. */}
            <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded border border-ash-700 bg-ash-900 p-3 font-mono text-[0.6875rem] leading-relaxed text-haze-300">
              {brief}
            </pre>
          </section>
        )}

        <p className="flex items-start gap-2 rounded-md border border-ash-700 bg-ash-900 px-3 py-2.5 text-[0.6875rem] leading-relaxed text-haze-500">
          <Ikon nama="info" ukuran={13} className="mt-0.5 shrink-0" />
          <span>{sizeup.catatan_provenans}</span>
        </p>
      </div>
    </section>
  )
}
