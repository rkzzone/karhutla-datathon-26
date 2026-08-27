/**
 * Ikon inline — tanpa pustaka ikon eksternal.
 *
 * Ada bukan sebagai dekorasi: DESIGN_BRIEF Bagian 5 melarang makna di-encode
 * lewat warna saja, jadi setiap status wajib punya pasangan ikon + label teks.
 * `api` vs `centang` adalah pembeda bentuk antara "berisiko" dan "aman".
 */

const JALUR = {
  api: 'M12 2c.5 3.2-1.4 4.6-2.6 5.9C7.9 9.5 7 10.9 7 13a5 5 0 0 0 10 0c0-1.8-.7-3-1.6-4.2-.4 1-1.1 1.7-1.9 2 .5-2.4-.4-5.4-1.5-8.8Z',
  bara: 'M12 3.5c.4 2.4-1 3.5-1.9 4.5-.8.9-1.4 2-1.4 3.5a3.3 3.3 0 0 0 6.6 0c0-1.3-.5-2.3-1.2-3.2-.3.8-.8 1.3-1.4 1.5.4-1.8-.3-4.1-.7-6.3Z',
  centang: 'M20 6.5 9.6 17 4 11.4',
  satelit:
    'M5.6 12.4 3 9.8l3.5-3.5 2.6 2.6M11.6 6.4 14.2 3.8l3.5 3.5-2.6 2.6M9 15l-3.2 3.2M8.4 9.9l5.7 5.7M15 12.5a4.5 4.5 0 0 1 4.5 4.5M15 16.4a1 1 0 0 1 1 1',
  sensor: 'M12 12v8M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM7.8 3.8a8 8 0 0 0 0 8.4M16.2 3.8a8 8 0 0 1 0 8.4M8 20h8',
  patroli: 'M12 21s7-5.5 7-11a7 7 0 1 0-14 0c0 5.5 7 11 7 11Z M12 12.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z',
  peringatan: 'M12 3.6 2.5 20h19L12 3.6ZM12 9.5v4.5M12 17.2h.01',
  lapis: 'M12 3 3 8l9 5 9-5-9-5ZM3 13l9 5 9-5M3 17.5l9 5 9-5',
  panah: 'M5 12h13M13 6.5 18.5 12 13 17.5',
  jam: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM12 7.5V12l3 2',
  info: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM12 11v5M12 7.8h.01',
  muat: 'M20 12a8 8 0 1 1-2.6-5.9M20 4v4.5h-4.5',
  peta: 'M9 4 3 6.5v13.5L9 17.5M9 4l6 3M9 4v13.5M15 7l6-2.5V18l-6 2.5M15 7v13.5M9 17.5l6 3',
  daftar: 'M8 6.5h13M8 12h13M8 17.5h13M3.6 6.5h.01M3.6 12h.01M3.6 17.5h.01',
  bagan: 'M4 20V9M10 20V4M16 20v-7M22 20H2',
  tutup: 'M6 6l12 12M18 6 6 18',
  mata: 'M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z M12 14.8a2.8 2.8 0 1 0 0-5.6 2.8 2.8 0 0 0 0 5.6Z',
  gelombang: 'M2 12h3l2.5-7 4 14 3-9 2 2h5.5',
  matahari:
    'M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10ZM12 1.8v2.4M12 19.8v2.4M4.8 4.8l1.7 1.7M17.5 17.5l1.7 1.7M1.8 12h2.4M19.8 12h2.4M4.8 19.2l1.7-1.7M17.5 6.5l1.7-1.7',
  bulan: 'M20.5 14.4A8.6 8.6 0 0 1 9.6 3.5a8.6 8.6 0 1 0 10.9 10.9Z',
  // Lapisan size-up. `angin` sengaja bukan panah: panah menyiratkan lintasan,
  // sementara yang ditampilkan cuma arah dorongan (larangan nomor 14).
  angin: 'M3 8.5h9.5a3 3 0 1 0-3-3M3 12.5h13a3 3 0 1 1-3 3M3 16.5h7.5a2.5 2.5 0 1 1-2.5 2.5',
  air: 'M12 3.2c3.4 3.6 5.6 6.3 5.6 9.1a5.6 5.6 0 1 1-11.2 0c0-2.8 2.2-5.5 5.6-9.1Z',
  jalan: 'M8.5 3 5 21M15.5 3 19 21M12 4v3M12 10.5v3M12 17v3',
  alat: 'M14.5 3.5a4.5 4.5 0 0 0-5.9 5.8L3.5 14.4a2 2 0 1 0 2.8 2.8l5.1-5.1a4.5 4.5 0 0 0 5.8-5.9l-2.6 2.6-2.3-2.3 2.2-2.6Z',
  salin: 'M9 9V5.5A1.5 1.5 0 0 1 10.5 4h8A1.5 1.5 0 0 1 20 5.5v8a1.5 1.5 0 0 1-1.5 1.5H15M5.5 9h8A1.5 1.5 0 0 1 15 10.5v8A1.5 1.5 0 0 1 13.5 20h-8A1.5 1.5 0 0 1 4 18.5v-8A1.5 1.5 0 0 1 5.5 9Z',
}

const ISIAN = new Set(['api', 'bara'])

export default function Ikon({ nama, ukuran = 16, className = '', ...sisa }) {
  const d = JALUR[nama]
  if (!d) return null
  const terisi = ISIAN.has(nama)
  return (
    <svg
      viewBox="0 0 24 24"
      width={ukuran}
      height={ukuran}
      className={className}
      fill={terisi ? 'currentColor' : 'none'}
      stroke={terisi ? 'none' : 'currentColor'}
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...sisa}
    >
      <path d={d} />
    </svg>
  )
}
