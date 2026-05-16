import CreateWorkspace from './components/CreateWorkspace/CreateWorkspace'
import MessageComposer from './components/MessageComposer/MessageComposer'
import RequestDetails from './components/RequestDetails/RequestDetails'
import WorkspacesList from './components/WorkspacesList/WorkspacesList'
import logo from './assets/favicon.png'
import RequestsList from './components/RequestList/RequestsList'
import { useWorkspacesStore } from './stores/workspacesStore'
import styles from './styles/App.module.css'

function App() {
    const activeWorkspaceId = useWorkspacesStore(
        (state) => state.activeWorkspaceId,
    )
    const setActiveWorkspaceId = useWorkspacesStore(
        (state) => state.setActiveWorkspaceId,
    )

    const handleAddWorkspace = () => {
        setActiveWorkspaceId(null)
    }

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
                {activeWorkspaceId ? (
                    <div className={styles.workspaceContent}>
                        <RequestsList />
                        <MessageComposer />
                    </div>
                ) : (
                    <CreateWorkspace />
                )}
            </main>

            <aside
                className={`${styles.panel} ${styles.rightPanel}`}
                aria-label="Details"
            >
                <RequestDetails />
            </aside>
        </div>
    )
}

export default App
