/** Nach jeder Änderung an den Vertragsdaten (Kopf, Prüfung und Reiter „Vertragsdaten“ bleiben gleich). */
export const REGISTER_CHANGED_EVENT = "medflux:register-changed";

export function announceRegisterChange() {
  window.dispatchEvent(new Event(REGISTER_CHANGED_EVENT));
}
