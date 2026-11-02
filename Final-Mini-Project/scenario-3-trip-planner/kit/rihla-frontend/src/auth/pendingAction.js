// The one action waiting for sign-in (e.g. "generate this trip"). take() hands it over exactly once: a second
// take(), a closed login modal, a failed sign-in or a Log In started from the navbar never runs it.
export function createPendingAction() {
  let action = null
  return {
    set(fn) {
      action = typeof fn === 'function' ? fn : null
    },
    clear() {
      action = null
    },
    take() {
      const fn = action
      action = null
      return fn
    },
    get pending() {
      return action !== null
    },
  }
}
