import { useEffect, useState } from 'react'
import { locaisEventoApi } from '../api/services'
import Topbar from '../components/layout/Topbar'
import { Btn, Spinner, Empty, Toast, Modal, Field, Input, Textarea } from '../components/ui'
import styles from './Locais.module.css'

const EMPTY = { nome: '', endereco: '', bairro: '', cidade: 'Teresina', referencia: '', ativo: true }

export default function Locais() {
  const [locais, setLocais] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editLocal, setEditLocal] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState(null)

  const load = () => {
    setLoading(true)
    locaisEventoApi.list()
      .then((r) => setLocais(r.data.results ?? r.data))
      .catch(() => setLocais([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const open = (l = null) => {
    setEditLocal(l)
    setForm(l ? {
      nome: l.nome, endereco: l.endereco, bairro: l.bairro,
      cidade: l.cidade, referencia: l.referencia, ativo: l.ativo,
    } : EMPTY)
    setShowForm(true)
  }

  const save = async () => {
    if (!form.nome.trim()) return
    setSaving(true)
    try {
      if (editLocal) await locaisEventoApi.update(editLocal.id, form)
      else await locaisEventoApi.create(form)
      setToast({ message: editLocal ? 'Local atualizado!' : 'Local criado!', type: 'success' })
      setShowForm(false)
      load()
    } catch {
      setToast({ message: 'Erro ao salvar local.', type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  const remove = async (id) => {
    if (!confirm('Remover este local de evento?')) return
    try {
      await locaisEventoApi.remove(id)
      setToast({ message: 'Local removido.', type: 'success' })
      load()
    } catch {
      setToast({ message: 'Erro ao remover.', type: 'error' })
    }
  }

  const toggleAtivo = async (l) => {
    try {
      await locaisEventoApi.update(l.id, { ativo: !l.ativo })
      load()
    } catch {
      setToast({ message: 'Erro ao atualizar.', type: 'error' })
    }
  }

  return (
    <div className={styles.page}>
      <Topbar
        title="Locais de Evento"
        actions={<Btn icon="plus" onClick={() => open()}>Novo Local</Btn>}
      />

      <div className={styles.content}>
        {loading ? (
          <div className={styles.center}><Spinner size={26} /></div>
        ) : locais.length === 0 ? (
          <Empty icon="map-pin" message="Nenhum local de evento cadastrado ainda." />
        ) : (
          <div className={styles.grid}>
            {locais.map((l) => (
              <div key={l.id} className={`${styles.card} ${!l.ativo ? styles.cardInativo : ''}`}>
                <div className={styles.info}>
                  <span className={styles.nome}>{l.nome}</span>
                  <span className={styles.endereco}>{l.endereco_completo || [l.endereco, l.bairro, l.cidade].filter(Boolean).join(', ')}</span>
                  {l.referencia && <span className={styles.referencia}>{l.referencia}</span>}
                </div>
                <div className={styles.actions}>
                  <button
                    className={`${styles.pill} ${l.ativo ? styles.pillAtivo : styles.pillInativo}`}
                    onClick={() => toggleAtivo(l)}
                    title="Clique para alternar"
                  >
                    {l.ativo ? 'Ativo' : 'Inativo'}
                  </button>
                  <button className={styles.iconBtn} onClick={() => open(l)}><i className="ti ti-edit" /></button>
                  <button className={`${styles.iconBtn} ${styles.iconBtnDanger}`} onClick={() => remove(l.id)}><i className="ti ti-trash" /></button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <Modal
        open={showForm}
        onClose={() => setShowForm(false)}
        title={editLocal ? 'Editar Local' : 'Novo Local de Evento'}
        width={420}
        footer={
          <>
            <Btn variant="ghost" onClick={() => setShowForm(false)}>Cancelar</Btn>
            <Btn loading={saving} icon="check" onClick={save}>
              {editLocal ? 'Salvar' : 'Criar'}
            </Btn>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          <Field label="Nome do local *">
            <Input
              placeholder="Ex: Espaço Villa das Flores"
              value={form.nome}
              onChange={(e) => setForm((f) => ({ ...f, nome: e.target.value }))}
              onKeyDown={(e) => { if (e.key === 'Enter') save() }}
            />
          </Field>
          <Field label="Endereço">
            <Input
              placeholder="Rua, número"
              value={form.endereco}
              onChange={(e) => setForm((f) => ({ ...f, endereco: e.target.value }))}
            />
          </Field>
          <div style={{ display: 'flex', gap: 12 }}>
            <div style={{ flex: 1 }}>
              <Field label="Bairro">
                <Input
                  placeholder="Ex: Fátima"
                  value={form.bairro}
                  onChange={(e) => setForm((f) => ({ ...f, bairro: e.target.value }))}
                />
              </Field>
            </div>
            <div style={{ flex: 1 }}>
              <Field label="Cidade">
                <Input
                  value={form.cidade}
                  onChange={(e) => setForm((f) => ({ ...f, cidade: e.target.value }))}
                />
              </Field>
            </div>
          </div>
          <Field label="Referência">
            <Textarea
              rows={2}
              placeholder="Ex: portão azul, fundos, sala 3"
              value={form.referencia}
              onChange={(e) => setForm((f) => ({ ...f, referencia: e.target.value }))}
            />
          </Field>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--muted)' }}>
            <input
              type="checkbox"
              checked={form.ativo}
              onChange={(e) => setForm((f) => ({ ...f, ativo: e.target.checked }))}
            />
            Local ativo (disponível para seleção)
          </label>
        </div>
      </Modal>

      {toast && <Toast {...toast} onClose={() => setToast(null)} />}
    </div>
  )
}
