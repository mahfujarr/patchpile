// --- Theme Handling Control ---
(function () {
  const root = document.documentElement;
  const toggle = document.getElementById("theme-toggle");
  const metaTheme = document.querySelector('meta[name="theme-color"]');

  function applyMetaColor(theme) {
    metaTheme.setAttribute("content", theme === "dark" ? "#08111f" : "#f7f7f7");
  }
  applyMetaColor(root.getAttribute("data-theme"));

  toggle.addEventListener("click", () => {
    const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    localStorage.setItem("patchpile-theme", next);
    applyMetaColor(next);
  });
})();

// --- Release Management and APIs ---
(function () {
  const releaseCards = document.querySelectorAll(
    "[data-repo][data-patch-source][data-asset-match]",
  );

  setTimeout(() => {
    const el = document.getElementById("last-sync-date");
    if (el && el.textContent === "checking…") el.textContent = "see GitHub";
  }, 6000);

  function formatBytes(bytes) {
    if (!bytes) return "";
    return "Size: " + (bytes / (1024 * 1024)).toFixed(1) + " MB";
  }

  function formatBuiltAt(iso) {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return "recent";
    const datePart = d
      .toLocaleDateString("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric",
      })
      .replace(",", "");
    const timePart = d.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
    });
    return ` ${timePart}, ${datePart}`;
  }

  let rateLimitRemaining = null;
  let rateLimitTriggered = false;
  let rateLimitResetAt = null;
  let rateLimitTimer = null;

  function formatCountdown(ms) {
    const totalSeconds = Math.max(0, Math.ceil(ms / 1000));
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}m ${seconds}s`;
  }

  function showTopWarning(message) {
    const warningEl = document.getElementById("top-warning");
    if (!warningEl) return;
    warningEl.textContent = message;
    warningEl.hidden = false;
  }

  function hideTopWarning() {
    const warningEl = document.getElementById("top-warning");
    if (!warningEl) return;
    warningEl.textContent = "";
    warningEl.hidden = true;
  }

  function updateRateLimitWarning() {
    const warningEl = document.getElementById("top-warning");
    if (!warningEl || !rateLimitResetAt) return;

    const remainingMs = rateLimitResetAt - Date.now();
    if (remainingMs <= 0) {
      hideTopWarning();
      rateLimitResetAt = null;
      rateLimitTriggered = false;
      if (rateLimitTimer) {
        clearInterval(rateLimitTimer);
        rateLimitTimer = null;
      }
      location.reload();
      return;
    }

    const resetTime = new Date(rateLimitResetAt).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });

    showTopWarning(
      `⚠ GitHub API rate limit reached. Direct links may be unavailable until ${resetTime} (${formatCountdown(remainingMs)} remaining).`,
    );
  }

  function startRateLimitCountdown(resetEpochSeconds) {
    if (!resetEpochSeconds) return;

    rateLimitResetAt = Number(resetEpochSeconds) * 1000;
    if (rateLimitTimer) clearInterval(rateLimitTimer);

    updateRateLimitWarning();
    rateLimitTimer = setInterval(() => {
      updateRateLimitWarning();
    }, 1000);
  }

  async function getReleasesList(repo) {
    const cacheKey = `releases_${repo}`;
    const cached = sessionStorage.getItem(cacheKey);
    if (cached) {
      try {
        return JSON.parse(cached);
      } catch (e) {
        sessionStorage.removeItem(cacheKey);
      }
    }

    const token = localStorage.getItem("gh-token");
    const headers = token ? { Authorization: `token ${token}` } : {};
    const res = await fetch(
      `https://api.github.com/repos/${repo}/releases?per_page=100`,
      { headers },
    );

    // Track rate limit
    rateLimitRemaining = res.headers.get("x-ratelimit-remaining");
    const rateLimitReset = res.headers.get("x-ratelimit-reset");
    if (rateLimitRemaining !== null) {
      console.log(
        `GitHub API: ${rateLimitRemaining} calls remaining (resets at ${new Date(parseInt(rateLimitReset) * 1000).toLocaleTimeString()})`,
      );
    }

    if (res.status === 403) {
      if (rateLimitReset) startRateLimitCountdown(rateLimitReset);
      throw new Error("GitHub API rate limited");
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    sessionStorage.setItem(cacheKey, JSON.stringify(data));
    return data;
  }

  function pickLatestMatchingRelease(releases, patchSource) {
    return (releases || [])
      .filter(
        (r) => !r.draft && r.tag_name && r.tag_name.endsWith(`-${patchSource}`),
      )
      .sort((a, b) => {
        const aTime = Date.parse(a.published_at || a.created_at || 0);
        const bTime = Date.parse(b.published_at || b.created_at || 0);
        return bTime - aTime;
      });
  }

  function pickApkAsset(release, match) {
    if (!release) return null;
    const assets = release.assets || [];
    const normalized = String(match || "").toLowerCase();
    return (
      assets.find((a) => {
        const name = String(a.name || "").toLowerCase();
        return name.endsWith(".apk") && name.includes(normalized);
      }) || null
    );
  }

  // --- Independent Global Actions Timeline Execution ---
  (async () => {
    try {
      const res = await fetch(
        `https://api.github.com/repos/mahfujarr/patchpile/actions/workflows/ci.yml/runs?per_page=1`,
      );
      if (res.ok) {
        const data = await res.json();
        if (data.workflow_runs && data.workflow_runs[0]) {
          document.getElementById("last-sync-date").textContent = formatBuiltAt(
            data.workflow_runs[0].updated_at,
          );
        }
      }
    } catch (e) {}
  })();

  // --- Application Release Mapping Engine ---
  (async () => {
    const repoGroups = {};
    releaseCards.forEach((card) => {
      const repo = card.dataset.repo;
      (repoGroups[repo] = repoGroups[repo] || []).push(card);
    });

    for (const [repo, group] of Object.entries(repoGroups)) {
      let releases;
      try {
        releases = await getReleasesList(repo);
      } catch (e) {
        if (e.message === "GitHub API rate limited") {
          rateLimitTriggered = true;
        } else {
          group.forEach((card) => {
            const dlBtn =
              card.querySelector(":scope > .dl-btn") ||
              card.querySelector(".dl-btn");
            if (dlBtn) {
              dlBtn.textContent = `⚠ ${e.message}`;
              dlBtn.classList.add("error");
            }
            card.querySelector(".f-size")?.remove();
            card.querySelector(".f-built")?.remove();
          });
        }
        continue;
      }

      group.forEach((card) => {
        const patchSource = card.dataset.patchSource;
        const match = card.dataset.assetMatch;
        const sizeEl = card.querySelector(".f-size");
        const builtEl = card.querySelector(".f-built");
        const versionEl = card.querySelector(".v-num");
        const dlBtn =
          card.querySelector(":scope > .dl-btn") ||
          card.querySelector(".dl-btn");

        const matchedReleases = pickLatestMatchingRelease(
          releases,
          patchSource,
        );
        let data = null;
        let asset = null;

        for (const rel of matchedReleases) {
          const relAsset = pickApkAsset(rel, match);
          if (relAsset) {
            data = rel;
            asset = relAsset;
            break;
          }
        }

        if (!data || !asset) {
          if (dlBtn) {
            dlBtn.textContent = "⚠ Build not found";
            dlBtn.classList.add("error");
          }
          sizeEl?.remove();
          builtEl?.remove();
          return;
        }

        sizeEl.textContent = formatBytes(asset.size);
        sizeEl.classList.remove("skel");
        dlBtn.href = asset.browser_download_url;

        const vMatch = asset.name.match(/v?([\d.]+)-arm64/);
        if (vMatch) versionEl.textContent = "Ver: " + vMatch[1];

        const builtSource = asset.updated_at || data.published_at;
        if (builtEl && builtSource) {
          builtEl.textContent = "Build time: " + formatBuiltAt(builtSource);
          builtEl.classList.remove("skel");
        }
      });
    }

    if (rateLimitTriggered) {
      updateRateLimitWarning();
    } else {
      hideTopWarning();
    }
  })();

  // --- Refresh Button Handler ---
  const refreshBtn = document.getElementById("refresh-releases");
  if (refreshBtn) {
    const originalHTML = refreshBtn.innerHTML;
    refreshBtn.addEventListener("click", () => {
      // Show spinner
      refreshBtn.innerHTML =
        '<svg style="animation: spin 1s linear infinite; display: inline-block;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><path d="M12 6v6l4 2"></path></svg>';
      refreshBtn.style.pointerEvents = "none";

      // Clear all release caches
      for (let i = sessionStorage.length - 1; i >= 0; i--) {
        const key = sessionStorage.key(i);
        if (key && key.startsWith("releases_")) {
          sessionStorage.removeItem(key);
        }
      }

      // Reload page to fetch fresh data
      setTimeout(() => {
        location.reload();
      }, 300);
    });
  }

  // --- ytdlnis Pipeline Setup ---
  (async () => {
    const row = document.getElementById("ytdlnis-row");
    if (!row) return;
    const repo = row.dataset.repo;
    const versionEl = document.getElementById("ytdlnis-version");
    const linkEl = document.getElementById("ytdlnis-link");

    try {
      const res = await fetch(
        `https://api.github.com/repos/${repo}/releases/latest`,
      );
      if (!res.ok) throw new Error("restricted");
      const data = await res.json();

      const asset = (data.assets || []).find((a) =>
        a.name.toLowerCase().endsWith(".apk"),
      );
      if (asset && linkEl) {
        linkEl.href = asset.browser_download_url;
      }
      if (data.tag_name && versionEl) {
        versionEl.textContent = ` (${data.tag_name.replace(/^v/, "v")})`;
      }
    } catch (e) {}
  })();
})();

// --- Add spinner animation CSS ---
if (!document.getElementById("spinner-style")) {
  const style = document.createElement("style");
  style.id = "spinner-style";
  style.textContent = `@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`;
  document.head.appendChild(style);
}

// --- Pure Text Visitor Counter Engine ---
(async () => {
  const counterEl = document.getElementById("visit-count");
  if (!counterEl) return;

  const hasVisited = sessionStorage.getItem("patchpile-hit");
  // const hasVisited = localStorage.getItem('patchpile-hit');
  const endpoint = hasVisited ? "get" : "hit";

  try {
    const res = await fetch(
      `https://countapi.mileshilliard.com/api/v1/${endpoint}/patchpile_live`,
    );
    if (res.ok) {
      const data = await res.json();
      if (data && typeof data.value !== "undefined") {
        counterEl.textContent = data.value.toLocaleString() + " times";
        sessionStorage.setItem("patchpile-hit", "true");
        // localStorage.setItem('patchpile-hit', 'true');
        return;
      }
    }
    counterEl.textContent = "active";
  } catch (e) {
    counterEl.textContent = "online";
  }
})();
