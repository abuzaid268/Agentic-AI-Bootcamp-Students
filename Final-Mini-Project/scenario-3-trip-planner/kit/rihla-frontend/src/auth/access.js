// Who may open which page. Pure: RequireAuth.jsx renders the answer, the tests check it.
//   'wait'  the sign-in check is still running
//   'allow' show the page
//   'login' send to the public home page and open the login modal
//   'home'  send to the public home page (signed in, but this is not their data)
//
// kind 'private': a page that only exists for a signed-in user (My Trips).
// kind 'trip':    the trip dashboard. Without an AI result it shows the public sample trip. With one, the
//                 itinerary belongs to the user who generated or opened it (state.ownerUid): after a logout,
//                 the browser's Back button must not show it to a guest or to the next account.
export function routeAccess({ kind, status, user, state }) {
  if (kind === 'trip' && !state?.aiResult) return 'allow'
  if (status === 'loading') return 'wait'
  if (!user) return 'login'
  if (kind === 'trip' && state.ownerUid !== user.uid) return 'home'
  return 'allow'
}
