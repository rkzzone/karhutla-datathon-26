/**
 * Token dari DESIGN_BRIEF.md Bagian 2 — hex inti di sana FINAL.
 *
 * Nilai yang ditandai (brief) disalin persis dan tidak boleh diubah sepihak.
 * Nilai lain adalah langkah antara yang diturunkan untuk kebutuhan border/hover;
 * menambah langkah antara diizinkan (brief = lantai minimum), mengubah hex inti
 * tidak — itu harus lewat CHANGELOG.md dan kesepakatan tim.
 *
 * Kode memanggil `bg-ash-950`, JANGAN `bg-[#14120F]`.
 *
 * DUA TEMA — `ash`, `haze`, `canopy`, `satellite`, dan `iot` menunjuk ke CSS
 * variable, nilainya ditukar di src/index.css saat `data-tema="terang"`. Bentuk
 * `rgb(var(--x) / <alpha-value>)` dipakai supaya modifier opacity Tailwind
 * (`bg-ash-950/92`, `bg-iot/20`) tetap bekerja — hex mentah akan mematikannya.
 *
 * Skala Ember TIDAK ikut bertukar: ramp Ironbow adalah elemen signature dan
 * harus identik di kedua tema. Yang berbeda hanya varian TEKS-nya (Ember asli
 * cuma 1.6:1 di atas kertas terang) — itu diatur lewat `--tingkat-*-teks`.
 */
const v = (nama) => `rgb(var(${nama}) / <alpha-value>)`

export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ash: {
          950: v('--ash-950'), // gelap #14120F (brief) ↔ terang #EFEAE0
          900: v('--ash-900'), // gelap #1C1915 (brief) ↔ terang #FBF8F2
          800: v('--ash-800'), // gelap #26221C (brief) ↔ terang #E4DDD0
          700: v('--ash-700'),
          600: v('--ash-600'),
          500: v('--ash-500'),
        },
        haze: {
          100: v('--haze-100'), // gelap #F2EDE4 (brief) ↔ terang #171410
          200: v('--haze-200'),
          300: v('--haze-300'),
          400: v('--haze-400'), // gelap #B8AFA0 (brief) ↔ terang #5C5346
          500: v('--haze-500'),
        },
        canopy: {
          700: v('--canopy-700'),
          600: v('--canopy-600'), // brief — permukaan status aman
          500: v('--canopy-500'),
          400: v('--canopy-400'), // brief — aksen status aman (isi)
          300: v('--canopy-300'), // varian teks kontras tinggi
        },
        // Skala Ember — SIGNATURE, identik di kedua tema.
        // HANYA untuk fill/stroke/border. Untuk TEKS pakai `aksen`/`aksen-kuat`
        // di bawah: `flame` cuma 2.83:1 dan `flare` 1.56:1 di atas kertas terang.
        smoke: '#6B6259', // brief — tingkat 1
        ember: '#C1392B', // brief — tingkat 2
        flame: '#E8752C', // brief — tingkat 3
        flare: '#F5C242', // brief — tingkat 4
        // Varian TEKS dari aksen Ember — satu-satunya yang boleh jadi teks.
        aksen: v('--aksen'), // gelap = flame, terang = #9A4E12
        'aksen-kuat': v('--aksen-kuat'), // gelap = flare, terang = #8A5E00
        satellite: {
          DEFAULT: v('--satellite'), // brief — marker hotspot FIRMS
          dim: v('--satellite-dim'),
        },
        iot: {
          DEFAULT: v('--iot'), // brief — marker sensor simulasi
          dim: v('--iot-dim'),
        },
      },
      fontFamily: {
        display: ['"Space Grotesk"', 'sans-serif'],
        sans: ['"IBM Plex Sans"', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
      fontSize: {
        // DESIGN_BRIEF Bagian 2.2 — skala tipe, basis 16px
        'display-xl': ['3rem', { lineHeight: '1.05', letterSpacing: '-0.03em' }],
        'display-lg': ['2rem', { lineHeight: '1.1', letterSpacing: '-0.02em' }],
        heading: ['1.25rem', { lineHeight: '1.3', letterSpacing: '-0.01em' }],
        body: ['1rem', { lineHeight: '1.7' }],
        caption: ['0.8125rem', { lineHeight: '1.5' }],
        'mono-data': ['0.875rem', { lineHeight: '1.4' }],
      },
      boxShadow: {
        // Bertingkat & bertoning ash — dilarang `shadow-md` polos.
        // Nilainya ikut tema: di terang, bayangan pekat ala mode gelap akan
        // terlihat kotor, jadi opasitasnya diturunkan (lihat src/index.css).
        'ash-sm': 'var(--bayang-sm)',
        'ash-md': 'var(--bayang-md)',
        'ash-lg': 'var(--bayang-lg)',
        'ember-glow': 'var(--bayang-ember)',
      },
      backgroundImage: {
        // Ironbow Risk Ribbon — dipakai identik di AlertCard, legenda peta,
        // dan color ramp HeatmapOverlay. Lihat DESIGN_BRIEF Bagian 2.3.
        ironbow:
          'linear-gradient(to top, #6B6259 0%, #C1392B 38%, #E8752C 70%, #F5C242 100%)',
        'ironbow-x':
          'linear-gradient(to right, #6B6259 0%, #C1392B 38%, #E8752C 70%, #F5C242 100%)',
      },
      transitionTimingFunction: {
        instrument: 'cubic-bezier(0.22, 0.61, 0.36, 1)',
      },
    },
  },
  plugins: [],
}
