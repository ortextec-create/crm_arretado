import { useEffect, useState } from 'react'
import { taxasEntregaApi, configEntregaApi } from '../api/services'
import Topbar from '../components/layout/Topbar'
import { Btn, Spinner, Empty, Toast, Modal, Field, Input } from '../components/ui'
import styles from './TaxasEntrega.module.css'

export default function TaxasEntrega() {
  const [taxas, setTaxas] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editTaxa, setEditTaxa] = useState(null)
  const [form, setForm] = useState({ bairro: '', taxa: '', ativo: true })
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState(null)

  const [fretePadrao, setFretePadrao] = useState('0')
  const [savingFrete, setSavingFrete] = useState(false)

  const load = () => {
    setLoading(true)
    taxasEntregaApi.list()
      .then((r) => setTaxas(r.data.results ?? r.data))
      .catch(() => setTaxas([]))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
    configEntregaApi.get().then(r => setFretePadrao(String(r.data.frete_padrao))).catch(() => {})
  }, [])

  const salvarFretePadrao = async () => {
    setSavingFrete(true)
    try {
      const { data } = await configEntregaApi.update({ frete_padrao: Number(fretePadrao || 0) })
      setFretePadrao(String(data.frete_padrao))
      setToast({ message: 'Frete padrão atualizado!', type: 'success' })
    } catch {
      setToast({ message: 'Erro ao salvar frete padrão.', type: 'error' })
    } finally {
      setSavingFrete(false)
    }
  }

  const open = (t = null) => {
    setEditTaxa(t)
    setForm(t ? { bairro: t.bairro, taxa: t.taxa, ativo: t.ativo } : { bairro: '', taxa: '', ativo: true })
    setShowForm(true)
  }

  const save = async () => {
    if (!form.bairro.trim()) return
    setSaving(true)
    try {
      const payload = { ...form, taxa: Number(form.taxa || 0) }
      if (editTaxa) await taxasEntregaApi.update(editTaxa.id, payload)
      else await taxasEntregaApi.create(payload)
      setToast({ message: editTaxa ? 'Taxa atualizada!' : 'Taxa criada!', type: 'success' })
      setShowForm(false)
      load()
    } catch {
      setToast({ message: 'Erro ao salvar taxa.', type: 'error' })
    } finally {
      setSaving(false)
    }
  }

  const remove = async (id) => {
    if (!confirm('Remover esta taxa de entrega?')) return
    try {
      await taxasEntregaApi.remove(id)
      setToast({ message: 'Taxa removida.', type: 'success' })
      load()
    } catch {
      setToast({ message: 'Erro ao remover.', type: 'error' })
    }
  }

  const toggleAtivo = async (t) => {
    try {
      await taxasEntregaApi.update(t.id, { ativo: !t.ativo })
      load()
    } catch {
      setToast({ message: 'Erro ao atualizar.', type: 'error' })
    }
  }

  return (
    <div className={styles.page}>
      <Topbar
        title="Taxas de Entrega por Bairro"
        actions={<Btn icon="plus" onClick={() => open()}>Novo Bairro</Btn>}
      />

      <div className={styles.content}>
        <div className={styles.fretePadraoCard}>
          <div>
            <span className={styles.fretePadraoLabel}>Frete padrão</span>
            <p className={styles.fretePadraoHint}>
              Valor usado quando a entrega for por bairro, mas nenhum bairro cadastrado for selecionado.
            </p>
          </div>
          <div className={styles.fretePadraoForm}>
            <span>R$</span>
            <input
              type="number" min="0" step="0.01"
              value={fretePadrao}
              onChange={e => setFretePadrao(e.target.value)}
            />
            <Btn loading={savingFrete} onClick={salvarFretePadrao}>Salvar</Btn>
          </div>
        </div>

        {loading ? (
          <div className={styles.center}><Spinner size={26} /></div>
        ) : taxas.length === 0 ? (
          <Empty icon="map-pin" message="Nenhuma taxa de entrega cadastrada ainda." />
        ) : (
          <div className={styles.grid}>
            {taxas.map((t) => (
              <div key={t.id} className={`${styles.card} ${!t.ativo ? styles.cardInativo : ''}`}>
                <div className={styles.info}>
                  <span className={styles.bairro}>{t.bairro}</span>
                  <span className={styles.taxa}>R$ {Number(t.taxa).toFixed(2)}</span>
                </div>
                <div className={styles.actions}>
                  <button
                    className={`${styles.pill} ${t.ativo ? styles.pillAtivo : styles.pillInativo}`}
                    onClick={() => toggleAtivo(t)}
                    title="Clique para alternar"
                  >
                    {t.ativo ? 'Ativo' : 'Inativo'}
                  </button>
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
        title={editTaxa ? 'Editar Taxa de Entrega' : 'Novo Bairro'}
        width={380}
        footer={
          <>
            <Btn variant="ghost" onClick={() => setShowForm(false)}>Cancelar</Btn>
            <Btn loading={saving} icon="check" onClick={save}>
              {editTaxa ? 'Salvar' : 'Criar'}
            </Btn>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          <Field label="Bairro *">
            <Input
              placeholder="Ex: Centro, Ininga, São Cristóvão..."
              value={form.bairro}
              onChange={(e) => setForm((f) => ({ ...f, bairro: e.target.value }))}
              onKeyDown={(e) => { if (e.key === 'Enter') save() }}
            />
          </Field>
          <Field label="Taxa de entrega (R$) *">
            <Input
              type="number"
              min="0"
              step="0.01"
              placeholder="0,00"
              value={form.taxa}
              onChange={(e) => setForm((f) => ({ ...f, taxa: e.target.value }))}
              onKeyDown={(e) => { if (e.key === 'Enter') save() }}
            />
          </Field>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--muted)' }}>
            <input
              type="checkbox"
              checked={form.ativo}
              onChange={(e) => setForm((f) => ({ ...f, ativo: e.target.checked }))}
            />
            Bairro ativo (disponível para seleção)
          </label>
        </div>
      </Modal>

      {toast && <Toast {...toast} onClose={() => setToast(null)} />}
    </div>
  )
}
