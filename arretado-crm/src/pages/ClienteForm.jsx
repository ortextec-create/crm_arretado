import { useState, useEffect } from 'react'
import { Modal, Btn, Field, Input, Select, Textarea } from '../components/ui'
import { tagsApi } from '../api/services'

const EMPTY = {
  nome: '', cpf: '', email: '', telefone_principal: '',
  telefone_secundario: '', data_nascimento: '', sexo: '',
  status: 'ativo', observacoes: '', tag_ids: [],
}

export default function ClienteForm({ open, onClose, onSave, initial = null }) {
  const [form, setForm] = useState(EMPTY)
  const [tags, setTags] = useState([])
  const [errors, setErrors] = useState({})
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    tagsApi.list().then((r) => setTags(r.data.results ?? r.data)).catch(() => {})
  }, [])

  useEffect(() => {
    if (open) {
      setErrors({})
      setForm(
        initial
          ? {
              nome: initial.nome || '',
              cpf: initial.cpf || '',
              email: initial.email || '',
              telefone_principal: initial.telefone_principal || '',
              telefone_secundario: initial.telefone_secundario || '',
              data_nascimento: initial.data_nascimento || '',
              sexo: initial.sexo || '',
              status: initial.status || 'ativo',
              observacoes: initial.observacoes || '',
              tag_ids: (initial.tags || []).map((t) => t.id),
            }
          : { ...EMPTY }
      )
    }
  }, [open, initial])

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  const toggleTag = (id) =>
    set('tag_ids', form.tag_ids.includes(id)
      ? form.tag_ids.filter((t) => t !== id)
      : [...form.tag_ids, id]
    )

  const validate = () => {
    const e = {}
    if (!form.nome.trim()) e.nome = 'Nome é obrigatório'
    if (!form.telefone_principal.trim()) e.telefone_principal = 'Telefone é obrigatório'
    if (form.cpf && !/^\d{3}\.\d{3}\.\d{3}-\d{2}$/.test(form.cpf)) e.cpf = 'Formato: 000.000.000-00'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const handleSubmit = async () => {
    if (!validate()) return
    setLoading(true)
    try {
      await onSave(form)
      onClose()
    } catch (err) {
      const data = err?.response?.data
      if (data) {
        const mapped = {}
        Object.keys(data).forEach((k) => { mapped[k] = Array.isArray(data[k]) ? data[k][0] : data[k] })
        setErrors(mapped)
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={initial ? 'Editar Cliente' : 'Novo Cliente'}
      width={580}
      footer={
        <>
          <Btn variant="ghost" onClick={onClose} disabled={loading}>Cancelar</Btn>
          <Btn loading={loading} onClick={handleSubmit} icon={loading ? undefined : 'check'}>
            {initial ? 'Salvar Alterações' : 'Cadastrar Cliente'}
          </Btn>
        </>
      }
    >
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div style={{ gridColumn: '1 / -1' }}>
          <Field label="Nome Completo *" error={errors.nome}>
            <Input placeholder="Nome do cliente" value={form.nome} onChange={(e) => set('nome', e.target.value)} />
          </Field>
        </div>

        <Field label="CPF" error={errors.cpf}>
          <Input placeholder="000.000.000-00" value={form.cpf} onChange={(e) => set('cpf', e.target.value)} />
        </Field>

        <Field label="Data de Nascimento">
          <Input type="date" value={form.data_nascimento} onChange={(e) => set('data_nascimento', e.target.value)} />
        </Field>

        <Field label="Telefone Principal *" error={errors.telefone_principal}>
          <Input placeholder="(86) 99999-0000" value={form.telefone_principal} onChange={(e) => set('telefone_principal', e.target.value)} />
        </Field>

        <Field label="Telefone Secundário">
          <Input placeholder="(86) 99999-0000" value={form.telefone_secundario} onChange={(e) => set('telefone_secundario', e.target.value)} />
        </Field>

        <Field label="E-mail" error={errors.email}>
          <Input type="email" placeholder="cliente@email.com" value={form.email} onChange={(e) => set('email', e.target.value)} />
        </Field>

        <Field label="Sexo">
          <Select value={form.sexo} onChange={(e) => set('sexo', e.target.value)}>
            <option value="">Selecionar</option>
            <option value="M">Masculino</option>
            <option value="F">Feminino</option>
            <option value="O">Outro</option>
            <option value="N">Prefiro não informar</option>
          </Select>
        </Field>

        <Field label="Status">
          <Select value={form.status} onChange={(e) => set('status', e.target.value)}>
            <option value="ativo">Ativo</option>
            <option value="inativo">Inativo</option>
            <option value="bloqueado">Bloqueado</option>
          </Select>
        </Field>

        <div style={{ gridColumn: '1 / -1' }}>
          <Field label="Observações">
            <Textarea placeholder="Notas sobre o cliente..." value={form.observacoes} onChange={(e) => set('observacoes', e.target.value)} />
          </Field>
        </div>

        {tags.length > 0 && (
          <div style={{ gridColumn: '1 / -1' }}>
            <Field label="Tags">
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 2 }}>
                {tags.map((t) => {
                  const active = form.tag_ids.includes(t.id)
                  return (
                    <button
                      key={t.id}
                      type="button"
                      onClick={() => toggleTag(t.id)}
                      style={{
                        padding: '4px 12px',
                        borderRadius: 20, fontSize: 11, cursor: 'pointer',
                        background: active ? t.cor + '28' : 'transparent',
                        color: active ? t.cor : 'var(--muted)',
                        border: `0.5px solid ${active ? t.cor + '60' : 'var(--border)'}`,
                        transition: 'all 0.15s',
                        fontFamily: 'inherit',
                      }}
                    >
                      {t.nome}
                    </button>
                  )
                })}
              </div>
            </Field>
          </div>
        )}
      </div>
    </Modal>
  )
}
