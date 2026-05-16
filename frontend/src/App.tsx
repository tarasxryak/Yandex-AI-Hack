import WorkspacesList from './components/WorkspacesList/WorkspacesList'
import logo from './assets/favicon.png'
import RequestsList from './components/RequestList/RequestsList'
import styles from './styles/App.module.css'

function App() {
    const handleAddWorkspace = () => undefined

    return (
        <div className={styles.appShell}>
            <aside
                className={`${styles.panel} ${styles.leftPanel}`}
                aria-label="Workspace navigation"
            >
                <header className={styles.brand}>
                    <img
                        src={logo}
                        alt="GraphPilot logo"
                        className={styles.brandLogo}
                    />
                    <span className={styles.brandName}>GraphPilot</span>
                </header>

                <WorkspacesList />

                <button
                    className={styles.addWorkspaceButton}
                    type="button"
                    onClick={handleAddWorkspace}
                >
                    Добавить воркспейс
                </button>
            </aside>

            <main
                className={`${styles.panel} ${styles.mainPanel}`}
                aria-label="Workspace content"
            >
                <RequestsList />
            </main>

            <aside
                className={`${styles.panel} ${styles.rightPanel}`}
                aria-label="Details"
            />
        </div>
    )
}

export default App
