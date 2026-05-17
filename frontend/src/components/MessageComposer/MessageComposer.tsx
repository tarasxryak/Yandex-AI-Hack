import { useEffect, useRef, useState, type FormEvent } from 'react';
import { getApiUrl } from '../../config/api';
import { useMessageComposerStore } from '../../stores/messageComposerStore';
import { useWorkspacesStore } from '../../stores/workspacesStore';
import styles from './MessageComposer.module.css';

type GeneratedGraphqlRequest = {
    query?: unknown;
    note?: unknown;
    hints?: unknown;
    report_link?: unknown;
};

type QueryResponse = {
    success: boolean;
    error?: string;
    graphql?: GeneratedGraphqlRequest | null;
    report_link?: unknown;
};

const getRequestTime = () =>
    new Intl.DateTimeFormat('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
    }).format(new Date());

const normalizeHints = (hints: unknown) =>
    Array.isArray(hints)
        ? hints.filter((hint): hint is string => typeof hint === 'string')
        : [];

const normalizeReportLink = (reportLink: unknown) => {
    if (typeof reportLink !== 'string') {
        return null;
    }

    const trimmedReportLink = reportLink.trim();

    return trimmedReportLink || null;
};

const DEFAULT_INPUT_HEIGHT = 38;
const COMPACT_INPUT_HEIGHT = 58;
const COMPACT_INPUT_WIDTH = 365;
const MAX_INPUT_HEIGHT = 132;

const MessageComposer = () => {
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const activeWorkspaceId = useWorkspacesStore(
        state => state.activeWorkspaceId,
    );
    const addRequest = useWorkspacesStore(state => state.addRequest);
    const message = useMessageComposerStore(state => state.draft);
    const setMessage = useMessageComposerStore(state => state.setDraft);

    const [isSending, setIsSending] = useState(false);
    const [error, setError] = useState('');

    const resizeTextarea = () => {
        const textarea = textareaRef.current;

        if (!textarea) {
            return;
        }

        const minHeight =
            textarea.clientWidth < COMPACT_INPUT_WIDTH
                ? COMPACT_INPUT_HEIGHT
                : DEFAULT_INPUT_HEIGHT;

        textarea.style.minHeight = `${minHeight}px`;
        textarea.style.height = 'auto';
        textarea.style.height = `${Math.min(
            Math.max(textarea.scrollHeight, minHeight),
            MAX_INPUT_HEIGHT,
        )}px`;
    };

    useEffect(() => {
        resizeTextarea();

        const textarea = textareaRef.current;

        if (!textarea) {
            return;
        }

        const observer = new ResizeObserver(resizeTextarea);
        observer.observe(textarea);

        return () => observer.disconnect();
    }, []);

    useEffect(() => {
        requestAnimationFrame(resizeTextarea);
    }, [message]);

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

            const generatedRequest = result.graphql;

            if (!generatedRequest) {
                throw new Error('Backend не вернул GraphQL результат');
            }

            addRequest(activeWorkspaceId, {
                id: crypto.randomUUID(),
                time: getRequestTime(),
                message: trimmedMessage,
                query: generatedRequest.query ?? null,
                note:
                    typeof generatedRequest.note === 'string'
                        ? generatedRequest.note
                        : '',
                hints: normalizeHints(generatedRequest.hints),
                report_link: normalizeReportLink(
                    generatedRequest.report_link ?? result.report_link,
                ),
            });
            setMessage('');
            requestAnimationFrame(resizeTextarea);
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
                    ref={textareaRef}
                    className={styles.input}
                    value={message}
                    onChange={event => {
                        setMessage(event.target.value);
                        requestAnimationFrame(resizeTextarea);
                    }}
                    placeholder='Опишите, какой GraphQL запрос нужно собрать'
                    rows={1}
                    disabled={isSending}
                />
                <button
                    className={styles.submitButton}
                    type='submit'
                    disabled={isSending || !message.trim()}
                    aria-label='Отправить запрос'
                    title='Отправить запрос'>
                    <svg
                        className={styles.submitIcon}
                        viewBox='0 0 24 24'
                        aria-hidden='true'>
                        <path
                            d='M5 12h14M13 6l6 6-6 6'
                            fill='none'
                            stroke='currentColor'
                            strokeLinecap='round'
                            strokeLinejoin='round'
                            strokeWidth='2.4'
                        />
                    </svg>
                </button>
            </form>
        </div>
    );
};

export default MessageComposer;
