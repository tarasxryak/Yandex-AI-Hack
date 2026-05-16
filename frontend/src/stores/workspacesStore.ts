import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

export type WorkspaceChat = {
    id: string;
    title: string;
};

export type Workspace = {
    id: string;
    title: string;
    base_url: string;
    chats: WorkspaceChat[];
};

type WorkspacesState = {
    workspaces: Workspace[];
    activeWorkspaceId: string | null;
    addWorkspace: (title: string) => void;
    setActiveWorkspaceId: (workspaceId: string) => void;
};

const createWorkspaceId = () => crypto.randomUUID();

export const useWorkspacesStore = create<WorkspacesState>()(
    persist(
        set => ({
            workspaces: [],
            activeWorkspaceId: null,
            addWorkspace: title => {
                const workspace = {
                    id: createWorkspaceId(),
                    title,
                    chats: [],
                };

                set(state => ({
                    workspaces: [...state.workspaces, workspace],
                    activeWorkspaceId: workspace.id,
                }));
            },
            setActiveWorkspaceId: workspaceId => {
                set({ activeWorkspaceId: workspaceId });
            },
        }),
        {
            name: 'workspaces-storage',
            storage: createJSONStorage(() => localStorage),
        },
    ),
);
