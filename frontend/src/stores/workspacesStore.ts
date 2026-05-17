import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

export type WorkspaceRequest = {
    id: string;
    time: string;
    message: string;
    query: unknown;
    note: string;
    hints: string[];
};

export type Workspace = {
    id: string;
    title: string;
    base_url: string;
    requests: WorkspaceRequest[];
};

type WorkspacesState = {
    workspaces: Workspace[];
    activeWorkspaceId: string | null;
    activeRequestId: string | null;
    addWorkspace: (title: string) => void;
    addRequest: (workspaceId: string, request: WorkspaceRequest) => void;
    deleteWorkspace: (workspaceId: string) => void;
    saveWorkspace: (workspace: Workspace) => void;
    setActiveWorkspaceId: (workspaceId: string | null) => void;
    setActiveRequestId: (workspaceId: string) => void;
};

const createWorkspaceId = () => crypto.randomUUID();

export const useWorkspacesStore = create<WorkspacesState>()(
    persist(
        set => ({
            workspaces: [],
            activeWorkspaceId: null,
            activeRequestId: null,
            addWorkspace: title => {
                const workspace: Workspace = {
                    id: createWorkspaceId(),
                    title,
                    base_url: '',
                    requests: [],
                };

                set((state: WorkspacesState) => ({
                    workspaces: [...state.workspaces, workspace],
                    activeWorkspaceId: workspace.id,
                }));
            },
            addRequest: (workspaceId, request) => {
                set((state: WorkspacesState) => ({
                    workspaces: state.workspaces.map(workspace =>
                        workspace.id === workspaceId
                            ? {
                                  ...workspace,
                                  requests: [
                                      ...(workspace.requests ?? []),
                                      request,
                                  ],
                              }
                            : workspace,
                    ),
                    activeRequestId: request.id,
                }));
            },
            deleteWorkspace: workspaceId => {
                set((state: WorkspacesState) => {
                    const workspaces = state.workspaces.filter(
                        workspace => workspace.id !== workspaceId,
                    );
                    const isActiveWorkspace =
                        state.activeWorkspaceId === workspaceId;

                    return {
                        workspaces,
                        activeWorkspaceId: isActiveWorkspace
                            ? null
                            : state.activeWorkspaceId,
                        activeRequestId: isActiveWorkspace
                            ? null
                            : state.activeRequestId,
                    };
                });
            },
            saveWorkspace: workspace => {
                set((state: WorkspacesState) => {
                    const workspaces = state.workspaces.some(
                        item => item.id === workspace.id,
                    )
                        ? state.workspaces.map(item =>
                              item.id === workspace.id ? workspace : item,
                          )
                        : [...state.workspaces, workspace];

                    return {
                        workspaces,
                        activeWorkspaceId: workspace.id,
                    };
                });
            },
            setActiveWorkspaceId: workspaceId => {
                set({ activeWorkspaceId: workspaceId });
            },
            setActiveRequestId: requestId => {
                set({ activeRequestId: requestId });
            },
        }),
        {
            name: 'workspaces-storage',
            storage: createJSONStorage(() => localStorage),
        },
    ),
);
