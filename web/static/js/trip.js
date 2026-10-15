import { confetti } from "./lib.js";

// Celebrate once, right after a booking is confirmed.
if (document.querySelector("[data-celebrate]")) {
  setTimeout(confetti, 250);
  history.replaceState(null, "", location.pathname);   // no confetti on refresh
}
