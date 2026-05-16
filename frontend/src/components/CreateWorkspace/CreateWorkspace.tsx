import { useState, type FormEvent } from 'react';
import { getApiUrl } from '../../config/api';
import {
    useWorkspacesStore,
    type Workspace,
} from '../../stores/workspacesStore';
import styles from './CreateWorkspace.module.css';

type CreateWorkspaceResponse = {
    success: boolean;
    workspace?: {
        chat_id?: string;
        id?: string;
    };
    error?: string;
    introspection?: {
        message?: string;
        status?: string;
    };
};

const getWorkspaceTitle = (endpoint: string) => {
    try {
        return new URL(endpoint).hostname;
    } catch {
        return 'GraphQL workspace';
    }
};

const CreateWorkspace = () => {
    const saveWorkspace = useWorkspacesStore(state => state.saveWorkspace);

    const [endpoint, setEndpoint] = useState('');
    const [token, setToken] = useState('');
    const [isCreating, setIsCreating] = useState(false);
    const [createError, setCreateError] = useState('');

    const handleCreateWorkspace = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        setCreateError('');

        const trimmedEndpoint = endpoint.trim();
        const trimmedToken = token.trim();

        if (!trimmedEndpoint) {
            setCreateError('Укажите URL GraphQL API');
            return;
        }

        setIsCreating(true);

        try {
            const response = await fetch(getApiUrl('/create_workspace'), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    endpoint: trimmedEndpoint,
                    token: trimmedToken,
                }),
            });
            const result = (await response.json()) as CreateWorkspaceResponse;

            if (!response.ok || !result.success) {
                throw new Error(
                    result.error ||
                        result.introspection?.message ||
                        result.introspection?.status ||
                        'Не удалось создать workspace',
                );
            }

            const workspaceId =
                result.workspace?.chat_id || result.workspace?.id;

            if (!workspaceId) {
                throw new Error('Backend не вернул id workspace');
            }

            const workspace: Workspace = {
                id: workspaceId,
                title: getWorkspaceTitle(trimmedEndpoint),
                base_url: trimmedEndpoint,
                requests: [],
            };

            saveWorkspace(workspace);
            setEndpoint('');
            setToken('');
        } catch (error) {
            setCreateError(
                error instanceof Error
                    ? error.message
                    : 'Не удалось создать workspace',
            );
        } finally {
            setIsCreating(false);
        }
    };

    return (
        <section className={styles.welcome}>
            <div className={styles.welcomeContent}>
                <p className={styles.kicker}>GraphPilot</p>
                <h1 className={styles.welcomeTitle}>Подключите GraphQL API</h1>
                <p className={styles.welcomeText}>
                    Вставьте endpoint, и GraphPilot создаст воркспейс для
                    будущих запросов.
                </p>

                <form
                    className={styles.createWorkspaceForm}
                    onSubmit={handleCreateWorkspace}>
                    <label className={styles.field}>
                        <span className={styles.fieldLabel}>
                            URL GraphQL API
                        </span>
                        <input
                            className={styles.input}
                            type='url'
                            value={endpoint}
                            onChange={event => setEndpoint(event.target.value)}
                            placeholder='https://api.example.com/graphql'
                            required
                        />
                    </label>

                    <label className={styles.field}>
                        <span className={styles.fieldLabel}>Token</span>
                        <input
                            className={styles.input}
                            type='password'
                            value={token}
                            onChange={event => setToken(event.target.value)}
                            placeholder='Опционально'
                        />
                    </label>

                    <p
                        className={styles.formError}
                        aria-live='polite'
                        data-visible={Boolean(createError)}>
                        {createError || ' '}
                    </p>

                    <button
                        className={styles.submitButton}
                        type='submit'
                        disabled={isCreating}>
                        {isCreating
                            ? 'Создаем workspace...'
                            : 'Создать workspace'}
                    </button>
                </form>
            </div>
        </section>
    );
};

export default CreateWorkspace;
