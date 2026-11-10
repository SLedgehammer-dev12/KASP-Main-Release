/**
 * KASP Lightweight Reactive Store
 * Zero-dependency Pub/Sub state container with granular subscription support.
 */

export function createStore(initialState) {
  let state = { ...initialState };
  const listeners = new Set();

  function getState() {
    return state;
  }

  function setState(updater) {
    const partial = typeof updater === "function" ? updater(state) : updater;
    const oldState = state;
    state = { ...state, ...partial };
    for (const listener of listeners) {
      try {
        listener(state, oldState);
      } catch (err) {
        console.error("Store listener error:", err);
      }
    }
  }

  function subscribe(listener) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  }

  return {
    getState,
    setState,
    subscribe,
  };
}
