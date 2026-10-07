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

  document.querySelectorAll(".changelog-link").forEach((link) => {
    link.hidden = true;
  });

  const googlePhotosCards = document.querySelectorAll(".gphotos-variant");
  const googlePhotosButtons = document.querySelectorAll(".gphotos-variant-btn");

  function setAppChangelogOpen(app, open) {
    app?.querySelectorAll(".changelog-menu").forEach((menu) => {
      menu.open = open;
    });
  }

  document.querySelectorAll(".app").forEach((app) => {
    app.querySelectorAll(".changelog-menu > summary").forEach((summary) => {
      summary.addEventListener("click", (event) => {
        event.preventDefault();
        const menu = summary.parentElement;
        setAppChangelogOpen(app, !menu.open);
      });
    });
  });

  function setGooglePhotosVariant(variant) {
    const currentCard = [...googlePhotosCards].find((card) => !card.hidden);
    const changelogOpen = currentCard
      ? [...currentCard.querySelectorAll(".changelog-menu")].some(
          (menu) => menu.open,
        )
      : false;
    googlePhotosCards.forEach((card) => {
      card.hidden = card.dataset.variant !== variant;
    });
    const nextCard = [...googlePhotosCards].find(
      (card) => card.dataset.variant === variant,
    );
    setAppChangelogOpen(nextCard, changelogOpen);
    googlePhotosButtons.forEach((button) => {
      button.setAttribute(
        "aria-pressed",
        String(button.dataset.variant === variant),
      );
    });
  }

  googlePhotosButtons.forEach((button) => {
    button.addEventListener("click", () => {
      setGooglePhotosVariant(button.dataset.variant);
    });
  });

  document.querySelectorAll(".build-variant-btn").forEach((button) => {
    button.addEventListener("click", () => {
      const app = button.closest(".app");
      const experimentalMenu = app?.querySelector(".exp-menu");
      const selectedBuild = button.dataset.build;
      if (!app || !experimentalMenu || !selectedBuild) return;

      const changelogOpen = [...app.querySelectorAll(".changelog-menu")].some(
        (menu) => menu.open,
      );
      app.dataset.buildState = selectedBuild;
      if (selectedBuild === "experimental") {
        experimentalMenu.open = true;
        experimentalMenu.setAttribute("open", "");
      } else {
        experimentalMenu.open = false;
        experimentalMenu.removeAttribute("open");
      }
      setAppChangelogOpen(app, changelogOpen);
      app.querySelectorAll(".build-variant-btn").forEach((variantButton) => {
        variantButton.setAttribute(
          "aria-pressed",
          String(variantButton.dataset.build === selectedBuild),
        );
      });
    });
  });

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

  function formatShortTime(iso) {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return "";
    const diff = Math.max(0, Date.now() - d.getTime());
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${Math.max(1, mins)}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 30) return `${days}d ago`;
    return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short" });
  }

  function formatHoursAgo(iso) {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return "";
    const diffMs = Math.max(0, Date.now() - d.getTime());
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return "just now";
    if (diffMins < 60) {
      return diffMins === 1 ? "1 minute ago" : `${diffMins} minutes ago`;
    }
    const hours = Math.floor(diffMins / 60);
    if (hours === 1) return "1 hour ago";
    if (hours < 48) return `${hours} hours ago`;
    const days = Math.floor(hours / 24);
    if (days === 1) return "yesterday";
    return `${days} days ago`;
  }

  let rateLimitRemaining = null;
  let rateLimitTriggered = false;
  let rateLimitResetAt = null;
  let rateLimitTimer = null;
  let localManifest = null;

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

  async function getLocalManifest() {
    if (!localManifest) {
      try {
        const manifestRes = await fetch(
          "https://raw.githubusercontent.com/mahfujarr/patchpile/main/assets/releases.json",
          {
            cache: "no-store",
          },
        );
        if (manifestRes.ok) {
          localManifest = await manifestRes.json();
          return localManifest;
        }
      } catch (_) {}

      const localRes = await fetch("./assets/releases.json", {
        cache: "no-store",
      });
      if (!localRes.ok) throw new Error(`HTTP ${localRes.status}`);
      localManifest = await localRes.json();
    }
    return localManifest;
  }

  async function getReleasesList(repo) {
    const manifest = await getLocalManifest();
    const manifestReleases = manifest?.repos?.[repo];
    if (!Array.isArray(manifestReleases)) {
      throw new Error("Release manifest has no data for this repository");
    }
    return manifestReleases;
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

  function updateChangelog(card, upstreamRelease) {
    const contentEl = card.querySelector(".changelog-content");
    const linkEl = card.querySelector(".changelog-link");
    const versionEl = card.querySelector(".app-version, .exp-version");
    if (!contentEl) return;

    const patchTag = upstreamRelease?.tag_name;
    if (versionEl && patchTag) {
      let patchVersionEl = versionEl.querySelector(".p-num");
      if (!patchVersionEl) {
        patchVersionEl = document.createElement("span");
        patchVersionEl.className = "p-num";
        versionEl.append(patchVersionEl);
      }
      patchVersionEl.textContent = "Patch: " + patchTag;
    }

    if (!upstreamRelease) {
      contentEl.textContent =
        "The upstream changelog is unavailable right now.";
      if (linkEl) linkEl.hidden = true;
      return;
    }

    const notes = String(upstreamRelease.body || "").trim();
    renderChangelog(
      contentEl,
      notes || "No release notes were provided for this build.",
    );
    if (linkEl && upstreamRelease.html_url) {
      linkEl.href = upstreamRelease.html_url;
      linkEl.hidden = false;
    }
  }

  function appendInlineMarkdown(parent, text) {
    const pattern = /(`[^`]+`|\*\*[^*]+\*\*|\[[^\]]+\]\(https?:\/\/[^)]+\))/g;
    let cursor = 0;
    for (const match of text.matchAll(pattern)) {
      if (match.index > cursor)
        parent.append(document.createTextNode(text.slice(cursor, match.index)));
      const token = match[0];
      if (token.startsWith("`")) {
        const code = document.createElement("code");
        code.textContent = token.slice(1, -1);
        parent.append(code);
      } else if (token.startsWith("**")) {
        const strong = document.createElement("strong");
        strong.textContent = token.slice(2, -2);
        parent.append(strong);
      } else {
        const linkMatch = token.match(/^\[([^\]]+)\]\((https?:\/\/[^)]+)\)$/);
        if (linkMatch) {
          const link = document.createElement("a");
          link.href = linkMatch[2];
          link.target = "_blank";
          link.rel = "noopener";
          link.textContent = linkMatch[1];
          parent.append(link);
        }
      }
      cursor = match.index + token.length;
    }
    parent.append(document.createTextNode(text.slice(cursor)));
  }

  function renderChangelog(contentEl, markdown) {
    contentEl.replaceChildren();
    const lines = markdown.split(/\r?\n/);
    let list = null;
    for (const line of lines) {
      const listMatch = line.match(/^\s*[-*]\s+(.+)$/);
      if (listMatch) {
        if (!list) {
          list = document.createElement("ul");
          contentEl.append(list);
        }
        const item = document.createElement("li");
        appendInlineMarkdown(item, listMatch[1]);
        list.append(item);
        continue;
      }
      list = null;
      if (!line.trim()) continue;
      const headingMatch = line.match(/^#{1,3}\s+(.+)$/);
      const paragraph = document.createElement(headingMatch ? "h4" : "p");
      appendInlineMarkdown(
        paragraph,
        headingMatch ? headingMatch[1] : line.trim(),
      );
      contentEl.append(paragraph);
    }
  }

  // --- What's New Section Engine ---
  function getAppIconHtml(appType) {
    switch (appType) {
      case "yt":
        return `<div class="icon yt" aria-hidden="true"><svg viewBox="0 0 24 24" fill="#ff0000"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814z"/><path d="M9.545 15.568V8.432L15.818 12l-6.273 3.568Z" fill="#ffffff"/></svg></div>`;
      case "ytm":
        return `<div class="icon ytm" aria-hidden="true"><svg viewBox="0 0 24 24" fill="#ff0000"><path d="M12 0C5.376 0 0 5.376 0 12s5.376 12 12 12 12-5.376 12-12S18.624 0 12 0zm0 19.104c-3.924 0-7.104-3.18-7.104-7.104S8.076 4.896 12 4.896s7.104 3.18 7.104 7.104-3.18 7.104-7.104 7.104zm0-13.332c-3.432 0-6.228 2.796-6.228 6.228S8.568 18.228 12 18.228s6.228-2.796 6.228-6.228S15.432 5.772 12 5.772z"/><path d="m9.684 15.54 6.132-3.54-6.132-3.54v7.08Z" fill="#ffffff"/></svg></div>`;
      case "ig":
        return `<div class="icon ig" aria-hidden="true"><svg viewBox="0 0 24 24"><defs><linearGradient id="wn-ig-grad" x1="3" y1="21" x2="21" y2="3" gradientUnits="userSpaceOnUse"><stop stop-color="#ffdc80"/><stop offset=".35" stop-color="#fcaf45"/><stop offset=".65" stop-color="#e1306c"/><stop offset="1" stop-color="#833ab4"/></linearGradient></defs><rect x="2.5" y="2.5" width="19" height="19" rx="5.5" fill="url(#wn-ig-grad)"/><rect x="6.5" y="6.5" width="11" height="11" rx="3.5" fill="none" stroke="#ffffff" stroke-width="1.8"/><circle cx="12" cy="12" r="2.7" fill="none" stroke="#ffffff" stroke-width="1.8"/><circle cx="17.2" cy="6.8" r="1.1" fill="#ffffff"/></svg></div>`;
      case "gph":
        return `<div class="icon gph" aria-hidden="true"><img src="https://www.gstatic.com/images/branding/product/2x/photos_96dp.png" alt="" /></div>`;
      default:
        return `<div class="icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect width="18" height="18" x="3" y="3" rx="2"/><path d="M9 12h6m-3-3v6"/></svg></div>`;
    }
  }

  function parseChangedApps(release) {
    const apps = [];
    const body = release.body || "";
    const lines = body.split(/\r?\n/);
    const lineRegex =
      /[-*]\s*🟢\s*»\s*([^:(]+)(?:\s*\(([^)]+)\))?:\s*\[`?([^`\]]+)`?\]\((https?:\/\/[^\s)]+)\)/;

    for (const line of lines) {
      const match = line.match(lineRegex);
      if (!match) continue;

      const rawName = match[1].trim();
      const arch = (match[2] || "arm64-v8a").trim();
      const version = match[3].replace(/`/g, "").trim();
      const dlUrl = match[4].trim();

      const asset = (release.assets || []).find((a) => {
        if (a.browser_download_url === dlUrl) return true;
        if (version && a.name.includes(version)) return true;
        return false;
      });

      const size = asset ? formatBytes(asset.size) : "";

      let appType = "other";
      const lower = rawName.toLowerCase();
      if (
        lower.includes("music") ||
        lower.includes("yt music") ||
        lower.includes("yt-music")
      ) {
        appType = "ytm";
      } else if (lower.includes("youtube") || lower.includes("yt")) {
        appType = "yt";
      } else if (lower.includes("instagram") || lower.includes("piko")) {
        appType = "ig";
      } else if (lower.includes("photo") || lower.includes("gphotos")) {
        appType = "gph";
      }

      apps.push({
        name: rawName,
        arch,
        version,
        dlUrl,
        size,
        appType,
      });
    }

    if (apps.length === 0 && Array.isArray(release.assets)) {
      for (const asset of release.assets) {
        if (!asset.name.endsWith(".apk")) continue;
        const vMatch = asset.name.match(/v?([\d.]+)-arm64/);
        const version = vMatch ? vMatch[1] : "";
        let rawName = release.name || release.tag_name;
        let appType = "other";
        const lower = asset.name.toLowerCase();
        if (lower.includes("music") || lower.includes("yt-music")) {
          rawName = "YT Music";
          appType = "ytm";
        } else if (lower.includes("youtube")) {
          rawName = "YouTube";
          appType = "yt";
        } else if (lower.includes("instagram")) {
          rawName = "Instagram";
          appType = "ig";
        } else if (lower.includes("photos") || lower.includes("gphotos")) {
          rawName = "Google Photos";
          appType = "gph";
        }

        apps.push({
          name: rawName,
          arch: "arm64-v8a",
          version,
          dlUrl: asset.browser_download_url,
          size: formatBytes(asset.size),
          appType,
        });
      }
    }

    return apps;
  }

  function getReleaseBrand(rel) {
    if (!rel) return "Build";
    const tag = rel.tag_name || "";
    const match = tag.match(/^\d+[\d.]*-(.+)$/);
    const raw = match ? match[1].toLowerCase() : tag.toLowerCase();
    const brandMap = {
      "morphe": "Morphe",
      "morphe-dev": "Morphe-dev",
      "piko": "Piko",
      "piko-dev": "Piko-dev",
      "devanced": "De-vanced",
      "de-vanced": "De-vanced",
      "rushi": "Rushi",
      "hoo-dles": "Hoo-dles",
      "hooman": "Hooman",
      "paresh": "Paresh",
      "tiktok": "TikTok",
    };
    if (brandMap[raw]) return brandMap[raw];
    return raw
      .split("-")
      .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
      .join("-");
  }

  function setupWhatsNew(releases) {
    const section = document.getElementById("whats-new-section");
    if (!section || !Array.isArray(releases) || releases.length === 0) return;

    const sorted = [...releases].sort((a, b) => {
      const at = Date.parse(a.published_at || a.created_at || 0);
      const bt = Date.parse(b.published_at || b.created_at || 0);
      return bt - at;
    });

    const recentRuns = sorted.slice(0, 5);
    const runsBar = document.getElementById("wn-runs-bar");
    const brandEl = document.getElementById("wn-summary-brand");
    const sepEl = document.getElementById("wn-summary-sep");
    const tagEl = document.getElementById("wn-release-tag");
    const timeEl = document.getElementById("wn-release-time");
    const linkEl = document.getElementById("wn-release-link");
    const appsListEl = document.getElementById("wn-apps-list");
    const patchTagEl = document.getElementById("wn-patch-tag");
    const changelogContentEl = document.getElementById("wn-changelog-content");
    const expandBtn = document.getElementById("wn-expand-btn");
    const upstreamLinkEl = document.getElementById("wn-upstream-link");

    function renderRelease(rel, isLatest) {
      if (!rel) return;

      if (brandEl) {
        brandEl.textContent = getReleaseBrand(rel);
      }
      if (tagEl) {
        tagEl.textContent = rel.tag_name;
      }
      if (timeEl) {
        const timeStr = formatHoursAgo(rel.published_at || rel.created_at);
        timeEl.textContent = timeStr;
        timeEl.title = formatBuiltAt(rel.published_at || rel.created_at).trim();
        if (sepEl) sepEl.hidden = !timeStr;
      }
      if (linkEl) {
        linkEl.href =
          rel.html_url ||
          `https://github.com/mahfujarr/patchpile/releases/tag/${rel.tag_name}`;
      }

      // Changed apps
      const apps = parseChangedApps(rel);

      appsListEl.replaceChildren();

      if (apps.length === 0) {
        const emptyDiv = document.createElement("div");
        emptyDiv.className = "wn-empty";
        emptyDiv.textContent = "No APK assets recorded in this release.";
        appsListEl.append(emptyDiv);
      } else {
        apps.forEach((app) => {
          const item = document.createElement("div");
          item.className = "wn-app-item";

          const left = document.createElement("div");
          left.className = "wn-app-left";

          const iconWrapper = document.createElement("div");
          iconWrapper.innerHTML = getAppIconHtml(app.appType);
          const iconEl = iconWrapper.firstElementChild;
          if (iconEl) left.append(iconEl);

          const info = document.createElement("div");
          info.className = "wn-app-info";

          const nameEl = document.createElement("div");
          nameEl.className = "wn-app-name";
          nameEl.textContent = app.name;
          info.append(nameEl);

          const meta = document.createElement("div");
          meta.className = "wn-app-meta";

          if (app.version) {
            const vSpan = document.createElement("span");
            vSpan.className = "wn-ver";
            vSpan.textContent = "v" + app.version;
            meta.append(vSpan);
          }
          if (app.arch) {
            const aSpan = document.createElement("span");
            aSpan.textContent = app.arch;
            meta.append(aSpan);
          }
          if (app.size) {
            const sSpan = document.createElement("span");
            sSpan.textContent = "· " + app.size;
            meta.append(sSpan);
          }
          info.append(meta);
          left.append(info);
          item.append(left);

          const dlBtn = document.createElement("a");
          dlBtn.className = "wn-app-btn";
          dlBtn.href = app.dlUrl;
          dlBtn.setAttribute("target", "_blank");
          dlBtn.setAttribute("rel", "noopener");
          dlBtn.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 3v12m0 0 4-4m-4 4-4-4M5 21h14"/>
            </svg>
            <span>Download APK</span>
          `;
          item.append(dlBtn);

          appsListEl.append(item);
        });
      }

      // Changelog
      const upstream = rel.upstream_release;
      if (upstream && patchTagEl) {
        patchTagEl.textContent = "Patches: " + (upstream.tag_name || "latest");
        patchTagEl.hidden = false;
      } else if (patchTagEl) {
        patchTagEl.hidden = true;
      }

      if (upstream && upstream.html_url && upstreamLinkEl) {
        upstreamLinkEl.href = upstream.html_url;
        upstreamLinkEl.hidden = false;
      } else if (upstreamLinkEl) {
        upstreamLinkEl.hidden = true;
      }

      const notes =
        upstream?.body || rel.body || "No changelog details available.";
      renderChangelog(changelogContentEl, notes);

      // Expand button visibility check
      if (changelogContentEl) {
        changelogContentEl.classList.remove("expanded");
        if (expandBtn) {
          expandBtn.textContent = "Show more";
          expandBtn.setAttribute("aria-expanded", "false");
          if (section.open) {
            setTimeout(() => {
              if (changelogContentEl.scrollHeight > 200) {
                expandBtn.style.display = "inline-flex";
              } else {
                expandBtn.style.display = "none";
              }
            }, 60);
          } else {
            expandBtn.style.display = "none";
          }
        }
      }
    }

    // Recalculate changelog expand button when details unfolds
    section.addEventListener("toggle", () => {
      if (section.open && changelogContentEl && expandBtn) {
        setTimeout(() => {
          if (changelogContentEl.scrollHeight > 200) {
            expandBtn.style.display = "inline-flex";
          } else {
            expandBtn.style.display = "none";
          }
        }, 60);
      }
    });

    // Populate runs bar switcher
    if (runsBar) {
      runsBar.replaceChildren();
      recentRuns.forEach((rel, index) => {
        const pill = document.createElement("button");
        pill.type = "button";
        pill.className = "wn-run-pill" + (index === 0 ? " active" : "");
        pill.setAttribute("role", "tab");
        pill.setAttribute("aria-selected", String(index === 0));

        if (index === 0) {
          pill.innerHTML = `<span class="live-dot" style="width:5px;height:5px;"></span> Latest: ${rel.tag_name}`;
        } else {
          pill.textContent = `${rel.tag_name}`;
        }

        pill.addEventListener("click", () => {
          runsBar.querySelectorAll(".wn-run-pill").forEach((p) => {
            p.classList.remove("active");
            p.setAttribute("aria-selected", "false");
          });
          pill.classList.add("active");
          pill.setAttribute("aria-selected", "true");
          renderRelease(rel, index === 0);
        });

        runsBar.append(pill);
      });

      // Enable smooth drag-to-scroll on runsBar
      let isPointerDown = false;
      let startX = 0;
      let scrollLeft = 0;
      let hasDragged = false;

      runsBar.addEventListener("pointerdown", (e) => {
        if (e.pointerType === "mouse" && e.button !== 0) return;
        isPointerDown = true;
        hasDragged = false;
        startX = e.clientX;
        scrollLeft = runsBar.scrollLeft;
      });

      window.addEventListener("pointermove", (e) => {
        if (!isPointerDown) return;
        const dx = e.clientX - startX;
        if (Math.abs(dx) > 4) {
          hasDragged = true;
          runsBar.scrollLeft = scrollLeft - dx;
        }
      });

      const endPointer = () => {
        isPointerDown = false;
      };
      window.addEventListener("pointerup", endPointer);
      window.addEventListener("pointercancel", endPointer);

      // Prevent accidental pill activation when dragging/swiping
      runsBar.addEventListener(
        "click",
        (e) => {
          if (hasDragged) {
            e.preventDefault();
            e.stopPropagation();
            hasDragged = false;
          }
        },
        true,
      );
    }

    if (expandBtn && changelogContentEl) {
      expandBtn.addEventListener("click", () => {
        const isExp = changelogContentEl.classList.toggle("expanded");
        expandBtn.textContent = isExp ? "Show less" : "Show more";
        expandBtn.setAttribute("aria-expanded", String(isExp));
      });
    }

    // Initial render of latest release
    renderRelease(recentRuns[0], true);
  }

  // --- Initialize What's New Section ---
  (async () => {
    try {
      const manifest = await getLocalManifest();
      const releases = manifest?.repos?.["mahfujarr/patchpile"];
      if (Array.isArray(releases) && releases.length > 0) {
        setupWhatsNew(releases);
      }
    } catch (e) {
      console.warn("What's New section failed to initialize:", e);
    }
  })();

  // --- Independent Global Actions Timeline Execution ---
  (async () => {
    try {
      const manifest = await getLocalManifest();
      const lastSync = manifest?.actions?.last_sync;
      if (lastSync) {
        document.getElementById("last-sync-date").textContent =
          formatBuiltAt(lastSync);
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
            card
              .querySelector(".changelog-content")
              ?.replaceChildren("Release notes are unavailable right now.");
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
          card
            .querySelector(".changelog-content")
            ?.replaceChildren("No release notes are available for this build.");
          return;
        }

        updateChangelog(card, data.upstream_release || null);
        sizeEl.textContent = formatBytes(asset.size);
        sizeEl.classList.remove("skel");
        dlBtn.href = asset.browser_download_url;
        if (card.classList.contains("exp-item")) {
          const experimentalBtn = card
            .closest(".app")
            ?.querySelector(".experimental-dl-btn");
          if (experimentalBtn)
            experimentalBtn.href = asset.browser_download_url;
        }

        const vMatch = asset.name.match(/v?([\d.]+)-arm64/);
        if (vMatch) versionEl.textContent = "Ver: " + vMatch[1];

        const builtSource = asset.updated_at || data.published_at;
        if (builtEl && builtSource) {
          builtEl.textContent = "Build time: " + formatBuiltAt(builtSource);
          builtEl.classList.remove("skel");
        }

        if (card.classList.contains("gphotos-variant")) {
          card.dataset.releaseTime = data.published_at || data.created_at || "";
        }
      });
    }

    const latestGooglePhotosCard = [...googlePhotosCards]
      .filter((card) => card.dataset.releaseTime)
      .sort(
        (a, b) =>
          Date.parse(b.dataset.releaseTime) - Date.parse(a.dataset.releaseTime),
      )[0];
    if (latestGooglePhotosCard) {
      setGooglePhotosVariant(latestGooglePhotosCard.dataset.variant);
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
    refreshBtn.addEventListener("click", async () => {
      refreshBtn.innerHTML =
        '<svg style="animation: spin 1s linear infinite; display: inline-block;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><path d="M12 6v6l4 2"></path></svg>';
      refreshBtn.style.pointerEvents = "none";
      localManifest = null;
      setTimeout(() => {
        location.reload();
      }, 500);
    });
  }

  // --- ytdlnis Pipeline Setup ---
  (async () => {
    const row = document.getElementById("ytdlnis-row");
    if (!row) return;
    const versionEl = document.getElementById("ytdlnis-version");
    const linkEl = document.getElementById("ytdlnis-link");

    try {
      const manifest = await getLocalManifest();
      const data = manifest?.ytdlnis;
      if (data) {
        const asset = (data.assets || []).find((a) =>
          a.name.toLowerCase().endsWith(".apk"),
        );
        if (asset && linkEl) linkEl.href = asset.browser_download_url;
        if (data.tag_name && versionEl) {
          versionEl.textContent = ` (${data.tag_name.replace(/^v/, "v")})`;
        }
        return;
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

// --- Supabase Visitor Counter ---
(async () => {
  const counterEl = document.getElementById("visit-count");
  if (!counterEl) return;

  const hasVisited = sessionStorage.getItem("patchpile-hit");

  try {
    let count;

    if (hasVisited) {
      const { data, error } = await supabaseClient.rpc("get_views");

      if (error) throw error;

      count = data;
    } else {
      const { data, error } = await supabaseClient.rpc("increment_views");

      if (error) throw error;

      count = data;
      sessionStorage.setItem("patchpile-hit", "true");
    }

    counterEl.textContent = Number(count).toLocaleString() + " times";
  } catch (e) {
    console.error("Visitor counter error:", e);
    counterEl.textContent = "online";
  }
})();

// --- Web Push Notifications Manager ---
(function () {
  const VAPID_PUBLIC_KEY =
    "BKHQ6jfcI8aUOUHR10SH2DmKDTEz9kX9thkdzR-8ZEY462f8LMutAfe9XLcxMnFye4rCS1tZ0i3Gnx1oNy-tjmE";

  let toastTimer = null;
  function showToast(message, duration = 4500) {
    const toast = document.getElementById("notif-toast");
    if (!toast) return;
    toast.textContent = message;
    toast.classList.add("show");
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toast.classList.remove("show");
    }, duration);
  }

  function urlBase64ToUint8Array(base64String) {
    const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding)
      .replace(/-/g, "+")
      .replace(/_/g, "/");
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  }

  const notifToggle = document.getElementById("notif-toggle");

  const isSupported =
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window;

  function updateUiState(state) {
    if (state === "active") {
      notifToggle?.classList.add("active");
      notifToggle?.classList.remove("denied");
      notifToggle?.setAttribute(
        "title",
        "Release notifications active (click to turn off)",
      );
    } else if (state === "denied") {
      notifToggle?.classList.remove("active");
      notifToggle?.classList.add("denied");
      notifToggle?.setAttribute(
        "title",
        "Notifications blocked in browser settings",
      );
    } else {
      notifToggle?.classList.remove("active", "denied");
      notifToggle?.setAttribute(
        "title",
        "Turn on instant release notifications",
      );
    }
  }

  const SUPABASE_URL = "https://anikploodichlpgfymiq.supabase.co";
  const SUPABASE_KEY = "sb_publishable_r6Q5fgqVFu9TkH21jtmGjw_9MRXOYz8";

  async function syncSubscriptionToSupabase(sub) {
    if (!sub || !sub.endpoint) return;
    const subJson = typeof sub.toJSON === "function" ? sub.toJSON() : sub;
    const payload = {
      endpoint: subJson.endpoint,
      p256dh: subJson.keys?.p256dh || "",
      auth: subJson.keys?.auth || "",
      user_agent: (navigator.userAgent || "").slice(0, 200),
      updated_at: new Date().toISOString(),
    };

    // 1. Try Supabase Client if available
    const client = window.supabaseClient;
    if (client) {
      try {
        const { error } = await client
          .from("push_subscriptions")
          .upsert(payload, { onConflict: "endpoint" });
        if (!error) {
          console.log("[Push] Subscription synced to Supabase successfully.");
          return;
        }
        console.warn("[Push] Supabase SDK upsert error:", error.message);
      } catch (err) {
        console.warn("[Push] Supabase SDK exception:", err);
      }
    }

    // 2. Direct REST API upsert fallback (always works independently)
    try {
      const res = await fetch(
        `${SUPABASE_URL}/rest/v1/push_subscriptions?on_conflict=endpoint`,
        {
          method: "POST",
          headers: {
            apikey: SUPABASE_KEY,
            Authorization: `Bearer ${SUPABASE_KEY}`,
            "Content-Type": "application/json",
            Prefer: "resolution=merge-duplicates",
          },
          body: JSON.stringify(payload),
        },
      );
      if (res.ok) {
        console.log("[Push] Subscription synced via direct REST API successfully.");
      } else {
        const errBody = await res.text();
        console.error("[Push] Direct Supabase REST sync failed:", res.status, errBody);
      }
    } catch (netErr) {
      console.error("[Push] Network error syncing to Supabase:", netErr);
    }
  }

  async function deleteSubscriptionFromSupabase(endpoint) {
    if (!endpoint) return;
    const client = window.supabaseClient;
    if (client) {
      try {
        await client.from("push_subscriptions").delete().eq("endpoint", endpoint);
        return;
      } catch (_) {}
    }
    try {
      await fetch(
        `${SUPABASE_URL}/rest/v1/push_subscriptions?endpoint=eq.${encodeURIComponent(endpoint)}`,
        {
          method: "DELETE",
          headers: {
            apikey: SUPABASE_KEY,
            Authorization: `Bearer ${SUPABASE_KEY}`,
          },
        },
      );
    } catch (_) {}
  }

  // Initial passive status check - NEVER request permission on load
  if (!isSupported) {
    updateUiState("unsupported");
  } else if (Notification.permission === "denied") {
    updateUiState("denied");
  } else if (Notification.permission === "granted") {
    navigator.serviceWorker.getRegistration().then((reg) => {
      if (!reg) {
        updateUiState("inactive");
        return;
      }
      reg.pushManager.getSubscription().then(async (sub) => {
        if (sub) {
          updateUiState("active");
          // Re-sync existing subscription to Supabase so it's guaranteed to be registered!
          await syncSubscriptionToSupabase(sub);
        } else {
          updateUiState("inactive");
        }
      });
    });
  } else {
    // Permission is "default" -> keep idle/inactive. DO NOT prompt.
    updateUiState("inactive");
  }

  async function handleToggleClick() {
    if (!isSupported) {
      if (/iPhone|iPad|iPod/.test(navigator.userAgent)) {
        showToast(
          "On iOS, tap Share → 'Add to Home Screen' first to enable push notifications.",
        );
      } else {
        showToast("Push notifications are not supported in this browser.");
      }
      return;
    }

    if (Notification.permission === "denied") {
      showToast(
        "⚠️ Notifications are blocked. Please allow notifications in site permissions to receive build alerts.",
      );
      updateUiState("denied");
      return;
    }

    // Check if an existing subscription is active
    let reg;
    try {
      reg = await navigator.serviceWorker.getRegistration();
    } catch (e) {
      reg = null;
    }

    let currentSub = null;
    if (reg) {
      try {
        currentSub = await reg.pushManager.getSubscription();
      } catch (e) {
        currentSub = null;
      }
    }

    if (currentSub) {
      // User deliberately clicked to turn notifications OFF
      try {
        const endpoint = currentSub.endpoint;
        await currentSub.unsubscribe();
        localStorage.setItem("patchpile-notif-enabled", "false");
        updateUiState("inactive");
        showToast("🔕 Release notifications turned off.");
        await deleteSubscriptionFromSupabase(endpoint);
      } catch (e) {
        console.error("Error unsubscribing:", e);
        showToast("Could not unsubscribe: " + e.message);
      }
      return;
    }

    // User deliberately clicked to turn notifications ON -> Request permission now!
    try {
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        if (permission === "denied") {
          updateUiState("denied");
          showToast(
            "Notifications blocked. You can re-enable them in browser settings.",
          );
        } else {
          updateUiState("inactive");
        }
        return;
      }

      // Permission granted! Register SW if not already registered
      if (!reg) {
        reg = await navigator.serviceWorker.register("./sw.js");
      }
      const readyReg = await navigator.serviceWorker.ready;

      // Clean up any stale subscription before subscribing
      try {
        const existingSub = await readyReg.pushManager.getSubscription();
        if (existingSub) {
          await existingSub.unsubscribe();
        }
      } catch (_) {}

      // Subscribe to Web Push
      const appServerKey = urlBase64ToUint8Array(VAPID_PUBLIC_KEY);
      const newSub = await readyReg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: appServerKey,
      });

      localStorage.setItem("patchpile-notif-enabled", "true");
      updateUiState("active");
      showToast(
        "🔔 Notifications enabled! You'll be notified instantly when new builds are published.",
      );

      // Instant device confirmation notification
      try {
        await readyReg.showNotification("🔔 Patchpile Notifications Active", {
          body: "Instant alerts are ready! You'll be notified when new APK builds are published.",
          icon: "./assets/favicon.svg",
          badge: "./assets/favicon.svg",
          tag: "patchpile-welcome",
        });
      } catch (e) {}

      // Sync subscription to Supabase
      await syncSubscriptionToSupabase(newSub);
    } catch (err) {
      console.error("Failed to enable push notifications:", err);
      const errStr = String(err?.message || err);

      let isBrave = false;
      try {
        isBrave =
          Boolean(navigator.brave) &&
          typeof navigator.brave.isBrave === "function" &&
          (await navigator.brave.isBrave());
      } catch (_) {}

      if (
        isBrave &&
        (errStr.includes("push service error") ||
          errStr.includes("Registration failed"))
      ) {
        showToast(
          "🦁 Brave blocks push messaging by default. Open brave://settings/privacy, enable 'Use Google services for push messaging', and relaunch Brave.",
          9000,
        );
      } else if (
        errStr.includes("push service error") ||
        errStr.includes("Registration failed")
      ) {
        showToast(
          "⚠️ Push service unreachable. Check if an ad blocker or VPN blocks Google FCM.",
          8000,
        );
      } else {
        showToast("Could not enable notifications: " + errStr);
      }
      updateUiState("inactive");
    }
  }

  if (notifToggle) {
    notifToggle.addEventListener("click", handleToggleClick);
  }
})();
