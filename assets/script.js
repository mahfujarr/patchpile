// --- Theme Handling Control ---
(function () {
    const root = document.documentElement;
    const toggle = document.getElementById('theme-toggle');
    const metaTheme = document.querySelector('meta[name="theme-color"]');

    function applyMetaColor(theme) {
        metaTheme.setAttribute('content', theme === 'dark' ? '#08111f' : '#f7f7f7');
    }
    applyMetaColor(root.getAttribute('data-theme'));

    toggle.addEventListener('click', () => {
        const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        root.setAttribute('data-theme', next);
        localStorage.setItem('patchpile-theme', next);
        applyMetaColor(next);
    });
})();

// --- Release Management and APIs ---
(function () {
    const releaseCards = document.querySelectorAll('[data-repo][data-patch-source][data-asset-match]');

    setTimeout(() => {
        const el = document.getElementById('last-sync-date');
        if (el && el.textContent === 'checking…') el.textContent = 'see GitHub';
    }, 6000);

    function formatBytes(bytes) {
        if (!bytes) return '';
        return ('Size: ' + (bytes / (1024 * 1024)).toFixed(1) + ' MB');
    }

    function formatBuiltAt(iso) {
        const d = new Date(iso);
        if (isNaN(d.getTime())) return 'recent';
        const datePart = d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }).replace(',', '');
        const timePart = d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
        return ` ${timePart}, ${datePart}`;
    }

    async function getReleasesList(repo) {
        const res = await fetch(`https://api.github.com/repos/${repo}/releases?per_page=30`);
        if (!res.ok) throw new Error('rate limited or context missing');
        return res.json();
    }

    function pickLatestMatchingRelease(releases, patchSource) {
        return (releases || [])
            .filter(r => !r.draft && r.tag_name && r.tag_name.endsWith(`-${patchSource}`))
            .sort((a, b) => {
                const aTime = Date.parse(a.published_at || a.created_at || 0);
                const bTime = Date.parse(b.published_at || b.created_at || 0);
                return bTime - aTime;
            });
    }

    function pickApkAsset(release, match) {
        if (!release) return null;
        const assets = release.assets || [];
        const normalized = String(match || '').toLowerCase();
        return assets.find(a => {
            const name = String(a.name || '').toLowerCase();
            return name.endsWith('.apk') && name.includes(normalized);
        }) || null;
    }

    // --- Independent Global Actions Timeline Execution ---
    (async () => {
        try {
            const res = await fetch(`https://api.github.com/repos/mahfujarr/patchpile/actions/workflows/ci.yml/runs?per_page=1`);
            if (res.ok) {
                const data = await res.json();
                if (data.workflow_runs && data.workflow_runs[0]) {
                    document.getElementById('last-sync-date').textContent = formatBuiltAt(data.workflow_runs[0].updated_at);
                }
            }
        } catch (e) { }
    })();

    // --- Application Release Mapping Engine ---
    (async () => {
        const repoGroups = {};
        releaseCards.forEach(card => {
            const repo = card.dataset.repo;
            (repoGroups[repo] = repoGroups[repo] || []).push(card);
        });

        for (const [repo, group] of Object.entries(repoGroups)) {
            let releases;
            try {
                releases = await getReleasesList(repo);
            } catch (e) {
                group.forEach(card => {
                    card.querySelector('.f-size')?.remove();
                    card.querySelector('.f-built')?.remove();
                });
                continue;
            }

            group.forEach(card => {
                const patchSource = card.dataset.patchSource;
                const match = card.dataset.assetMatch;
                const sizeEl = card.querySelector('.f-size');
                const dateEl = card.querySelector('.f-date');
                const builtEl = card.querySelector('.f-built');
                const versionEl = card.querySelector('.v-num');
                const dlBtn = card.querySelector(':scope > .dl-btn') || card.querySelector('.dl-btn');

                const matchedReleases = pickLatestMatchingRelease(releases, patchSource);
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
                    sizeEl?.remove();
                    dateEl?.remove();
                    builtEl?.remove();
                    return;
                }

                sizeEl.textContent = formatBytes(asset.size);
                sizeEl.classList.remove('skel');
                dlBtn.href = asset.browser_download_url;

                const vMatch = asset.name.match(/v?([\d.]+)-arm64/);
                if (vMatch) versionEl.textContent = 'Ver: ' + vMatch[1];

                const builtSource = asset.updated_at || data.published_at;
                if (builtEl && builtSource) {
                    builtEl.textContent = 'Build time: ' + formatBuiltAt(builtSource);
                    builtEl.classList.remove('skel');
                }
            });
        }
    })();

    // --- MicroG Pipeline Setup ---
    (async () => {
        const row = document.getElementById('microg-row');
        if (!row) return;
        const repo = row.dataset.repo;
        const versionEl = document.getElementById('microg-version');
        const linkEl = document.getElementById('microg-link');

        try {
            const res = await fetch(`https://api.github.com/repos/${repo}/releases/latest`);
            if (!res.ok) throw new Error('restricted');
            const data = await res.json();

            const asset = (data.assets || []).find(a => a.name.toLowerCase().endsWith('.apk'));
            if (asset && linkEl) {
                linkEl.href = asset.browser_download_url;
            }
            if (data.tag_name && versionEl) {
                versionEl.textContent = ` (${data.tag_name.replace(/^v/, 'v')})`;
            }
        } catch (e) { }
    })();
})();

// --- Pure Text Visitor Counter Engine ---
(async () => {
    const counterEl = document.getElementById('visit-count');
    if (!counterEl) return;

    const hasVisited = sessionStorage.getItem('patchpile-hit');
    // const hasVisited = localStorage.getItem('patchpile-hit');
    const endpoint = hasVisited ? 'get' : 'hit';

    try {
        const res = await fetch(`https://countapi.mileshilliard.com/api/v1/${endpoint}/patchpile_live`);
        if (res.ok) {
            const data = await res.json();
            if (data && typeof data.value !== 'undefined') {
                counterEl.textContent = data.value.toLocaleString() + " times";
                sessionStorage.setItem('patchpile-hit', 'true');
                // localStorage.setItem('patchpile-hit', 'true');
                return;
            }
        }
        counterEl.textContent = 'active';
    } catch (e) {
        counterEl.textContent = 'online';
    }
})();