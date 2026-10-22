export const THEME_STORAGE_KEY = "ai-receptionist-theme";

export const themeInitScript = `(function(){try{var stored=localStorage.getItem("${THEME_STORAGE_KEY}");var dark=stored?stored==="dark":true;document.documentElement.classList.toggle("dark",dark);document.documentElement.style.colorScheme=dark?"dark":"light";}catch(e){document.documentElement.classList.add("dark");document.documentElement.style.colorScheme="dark";}})();`;
