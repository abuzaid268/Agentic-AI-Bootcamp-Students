// An error boundary around the trip page's "Weather and flights" section (TripTravelInfo). If that section throws
// while rendering, only it is replaced by a short notice: the itinerary, budget and everything else on the page keep
// working. Written without JSX so the plain Node test runner can load it (see tripTravel.test.js).
//
// Boundaries catch errors thrown while rendering, in lifecycle methods and in constructors of the components below
// them. They do not catch event handlers or async code: FlightSearch handles its own network failures in state.
import { Component, createElement } from 'react'

export default class TravelInfoBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { failed: false }
    this.retry = this.retry.bind(this)
  }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  componentDidCatch(error) {
    console.error('Weather and flights could not be shown:', error)
  }

  retry() {
    this.setState({ failed: false })
  }

  render() {
    if (!this.state.failed) return this.props.children
    return createElement(
      'section',
      { role: 'status', className: 'rounded-[28px] border border-[#dbe8eb] bg-white p-5 text-sm text-[#456774] shadow-sm sm:p-7' },
      createElement('p', { className: 'font-semibold text-[#1c3544]' }, 'Weather and flights could not be shown'),
      createElement('p', { className: 'mt-1' }, 'Your itinerary is not affected.'),
      createElement('button', { type: 'button', onClick: this.retry, className: 'mt-3 font-semibold underline' }, 'Try again'),
    )
  }
}
