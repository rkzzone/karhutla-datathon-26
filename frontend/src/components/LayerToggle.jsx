import Ikon from './Ikon.jsx'

/**
 * Toggle lapisan peta. Warna titik indikator = warna marker lapisan itu di peta,
 * supaya kontrol dan peta terbaca sebagai satu sistem, bukan dua daftar terpisah.
 *
 * Tidak ada warna default Tailwind di sini — semua dari token brief 2.1.
 */

export const LAPISAN = [
  // Titik indikator = isi (fill), bukan teks. Nilai Ember dipakai apa adanya;
  // warna sumber memakai variabel supaya cocok dengan marker di kedua tema.
  { kunci: 'alert', nama: 'Alert model', warna: '#E8752C', ikon: 'api' },
  { kunci: 'firms', nama: 'Hotspot FIRMS', warna: 'var(--marker-satelit)', ikon: 'satelit' },
  {
    kunci: 'iot',
    nama: 'Sensor darat',
    warna: 'var(--marker-iot)',
    ikon: 'sensor',
    tanda: 'simulasi',
  },
  // Berlabel "contoh" dengan alasan yang sama seperti sensor darat berlabel
  // "simulasi": rencana rutenya karangan. Geometrinya memang jalan sungguhan
  // dari OSM, tapi jalur yang TERLIHAT meyakinkan justru lebih mudah
  // disalahartikan sebagai rencana posko daripada garis lurus yang jelas kasar.
  { kunci: 'patroli', nama: 'Pengerahan regu', warna: 'var(--marker-patroli)', ikon: 'patroli', tanda: 'contoh' },
  // Lapisan konteks, bukan lapisan deteksi. Penandanya "proyeksi" dan bukan
  // "prediksi": yang digambar cuma arah dorongan angin, tanpa bahan bakar,
  // kelerengan, maupun kelembapan gambut.
  { kunci: 'angin', nama: 'Proyeksi angin', warna: '#E8752C', ikon: 'angin', tanda: 'proyeksi' },
  // Sumber air & akses hanya digambar untuk titik yang sedang disorot, bukan
  // untuk sepuluh alert sekaligus. Sepuluh titik × enam fitur air × enam jalan
  // = 120 marker yang menenggelamkan alert model di baliknya — dan size-up di
  // lapangan memang dikerjakan satu titik pada satu waktu.
  { kunci: 'konteks', nama: 'Sumber air & akses', warna: 'var(--marker-satelit)', ikon: 'air' },
  // "Prioritas patroli", BUKAN "sapuan drone".
  //
  // Bedanya bukan gaya bahasa. `03_KRITERIA2` baris 230 menetapkan posisi tim:
  // "Kami tidak mengoperasikan drone, tidak mengubah profil penerbangan, dan
  // tidak menambah kewajiban perizinan baru." Lapisan yang berbunyi "sapuan
  // drone" menyiratkan kita mengerahkan armada — klaim yang menambah beban
  // regulasi yang justru dinyatakan nol, dan yang tidak bisa dipertahankan.
  //
  // Yang sebenarnya dilakukan: patroli SUDAH terbang di bawah izin yang ada,
  // dan konsol membantu memilih urutan titik mana yang disinggahi lebih dulu.
  { kunci: 'sapuan', nama: 'Prioritas patroli', warna: '#F5C242', ikon: 'peta', tanda: 'urutan' },
]

export default function LayerToggle({ nilai, onUbah, jumlah = {} }) {
  return (
    <div
      role="group"
      aria-label="Lapisan peta"
      className="flex flex-wrap items-center gap-1.5"
    >
      <span className="label-meta mr-1 hidden sm:inline">
        <Ikon nama="lapis" ukuran={12} className="mr-1 inline align-[-1px]" />
        Lapisan
      </span>
      {LAPISAN.map((lapis) => {
        const aktif = nilai[lapis.kunci]
        return (
          <button
            key={lapis.kunci}
            type="button"
            aria-pressed={aktif}
            onClick={() => onUbah({ ...nilai, [lapis.kunci]: !aktif })}
            className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-caption
              [transition:background-color_150ms_cubic-bezier(0.22,0.61,0.36,1),border-color_150ms_cubic-bezier(0.22,0.61,0.36,1),opacity_150ms_linear]
              active:translate-y-px
              ${
                aktif
                  ? 'border-ash-500 bg-ash-800 text-haze-100'
                  : 'border-ash-700 bg-ash-900 text-haze-500 hover:border-ash-600 hover:text-haze-400'
              }`}
          >
            <span
              className="h-2 w-2 shrink-0 rounded-full"
              style={{
                backgroundColor: aktif ? lapis.warna : 'transparent',
                boxShadow: aktif ? 'none' : 'inset 0 0 0 1.5px rgb(var(--ash-500))',
              }}
            />
            {lapis.nama}
            {typeof jumlah[lapis.kunci] === 'number' && (
              <span className="font-mono text-[0.6875rem] text-haze-500">
                {jumlah[lapis.kunci]}
              </span>
            )}
            {/* Penanda lapisan ikut warna lapisannya, supaya kontrol dan peta
                terbaca sebagai satu sistem — dan supaya "simulasi" tidak lagi
                jadi satu-satunya jenis penanda yang bisa muncul di sini. */}
            {lapis.tanda && aktif && (
              <span
                className="rounded-sm px-1 font-mono text-[0.5625rem] uppercase tracking-[0.12em]"
                style={{
                  color: lapis.warna,
                  backgroundColor: `color-mix(in srgb, ${lapis.warna} 20%, transparent)`,
                }}
              >
                {lapis.tanda}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
