import { describe, expect, it } from "vitest"

import { isComposing } from "./ime"

/** Build the shape `isComposing` reads off a React keyboard event. */
const keydown = (native: { isComposing?: boolean; keyCode?: number }) => ({
  nativeEvent: native,
})

describe("isComposing", () => {
  it("blocks the Enter that commits an IME candidate in Chrome/Firefox", () => {
    // Typing English through a Chinese IME: the candidate list is open, so the
    // first Enter belongs to the IME even though the text looks finished.
    expect(isComposing(keydown({ isComposing: true, keyCode: 229 }))).toBe(true)
  })

  it("blocks it in Safari, where compositionend lands before the keydown", () => {
    // isComposing has already flipped back to false by the time we see the key;
    // only the legacy keyCode still says the IME handled it.
    expect(isComposing(keydown({ isComposing: false, keyCode: 229 }))).toBe(true)
  })

  it("allows a plain Enter so the message still sends", () => {
    expect(isComposing(keydown({ isComposing: false, keyCode: 13 }))).toBe(false)
  })

  it("allows the Enter that follows a finished composition", () => {
    // Second press: the IME is done, this one is meant for us.
    expect(isComposing(keydown({ isComposing: false, keyCode: 13 }))).toBe(false)
  })

  it("does not treat a missing field as composition", () => {
    // jsdom and synthetic events may omit both; failing open keeps Enter working
    // rather than silently breaking submit for everyone.
    expect(isComposing(keydown({}))).toBe(false)
  })
})
