import { useState } from 'react'
import { Plus, Trash2, ChevronRight, ArrowLeft } from 'lucide-react'

import { useLists } from '../../hooks/useLists'
import styles from './ListsPage.module.css'

export default function ListsPage() {
  const { lists, loading, error, createList, deleteList } = useLists()
  const [creating, setCreating] = useState(false)

  async function handleCreate() {
    setCreating(true)
    try {
      const list = await createList('Mi lista')
      window.location.hash = `#/app/lists/${list.id}`
    } finally {
      setCreating(false)
    }
  }

  async function handleDelete(e, id) {
    e.stopPropagation()
    if (!window.confirm('¿Eliminar esta lista?')) return
    await deleteList(id)
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <a href="#/app" className={styles.backLink}>
          <ArrowLeft size={16} /> Volver al panel
        </a>
        <h1 className={styles.title}>Mis listas</h1>
        <button className={styles.newBtn} onClick={handleCreate} disabled={creating}>
          <Plus size={16} /> Nueva lista
        </button>
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
