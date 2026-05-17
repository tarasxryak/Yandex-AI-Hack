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
    const deleteWorkspace = useWorkspacesStore(state => state.deleteWorkspace);

    return (
        <>
            {workspaces.length > 0 ? (
                <ul className={styles.list}>
                    {workspaces.map(workspace => {
                        const isActive = workspace.id === activeWorkspaceId;

                        return (
                            <li className={styles.item} key={workspace.id}>
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
                                </button>
                                <span className={styles.chatCount}>
                                    {workspace.requests.length}
                                </span>
                                <button
                                    className={styles.deleteButton}
                                    type='button'
                                    onClick={() => deleteWorkspace(workspace.id)}
                                    aria-label={`Удалить ${workspace.title}`}
                                    title='Удалить воркспейс'>
                                    <svg
                                        className={styles.deleteIcon}
                                        viewBox='0 0 24 24'
                                        aria-hidden='true'>
                                        <path
                                            d='M6 6l12 12M18 6 6 18'
                                            fill='none'
                                            stroke='currentColor'
                                            strokeLinecap='round'
                                            strokeWidth='2.2'
                                        />
                                    </svg>
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
