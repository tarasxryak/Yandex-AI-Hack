import { useState, type FormEvent } from 'react';
import { getApiUrl } from '../../config/api';
import { useWorkspacesStore } from '../../stores/workspacesStore';
import styles from './MessageComposer.module.css';

type QueryResponse = {
    success: boolean;
    error?: string;
};

const getRequestTime = () =>
    new Intl.DateTimeFormat('ru-RU', {
        hour: '2-digit',
        minute: '2-digit',
    }).format(new Date());

const MessageComposer = () => {
    const activeWorkspaceId = useWorkspacesStore(
        state => state.activeWorkspaceId,
    );
    const addRequest = useWorkspacesStore(state => state.addRequest);

    const [message, setMessage] = useState('');
    const [isSending, setIsSending] = useState(false);
    const [error, setError] = useState('');

    const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        setError('');

        const trimmedMessage = message.trim();

        if (!activeWorkspaceId || !trimmedMessage) {
            return;
        }

        setIsSending(true);

        try {
            const response = await fetch(getApiUrl('/query'), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    chat_id: activeWorkspaceId,
                    query: trimmedMessage,
                }),
            });
            const result = (await response.json()) as QueryResponse;

            if (!response.ok || !result.success) {
                throw new Error(result.error || 'Не удалось отправить запрос');
            }

            addRequest(activeWorkspaceId, {
                id: crypto.randomUUID(),
                time: getRequestTime(),
                message: trimmedMessage,
            });
            setMessage('');
        } catch (submitError) {
            setError(
                submitError instanceof Error
                    ? submitError.message
                    : 'Не удалось отправить запрос',
            );
        } finally {
            setIsSending(false);
        }
    };

    return (
        <div className={styles.root}>
            {error && <p className={styles.error}>{error}</p>}
            <form className={styles.form} onSubmit={handleSubmit}>
                <textarea
                    className={styles.input}
                    value={message}
                    onChange={event => setMessage(event.target.value)}
                    placeholder="Опишите, какой GraphQL запрос нужно собрать"
                    rows={1}
                    disabled={isSending}
                />
                <button
                    className={styles.submitButton}
                    type="submit"
                    disabled={isSending || !message.trim()}
                    aria-label="Отправить запрос"
                    title="Отправить запрос"
                >
                    <svg
                        className={styles.submitIcon}
                        viewBox="0 0 24 24"
                        aria-hidden="true"
                    >
                        <path
                            d="M5 12h14M13 6l6 6-6 6"
                            fill="none"
                            stroke="currentColor"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2.4"
                        />
                    </svg>
                </button>
            </form>
        </div>
    );
};

export default MessageComposer;
