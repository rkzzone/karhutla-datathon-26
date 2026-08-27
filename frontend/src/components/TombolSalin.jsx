import { useEffect, useRef, useState } from 'react'

import Ikon from './Ikon.jsx'

/**
 * Tombol salin — dipakai untuk koordinat dan untuk brief size-up.
 *
 * KENAPA INI KOMPONEN SENDIRI, bukan `navigator.clipboard.writeText` di tempat:
 * keluaran produk yang paling mungkin benar-benar dipakai bukan dasbor yang
 * dipelototi, melainkan teks yang ditempel ke grup WhatsApp siaga bencana
 * (BPBD, damkar, dinas kehutanan) — kanal distribusi yang disebut narasumber
 * polisi hutan. Menyalin adalah aksi utama di alur itu, bukan kenyamanan
 * tambahan, jadi ia layak punya state yang benar di semua jalur.
 *
 * `navigator.clipboard` butuh konteks aman (HTTPS atau localhost) dan bisa
 * ditolak izinnya. Kalau gagal, tombol MELAPOR gagal dan menyarankan salin
 * manual — tidak pernah diam-diam tidak melakukan apa-apa sambil terlihat
 * berhasil. Operator yang mengira sudah menyalin lalu menempel teks lama ke
 * grup siaga adalah kegagalan yang jauh lebih mahal daripada tombol yang jujur
 * bilang tidak bisa.
 */
export default function TombolSalin({
  teks,
  label = 'Salin',
  labelBerhasil = 'Tersalin',
  judul,
  penuh = false,
  utama = false,
}) {
  const [keadaan, setKeadaan] = useState('idle') // idle | berhasil | gagal
  const jeda = useRef(null)

  useEffect(() => () => clearTimeout(jeda.current), [])

  async function salin() {
    clearTimeout(jeda.current)
    try {
      if (!navigator.clipboard) throw new Error('clipboard tidak tersedia')
      await navigator.clipboard.writeText(teks)
      setKeadaan('berhasil')
    } catch {
      setKeadaan('gagal')
    }
    jeda.current = setTimeout(() => setKeadaan('idle'), 2400)
  }

  const TAMPILAN = {
    idle: { ikon: 'salin', teks: label },
    berhasil: { ikon: 'centang', teks: labelBerhasil },
    gagal: { ikon: 'peringatan', teks: 'Gagal — salin manual' },
  }
  const t = TAMPILAN[keadaan]

  return (
    <button
      type="button"
      onClick={salin}
      title={judul ?? label}
      className={`inline-flex items-center justify-center gap-1.5 rounded border px-2.5 py-1.5 text-caption
        [transition:background-color_140ms_cubic-bezier(0.22,0.61,0.36,1),color_140ms_linear,border-color_140ms_linear]
        active:translate-y-px
        ${penuh ? 'w-full' : ''}
        ${
          keadaan === 'berhasil'
            ? 'border-canopy-400 bg-canopy-600/25 text-canopy-300'
            : keadaan === 'gagal'
              ? 'border-ember/60 bg-ember/10 text-aksen-kuat'
              : utama
                ? 'border-ash-500 bg-ash-800 text-haze-100 hover:bg-ash-700'
                : 'border-ash-600 bg-ash-900 text-haze-300 hover:bg-ash-800 hover:text-haze-100'
        }`}
    >
      <Ikon nama={t.ikon} ukuran={13} className="shrink-0" />
      {t.teks}
      {/* Umpan balik salin hanya lewat warna+ikon tidak terbaca pembaca layar;
          brief Bagian 5 melarang makna di-encode tanpa teks. */}
      <span aria-live="polite" className="sr-only">
        {keadaan === 'berhasil'
          ? 'Tersalin ke papan klip.'
          : keadaan === 'gagal'
            ? 'Penyalinan otomatis gagal. Pilih teksnya lalu salin manual.'
            : ''}
      </span>
    </button>
  )
}
