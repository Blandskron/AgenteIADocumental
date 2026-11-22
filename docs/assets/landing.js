(() => {
  const root = document.documentElement;
  const themeBtn = document.getElementById("theme-toggle");
  const navToggle = document.querySelector(".nav-toggle");
  const navMenu = document.getElementById("nav-menu");
  const copyBtn = document.getElementById("copy-install");
  const installCommands = document.getElementById("install-commands");
  const lightbox = document.getElementById("lightbox");
  const lightboxImg = document.getElementById("lightbox-img");
  const lightboxCaption = document.getElementById("lightbox-caption");
  const lightboxClose = document.getElementById("lightbox-close");

  // Theme preference & Hero screenshot sync
  const heroImg = document.getElementById("hero-screenshot-img");
  function syncHeroTheme(theme) {
    if (!heroImg) return;
    const targetSrc =
      theme === "dark"
        ? heroImg.getAttribute("data-dark-src")
        : heroImg.getAttribute("data-light-src");
    if (targetSrc) {
      heroImg.src = targetSrc;
    }
  }

  const savedTheme = localStorage.getItem("blandskron.landing.theme");
  if (savedTheme === "dark" || savedTheme === "light") {
    root.setAttribute("data-theme", savedTheme);
    syncHeroTheme(savedTheme);
  }
  themeBtn?.addEventListener("click", () => {
    const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    localStorage.setItem("blandskron.landing.theme", next);
    syncHeroTheme(next);
  });

  // Gallery theme filter (all / light / dark)
  const filterBtns = document.querySelectorAll("[data-gallery-filter]");
  const galleryCards = document.querySelectorAll("#product-gallery .gallery-card");
  filterBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const mode = btn.getAttribute("data-gallery-filter") || "all";
      filterBtns.forEach((b) =>
        b.setAttribute("aria-pressed", String(b === btn)),
      );
      galleryCards.forEach((card) => {
        const cardTheme = card.getAttribute("data-theme-mode");
        card.hidden = mode !== "all" && cardTheme !== mode;
      });
    });
  });

  // Mobile nav
  navToggle?.addEventListener("click", () => {
    const isOpen = navMenu?.classList.toggle("open");
    navToggle.setAttribute("aria-expanded", String(Boolean(isOpen)));
  });

  // Copy install commands
  copyBtn?.addEventListener("click", async () => {
    if (!installCommands) return;
    try {
      await navigator.clipboard.writeText(installCommands.textContent || "");
      copyBtn.textContent = "Copiado";
      setTimeout(() => {
        copyBtn.textContent = "Copiar comandos";
      }, 2000);
    } catch {
      copyBtn.textContent = "Selecciona y copia";
    }
  });

  // Honest fallback if a screenshot file has not been generated yet
  document.querySelectorAll("img.real-screenshot").forEach((img) => {
    const showFallback = () => {
      img.hidden = true;
      const fallback = img.parentElement?.querySelector(".screenshot-fallback");
      if (fallback) fallback.hidden = false;
    };
    img.addEventListener("error", showFallback);
    if (img.complete && img.naturalWidth === 0) {
      showFallback();
    }
  });

  // Accessible lightbox for available screenshots
  document.querySelectorAll(".gallery-zoom").forEach((button) => {
    button.addEventListener("click", () => {
      const img = button.querySelector("img.real-screenshot");
      if (!img || img.hidden || !lightbox || !lightboxImg) return;
      lightboxImg.src = img.src;
      lightboxImg.alt = img.alt;
      if (lightboxCaption) {
        lightboxCaption.textContent = img.alt;
      }
      if (typeof lightbox.showModal === "function") {
        lightbox.showModal();
      }
    });
  });

  lightboxClose?.addEventListener("click", () => lightbox?.close());
  lightbox?.addEventListener("click", (event) => {
    if (event.target === lightbox) lightbox.close();
  });
})();

