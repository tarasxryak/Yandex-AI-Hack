import { Group, Panel, Separator } from 'react-resizable-panels';
import CreateWorkspace from './components/CreateWorkspace/CreateWorkspace';
import MessageComposer from './components/MessageComposer/MessageComposer';
import RequestDetails from './components/RequestDetails/RequestDetails';
import WorkspacesList from './components/WorkspacesList/WorkspacesList';
import logo from './assets/favicon.png';
import RequestsList from './components/RequestList/RequestsList';
import { useWorkspacesStore } from './stores/workspacesStore';
import styles from './styles/App.module.css';

function App() {
    const activeWorkspaceId = useWorkspacesStore(
        state => state.activeWorkspaceId,
    );
    const setActiveWorkspaceId = useWorkspacesStore(
        state => state.setActiveWorkspaceId,
    );

    const handleAddWorkspace = () => {
        setActiveWorkspaceId(null);
    };

    return (
        <Group
            className={styles.appShell}
            orientation='horizontal'
            defaultLayout={{ left: 18, center: 58, right: 24 }}>
            <Panel id='left' defaultSize={18} minSize='220px' maxSize='360px'>
                <aside
                    className={`${styles.panel} ${styles.leftPanel}`}
                    aria-label='Workspace navigation'>
                    <header className={styles.brand}>
                        <img
                            src={logo}
                            alt='GraphPilot logo'
                            className={styles.brandLogo}
                        />
                        <span className={styles.brandName}>GraphPilot</span>
                    </header>

                    <WorkspacesList />

                    <button
                        className={styles.addWorkspaceButton}
                        type='button'
                        onClick={handleAddWorkspace}>
                        Добавить воркспейс
                    </button>
                </aside>
            </Panel>

            <Separator className={styles.resizeHandle} />

            <Panel id='center' defaultSize={58} minSize='360px'>
                <main
                    className={`${styles.panel} ${styles.mainPanel}`}
                    aria-label='Workspace content'>
                    {activeWorkspaceId ? (
                        <div className={styles.workspaceContent}>
                            <RequestsList />
                            <MessageComposer />
                        </div>
                    ) : (
                        <CreateWorkspace />
                    )}
                </main>
            </Panel>

            <Separator className={styles.resizeHandle} />

            <Panel id='right' defaultSize={24} minSize='260px' maxSize='50%'>
                <aside
                    className={`${styles.panel} ${styles.rightPanel}`}
                    aria-label='Details'>
                    <RequestDetails />
                </aside>
            </Panel>
        </Group>
    );
}

export default App;
