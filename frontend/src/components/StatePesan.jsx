import Ikon from './Ikon.jsx'

/**
 * State kosong / error / memuat — copy mengikuti DESIGN_BRIEF Bagian 6.
 *
 * Aturan yang dijaga di sini:
 *   - Tidak ada "Terjadi kesalahan" atau "No data".
 *   - Tidak ada nada heroik/dramatis. Topik ini bencana nyata.
 *   - Loading selalu punya teks fungsional, bukan spinner telanjang.
 */

export function StateKosong({
  judul = 'Belum ada alert.',
  pesan = 'Sistem akan menampilkan titik terdeteksi begitu patroli dimulai.',
  aksi = null,
}) {
  return (
    <div className="permukaan flex flex-col items-center px-6 py-14 text-center">
      <span className="mb-4 flex h-11 w-11 items-center justify-center rounded-full border border-ash-600 bg-ash-800">
        <Ikon nama="daftar" ukuran={20} className="text-haze-500" />
      </span>
      <p className="font-display text-heading text-haze-100">{judul}</p>
      <p className="mt-1.5 max-w-sm text-caption text-haze-400">{pesan}</p>
      {aksi}
    </div>
  )
}

export function StateGalat({ galat, onCoba, judul = 'Data tidak bisa dimuat' }) {
  return (
    <div
      role="alert"
      className="rounded-lg border border-ember/45 bg-ember/[0.07] p-5 shadow-ash-sm"
    >
      <div className="flex items-start gap-3">
        <Ikon nama="peringatan" ukuran={18} className="mt-0.5 shrink-0 text-aksen-kuat" />
        <div className="min-w-0 flex-1">
          <p className="font-display text-heading text-haze-100">{judul}</p>
          <p className="mt-1 text-caption text-haze-300">
            {galat?.message ?? 'Sumber data tidak merespons.'}
          </p>
          {galat?.alasan && (
            <p className="mt-2 font-mono text-[0.6875rem] text-haze-500">
              kode: {galat.alasan}
              {galat.status ? ` · http ${galat.status}` : ''}
            </p>
          )}
          {onCoba && (
            <button
              type="button"
              onClick={onCoba}
              className="mt-3 inline-flex items-center gap-1.5 rounded border border-ash-600 bg-ash-800 px-3 py-1.5 text-caption text-haze-200 [transition:background-color_140ms_cubic-bezier(0.22,0.61,0.36,1)] hover:bg-ash-700 active:translate-y-px"
            >
              <Ikon nama="muat" ukuran={13} />
              Coba muat ulang
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export function StateMemuat({ pesan = 'Memuat titik patroli…' }) {
  return (
    <div className="flex items-center gap-2.5 px-1 py-3" role="status" aria-live="polite">
      <span className="h-1.5 w-1.5 rounded-full bg-flame animasi-denyut" />
      <span className="text-caption text-haze-400">{pesan}</span>
    </div>
  )
}
