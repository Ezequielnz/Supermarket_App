import { Search, ArrowRight, BarChart2, ListChecks, ShoppingBag, RefreshCw, ChevronRight } from 'lucide-react'
import Navbar from '../components/Navbar'
import styles from './LandingPage.module.css'

/* ── Demo data: same product across 3 supermarkets ── */
const COMPARE_ITEMS = [
  {
    id: 1,
    name: 'Leche entera 1L',
    emoji: '🥛',
    markets: [
      { name: 'Carrefour', price: 1300, best: false },
      { name: 'Vital', price: 1250, best: true },
      { name: 'Jaguar', price: 1400, best: false },
    ],
  },
  {
    id: 2,
    name: 'Huevos L x12',
    emoji: '🥚',
    markets: [
      { name: 'Carrefour', price: 800, best: false },
      { name: 'Vital', price: 700, best: true },
      { name: 'Jaguar', price: 850, best: false },
    ],
  },
  {
    id: 3,
    name: 'Pan de molde',
    emoji: '🍞',
    markets: [
      { name: 'Carrefour', price: 1100, best: false },
      { name: 'Vital', price: 1150, best: false },
      { name: 'Jaguar', price: 1000, best: true },
    ],
  },
]

/* ── Demo data: substitute comparison ── */
const SUBSTITUTES = [
  { name: 'Aceite de oliva extra virgen 1L', emoji: '🫒', price: 3500, sub: 'Aceite de girasol 1L', subEmoji: '🌻', subPrice: 2600 },
  { name: 'Salmón fresco 400g', emoji: '🐟', price: 9000, sub: 'Atún en conserva x3', subEmoji: '🐠', subPrice: 6000 },
]

/* ── How it works steps ── */
const STEPS = [
  { n: '01', icon: <ListChecks size={22} />, title: 'Arma tu lista', desc: 'Agrega los productos que necesitas comprar esta semana, como si fuera una lista de papel.' },
  { n: '02', icon: <Search size={22} />, title: 'Buscamos precios', desc: 'Comparamos automáticamente los precios de esa lista en los supermercados de tu zona.' },
  { n: '03', icon: <BarChart2 size={22} />, title: 'Elige dónde comprar', desc: 'Te mostramos en qué supermercado tu lista completa sale más barata, o dónde conviene ir por cada ítem.' },
  { n: '04', icon: <RefreshCw size={22} />, title: 'Compara sustitutos', desc: '¿Un producto está caro? Te sugerimos alternativas equivalentes y cuánto ahorrarías.' },
]

export default function LandingPage() {
  return (
    <main className={styles.main}>
      <Navbar />

      {/* ── Hero ── */}
      <section id="inicio" className={styles.hero}>
        <div className={styles.heroContent}>
          <div className={styles.badge}>
            <span className={styles.badgeDot} />
            Compara · Ahorra · Decide
          </div>
          <h1 className={styles.heroTitle}>
            Haz la compra<br />
            <span className={styles.heroAccent}>más barata.</span>
          </h1>
          <p className={styles.heroSubtitle}>
            Arma tu lista del supermercado, compara precios entre tiendas en segundos y descubre cuánto puedes ahorrar cada semana eligiendo mejor.
          </p>

          <div className={styles.heroCtas}>
            <a href="#auth" className={styles.ctaPrimary} onClick={e => { e.preventDefault(); window.location.hash = '#/auth' }}>
              Empezar gratis <ChevronRight size={18} />
            </a>
            <a href="#como-funciona" className={styles.ctaSecondary}>
              Cómo funciona
            </a>
          </div>

          <div className={styles.heroTrust}>
            <span>✓ Sin registro con tarjeta</span>
            <span>✓ 100% gratis</span>
            <span>✓ Múltiples supermercados</span>
          </div>
        </div>

        {/* ── Hero comparison card ── */}
        <div className={styles.heroVisual}>
          <div className={styles.compareCard}>
            <div className={styles.compareCardHead}>
              <span className={styles.compareCardIcon}>📋</span>
              <div>
                <p className={styles.compareCardLabel}>Tu lista esta semana</p>
                <p className={styles.compareCardTitle}>¿Dónde me conviene comprar?</p>
              </div>
            </div>
            <div className={styles.compareMarkets}>
              {[
                { name: 'Vital', total: '$104.500', savings: 'Más barato', best: true },
                { name: 'Jaguar', total: '$112.250', savings: '-$2.000', best: false },
                { name: 'Carrefour', total: '$106.000', savings: '-$1.500', best: false },
              ].map(m => (
                <div key={m.name} className={`${styles.marketRow} ${m.best ? styles.marketRowBest : ''}`}>
                  <span className={styles.marketName}>{m.name}</span>
                  <div className={styles.marketRight}>
                    <span className={styles.marketTotal}>{m.total}</span>
                    {m.best
                      ? <span className={styles.marketBestBadge}>Mejor precio</span>
                      : <span className={styles.marketDiff}>{m.savings}</span>
                    }
                  </div>
                </div>
              ))}
            </div>
            <p className={styles.compareCardFooter}>
              💡 Ahorras <strong>$7.750</strong> comprando en Vital esta semana
            </p>
          </div>

          <div className={styles.savingPill}>
            <span className={styles.savingPillIcon}>💰</span>
            <div>
              <p className={styles.savingTitle}>Ahorro mensual estimado</p>
              <p className={styles.savingAmount}>hasta $45.000 / mes</p>
            </div>
          </div>
        </div>
      </section>

      {/* ── Cómo funciona ── */}
      <section id="como-funciona" className={styles.howSection}>
        <div className={styles.howInner}>
          <div className={styles.sectionHead}>
            <p className="eyebrow">Así de sencillo</p>
            <h2 className={styles.sectionTitle}>
              Del papel a la app,<br className={styles.hideMobile} /> sin complicaciones.
            </h2>
            <p className={styles.sectionSubtitle}>
              Cuatro pasos para que nunca más pagues de más en el supermercado.
            </p>
          </div>

          <div className={styles.stepsGrid}>
            {STEPS.map(step => (
              <div key={step.n} className={styles.stepCard}>
                <div className={styles.stepTop}>
                  <span className={styles.stepNum}>{step.n}</span>
                  <span className={styles.stepIcon}>{step.icon}</span>
                </div>
                <h3 className={styles.stepTitle}>{step.title}</h3>
                <p className={styles.stepDesc}>{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Comparador demo ── */}
      <section id="comparador" className={styles.demoSection}>
        <div className={styles.demoInner}>
          <div className={styles.sectionHead}>
            <p className="eyebrow">Vista previa del comparador</p>
            <h2 className={styles.sectionTitle}>
              Precios en tiempo real,<br className={styles.hideMobile} /> producto a producto.
            </h2>
            <p className={styles.sectionSubtitle}>
              Cada ítem de tu lista muestra el precio en cada supermercado y resalta cuál es la mejor opción.
            </p>
          </div>

          <div className={styles.compareTable}>
            {/* Header */}
            <div className={styles.compareHeader}>
              <span className={styles.compareHeaderProduct}>Producto</span>
              {['Carrefour', 'Vital', 'Jaguar'].map(m => (
                <span key={m} className={styles.compareHeaderMarket}>{m}</span>
              ))}
            </div>
            {/* Rows */}
            {COMPARE_ITEMS.map(item => (
              <div key={item.id} className={styles.compareRow}>
                <span className={styles.compareProduct}>
                  <span className={styles.compareEmoji}>{item.emoji}</span>
                  {item.name}
                </span>
                {item.markets.map(m => (
                  <span
                    key={m.name}
                    className={`${styles.comparePrice} ${m.best ? styles.comparePriceBest : ''}`}
                  >
                    ${m.price.toFixed(2)}
                    {m.best && <span className={styles.bestDot} />}
                  </span>
                ))}
              </div>
            ))}
            {/* Footer totals */}
            <div className={`${styles.compareRow} ${styles.compareTotals}`}>
              <span className={styles.compareProduct} style={{ fontWeight: 700 }}>Total lista</span>
              {[
                { total: 3200, best: false },
                { total: 3100, best: true },
                { total: 3250, best: false },
              ].map((t, i) => (
                <span key={i} className={`${styles.comparePrice} ${t.best ? styles.comparePriceBest : ''}`}>
                  ${t.total.toFixed(2)}
                  {t.best && <span className={styles.bestDot} />}
                </span>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── Sustitutos ── */}
      <section id="sustitutos" className={styles.subSection}>
        <div className={styles.subInner}>
          <div className={styles.sectionHead}>
            <p className="eyebrow">Alternativas inteligentes</p>
            <h2 className={styles.sectionTitle}>
              ¿Está caro? Prueba<br className={styles.hideMobile} /> con el sustituto.
            </h2>
            <p className={styles.sectionSubtitle}>
              Si un producto supera tu presupuesto, te mostramos opciones equivalentes y cuánto ahorrarías al cambiar.
            </p>
          </div>

          <div className={styles.subGrid}>
            {SUBSTITUTES.map((s, i) => (
              <div key={i} className={styles.subCard}>
                <div className={styles.subOriginal}>
                  <span className={styles.subEmoji}>{s.emoji}</span>
                  <div className={styles.subInfo}>
                    <p className={styles.subLabel}>Original</p>
                    <p className={styles.subName}>{s.name}</p>
                    <p className={styles.subPrice}>${s.price.toFixed(2)}</p>
                  </div>
                </div>
                <div className={styles.subArrow}>
                  <ArrowRight size={20} />
                  <span className={styles.subSaving}>
                    Ahorras ${(s.price - s.subPrice).toFixed(2)}
                  </span>
                </div>
                <div className={`${styles.subOriginal} ${styles.subAlt}`}>
                  <span className={styles.subEmoji}>{s.subEmoji}</span>
                  <div className={styles.subInfo}>
                    <p className={styles.subLabel}>Sustituto</p>
                    <p className={styles.subName}>{s.sub}</p>
                    <p className={`${styles.subPrice} ${styles.subPriceSave}`}>${s.subPrice.toFixed(2)}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA final ── */}
      <section className={styles.ctaSection}>
        <div className={styles.ctaInner}>
          <ShoppingBag size={32} className={styles.ctaIcon} />
          <h2 className={styles.ctaTitle}>
            Empieza a ahorrar<br />desde hoy.
          </h2>
          <p className={styles.ctaText}>
            Crea tu cuenta gratis, arma tu primera lista y descubre cuánto puedes ahorrar esta semana.
          </p>
          <a
            href="#/auth"
            className={styles.ctaPrimaryLg}
            onClick={e => { e.preventDefault(); window.location.hash = '#/auth' }}
          >
            Crear cuenta gratis <ChevronRight size={20} />
          </a>
          <p className={styles.ctaNote}>Sin tarjeta de crédito · Cancela cuando quieras</p>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className={styles.footer}>
        <p className={styles.footerBrand}>
          FreshMart<span className={styles.logoDot}>.</span>
        </p>
        <p className={styles.footerText}>
          Tu comparador de supermercados · © 2026
        </p>
      </footer>
    </main>
  )
}
