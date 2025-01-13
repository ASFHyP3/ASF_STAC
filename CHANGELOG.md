# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.8]
### Added
- Add `mypy` to [`static-analysis`](.github/workflows/static-analysis.yml)

## [0.3.7]
### Fixed
- Remove the [Context extension](https://github.com/stac-api-extensions/context), which is no longer supported as of [stac-fastapi v3.0.0](https://github.com/stac-utils/stac-fastapi/blob/main/CHANGES.md#300---2024-07-29). Our previous release (v0.3.6) upgraded the `stac-fastapi.pgstac` dependency from `2.5.0` to `3.0.1` without removing the Context extension, which caused https://stac.asf.alaska.edu to return `Internal Server Error`.

## [0.3.6]
### Changed
- The [`static-analysis`](.github/workflows/static-analysis.yml) Github Actions workflow now uses `ruff` rather than `flake8` for linting.

## [0.3.5]
### Changed
- Dependency upgrades.

## [0.3.4]
### Changed
- HAND license changed to CC0 from CCBy 4.0 in `collections/glo-30-hand/glo-30-hand.json` to match NASA data publishing guidelines.

## [0.3.3]
### Changed
- Updated GitHub actions to use `setup-micromamba` instead of `setup-miniconda`
- Version upgrades for python dependencies and `ASFHyP3/actions`

## [0.3.2]
### Added
- Added a "related" link to the associated Copernicus DEM tile for every HAND item

## [0.3.1]
### Security
- Removed Transaction endpoints from the publicly available API, though create/update/delete permissions were already
  restricted at the database layer.

## [0.3.0]
### Added
- Created a STAC item collection for the `glo-30-hand` dataset.

## [0.2.0]
### Added
- Created a STAC item collection for the `sentinel-1-global-coherence` dataset.
### Changed
- Improved API performance by increasing database instance size and storage type.

## [0.1.0]
### Added
- Initial release of STAC API endpoint backed by a PostgreSQL database
