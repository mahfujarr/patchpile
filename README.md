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
