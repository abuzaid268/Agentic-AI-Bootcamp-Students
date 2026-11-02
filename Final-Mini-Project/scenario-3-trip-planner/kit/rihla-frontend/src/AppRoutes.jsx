import { Navigate, Routes, Route } from 'react-router-dom'
import App from './App.jsx'
import MyTrips from './pages/MyTrips.jsx'
import Profile from './pages/Profile.jsx'
import TripDashboard from './pages/TripDashboard.jsx'
import RequireAuth from './auth/RequireAuth.jsx'
import { useAuth } from './auth/authContext.js'

// Keyed on the logout counter: a logout discards every page's in-memory state (the trip form, an open
// itinerary, the trip list) instead of leaving it for the next person on this browser.
export default function AppRoutes() {
  const { resetKey } = useAuth()
  return (
    <Routes key={resetKey}>
      <Route path='/' element={<App />} />
      <Route path='/trip' element={<RequireAuth kind="trip"><TripDashboard /></RequireAuth>} />
      {/* Logging in is a modal over the home page now: old /login links open it there. */}
      <Route path="/login" element={<Navigate to="/" replace state={{ openLogin: true }} />} />
      <Route path="/my-trips" element={<RequireAuth resumeAfterLogin><MyTrips /></RequireAuth>} />
      <Route path="/profile" element={<RequireAuth resumeAfterLogin><Profile /></RequireAuth>} />
    </Routes>
  )
}
