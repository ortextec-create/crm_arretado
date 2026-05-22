import { useEffect, useState } from 'react'
import { tagsApi } from '../api/services'
import Topbar from '../components/layout/Topbar'
import { Btn, Spinner, Empty, Toast, Modal, Field, Input } from '../components/ui'
import styles from './Tags.module.css'

const PRESET_COLORS = ['#C8860A','#8FBC8B','#6B3A2A','#9CA3AF','#3B82F6','#EC4899','#F59E0B','#10B981','#8B5CF6','#EF4444']

export default function Tags() {
  const [tags, setTags] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editTag, setEditTag] = useState(null)
  const [form, setForm] = useState({ nome: '', cor: '#C8860A' })
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState(null)

  const load = () => {
    setLoading(true)
    tagsApi.list()
      .then((r) => setTags(r.data.results ?? r.data))
      .catch(() => setTags([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const open = (tag = null) => {
    setEditTag(tag)
    setForm(tag ? { nome: tag.nome, cor: tag.cor } : { nome: '', cor: '#C8860A' })
    setShowForm(true)
  }

  const save = async () => {
    if (!form.nome.trim()) return
    setSaving(true)
    try {
      if (editTag) await tagsApi.update(editTag.id, form)
      else await tagsApi.create(form)
      setToast({ message: editTag ? 'Tag atualizada!' : 'Tag criada!', type: 'success' })
      setShowForm(false)
      load()
    } catch {
      setToast({ message: 'Erro ao salvar tag.', type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  const remove = async (id) => {
    if (!confirm('Remover esta tag? Ela será desassociada dos clientes.')) return
    try {
      await tagsApi.delete(id)
      setToast({ message: 'Tag removida.', type: 'success' })
      load()
    } catch {
      setToast({ message: 'Erro ao remover.', type: 'error' })
    }
  }

  return (
    <div className={styles.page}>
      <Topbar
        title="Tags de Clientes"
        actions={<Btn icon="plus" onClick={() => open()}>Nova Tag</Btn>}
      />

      <div className={styles.content}>
        {loading ? (
          <div className={styles.center}><Spinner size={26} /></div>
        ) : tags.length === 0 ? (
          <Empty icon="tag" message="Nenhuma tag criada ainda." />
        ) : (
          <div className={styles.grid}>
            {tags.map((t) => (
              <div key={t.id} className={styles.tagCard}>
                <div className={styles.tagDot} style={{ background: t.cor }} />
                <div className={styles.tagInfo}>
                  <span className={styles.tagName}>{t.nome}</span>
                  <span className={styles.tagCor}>{t.cor}</span>
                </div>
                <div className={styles.tagActions}>
                  <button className={styles.iconBtn} onClick={() => open(t)}><i className="ti ti-edit" /></button>
                  <button className={`${styles.iconBtn} ${styles.iconBtnDanger}`} onClick={() => remove(t.id)}><i className="ti ti-trash" /></button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <Modal
        open={showForm}
        onClose={() => setShowForm(false)}
        title={editTag ? 'Editar Tag' : 'Nova Tag'}
        width={380}
        footer={
          <>
            <Btn variant="ghost" onClick={() => setShowForm(false)}>Cancelar</Btn>
            <Btn loading={saving} icon="check" onClick={save}>
              {editTag ? 'Salvar' : 'Criar Tag'}
            </Btn>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          <Field label="Nome da Tag *">
            <Input
              placeholder="Ex: VIP, Casamento, Corporativo..."
              value={form.nome}
              onChange={(e) => setForm((f) => ({ ...f, nome: e.target.value }))}
              onKeyDown={(e) => { if (e.key === 'Enter') save() }}
            />
          </Field>
          <Field label="Cor">
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 2 }}>
              {PRESET_COLORS.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setForm((f) => ({ ...f, cor: c }))}
                  style={{
                    width: 28, height: 28, borderRadius: '50%', background: c,
                    border: form.cor === c ? '2px solid var(--bege)' : '2px solid transparent',
                    cursor: 'pointer', transition: 'transform 0.1s',
                    transform: form.cor === c ? 'scale(1.2)' : 'scale(1)',
                  }}
                />
              ))}
              <input
                type="color"
                value={form.cor}
                onChange={(e) => setForm((f) => ({ ...f, cor: e.target.value }))}
                style={{ width: 28, height: 28, borderRadius: '50%', cursor: 'pointer', border: 'none', background: 'none', padding: 0 }}
                title="Cor personalizada"
              />
            </div>
          </Field>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 36, height: 36, borderRadius: '50%', background: form.cor, opacity: 0.8 }} />
            <span style={{ fontSize: 13, color: 'var(--bege)' }}>Prévia: <strong>{form.nome || 'Nome da tag'}</strong></span>
          </div>
        </div>
      </Modal>

      {toast && <Toast {...toast} onClose={() => setToast(null)} />}
    </div>
  )
}
