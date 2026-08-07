/**
 * Guard for Enter-to-submit inputs against IME composition.
 *
 * With a Chinese/Japanese/Korean IME, Enter has two jobs: commit the candidate
 * the IME is offering, and — separately — submit the form. The browser fires a
 * `keydown` for the committing press too, so a bare `if (e.key === "Enter")`
 * sends a half-typed message the moment the user accepts a candidate. Typing
 * English *through* a Chinese IME hits this every time, because there is always
 * a composition in progress even though the text looks finished.
 *
 * Two signals are needed, because browsers disagree on the ordering:
 *
 * - Chrome, Edge and Firefox keep `isComposing === true` on the committing
 *   keydown, so that flag alone is enough there.
 * - Safari fires `compositionend` *before* the keydown, leaving `isComposing`
 *   false; it reports the legacy `keyCode === 229` instead. That constant is
 *   the historical "IME is processing this key" marker and is still populated
 *   everywhere, which is why the deprecated field is worth reading here.
 */
export function isComposing(event: {
  nativeEvent: { isComposing?: boolean; keyCode?: number }
}): boolean {
  const native = event.nativeEvent
  return native.isComposing === true || native.keyCode === 229
}
