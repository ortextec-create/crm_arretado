import styles from './Topbar.module.css'

export default function Topbar({ title, search, onSearch, actions }) {
  return (
    <div className={styles.topbar}>
      <h1 className={`serif ${styles.title}`}>{title}</h1>

      {onSearch !== undefined && (
        <div className={styles.searchWrap}>
          <i className="ti ti-search" aria-hidden="true" />
          <input
            className={styles.search}
            placeholder="Buscar cliente, CPF, telefone..."
            value={search}
            onChange={(e) => onSearch(e.target.value)}
          />
          {search && (
            <button className={styles.clearBtn} onClick={() => onSearch('')}>
              <i className="ti ti-x" />
            </button>
          )}
        </div>
      )}

      {actions && <div className={styles.actions}>{actions}</div>}
    </div>
  )
}
