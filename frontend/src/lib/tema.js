import { useEffect, useState } from 'react'

/**
 * Peralihan tema gelap ↔ terang.
 *
 * Tema disimpan sebagai atribut `data-tema` di `<html>`; seluruh token warna
 * ditukar lewat CSS variable di src/index.css. Tidak ada komponen yang perlu
 * kelas `dark:` — `bg-ash-900` tetap berarti "permukaan kartu" di kedua tema.
 *
 * Default mengikuti preferensi sistem operator. Begitu operator memilih sendiri,
 * pilihan itu menang dan disimpan — di posko, orang tidak mau menyetel ulang
 * layar tiap kali membuka dashboard.
 *
 * Catatan mode gelap: DESIGN_BRIEF ditulis untuk sistem gelap, dan tema gelap
 * di sini TIDAK berubah sedikit pun dari spesifikasi itu. Tema terang adalah
 * tambahan atas permintaan, bukan penggantinya.
 */

const KUNCI = 'karhutla:tema'
export const TEMA = { gelap: 'gelap', terang: 'terang' }

const pendengar = new Set()

function bacaTersimpan() {
  try {
    const nilai = localStorage.getItem(KUNCI)
    return nilai === TEMA.gelap || nilai === TEMA.terang ? nilai : null
  } catch {
    // localStorage bisa diblokir (mode privat / kebijakan kios) — bukan alasan
    // untuk gagal render; cukup jatuh ke preferensi sistem.
    return null
  }
}

function preferensiSistem() {
  if (typeof window === 'undefined' || !window.matchMedia) return TEMA.gelap
  return window.matchMedia('(prefers-color-scheme: light)').matches
    ? TEMA.terang
    : TEMA.gelap
}

export function temaAwal() {
  return bacaTersimpan() ?? preferensiSistem()
}

export function terapkanTema(tema) {
  if (typeof document === 'undefined') return
  const akar = document.documentElement
  if (tema === TEMA.terang) akar.setAttribute('data-tema', 'terang')
  else akar.removeAttribute('data-tema')
  akar.style.colorScheme = tema === TEMA.terang ? 'light' : 'dark'
}

export function setTema(tema) {
  terapkanTema(tema)
  try {
    localStorage.setItem(KUNCI, tema)
  } catch {
    /* tidak bisa disimpan — tema tetap berlaku untuk sesi ini */
  }
  pendengar.forEach((fn) => fn(tema))
}

/** Dipanggil sekali sebelum React render, di main.jsx — mencegah kedip tema. */
export function pasangTemaAwal() {
  terapkanTema(temaAwal())
}

export function useTema() {
  const [tema, simpanState] = useState(temaAwal)

  useEffect(() => {
    const dengar = (nilai) => simpanState(nilai)
    pendengar.add(dengar)
    return () => pendengar.delete(dengar)
  }, [])

  // Ikuti perubahan preferensi sistem SELAMA operator belum memilih sendiri.
  useEffect(() => {
    if (!window.matchMedia) return
    const kueri = window.matchMedia('(prefers-color-scheme: light)')
    const ubah = () => {
      if (bacaTersimpan()) return
      const berikut = kueri.matches ? TEMA.terang : TEMA.gelap
      terapkanTema(berikut)
      simpanState(berikut)
    }
    kueri.addEventListener('change', ubah)
    return () => kueri.removeEventListener('change', ubah)
  }, [])

  return {
    tema,
    terang: tema === TEMA.terang,
    setTema,
    balik: () => setTema(tema === TEMA.terang ? TEMA.gelap : TEMA.terang),
  }
}

/**
 * Warna konkret (bukan `var()`) untuk konsumen yang tidak bisa memakai CSS
 * variable — Recharts menuliskan `stroke` sebagai ATRIBUT SVG, dan `var()`
 * tidak resolve di atribut presentasi. Halaman 4 memakai ini.
 *
 * ---------------------------------------------------------------------------
 * PALET SERI GRAFIK — divalidasi, bukan dikira-kira
 * ---------------------------------------------------------------------------
 * Ketiganya lolos cek CVD/kontras untuk SEMUA pasangan (bukan cuma yang
 * bersebelahan), di atas permukaan tema masing-masing:
 *
 *   gelap  (surface ash-900 #1C1915)
 *     terburuk: canopy↔flare  ΔE 13.8 protan · 19.1 tritan · normal 18.6
 *     kontras : ketiganya >= 3:1
 *
 *   terang (surface kartu #FBF8F2)
 *     terburuk: merah↔amber   ΔE 13.6 deutan · 14.5 tritan · normal 16.8
 *     kontras : ketiganya >= 3:1
 *
 * Dua penyimpangan dari "seri pakai skala Ember" (DESIGN_BRIEF Bagian 4), dan
 * alasannya — keduanya soal keterbacaan, bukan selera:
 *
 * 1. `rgb_only` TIDAK memakai `smoke #6B6259`. Di atas ash-900 warna itu cuma
 *    2.93:1 dan chroma-nya di bawah lantai (terbaca abu-abu polos), lalu ΔE
 *    protan-nya terhadap `ember` cuma 6.6. Diganti canopy — brief memang
 *    menyebut "skala Ember/Canopy" untuk seri chart.
 * 2. Di tema TERANG, `rgb_only` memakai satellite-blue, bukan canopy. Hijau-tua
 *    lawan merah-tua di atas kertas cuma ΔE 4.3 untuk protanopia — praktis satu
 *    warna bagi pembaca buta warna merah. DESIGN_BRIEF Bagian 5 menyatakan
 *    aksesibilitas wajib dan bukan opsional, jadi itu yang menang. Halaman 4
 *    tidak punya peta, sehingga tidak ada tabrakan makna dengan marker FIRMS.
 *
 * Warna tetap dipasangkan dengan pola garis + label langsung di ujung garis,
 * supaya identitas seri tidak pernah bergantung pada warna saja.
 */
export const PALET_SERI = {
  [TEMA.gelap]: {
    fusi: '#F5C242', // flare
    thermal_only: '#C1392B', // ember
    rgb_only: '#7FB394', // canopy-300
    kisi: '#332E27',
    sumbu: '#5A5147',
    tik: '#8E8677',
    latarTooltip: '#1C1915',
    garisTooltip: '#453E35',
    tekstTooltip: '#B8AFA0',
  },
  [TEMA.terang]: {
    fusi: '#B57200',
    thermal_only: '#A32A1E',
    rgb_only: '#2F6180', // satellite gelap — lihat catatan 2 di atas
    kisi: '#D2C9B8',
    sumbu: '#B9AE99',
    tik: '#6A604F',
    latarTooltip: '#FBF8F2',
    garisTooltip: '#B9AE99',
    tekstTooltip: '#5C5346',
  },
}
