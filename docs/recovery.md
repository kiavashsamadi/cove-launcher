# Recovery

Keep the Bixby package installed while it hosts Cove. Do not include it in app
cleanup or a debloat list. Keep Samsung Settings, Device Care, HDMI/CEC/eARC,
audio, networking, Bluetooth, accessibility, account/security and panel care
available.

## Renderer

Before an update, preserve the current renderer and original carrier files, record
their hashes, and prepare a scoped inverse. Recovery must match the actual
installed generation and container. Do not apply an old transaction to a deleted
or reinstalled package.

If a renderer regression occurs, inspect the installation receipt and cleanup
state, then use that generation's approved inverse to restore its retained build.
If the carrier is missing, reinstall it through Samsung Apps before preparing a
freshly verified renderer/Home repair. A backup of installed files is not assumed
to be a complete Samsung-accepted installer.

Brightness changes and scope selections can intentionally change saved picture settings.
A renderer rollback does not revert those choices. Preserve the prior brightness
for each input, mode and SDR/HDR context; never restore all presets from an old
snapshot to undo one adjustment.

Shared profile memories use a separate versioned file. Keep both that file and
the earlier per-context file during renderer rollback; the old renderer reads
its original format. Renderer recovery does not delete either file or translate
new shared levels back into every old context.

## Privacy changes

App-registration changes use native enable inverses in reverse applied order,
with guards against unrelated registry changes. The PISA/adagent inverse removes
only the transaction-owned startup marker, identified by its protected recovery
anchor and receipt. Removal can activate the native PISA path watcher; adagent
may need a normal restart.

Exact executors, original files and recovery receipts remain private and local.
Do not restore a whole live database from an old snapshot, clear app data, bypass
signature checks, flash firmware or modify partitions as a recovery shortcut.
If a command times out, inspect its receipt and process state before retrying.

After recovery, verify Home, Settings, Back, normal HDMI picture/sound and saved
presets. Remote recovery requires working local access; no zero-risk guarantee
or hardware recovery image is provided.

The input-following update keeps the shared v2 profile format. Its renderer
rollback preserves customized numbers and intentional native brightness choices.
Installation and rollback never reset the entire picture database.
