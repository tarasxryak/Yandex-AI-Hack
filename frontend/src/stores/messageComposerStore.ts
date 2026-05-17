import { create } from 'zustand';

type MessageComposerState = {
    draft: string;
    appendDraft: (text: string) => void;
    setDraft: (text: string) => void;
};

export const useMessageComposerStore = create<MessageComposerState>()(set => ({
    draft: '',
    appendDraft: text => {
        set(state => ({
            draft: state.draft.trim()
                ? `${state.draft.trimEnd()}\n${text}`
                : text,
        }));
    },
    setDraft: draft => {
        set({ draft });
    },
}));
