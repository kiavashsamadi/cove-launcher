# References

External projects inform design and investigation; their scripts are not portable
instructions for this firmware.

| Resource | Relevant use | Boundary |
| --- | --- | --- |
| [Samsung Tizen debloat guide](https://github.com/ardazeytin/samsung-tizen-tv-debloat) | Package classification and stock SDB constraints | Its worked model and Tizen version differ |
| [Tizen root debloat notes](https://github.com/DemonKingSwarn/samsung-tv-tizen-root/blob/main/docs/DEBLOAT.md) | Native deactivation and startup-condition patterns | Inspect exact units and inverses; do not transplant bulk removals or watchdogs |
| [AeroTizen](https://github.com/helalaou/AeroTizen) | Startup, visibility-aware refresh and Home handoff | Regional firmware and architecture assumptions still require verification |
| [Samsung TV tools](https://github.com/invaliddayta/samsung-tv-tools) | Update policies, app-restoration controls and DNS filtering research | Reviewed at `ddc9035d0c7d35653ff51e5b7b3065248a396916`; successful root or screenshot reports do not qualify its cleanup scripts on another build |
| [Tizen application information](https://samsung.github.io/TizenFX/API9/api/Tizen.Applications.ApplicationInfo.html) | Installed-app metadata | Metadata is not proof of runtime activation behavior |

DNS blocklists and community service names are investigation leads, not proof of
complete egress control or safe removal. Exact-device evidence and preservation
requirements take precedence.
