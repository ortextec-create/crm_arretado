import { useAuth } from '../../hooks/useAuth'
import styles from './SeletorTema.module.css'

// Fase 3 do Multi-Empresa (temas, ver MULTIEMPRESA.md). Mesmo desvio já
// documentado no EmpresaSwitcher: o spec original previa o seletor "no
// header", mas este projeto não tem header/topbar global — só Sidebar.
const OPCOES = [
  { valor: 'empresa', icone: 'building-store', titulo: 'Tema da empresa' },
  { valor: 'neutro_claro', icone: 'sun', titulo: 'Tema claro' },
  { valor: 'neutro_escuro', icone: 'moon', titulo: 'Tema escuro' },
]

export default function SeletorTema() {
  const { user, definirPreferenciaTema } = useAuth()
  const atual = user?.preferencia_tema || 'empresa'

  return (
    <div className={styles.wrap} title="Tema">
      {OPCOES.map(({ valor, icone, titulo }) => (
        <button
          key={valor}
          type="button"
          className={`${styles.opcao} ${atual === valor ? styles.ativo : ''}`}
          onClick={() => valor !== atual && definirPreferenciaTema(valor)}
          title={titulo}
        >
          <i className={`ti ti-${icone}`} />
        </button>
      ))}
    </div>
  )
}
