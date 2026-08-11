import { useEffect, useRef, useState } from 'react'
import { empresasApi } from '../api/services'
import Topbar from '../components/layout/Topbar'
import { Btn, Spinner, Empty, Toast, Modal, Field, Input } from '../components/ui'
import styles from './Empresas.module.css'

const EMPTY = {
  nome: '', subtitulo: '', razao_social: '', cnpj: '', ativo: true,
  cor_fundo: '', cor_surface: '', cor_surface_alt: '', cor_borda: '', cor_texto: '', cor_muted: '',
  cor_primaria: '', cor_primaria_texto: '', cor_acento: '',
  cor_sidebar: '', cor_sidebar_texto: '', cor_sidebar_ativo: '',
}

const COLOR_GROUPS = [
  {
    titulo: 'Fundo & Superfícies',
    campos: [
      { key: 'cor_fundo', label: 'Fundo' },
      { key: 'cor_surface', label: 'Superfície' },
      { key: 'cor_surface_alt', label: 'Superfície (alt)' },
      { key: 'cor_borda', label: 'Borda' },
    ],
  },
  {
    titulo: 'Texto',
    campos: [
      { key: 'cor_texto', label: 'Texto principal' },
      { key: 'cor_muted', label: 'Texto secundário' },
    ],
  },
  {
    titulo: 'Marca',
    campos: [
      { key: 'cor_primaria', label: 'Primária' },
      { key: 'cor_primaria_texto', label: 'Texto sobre primária' },
      { key: 'cor_acento', label: 'Acento' },
    ],
  },
  {
    titulo: 'Sidebar',
    campos: [
      { key: 'cor_sidebar', label: 'Fundo' },
      { key: 'cor_sidebar_texto', label: 'Texto' },
      { key: 'cor_sidebar_ativo', label: 'Item ativo' },
    ],
  },
]

const LOGO_FIELDS = [
  { key: 'logo_horizontal', label: 'Logo horizontal', hint: 'Para fundos claros' },
  { key: 'logo_negativo', label: 'Logo negativo', hint: 'Para fundos escuros (sidebar/noturno)' },
  { key: 'logo_simbolo', label: 'Símbolo', hint: 'Favicon / avatar / tela de escolha' },
]

function CorField({ label, value, onChange }) {
  const valido = /^#[0-9A-Fa-f]{6}$/.test(value)
  return (
    <div className={styles.corField}>
      <input
        type="color"
        className={styles.corSwatch}
        value={valido ? value : '#ffffff'}
        onChange={(e) => onChange(e.target.value)}
      />
      <div className={styles.corInputWrap}>
        <span className={styles.corLabel}>{label}</span>
        <input
          className={styles.corHex}
          type="text"
          placeholder="padrão"
          value={value}
          maxLength={7}
          onChange={(e) => onChange(e.target.value)}
        />
      </div>
    </div>
  )
}

function LogoSlot({ label, hint, url, uploading, onSelecionar, onRemover }) {
  const inputRef = useRef()
  return (
    <div className={styles.logoSlot}>
      <div className={styles.logoPreview}>
        {url ? <img src={url} alt={label} /> : <i className="ti ti-photo" />}
      </div>
      <div className={styles.logoInfo}>
        <span className={styles.logoLabel}>{label}</span>
        <span className={styles.hint}>{hint}</span>
        <div className={styles.logoBtnRow}>
          <input ref={inputRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={onSelecionar} />
          <button type="button" className={styles.btnFoto} disabled={uploading} onClick={() => inputRef.current?.click()}>
            <i className="ti ti-upload" /> {url ? 'Trocar' : 'Enviar'}
          </button>
          {url && (
            <button type="button" className={`${styles.btnFoto} ${styles.btnFotoRemover}`} disabled={uploading} onClick={onRemover}>
              <i className="ti ti-trash" /> Remover
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default function Empresas() {
  const [empresas, setEmpresas] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editEmpresa, setEditEmpresa] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)
  const [uploadingCampo, setUploadingCampo] = useState(null)
  const [toast, setToast] = useState(null)

  const load = () => {
    setLoading(true)
    empresasApi.list()
      .then((r) => setEmpresas(r.data.results ?? r.data))
      .catch(() => setEmpresas([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const open = (e = null) => {
    setEditEmpresa(e)
    setForm(e ? {
      nome: e.nome, subtitulo: e.subtitulo, razao_social: e.razao_social, cnpj: e.cnpj, ativo: e.ativo,
      cor_fundo: e.cor_fundo, cor_surface: e.cor_surface, cor_surface_alt: e.cor_surface_alt, cor_borda: e.cor_borda,
      cor_texto: e.cor_texto, cor_muted: e.cor_muted,
      cor_primaria: e.cor_primaria, cor_primaria_texto: e.cor_primaria_texto, cor_acento: e.cor_acento,
      cor_sidebar: e.cor_sidebar, cor_sidebar_texto: e.cor_sidebar_texto, cor_sidebar_ativo: e.cor_sidebar_ativo,
    } : EMPTY)
    setShowForm(true)
  }

  const close = () => { setShowForm(false); setEditEmpresa(null) }

  const save = async () => {
    if (!form.nome.trim()) { setToast({ message: 'Informe o nome da empresa.', type: 'error' }); return }
    setSaving(true)
    try {
      if (editEmpresa) {
        const res = await empresasApi.update(editEmpresa.id, form)
        setEditEmpresa(res.data)
        setToast({ message: 'Empresa atualizada!', type: 'success' })
      } else {
        const res = await empresasApi.create(form)
        setEditEmpresa(res.data)
        setToast({ message: 'Empresa criada! Agora você já pode enviar os logos.', type: 'success' })
      }
      load()
    } catch (e) {
      const d = e?.response?.data || {}
      const msg = d.cnpj?.[0] || d.nome?.[0] || d.non_field_errors?.[0] || 'Erro ao salvar empresa.'
      setToast({ message: msg, type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  const toggleAtivo = async (e) => {
    try {
      await empresasApi.update(e.id, { ativo: !e.ativo })
      load()
    } catch {
      setToast({ message: 'Erro ao atualizar.', type: 'error' })
    }
  }

  const handleArquivoSelecionado = async (campo, ev) => {
    const file = ev.target.files?.[0]
    ev.target.value = ''
    if (!file || !editEmpresa) return
    setUploadingCampo(campo)
    try {
      const res = await empresasApi.uploadArquivo(editEmpresa.id, campo, file)
      setEditEmpresa(res.data)
      load()
    } catch {
      setToast({ message: 'Erro ao enviar arquivo.', type: 'error' })
    } finally {
      setUploadingCampo(null)
    }
  }

  const handleRemoverArquivo = async (campo) => {
    if (!editEmpresa) return
    setUploadingCampo(campo)
    try {
      const res = await empresasApi.removerArquivo(editEmpresa.id, campo)
      setEditEmpresa(res.data)
      load()
    } catch {
      setToast({ message: 'Erro ao remover arquivo.', type: 'error' })
    } finally {
      setUploadingCampo(null)
    }
  }

  return (
    <div className={styles.page}>
      <Topbar title="Empresas" actions={<Btn icon="plus" onClick={() => open()}>Nova Empresa</Btn>} />

      <div className={styles.content}>
        {loading ? (
          <div className={styles.center}><Spinner size={26} /></div>
        ) : empresas.length === 0 ? (
          <Empty icon="building-store" message="Nenhuma empresa cadastrada ainda." />
        ) : (
          <div className={styles.grid}>
            {empresas.map((e) => (
              <div
                key={e.id}
                className={`${styles.card} ${!e.ativo ? styles.cardInativo : ''}`}
                style={{ borderLeftColor: e.cor_primaria || 'var(--caramelo)' }}
              >
                <div className={styles.cardLogo}>
                  {e.logo_simbolo ? <img src={e.logo_simbolo} alt={e.nome} /> : <i className="ti ti-building-store" />}
                </div>
                <div className={styles.info}>
                  <span className={styles.nome}>{e.nome}</span>
                  {(e.subtitulo || e.cnpj) && (
                    <span className={styles.sub}>{[e.subtitulo, e.cnpj].filter(Boolean).join(' · ')}</span>
                  )}
                </div>
                <div className={styles.actions}>
                  {e.padrao ? (
                    <span className={`${styles.pill} ${styles.pillPadrao}`}>Padrão</span>
                  ) : (
                    <button
                      className={`${styles.pill} ${e.ativo ? styles.pillAtivo : styles.pillInativo}`}
                      onClick={() => toggleAtivo(e)}
                      title="Clique para alternar"
                    >
                      {e.ativo ? 'Ativo' : 'Inativo'}
                    </button>
                  )}
                  <button className={styles.iconBtn} onClick={() => open(e)}><i className="ti ti-edit" /></button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <Modal
        open={showForm}
        onClose={close}
        title={editEmpresa ? `Editar: ${editEmpresa.nome}` : 'Nova Empresa'}
        width={680}
        footer={
          <>
            <Btn variant="ghost" onClick={close}>Fechar</Btn>
            <Btn loading={saving} icon="check" onClick={save}>{editEmpresa ? 'Salvar' : 'Criar'}</Btn>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div className={styles.formSection}>
            <span className={styles.sectionTitle}>Dados básicos</span>
            <div className={styles.rowGrid}>
              <Field label="Nome fantasia *">
                <Input value={form.nome} onChange={(e) => setForm((f) => ({ ...f, nome: e.target.value }))} placeholder="Ex: Mangaio" />
              </Field>
              <Field label="Subtítulo (sidebar)">
                <Input value={form.subtitulo} onChange={(e) => setForm((f) => ({ ...f, subtitulo: e.target.value }))} placeholder="Ex: Cozinha Brasileira" />
              </Field>
            </div>
            <div className={styles.rowGrid}>
              <Field label="Razão social">
                <Input value={form.razao_social} onChange={(e) => setForm((f) => ({ ...f, razao_social: e.target.value }))} />
              </Field>
              <Field label="CNPJ">
                <Input value={form.cnpj} onChange={(e) => setForm((f) => ({ ...f, cnpj: e.target.value }))} placeholder="12.345.678/0001-90" />
              </Field>
            </div>
            {editEmpresa && !editEmpresa.padrao && (
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--muted)' }}>
                <input type="checkbox" checked={form.ativo} onChange={(e) => setForm((f) => ({ ...f, ativo: e.target.checked }))} />
                Empresa ativa (disponível para seleção)
              </label>
            )}
          </div>

          <div className={styles.formSection}>
            <span className={styles.sectionTitle}>Cores da marca</span>
            <span className={styles.hint} style={{ marginBottom: 8 }}>
              Deixe em branco para herdar a cor padrão do sistema (UI atual da Arretado).
            </span>
            {COLOR_GROUPS.map((grupo) => (
              <div key={grupo.titulo} className={styles.corGroup}>
                <span className={styles.corGroupTitle}>{grupo.titulo}</span>
                <div className={styles.corGrid}>
                  {grupo.campos.map(({ key, label }) => (
                    <CorField
                      key={key}
                      label={label}
                      value={form[key]}
                      onChange={(v) => setForm((f) => ({ ...f, [key]: v }))}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>

          {editEmpresa ? (
            <div className={styles.formSection}>
              <span className={styles.sectionTitle}>Logos</span>
              <div className={styles.logoGrid}>
                {LOGO_FIELDS.map(({ key, label, hint }) => (
                  <LogoSlot
                    key={key}
                    label={label}
                    hint={hint}
                    url={editEmpresa[key]}
                    uploading={uploadingCampo === key}
                    onSelecionar={(ev) => handleArquivoSelecionado(key, ev)}
                    onRemover={() => handleRemoverArquivo(key)}
                  />
                ))}
              </div>
            </div>
          ) : (
            <p className={styles.hint}>Salve os dados básicos para poder enviar os logos.</p>
          )}
        </div>
      </Modal>

      {toast && <Toast {...toast} onClose={() => setToast(null)} />}
    </div>
  )
}
