import { useWorkspacesStore } from '../../stores/workspacesStore';
import styles from './RequestDetails.module.css';

const formatGraphqlQuery = (query: string) =>
    query
        .replace(/\s+/g, ' ')
        .replace(/\s*{\s*/g, ' { ')
        .replace(/\s*}\s*/g, ' } ')
        .split(/(?=[{}])|(?<=[{}])/)
        .map(part => part.trim())
        .filter(Boolean)
        .reduce(
            (lines, part) => {
                if (part === '}') {
                    const indent = Math.max(lines.indent - 1, 0);

                    return {
                        indent,
                        result: [...lines.result, `${'  '.repeat(indent)}}`],
                    };
                }

                const formattedLine =
                    part === '{'
                        ? `${'  '.repeat(lines.indent)}{`
                        : `${'  '.repeat(lines.indent)}${part}`;
                const indent = part === '{' ? lines.indent + 1 : lines.indent;

                return {
                    indent,
                    result: [...lines.result, formattedLine],
                };
            },
            { indent: 0, result: [] as string[] },
        )
        .result.join('\n');

const formatQueryValue = (query: unknown) => {
    if (typeof query === 'string') {
        return formatGraphqlQuery(query);
    }

    if (query === null || query === undefined) {
        return '';
    }

    return JSON.stringify(query, null, 2);
};

const RequestDetails = () => {
    const request = useWorkspacesStore(state => {
        if (!state.activeWorkspaceId || !state.activeRequestId) {
            return null;
        }

        const workspace = state.workspaces.find(
            item => item.id === state.activeWorkspaceId,
        );

        return (
            workspace?.requests.find(
                item => item.id === state.activeRequestId,
            ) ?? null
        );
    });

    if (!request) {
        return (
            <section className={styles.emptyState}>
                <p>Выберите запрос, чтобы увидеть GraphQL результат.</p>
            </section>
        );
    }

    const formattedQuery = formatQueryValue(request.query);

    return (
        <section className={styles.root}>
            <header className={styles.header}>
                <p className={styles.kicker}>GraphQL</p>
                <h2 className={styles.title}>Результат запроса</h2>
                <span className={styles.time}>{request.time}</span>
            </header>

            <div className={styles.block}>
                <h3 className={styles.blockTitle}>Сообщение</h3>
                <p className={styles.message}>{request.message}</p>
            </div>

            <div className={styles.block}>
                <h3 className={styles.blockTitle}>Query</h3>
                {formattedQuery ? (
                    <pre className={styles.codeBlock}>
                        <code>{formattedQuery}</code>
                    </pre>
                ) : (
                    <p className={styles.muted}>Query не найден в ответе.</p>
                )}
            </div>

            {request.note && (
                <div className={styles.block}>
                    <h3 className={styles.blockTitle}>Note</h3>
                    <p className={styles.message}>{request.note}</p>
                </div>
            )}

            {request.hints.length > 0 && (
                <div className={styles.block}>
                    <h3 className={styles.blockTitle}>Hints</h3>
                    <ul className={styles.hints}>
                        {request.hints.map(hint => (
                            <li key={hint}>{hint}</li>
                        ))}
                    </ul>
                </div>
            )}
        </section>
    );
};

export default RequestDetails;
