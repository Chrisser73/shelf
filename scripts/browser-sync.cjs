/** Development-only browser refresh proxy for the FastAPI/Jinja app. */
module.exports = {
  proxy: "http://127.0.0.1:8000",
  port: 3000,
  open: false,
  ui: false,
  notify: false,
  files: [
    "app/templates/**/*.html",
    "app/**/*.py",
    "static/css/app.css",
    "static/js/**/*.js",
    "static/icons/platforms/**/*.svg",
  ],
  watchOptions: {
    // The project lives on /mnt/e under WSL, where native file events are
    // unreliable. Match the polling strategy used by the other dev watchers.
    usePolling: true,
    interval: 300,
  },
  reloadDelay: 750,
};
