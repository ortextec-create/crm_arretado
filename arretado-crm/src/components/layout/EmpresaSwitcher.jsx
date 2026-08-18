import { useEffect, useRef, useState } from 'react'
import { useAuth } from '../../hooks/useAuth'
import styles from './EmpresaSwitcher.module.css'

// Multi-Empresa — Fase 2 (ver MULTIEMPRESA.md). Só aparece com 2+ empresas
// (vinculadas, ou todas ativas no caso de role=admin — ver usuarios/views.py
// ::_empresas_efetivas) — usuário de empresa única não vê nada de novo.
export default function EmpresaSwitcher() {
  const { empresas, empresaAtiva, trocarEmpresa } = useAuth()
  const [open, setOpen] = useState(false)
  const [trocando, setTrocando] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    const onClickFora = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', onClickFora)
    return () => document.removeEventListener('mousedown', onClickFora)
  }, [open])

  if ((empresas?.length || 0) < 2 || !empresaAtiva) return null

  const escolher = async (empresa) => {
    if (empresa.id === empresaAtiva.id) { setOpen(false); return }
    setTrocando(true)
    try {
      await trocarEmpresa(empresa.id)
    } finally {
      setTrocando(false)
      setOpen(false)
    }
  }

  return (
    <div className={styles.wrap} ref={ref}>
      <button
        className={styles.pill}
        style={{ '--cor-empresa': empresaAtiva.cor_primaria || 'var(--caramelo)' }}
        onClick={() => setOpen((v) => !v)}
        title="Trocar empresa"
        disabled={trocando}
      >
        <span className={styles.dotEmpresa} />
        <span className={styles.nome}>{empresaAtiva.nome}</span>
        <i className={`ti ti-chevron-${open ? 'up' : 'down'}`} style={{ fontSize: 12, marginLeft: 'auto' }} />
      </button>

      {open && (
        <div className={styles.menu}>
          {empresas.map((empresa) => (
            <button
              key={empresa.id}
              className={`${styles.item} ${empresa.id === empresaAtiva.id ? styles.itemActive : ''}`}
              style={{ '--cor-empresa': empresa.cor_primaria || 'var(--caramelo)' }}
              onClick={() => escolher(empresa)}
              disabled={trocando}
            >
              <span className={styles.dotEmpresa} />
              {empresa.nome}
              {empresa.id === empresaAtiva.id && <i className="ti ti-check" style={{ marginLeft: 'auto', fontSize: 13 }} />}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
