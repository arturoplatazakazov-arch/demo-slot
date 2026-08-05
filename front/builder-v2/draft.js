// Constructor v2 — client-side draft store.
//
// For now the whole game-in-progress lives in localStorage so the 3-page flow
// is fully clickable without any backend. Later this same shape is what we POST
// to the builder API / emit as the game manifest. One draft at a time (keyed by
// slug) is enough for the pilot; a draft list can come later.

const DRAFT_KEY = 'builderV2.draft';

window.Draft = {
  slugify(name) {
    return (name || '')
      .toLowerCase().trim()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '') || 'game';
  },

  empty() {
    return {
      name: '',
      slug: '',
      base: null,          // '3x3' | '5x3' | '6x5'
      gap: 10,             // px between reel elements
      mechanics: [],       // mechanic ids
      assets: {},          // { requiredAssetId: {file, name} }  (page 2)
      layout: {},          // { screenId: { elements: [...] } }  (page 3)
      updatedAt: null,
    };
  },

  load() {
    try {
      const raw = localStorage.getItem(DRAFT_KEY);
      if (!raw) return this.empty();
      return { ...this.empty(), ...JSON.parse(raw) };
    } catch (e) {
      return this.empty();
    }
  },

  save(draft) {
    draft.updatedAt = Date.now();
    localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
    return draft;
  },

  reset() {
    localStorage.removeItem(DRAFT_KEY);
  },
};
