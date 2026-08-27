import { LABEL_PEMICU, WARNA_PEMICU } from '../lib/risk.js'
import Ikon from './Ikon.jsx'

const IKON_PEMICU = {
  satellite_firms: 'satelit',
  iot_ground: 'sensor',
  patrol_scheduled: 'patroli',
}

/**
 * Penanda sumber pemicu. Warna mengikuti marker peta yang sama (satellite-blue /
 * iot-mauve / haze) supaya kartu dan peta terbaca sebagai satu sistem.
 *
 * `iot_ground` selalu membawa penanda "simulasi" selama Stage 12 memakai
 * simulator — data simulasi tidak boleh tampil seperti sensor nyata.
 */
export default function SourceBadge({ pemicu, simulasi = pemicu === 'iot_ground' }) {
  // `WARNA_PEMICU` berisi CSS variable supaya ikut tema, jadi transparansinya
  // dihitung dengan `color-mix` — sambung-hex (`${warna}59`) tidak berlaku
  // untuk `var()`.
  const warna = WARNA_PEMICU[pemicu] ?? 'var(--marker-patroli)'
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-caption"
      style={{
        borderColor: `color-mix(in srgb, ${warna} 40%, transparent)`,
        backgroundColor: `color-mix(in srgb, ${warna} 9%, transparent)`,
        color: warna,
      }}
    >
      <Ikon nama={IKON_PEMICU[pemicu] ?? 'info'} ukuran={12} />
      {LABEL_PEMICU[pemicu] ?? pemicu}
      {simulasi && (
        <span className="ml-0.5 rounded-sm bg-ash-950/60 px-1 font-mono text-[0.5625rem] uppercase tracking-[0.12em] text-haze-400">
          simulasi
        </span>
      )}
    </span>
  )
}
