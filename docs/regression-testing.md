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
| Manager-owned DNS recovery | `test_dns_manager.py`: ten-case coverage, exact 239-query evidence, manager controls, ownership, cleanup and explicit privilege limitations | Original matrix retained with its group limitation; stronger qualification is separate |
| Restricted DNS worker and native inverse | `test_dns_confinement.py`: exact permissions, case/query coverage, conflict/interruption proofs, independent inverse, cgroup ownership, cleanup and deployment boundaries | Eight strict-worker cases, a 60-assertion native inverse and two 28-assertion independent deadline inverses passed; live deployment remains unqualified |
| DNS rule-controller loss and native replay | `test_dns_controller_loss.py`: automatic native cleanup, backup deadlines, rule/process ownership, retained TCP reset, capture accounting and transport matrix | Rule-controller loss and limited native lookup/replay passed; complete-agent loss has a separate checker, while background-app compatibility remains unresolved |
| Native DNS TCP reconnect | `test_dns_native_retry.py`: exact call order, native errors, socket reuse/reconnect and inherited preservation gates | Eight native libc calls passed; first-call recovery does not qualify every application |
| Native NSS fallback | `test_dns_nss.py`: resolver-view framing, IPv4/IPv6 and UDP/TCP cases, blocked/allowed answers, native identity and explicit group limitation | Twelve isolated native lookup cases passed; ordinary apps and production client confinement remain separate |
| Complete diagnostic-agent loss | `test_dns_session_loss.py`: signal exit, pending process ledger, independent witness, partial primary failure, backup, strict log parsing and later host preservation | Agent/callback loss and combined fault passed; physical PC, kernel/manager and power loss remain separate |
| Client-scoped DNS recovery | `test_dns_owned_loss.py`: child-group ownership, nonmember preservation, restricted helper membership, exact scoped rules and complete inverse evidence | Isolated agent-loss/partial-primary recovery passed; 48 exact-script failure cases passed separately |
| Live-network owned-client recovery | `test_dns_owned_host.py`: explicit scope, unchanged renderer, independent host readback, exact reconciliation provenance, quoted rule values and refusal of missing fault/cleanup evidence | Owned clients recovered after complete controller loss and interrupted primary inverse; ordinary apps were excluded. The original parser-stop receipt remains immutable; separate reconciliation completes the proof. Permanent filtering remains unqualified |
| Native lookups through a real-upstream filter | `test_dns_native_live.py`: exact transport/block matrix, private resolver fingerprint, empty-group identity, native answers and preservation | Eight bounded native client cases passed; ordinary-app interception and durable deployment remain unqualified |
| DNS transaction recovery model | `test_dns_recovery_model.py`: ten interruption points, idempotent inverse, foreign changes before/between steps, unrelated-rule preservation and dead-worker recovery | In-memory DNS-setting model; the separate native interception inverse leaves DNS settings intact. Durable deployment remains unqualified |
| Passive DNS observation and bounded replay | `test_dns_passive.py`, `test_dns_passive_replay.py`: strict scope/permissions, aggregate accounting, paired runtime logs, empty samples, response/transport coverage, cleanup and separate preservation reads | A passive sample observed two background questions; a later replay sample observed none. No ordinary app was redirected; empty coverage does not qualify compatibility |
| Boot-peer recovery model | `test_dns_boot_recovery.py`: every modeled operation interrupted, repeated boots, fresh acknowledgment, stale/reused tokens, owner changes and untrusted journals | Assumes atomic durable authenticated preparation and conditional writes. These primitives and startup recovery are not qualified on the TV; model never executes TV operations |
| Saved tuning, Home/startup and recovery preservation | Transaction-policy/registry tests and private before/after comparisons | Exact current backups and scoped recovery must accompany an installation |
| Public export, UTF-8 and offline renderer/preview | Export scan, browser external-request assertions and repository review | Inspect screenshots and Git history before publishing; pattern scans alone are insufficient |

Regression coverage is organized by behavior, not a claim of 100% code or
hardware coverage. Adding a feature requires extending the relevant test suite
and this matrix. A skipped, unavailable or guard-stopped native test must be
reported separately from a pass. Hardware/visual limits are tracked in
[validation](remaining-validation.md).
