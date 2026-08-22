import { useState } from 'react'
import { Plus, Trash2, ChevronRight, ArrowLeft } from 'lucide-react'

import AppNav from '../../components/AppNav'
import { useLists } from '../../hooks/useLists'
import styles from './ListsPage.module.css'

export default function ListsPage() {
  const { lists, loading, error, createList, deleteList } = useLists()
  const [creating, setCreating] = useState(false)
  const [naming, setNaming] = useState(false)
  const [nameDraft, setNameDraft] = useState('')

  // Las listas quedan guardadas y el usuario vuelve a ellas, asi que tienen que
  // poder distinguirse. Antes todas se creaban con el literal 'Mi lista' y la
  // pantalla terminaba siendo una pila de listas homonimas.
  async function handleCreate(event) {
    event.preventDefault()
    setCreating(true)
    try {
      const list = await createList(nameDraft.trim() || 'Mi lista')
      window.location.hash = `#/app/lists/${list.id}`
    } finally {
      setCreating(false)
      setNaming(false)
      setNameDraft('')
    }
  }

  async function handleDelete(e, id) {
    e.stopPropagation()
    if (!window.confirm('¿Eliminar esta lista?')) return
    await deleteList(id)
  }

  return (
    <div className={styles.page}>
      <AppNav />
      <div className={styles.header}>
        <a href="#/app" className={styles.backLink}>
          <ArrowLeft size={16} /> Volver al panel
        </a>
        <h1 className={styles.title}>Mis listas</h1>
        {naming ? (
          <form className={styles.newForm} onSubmit={handleCreate}>
            <input
              className={styles.newInput}
              placeholder="Nombre de la lista"
              value={nameDraft}
              onChange={(e) => setNameDraft(e.target.value)}
              maxLength={120}
              aria-label="Nombre de la lista"
            />
            <button type="submit" className={styles.newBtn} disabled={creating}>
              {creating ? 'Creando…' : 'Crear'}
            </button>
            <button
              type="button"
              className={styles.cancelBtn}
              onClick={() => { setNaming(false); setNameDraft('') }}
            >
              Cancelar
            </button>
          </form>
        ) : (
          <button className={styles.newBtn} onClick={() => setNaming(true)} disabled={creating}>
            <Plus size={16} /> Nueva lista
          </button>
        )}
      </div>

      {error && <p className={styles.errorText}>{error}</p>}
      {loading && <p className={styles.muted}>Cargando…</p>}

      {!loading && lists.length === 0 && (
        <p className={styles.muted}>Todavía no tenés listas. Creá la primera para empezar a comparar precios.</p>
      )}

      <div className={styles.list}>
        {lists.map((list) => (
          <div
            key={list.id}
            className={styles.card}
            role="button"
            tabIndex={0}
            onClick={() => { window.location.hash = `#/app/lists/${list.id}` }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') window.location.hash = `#/app/lists/${list.id}`
            }}
          >
            <div>
              <p className={styles.cardName}>{list.name}</p>
              <p className={styles.cardMeta}>{list.items_count} producto{list.items_count === 1 ? '' : 's'}</p>
            </div>
            <div className={styles.cardActions}>
              <button
                className={styles.deleteBtn}
                onClick={(e) => handleDelete(e, list.id)}
                aria-label={`Eliminar ${list.name}`}
              >
                <Trash2 size={16} />
              </button>
              <ChevronRight size={18} />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
