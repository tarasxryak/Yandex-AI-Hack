import { useWorkspacesStore } from '../../stores/workspacesStore';
import RequestCard from '../RequestCard/RequestCard';
import styles from './RequestsList.module.css';

const RequestsList = () => {
    const requests = useWorkspacesStore(
        state =>
            state.workspaces.find(
                workspace => workspace.id == state.activeWorkspaceId,
            )?.requests,
    );
    const activeRequestId = useWorkspacesStore(state => state.activeRequestId);

    return (
        <div className={styles.requestsList}>
            {requests?.map(request => (
                <RequestCard
                    key={request.id}
                    request={request.message}
                    time={request.time}
                    isActive={request.id == activeRequestId}
                />
            ))}
        </div>
    );
};

export default RequestsList;
