// Runs before paint so the saved theme never flashes.
(function () {
  try {
    var saved = localStorage.getItem("flyte-theme");
    if (saved === "light" || saved === "dark") document.documentElement.setAttribute("data-theme", saved);
  } catch (e) { /* storage blocked – follow the OS */ }
})();
