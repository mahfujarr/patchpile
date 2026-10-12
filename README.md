# patchpile

This repository is a personal fork of the excellent work by [nvbangg](https://github.com/nvbangg) and the upstream contributors. It has been modified primarily for my own personal use to automate builds, publish releases, and power my download page.

This repository mainly contains my personal configuration, branding, and GitHub Actions workflow.

## What I have changed

- Personal build configuration (`config.toml`)
- Automated GitHub Actions workflow
- Automated release publishing
- Static download site integration
- Personal app branding and icons
- APK builds for my own devices

The actual patching logic and most of the implementation come from the upstream projects.

### Upstream

This repository is based primarily on:

- [nvbangg/builder-for-morphe](https://github.com/nvbangg/builder-for-morphe) — the build system and automation foundation
- [krvstek/uni-apks](https://github.com/krvstek/uni-apks) — the original `uni-apks` project and its build-system lineage
- [j-hc/revanced-magisk-module](https://github.com/j-hc/revanced-magisk-module) — the earlier project that `uni-apks` was derived from

The current build system is based on `builder-for-morphe`, which itself incorporates work from the `uni-apks` project and its contributors.

### Build configuration

The applications and patch sources used by this repository are defined in `config.toml`.

Current patch-source mapping:

| App                       | Patch source                                                                  |
| ------------------------- | ----------------------------------------------------------------------------- |
| YouTube                   | [MorpheApp/morphe-patches](https://github.com/MorpheApp/morphe-patches)       |
| YouTube Music             | [MorpheApp/morphe-patches](https://github.com/MorpheApp/morphe-patches)       |
| Instagram                 | [crimera/piko](https://github.com/crimera/piko)                               |
| Google Photos             | [rushiranpise/morphe-patches](https://github.com/rushiranpise/morphe-patches) |
| Google Photos (`GPhotos`) | [RookieEnough/De-Vanced](https://github.com/RookieEnough/De-Vanced)           |

The configuration also applies personal branding, icons, package-name options, and other build-specific settings.

### Auto-Updating via Obtainium

You can automatically track and update all patched apps directly on your Android device using [Obtainium](https://github.com/ImranR98/Obtainium).

Click or tap any badge below from your Android device to add the app variant directly to Obtainium with a single click:

| Application | Build Variant | Patch Source | Add to Obtainium |
| :--- | :--- | :--- | :--- |
| **YouTube** | Stable | `morphe` | [![Add to Obtainium](https://img.shields.io/badge/Add%20to-Obtainium-4A154B?style=for-the-badge&logo=android&logoColor=white)](https://mahfujarr.me/patchpile?obtainium=youtube-stable) |
| **YouTube** | Experimental | `morphe-dev` | [![Add to Obtainium](https://img.shields.io/badge/Add%20to-Obtainium-4A154B?style=for-the-badge&logo=android&logoColor=white)](https://mahfujarr.me/patchpile?obtainium=youtube-experimental) |
| **YouTube Music** | Stable | `morphe` | [![Add to Obtainium](https://img.shields.io/badge/Add%20to-Obtainium-4A154B?style=for-the-badge&logo=android&logoColor=white)](https://mahfujarr.me/patchpile?obtainium=yt-music-stable) |
| **YouTube Music** | Experimental | `morphe-dev` | [![Add to Obtainium](https://img.shields.io/badge/Add%20to-Obtainium-4A154B?style=for-the-badge&logo=android&logoColor=white)](https://mahfujarr.me/patchpile?obtainium=yt-music-experimental) |
| **Instagram** | Stable | `piko` | [![Add to Obtainium](https://img.shields.io/badge/Add%20to-Obtainium-4A154B?style=for-the-badge&logo=android&logoColor=white)](https://mahfujarr.me/patchpile?obtainium=instagram-stable) |
| **Instagram** | Experimental | `piko-dev` | [![Add to Obtainium](https://img.shields.io/badge/Add%20to-Obtainium-4A154B?style=for-the-badge&logo=android&logoColor=white)](https://mahfujarr.me/patchpile?obtainium=instagram-experimental) |
| **Google Photos** | Unlimited Backup | `rushi` | [![Add to Obtainium](https://img.shields.io/badge/Add%20to-Obtainium-4A154B?style=for-the-badge&logo=android&logoColor=white)](https://mahfujarr.me/patchpile?obtainium=photos-rushi) |
| **Google Photos** | De-Vanced | `devanced` | [![Add to Obtainium](https://img.shields.io/badge/Add%20to-Obtainium-4A154B?style=for-the-badge&logo=android&logoColor=white)](https://mahfujarr.me/patchpile?obtainium=photos-devanced) |

> [!TIP]
> Tapping a badge routes via [mahfujarr.me/patchpile](https://mahfujarr.me/patchpile) to automatically trigger the `obtainium://app/...` deep link on your Android device.

<details>
<summary><b>📋 Manual Configuration JSONs (Click to expand)</b></summary>

If you prefer importing configurations manually into Obtainium, copy the corresponding JSON below:

**YouTube (Stable)**
```json
{"id":"com.google.android.youtube","url":"https://github.com/mahfujarr/patchpile","author":"mahfujarr","name":"YouTube (Stable)","additionalSettings":"{\"includePrereleases\":false,\"fallbackToOlderReleases\":true,\"filterReleaseTitlesByRegEx\":\"-morphe$\",\"apkFilterRegEx\":\"youtube.*arm64\",\"autoApkFilterByArch\":true}"}
```

**YouTube (Experimental)**
```json
{"id":"com.google.android.youtube","url":"https://github.com/mahfujarr/patchpile","author":"mahfujarr","name":"YouTube (Experimental)","additionalSettings":"{\"includePrereleases\":true,\"fallbackToOlderReleases\":true,\"filterReleaseTitlesByRegEx\":\"-morphe-dev$\",\"apkFilterRegEx\":\"youtube.*arm64\",\"autoApkFilterByArch\":true}"}
```

**YT Music (Stable)**
```json
{"id":"com.google.android.apps.youtube.music","url":"https://github.com/mahfujarr/patchpile","author":"mahfujarr","name":"YT Music (Stable)","additionalSettings":"{\"includePrereleases\":false,\"fallbackToOlderReleases\":true,\"filterReleaseTitlesByRegEx\":\"-morphe$\",\"apkFilterRegEx\":\"yt-music.*arm64\",\"autoApkFilterByArch\":true}"}
```

**YT Music (Experimental)**
```json
{"id":"com.google.android.apps.youtube.music","url":"https://github.com/mahfujarr/patchpile","author":"mahfujarr","name":"YT Music (Experimental)","additionalSettings":"{\"includePrereleases\":true,\"fallbackToOlderReleases\":true,\"filterReleaseTitlesByRegEx\":\"-morphe-dev$\",\"apkFilterRegEx\":\"yt-music.*arm64\",\"autoApkFilterByArch\":true}"}
```

**Instagram (Stable)**
```json
{"id":"com.instagram.android","url":"https://github.com/mahfujarr/patchpile","author":"mahfujarr","name":"Instagram (Stable)","additionalSettings":"{\"includePrereleases\":false,\"fallbackToOlderReleases\":true,\"filterReleaseTitlesByRegEx\":\"-piko$\",\"apkFilterRegEx\":\"instagram.*arm64\",\"autoApkFilterByArch\":true}"}
```

**Instagram (Experimental)**
```json
{"id":"com.instagram.android","url":"https://github.com/mahfujarr/patchpile","author":"mahfujarr","name":"Instagram (Experimental)","additionalSettings":"{\"includePrereleases\":true,\"fallbackToOlderReleases\":true,\"filterReleaseTitlesByRegEx\":\"-piko-dev$\",\"apkFilterRegEx\":\"instagram.*arm64\",\"autoApkFilterByArch\":true}"}
```

**Google Photos (Rushi)**
```json
{"id":"com.google.android.apps.photos","url":"https://github.com/mahfujarr/patchpile","author":"mahfujarr","name":"Google Photos (Rushi)","additionalSettings":"{\"includePrereleases\":false,\"fallbackToOlderReleases\":true,\"filterReleaseTitlesByRegEx\":\"-rushi$\",\"apkFilterRegEx\":\"google-photos.*arm64\",\"autoApkFilterByArch\":true}"}
```

**Google Photos (De-Vanced)**
```json
{"id":"com.google.android.apps.photos","url":"https://github.com/mahfujarr/patchpile","author":"mahfujarr","name":"Google Photos (De-Vanced)","additionalSettings":"{\"includePrereleases\":false,\"fallbackToOlderReleases\":true,\"filterReleaseTitlesByRegEx\":\"-devanced$\",\"apkFilterRegEx\":\"gphotos.*arm64\",\"autoApkFilterByArch\":true}"}
```

</details>

### Purpose

This repository exists solely to build APKs for my own personal use.

If you want to build your own patched applications, please use the upstream projects and patch sources directly, or fork the relevant upstream repository instead of relying on this personal fork.

### Credits

- [nvbangg](https://github.com/nvbangg) — `builder-for-morphe`
- [krvstek](https://github.com/krvstek) — `uni-apks`
- [j-hc](https://github.com/j-hc) — original build-system foundation
- [MorpheApp](https://github.com/MorpheApp) — Morphe and Morphe Patches
- [crimera](https://github.com/crimera) — Piko
- [RookieEnough](https://github.com/RookieEnough) — De-Vanced
- [rushiranpise](https://github.com/rushiranpise) — Google Photos Morphe patches
- [MorpheApp/morphe-patches](https://github.com/MorpheApp/morphe-patches) — Morphe patch framework and patches
- [MorpheApp/MicroG-RE](https://github.com/MorpheApp/MicroG-RE) — GmsCore fork used by the Morphe ecosystem where applicable
- All other upstream developers and contributors whose code is incorporated into the projects above

Without their work, **patchpile would not exist**.

### Disclaimer

This repository is an unofficial personal fork and is **not affiliated with, endorsed by, or operated by** Morphe or any of the upstream developers and projects mentioned above.

The APKs and build artifacts produced by this repository are provided for my own personal use. Users should obtain original applications from their respective legitimate sources and comply with the licenses and terms applicable to each upstream project and application.
