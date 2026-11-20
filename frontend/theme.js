const themeToggle = document.getElementById("theme-toggle");
const systemTheme = window.matchMedia("(prefers-color-scheme: dark)");
let preferredTheme = document.cookie.match(
  /(?:^|; )trace_theme=(dark|light)(?:;|$)/,
)?.[1];

function applyTheme() {
  const theme = preferredTheme ?? (systemTheme.matches ? "dark" : "light");
  document.documentElement.dataset.theme = theme;
  themeToggle.setAttribute("aria-pressed", String(theme === "dark"));
  themeToggle.firstElementChild.textContent = theme === "dark" ? "☾" : "☀︎";
  themeToggle.title =
    theme === "dark" ? "Switch to light mode" : "Switch to dark mode";
}

themeToggle.addEventListener("click", () => {
  preferredTheme =
    document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.cookie =
    "trace_theme=" +
    preferredTheme +
    "; Path=/; Max-Age=31536000; SameSite=Strict";
  applyTheme();
});
systemTheme.addEventListener("change", applyTheme);
applyTheme();
