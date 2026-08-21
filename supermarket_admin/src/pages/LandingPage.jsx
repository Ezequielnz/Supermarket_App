import { Store, ClipboardList, TrendingUp, ArrowRight } from 'lucide-react'

import styles from './LandingPage.module.css'

const BENEFITS = [
  {
    icon: Store,
    title: 'Sumá todas tus sucursales',
    text: 'Cargá una vez los datos de tu cadena y agregá cuantas sucursales quieras, cada una con su dirección y sus horarios.',
  },
  {
    icon: ClipboardList,
    title: 'Recibí pedidos armados',
    text: 'El cliente arma la lista en la app y elige tu supermercado. Vos recibís el pedido con los productos y la hora de retiro.',
  },
  {
    icon: TrendingUp,
    title: 'Mostrá tus precios donde se comparan',
    text: 'Tus precios aparecen en el comparador junto a los del resto. Si sos más barato, se nota.',
  },
]

const STEPS = [
  { n: '1', title: 'Registrás tu cadena', text: 'Datos fiscales, tu primera sucursal y los horarios de atención.' },
  { n: '2', title: 'Verificamos los datos', text: 'Revisamos la solicitud, normalmente en menos de 48 horas hábiles.' },
  { n: '3', title: 'Empezás a recibir pedidos', text: 'Tu supermercado aparece en la app y los clientes pueden elegirte.' },
]

export default function LandingPage() {
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <a href="#/" className={styles.brand}>
          <span className={styles.brandMark} aria-hidden="true">✳</span>
          FreshMart
          <span className={styles.brandSub}>para supermercados</span>
        </a>
        <nav className={styles.nav} aria-label="Accesos">
          <a href="#/auth" className={styles.navLink}>Iniciar sesión</a>
          <a href="#/register" className={styles.navCta}>Registrar mi supermercado</a>
        </nav>
      </header>

      <main>
        <section className={styles.hero}>
          <div className="container">
            <p className="eyebrow">Panel de supermercados</p>
            <h1 className={styles.heroTitle}>
              Tus precios, donde<br />los clientes deciden.
            </h1>
            <p className={styles.heroText}>
              Miles de personas arman su lista de compras en FreshMart y comparan dónde les conviene
              comprar. Sumá tu supermercado y recibí esos pedidos listos para preparar.
            </p>
            <a href="#/register" className={styles.heroCta}>
              Registrar mi supermercado
              <ArrowRight size={18} aria-hidden="true" />
            </a>
            <p className={styles.heroNote}>Gratis. Sin costo de alta ni permanencia.</p>
          </div>
        </section>

        <section className={styles.section}>
          <div className="container">
            <div className={styles.grid}>
              {BENEFITS.map(({ icon: Icon, title, text }) => (
                <article key={title} className={styles.card}>
                  <span className={styles.cardIcon} aria-hidden="true"><Icon size={20} /></span>
                  <h2 className={styles.cardTitle}>{title}</h2>
                  <p className={styles.cardText}>{text}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className={`${styles.section} ${styles.sectionMuted}`}>
          <div className="container">
            <h2 className={styles.sectionTitle}>Cómo funciona</h2>
            <ol className={styles.steps}>
              {STEPS.map((step) => (
                <li key={step.n} className={styles.step}>
                  <span className={styles.stepNumber} aria-hidden="true">{step.n}</span>
                  <div>
                    <h3 className={styles.stepTitle}>{step.title}</h3>
                    <p className={styles.cardText}>{step.text}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>
      </main>

      <footer className={styles.footer}>
        <div className="container">
          <p>© 2026 FreshMart · Panel de supermercados</p>
        </div>
      </footer>
    </div>
  )
}
