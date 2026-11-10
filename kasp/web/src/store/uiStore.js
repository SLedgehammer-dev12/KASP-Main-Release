/**
 * KASP UI Store
 * Controls view routing, theme switcher, modal dialogs, and notifications.
 */

import { createStore } from "./store.js";

const SAVED_THEME = localStorage.getItem("kasp_theme") || "light";
const SAVED_LANG = localStorage.getItem("kasp_lang") || "tr";

export const uiStore = createStore({
  activeTab: "design",
  activeSubTab: "thermo",
  theme: SAVED_THEME,
  lang: SAVED_LANG,
  activeModal: null,
  modalData: null,
  toasts: [],
});

export function setActiveTab(tab) {
  uiStore.setState({ activeTab: tab });
}

export function setActiveSubTab(subTab) {
  uiStore.setState({ activeSubTab: subTab });
}

export function setTheme(theme) {
  localStorage.setItem("kasp_theme", theme);
  document.documentElement.setAttribute("data-theme", theme);
  uiStore.setState({ theme });
  window.dispatchEvent(new CustomEvent("kasp:theme-changed", { detail: theme }));
}

export function setLanguage(lang) {
  localStorage.setItem("kasp_lang", lang);
  uiStore.setState({ lang });
  window.dispatchEvent(new CustomEvent("kasp:lang-changed", { detail: lang }));
}

export function openModal(modalName, modalData = null) {
  uiStore.setState({ activeModal: modalName, modalData });
}

export function closeModal() {
  uiStore.setState({ activeModal: null, modalData: null });
}

let toastCounter = 0;
export function showToast(message, type = "success", durationMs = 3500) {
  const id = ++toastCounter;
  const newToast = { id, message, type };
  uiStore.setState((s) => ({ toasts: [...s.toasts, newToast] }));

  setTimeout(() => {
    uiStore.setState((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
  }, durationMs);
}
