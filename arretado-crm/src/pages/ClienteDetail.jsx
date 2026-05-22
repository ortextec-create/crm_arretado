import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { clientesApi } from '../api/services'
import Topbar from '../components/layout/Topbar'
import { Btn, Avatar, StatusBadge, IntBadge, Spinner, Toast, Modal, Field, Input, Select } from '../components/ui'
import ClienteForm from './ClienteForm'
import styles from './ClienteDetail.module.css'

const TIPO_LABELS = { entrega: 'Entrega', cobranca: 'Cobrança', residencial: 'Residencial', comercial: 'Comercial' }
const SEXO_LABELS = { M: 'Masculino', F: 'Feminino', O: 'Outro', N: 'Prefiro não informar' }

const EMPTY_ADDR = { tipo: 'entrega', apelido: '', cep: '', logradouro: '', numero: '', complemento: '', bairro: '', cidade: '', estado: '', principal: false }

export default function ClienteDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [cliente, setCliente] = useState(null)
  const [loading, setLoading] = useState(true)
  const [showEdit, setShowEdit] = useState(false)
  const [showAddrForm, setShowAddrForm] = useState(false)
  const [editAddr, setEditAddr] = useState(null)
  const [addrForm, setAddrForm] = useState(EMPTY_ADDR)
  const [savingAddr, setSavingAddr] = useState(false)
  const [toast, setToast] = useState(null)

  const load = () => {
    setLoading(true)
    clientesApi.get(id)
      .then((r) => setCliente(r.data))
      .catch(() => navigate('/clientes'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [id])

  const handleSaveCliente = async (form) => {
    await clientesApi.update(id, form)
    setToast({ message: 'Dados atualizados com sucesso!', type: 'success' })
    load()
  }

  const handleStatusAction = async (action) => {
    try {
      if (action === 'ativar') await clientesApi.ativar(id)
      else await clientesApi.bloquear(id)
      setToast({ message: `Status alterado com sucesso.`, type: 'success' })
      load()
    } catch {
      setToast({ message: 'Erro ao alterar status.', type: 'error' })
    }
  }

  const openAddrForm = (addr = null) => {
    setEditAddr(addr)
    setAddrForm(addr ? { ...addr } : { ...EMPTY_ADDR })
    setShowAddrForm(true)
  }

  const saveAddr = async () => {
    setSavingAddr(true)
    try {
      if (editAddr) {
        await clientesApi.updateEndereco(id, editAddr.id, addrForm)
      } else {
        await clientesApi.addEndereco(id, addrForm)
      }
      setShowAddrForm(false)
      setToast({ message: 'Endereço salvo.', type: 'success' })
      load()
    } catch {
      setToast({ message: 'Erro ao salvar endereço.', type: 'error' })
    } finally {
      setSavingAddr(false)
    }
  }

  const removeAddr = async (eid) => {
    if (!confirm('Remover este endereço?')) return
    try {
      await clientesApi.removeEndereco(id, eid)
      setToast({ message: 'Endereço removido.', type: 'success' })
      load()
    } catch {
      setToast({ message: 'Erro ao remover.', type: 'error' })
    }
  }

  if (loading) return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <Topbar title="Cliente" />
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Spinner size={28} />
      </div>
    </div>
  )

  if (!cliente) return null

  const setA = (k, v) => setAddrForm((f) => ({ ...f, [k]: v }))

  return (
    <div className={styles.page}>
      <Topbar
        title="Perfil do Cliente"
        actions={
          <>
            <Btn variant="ghost" icon="arrow-left" size="sm" onClick={() => navigate('/clientes')}>
              Voltar
            </Btn>
            <Btn variant="ghost" icon="edit" size="sm" onClick={() => setShowEdit(true)}>Editar</Btn>
            {cliente.status === 'bloqueado'
              ? <Btn icon="lock-open" size="sm" onClick={() => handleStatusAction('ativar')}>Ativar</Btn>
              : <Btn variant="danger-btn" icon="lock" size="sm" onClick={() => handleStatusAction('bloquear')}>Bloquear</Btn>
            }
          </>
        }
      />

      <div className={styles.content}>
        <div className={styles.grid}>
          {/* LEFT — main info */}
          <div>
            {/* Header card */}
            <div className={styles.headerCard}>
              <Avatar name={cliente.nome} size="xl" />
              <div className={styles.headerInfo}>
                <h2 className="serif">{cliente.nome}</h2>
                <div className={styles.headerMeta}>
                  <StatusBadge status={cliente.status} />
                  {cliente.tem_integracao_ifood && <IntBadge type="ifood" />}
                  {cliente.tem_integracao_anotaai && <IntBadge type="anotaai" />}
                </div>
                {(cliente.tags || []).length > 0 && (
                  <div className={styles.headerTags}>
                    {cliente.tags.map((t) => (
                      <span key={t.id} style={{ padding: '2px 10px', fontSize: 11, borderRadius: 20, border: `0.5px solid ${t.cor}50`, color: t.cor }}>
                        {t.nome}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Data grid */}
            <div className={styles.dataCard}>
              <div className={styles.cardTitle}>Dados Pessoais</div>
              <div className={styles.dataGrid}>
                <DataRow icon="phone" label="Telefone Principal" value={cliente.telefone_principal} />
                <DataRow icon="phone-call" label="Telefone Secundário" value={cliente.telefone_secundario || '—'} />
                <DataRow icon="mail" label="E-mail" value={cliente.email || '—'} />
                <DataRow icon="id" label="CPF" value={cliente.cpf || '—'} />
                <DataRow icon="cake" label="Nascimento" value={cliente.data_nascimento || '—'} />
                <DataRow icon="gender-bigender" label="Sexo" value={SEXO_LABELS[cliente.sexo] || '—'} />
              </div>
              {cliente.observacoes && (
                <div className={styles.obs}>
                  <i className="ti ti-notes" />
                  <span>{cliente.observacoes}</span>
                </div>
              )}
            </div>

            {/* Integrations */}
            <div className={styles.dataCard}>
              <div className={styles.cardTitle}>Integrações Externas</div>
              <div className={styles.dataGrid}>
                <DataRow icon="brand-firebase" label="ID iFood" value={cliente.ifood_customer_id || 'Não vinculado'} />
                <DataRow icon="device-mobile" label="ID Anota AI" value={cliente.anotaai_customer_id || 'Não vinculado'} />
              </div>
            </div>
          </div>

          {/* RIGHT — addresses */}
          <div>
            <div className={styles.addrHeader}>
              <h3 className="serif">Endereços</h3>
              <Btn variant="ghost" icon="plus" size="sm" onClick={() => openAddrForm()}>Adicionar</Btn>
            </div>

            {(cliente.enderecos || []).length === 0 && (
              <div className={styles.emptyAddr}>
                <i className="ti ti-map-pin-off" />
                <p>Nenhum endereço cadastrado.</p>
                <Btn size="sm" icon="plus" onClick={() => openAddrForm()}>Adicionar Endereço</Btn>
              </div>
            )}

            {(cliente.enderecos || []).map((end) => (
              <div key={end.id} className={styles.addrCard}>
                <div className={styles.addrTop}>
                  <span className={styles.addrTipo}>{TIPO_LABELS[end.tipo] || end.tipo}</span>
                  {end.apelido && <span className={styles.addrApelido}>{end.apelido}</span>}
                  {end.principal && <span className={styles.addrPrincipal}><i className="ti ti-star-filled" /> Principal</span>}
                  <div style={{ marginLeft: 'auto', display: 'flex', gap: 5 }}>
                    <button className={styles.addrBtn} onClick={() => openAddrForm(end)}><i className="ti ti-edit" /></button>
                    <button className={`${styles.addrBtn} ${styles.addrBtnDanger}`} onClick={() => removeAddr(end.id)}><i className="ti ti-trash" /></button>
                  </div>
                </div>
                <p className={styles.addrText}>{end.logradouro}, {end.numero}{end.complemento ? `, ${end.complemento}` : ''}</p>
                <p className={styles.addrSub}>{end.bairro} — {end.cidade}/{end.estado} — CEP {end.cep}</p>
              </div>
            ))}

            {/* Audit */}
            <div className={styles.dataCard} style={{ marginTop: 16 }}>
              <div className={styles.cardTitle}>Auditoria</div>
              <div className={styles.dataGrid}>
                <DataRow icon="calendar-plus" label="Cadastrado em" value={new Date(cliente.criado_em).toLocaleString('pt-BR')} />
                <DataRow icon="calendar-event" label="Atualizado em" value={new Date(cliente.atualizado_em).toLocaleString('pt-BR')} />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Edit modal */}
      <ClienteForm
        open={showEdit}
        onClose={() => setShowEdit(false)}
        onSave={handleSaveCliente}
        initial={cliente}
      />

      {/* Address form modal */}
      <Modal
        open={showAddrForm}
        onClose={() => setShowAddrForm(false)}
        title={editAddr ? 'Editar Endereço' : 'Novo Endereço'}
        width={520}
        footer={
          <>
            <Btn variant="ghost" onClick={() => setShowAddrForm(false)}>Cancelar</Btn>
            <Btn loading={savingAddr} icon="check" onClick={saveAddr}>Salvar Endereço</Btn>
          </>
        }
      >
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          <Field label="Tipo">
            <Select value={addrForm.tipo} onChange={(e) => setA('tipo', e.target.value)}>
              <option value="entrega">Entrega</option>
              <option value="cobranca">Cobrança</option>
              <option value="residencial">Residencial</option>
              <option value="comercial">Comercial</option>
            </Select>
          </Field>
          <Field label="Apelido (ex: Casa, Trabalho)">
            <Input placeholder="Casa" value={addrForm.apelido} onChange={(e) => setA('apelido', e.target.value)} />
          </Field>
          <Field label="CEP *">
            <Input placeholder="00000-000" value={addrForm.cep} onChange={(e) => setA('cep', e.target.value)} />
          </Field>
          <div style={{ gridColumn: '1 / -1' }}>
            <Field label="Logradouro *">
              <Input placeholder="Rua, Avenida..." value={addrForm.logradouro} onChange={(e) => setA('logradouro', e.target.value)} />
            </Field>
          </div>
          <Field label="Número *">
            <Input placeholder="123" value={addrForm.numero} onChange={(e) => setA('numero', e.target.value)} />
          </Field>
          <Field label="Complemento">
            <Input placeholder="Apto, Bloco..." value={addrForm.complemento} onChange={(e) => setA('complemento', e.target.value)} />
          </Field>
          <Field label="Bairro *">
            <Input placeholder="Bairro" value={addrForm.bairro} onChange={(e) => setA('bairro', e.target.value)} />
          </Field>
          <Field label="Cidade *">
            <Input placeholder="Teresina" value={addrForm.cidade} onChange={(e) => setA('cidade', e.target.value)} />
          </Field>
          <Field label="Estado *">
            <Input placeholder="PI" maxLength={2} value={addrForm.estado} onChange={(e) => setA('estado', e.target.value.toUpperCase())} />
          </Field>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, paddingTop: 20 }}>
            <input
              type="checkbox" id="principal"
              checked={addrForm.principal}
              onChange={(e) => setA('principal', e.target.checked)}
              style={{ accentColor: 'var(--caramelo)', width: 14, height: 14 }}
            />
            <label htmlFor="principal" style={{ fontSize: 13, color: 'var(--muted)', cursor: 'pointer' }}>
              Endereço principal
            </label>
          </div>
        </div>
      </Modal>

      {toast && <Toast {...toast} onClose={() => setToast(null)} />}
    </div>
  )
}

function DataRow({ icon, label, value }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '9px 0', borderBottom: '0.5px solid rgba(200,134,10,0.07)' }}>
      <i className={`ti ti-${icon}`} style={{ fontSize: 15, color: 'var(--muted)', marginTop: 1, flexShrink: 0 }} />
      <span style={{ fontSize: 11, color: 'var(--muted)', width: 140, flexShrink: 0 }}>{label}</span>
      <span style={{ fontSize: 13, color: 'var(--bege)' }}>{value}</span>
    </div>
  )
}
