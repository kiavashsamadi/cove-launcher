# Regression testing

Run the complete offline suite before shipping a renderer change:

```sh
python scripts/check.py --browser
```

It needs Python, the .NET 6 SDK, Node.js and Playwright. Install the browser tools
with `npm install --no-save --package-lock=false playwright@1.62.1`, then
`npx playwright install chromium`. `--dotnet` and `--node` accept local executable
paths. `PYTHON` selects the preview server's interpreter; `BROWSER_CHANNEL` can
select an already installed supported browser. Add `--framework-dir` for native
compilation with matching local Samsung assemblies.

The same offline command runs on pushes and pull requests. CI has read-only
repository permissions, uses pinned action commits, has no TV access and receives
no TV credentials, proprietary assemblies, operational logs or backups. Reports
and browser captures stay in ignored `artifacts/` locally. Native checks require
separate private deployment tooling and an exact firmware match.

## Feature coverage

| Shipped behavior | Repeatable regression coverage | Native/hardware boundary |
| --- | --- | --- |
| Connected HDMI cards; empty/partial reports; unplug/replug | `SourceChecks`, `HotplugChecks`, browser input simulation | Physical cable edges depend on Samsung's reporting; cannot be reproduced by selecting another input |
| Sleeping devices, unknown names and device artwork | `SourceChecks`, presentation checks, browser checks | A detected name is not proof that a console is awake |
| Hidden inventory updates and warm first frame | `SourceChecks` notification/coalescing/disposal; `HotplugChecks`; lifecycle checks | Native callback registration and UI navigation checked separately; app reclamation requires a fresh launch |
| Input selection and current-input indicator | Controls, presentation, real-window lifecycle and browser checks | Check source acceptance and actual viewer return on the TV |
| Sound-system shortcut, HDMI/eARC label and focus removal | Source, hotplug/lifecycle and browser checks | Verify native Sound destination; capability label is not an audio-format measurement |
| Cog opens Settings; Settings stays open; Back returns | Real-window lifecycle and browser checks | Native application/foreground checks; physical audio remains a separate observation |
| Home, repeated Back, hover independence and return fallback | `BackChecks`, lifecycle loops, cancellation and activation tests | Native compositor/remote timing cannot be proved by host simulation |
| Full Exit, low-memory cleanup and subscription teardown | Real-window lifecycle checks and monitor-disposal checks | OS process reclaim and full power loss are separate cases |
| Live brightness, limits, coalescing and failure handling | `BrightnessChecks`, observation checks, lifecycle and browser tests | Native setters and exact source/mode/scope readback require private guarded checks |
| Bright/Dim memory shared across inputs and picture modes | `ProfileChecks`, lifecycle and browser checks | Runtime readback must preserve the owner's latest choice |
| Current source / All sources; unavailable Game Mode scope | Brightness/profile policy tests, lifecycle and browser tests | Samsung's broader scope effects are not inferred from UI success |
| Explicit profile follows a different Cove card | `InputBrightnessChecks`, observation and lifecycle tests, browser checks | Test only with a stable awake signal; no physical signal is fabricated |
| External source/mode/brightness changes; provisional zero | Observation/sampling tests, lifecycle and browser tests | A naturally changing SDR/HDR signal is not automatically a regression |
| Atomic profile persistence, corrupt data and migration | `ProfileChecks` filesystem/error cases | Full restart and AC loss remain separate hardware coverage |
| Exact-build startup and bounded control protocol | Bootstrap and control-envelope tests | Another firmware requires independent qualification |
| Privacy app flags, scoped inverse and PISA/adagent receipts | Python policy, registry-diff and receipt-verifier tests | Read flags/process/unit state on TV; these do not prove all telemetry is absent |
| Automatic-update policy receipts | `test_update_policy.py`: exact keys/types, enabled or pending values, incomplete reads and cleanup | Fresh native readback passed after a confirmed new boot; future firmware needs requalification |
| Offline DNS review preparation | `test_network_policy.py`: explicit scope, input bounds/injection, shared-parent rejection, private paths and preserving previous reviews | Syntax-only resolver acceptance does not prove DNS response behavior, enforcement, compatibility or recovery |
| Isolated DNS response/recovery evidence | `test_dns_trial.py`: exact response coverage, failed supervisor recovery, scoped cleanup, original-file preservation, contradictory receipts and bounded private input | 233 native response checks passed; automatic supervisor-loss recovery failed safely. Production routing and persistence remain unqualified |
| Saved tuning, Home/startup and recovery preservation | Transaction-policy/registry tests and private before/after comparisons | Exact current backups and scoped recovery must accompany an installation |
| Public export, UTF-8 and offline renderer/preview | Export scan, browser external-request assertions and repository review | Inspect screenshots and Git history before publishing; pattern scans alone are insufficient |

Regression coverage is organized by behavior, not a claim of 100% code or
hardware coverage. Adding a feature requires extending the relevant test suite
and this matrix. A skipped, unavailable or guard-stopped native test must be
reported separately from a pass. Hardware/visual limits are tracked in
[validation](remaining-validation.md).
