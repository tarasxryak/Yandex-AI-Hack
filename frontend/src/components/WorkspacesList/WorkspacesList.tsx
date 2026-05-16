import { useWorkspacesStore } from '../../stores/workspacesStore';
import styles from './WorkspacesList.module.css';

const WorkspacesList = () => {
    const workspaces = useWorkspacesStore(state => state.workspaces);
    const activeWorkspaceId = useWorkspacesStore(
        state => state.activeWorkspaceId,
    );
    const setActiveWorkspaceId = useWorkspacesStore(
        state => state.setActiveWorkspaceId,
    );

    return (
        <>
            {workspaces.length > 0 ? (
                <ul className={styles.list}>
                    {workspaces.map(workspace => {
                        const isActive = workspace.id === activeWorkspaceId;

                        return (
                            <li key={workspace.id}>
                                <button
                                    className={`${styles.workspaceButton} ${
                                        isActive ? styles.active : ''
                                    }`}
                                    type='button'
                                    onClick={() =>
                                        setActiveWorkspaceId(workspace.id)
                                    }>
                                    <span className={styles.workspaceName}>
                                        {workspace.title}
                                    </span>
                                    <span className={styles.chatCount}>
                                        {workspace.requests.length}
                                    </span>
                                </button>
                            </li>
                        );
                    })}
                </ul>
            ) : (
                <div className={styles.emptyState}>
                    <p>Пока нет рабочих пространств</p>
                </div>
            )}
        </>
    );
};

export default WorkspacesList;
