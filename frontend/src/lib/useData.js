import { useCallback, useEffect, useState } from 'react'

/**
 * Pembungkus fetch dengan tiga state eksplisit: memuat / galat / data.
 *
 * Sengaja tidak menyembunyikan galat di balik data kosong — halaman harus bisa
 * membedakan "tidak ada alert" (state kosong) dari "gagal memuat" (state galat),
 * karena copy dan tindakan operator untuk keduanya berbeda (brief Bagian 6).
 */
export function useData(pengambil, deps = []) {
  const [data, setData] = useState(null)
  const [galat, setGalat] = useState(null)
  const [memuat, setMemuat] = useState(true)
  const [tik, setTik] = useState(0)

  const muatUlang = useCallback(() => setTik((n) => n + 1), [])

  useEffect(() => {
    let batal = false
    setMemuat(true)
    setGalat(null)
    Promise.resolve(pengambil())
      .then((hasil) => {
        if (!batal) setData(hasil)
      })
      .catch((e) => {
        if (!batal) {
          setGalat(e)
          setData(null)
        }
      })
      .finally(() => {
        if (!batal) setMemuat(false)
      })
    return () => {
      batal = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tik])

  return { data, galat, memuat, muatUlang, setData }
}
