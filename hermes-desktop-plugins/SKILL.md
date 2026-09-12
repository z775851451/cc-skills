---
name: hermes-desktop-plugins
description: "Build Hermes desktop plugins. SDK sources, area schemas."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [macos, linux, windows]
metadata:
  hermes:
    tags: [hermes, desktop, plugin, electron, sdk, ui, statusbar, pane, palette, keybind, theme]
    homepage: https://hermes-agent.nousresearch.com/docs/
    related_skills: [hermes-agent, hermes-desktop-self-help, inspecting-hermes-desktop-dom]
    requires_tools: [terminal, write_file, patch, search_files, read_file]
---

# Hermes Desktop Plugin Development

Build plugins for the Electron Hermes desktop app. A plugin is a single plain-JS ESM file the app loads at runtime — no build step, no repo changes, hot-reloads on save.

The hub skill `hermes-agent` ships a comprehensive `references/desktop-plugins.md` with the full API surface and procedure. This skill is the **fast-path workflow** on top of that reference: which SDK source files to grep, how to find the real area name and payload schema, and the gotchas that bite when you actually try to ship.

## 60-second version

1. **Start from the template** at `~/.hermes/skills/autonomous-ai-agents/hermes-agent/templates/plugin.js`. It is a statusbar chip + a side pane already wired — strip what you don't need.
2. **Save as** `~/.hermes/desktop-plugins/<id>/plugin.js` — the **folder name MUST equal the plugin `id`** (declared on the default export).
3. **In the app**: ⌘K → "Reload desktop plugins". A toast confirms load or names the error.
4. **Disable / uninstall** in Settings → Plugins (state persists across restarts; don't fight it).

Under a named profile, the path becomes `~/.hermes/profiles/<profile>/desktop-plugins/<id>/plugin.js`. Never hardcode `~/.hermes` in the plugin itself — paths are resolved by the loader.

## Always-on rules

- **Don't guess area names or payload schemas from prose docs — grep the SDK source.** The `desktop-plugins.md` reference shows the high-level picture; the truth lives in `apps/desktop/src/`. `PaletteContribution`, `StatusbarItem`, etc. are TypeScript interfaces in source. The literal `palettes` vs `palette` discrepancy cost a write cycle this session; the source is the only place the real string lives.
- **Imports are uncompiled ESM.** UI is `jsx('div', { children: ... })` calls from `react/jsx-runtime`, NOT JSX syntax. The file loads as ESM in the renderer. Only `@hermes/plugin-sdk`, `react`, and `react/jsx-runtime` resolve — other specifiers fail.
- **The `Cannot use import statement outside a module` lint error is a false positive** for plugin files. The plugin linter runs as CJS; the file is loaded as ESM. Ignore it — the on-disk write still succeeds when the tool result shows `verified: true`.
- **Theme variables only — no hardcoded colors.** Use `var(--ui-text-tertiary)`, `var(--ui-accent)`, `var(--ui-stroke-secondary)`, `var(--ui-surface-2)`, etc. Tailwind tokens like `text-amber-400` work for status colors but lose theming on pane backgrounds.
- **Live state in components → `useValue(atom)`.** In handlers → `atom.get()` (handlers are not in the React tree). Reading from render closures gives stale values on rapid events.
- **Keep components small.** Subscribe (`useValue`) only in the leaf that renders the value. Re-renders of big trees on per-token updates get expensive fast.
- **One purpose per plugin.** Split a chip + pane + palette command into one `plugin.js` (they share state); split unrelated features into separate plugins.

## Where the SDK actually lives

The renderer is a git checkout at `~/.hermes/hermes-agent/`. The load-bearing files:

| Concern | Path |
|---|---|
| Host state atoms (`focusedUsage`, `model`, `focusedSessionId`, …) | `apps/desktop/src/sdk/index.ts` (~lines 600-680 for the host.state surface) |
| Type definitions (`UsageStats`, `ContextBreakdown`, etc.) | `apps/desktop/src/types/hermes.ts` |
| Area constants + contribution interfaces | `apps/desktop/src/app/**/contrib.ts` (e.g. `command-palette/contrib.ts` → `PALETTE_AREA = 'palette'`, `PaletteContribution`) |
| Built-in context chip styling reference | `apps/desktop/src/app/shell/hooks/use-statusbar-items.tsx` |
| Built-in context breakdown panel reference | `apps/desktop/src/app/shell/context-usage-panel.tsx` |
| Pane / statusbar primitive code | `apps/desktop/src/app/shell/statusbar.tsx`, `panes/...` |

When you need a new area, find it with:

```bash
grep -rn "export const .*_AREA" ~/.hermes/hermes-agent/apps/desktop/src/
grep -rn "export interface.*Contribution" ~/.hermes/hermes-agent/apps/desktop/src/
```

## Areas cheat sheet

| Area string | Payload | Use for |
|---|---|---|
| `statusBar.right` / `statusBar.left` | `{ render }` (chip) | Small always-visible readouts. `order` controls position (lower = leftmost). |
| `panes` | `{ render, title, data: { placement, dock?, width?, height? } }` | Side panels. `placement: 'right'\|'left'\|'bottom'\|'main'` stacks; `dock: { pane, pos }` lands on a specific edge. |
| `palette` (NOT `palettes`) | `{ id, label, run, keywords?, detail?, keepOpen?, action? }` | ⌘K command rows. `id`/`label`/`run` are required; `action` is a keybind id for hotkey hint. |
| `keybinds` | see hub reference | Rebindable actions. |
| `themes` | see hub reference (`THEMES_AREA`) | Register a theme; `requestTheme(name)` to apply. |
| `routes` (`ROUTES_AREA`) | `{ path, render }` | Full pages. Pair with `SIDEBAR_NAV_AREA` for sidebar entry. |
| `transcript.directives` (`TRANSCRIPT_DIRECTIVE_AREA`) | `{ name, render }` | Inline blocks the assistant emits via `::name{attrs}`. |

`placement: 'right'` and friends are **hints, not opens.** The user must drag the pane into view (or have it docked to a zone) before it shows. There is no programmatic "open my plugin pane now" from a chip click.

## Live state atoms worth knowing

From `host.state` (see `apps/desktop/src/sdk/index.ts`):

- `focusedUsage` — live `UsageStats` of the focused session, streamed by the backend, no RPC needed. Fields: `input`, `output`, `total`, `calls`, `context_used`, `context_max`, `context_percent`, `context_estimated`, `cache_hit_pct`, `cost_usd`, `avg_tps`.
- `focusedSessionId` (runtime), `focusedStoredSessionId` (durable) — session identity. Use the stored id for navigation/persistence, the runtime id for `session.*` RPC.
- `focusedSessionProfile` — owner profile of the focused chat. Prefer this over `profile` (which is the gateway socket's home, not the focused chat's home).
- `busy` — true while the focused chat is working after a send (thinking + streaming). `awaitingResponse` is true until the first assistant payload. `busyBySession` maps runtime id → mid-turn (use for rosters).
- `model`, `gateway`, `cwd`, `viewport` — see source.

`useValue(host.state.focusedUsage)` in a leaf component gives per-frame updates without re-rendering siblings.

## Procedure (in order)

1. **Define the smallest contribution set** that solves the user's question. Don't register every area "in case" — each registration ships code paths to test.
2. **Copy `templates/plugin.js`**; rename `ID`; strip what you don't need.
3. **Find the right area + payload schema** by grepping the SDK source for `*_AREA` and `*Contribution` interfaces.
4. **Write the component.** `jsx()` calls, theme variables, `useValue` only in leaves.
5. **i18n with `ctx.i18n.register({ en, zh, ... })`** — never edit core locale files. Use `usePluginI18n(id)` in components (re-renders on locale switch).
6. **Save → app hot-reloads in ~2s.** Check the toast: "Plugin <id> failed to load: <reason>" names the error.
7. **Verify**: chip visible, pane draggable into view, ⌘K command shows up, no error toast.

## Pitfalls

- **Pane doesn't auto-open from a chip click.** `host.navigate(path)` is just `window.location.hash = '#<path>'` (see `sdk/index.ts:664`). Plugin-registered panes don't have a hash route. The honest UX: chip shows the data directly (statusbar chip is a statusbar), or chip click triggers a `host.notify` toast with instructions, or wire the chip to a palette command that does the same.
- **ReferenceError on a forgotten import.** Every identifier in a `jsx()` call must appear in the import line. `StatusDot`, `Button`, etc. all come from `@hermes/plugin-sdk` — re-check after editing.
- **Canvas panes need `ResizeObserver`.** Panes resize constantly (sash drags, layout switches). A mount-time-only size leaves blank space or blurry scaling. Re-size the canvas (`width`/`height` attributes, not just CSS).
- **Handlers must read state imperatively** (`$atom.get()`), never from render closures. Rapid events will see stale values.
- **JSX syntax will not parse.** The file loads uncompiled. `<div className="x"/>` errors; `jsx('div', { className: 'x' })` works.
- **Don't hardcode colors.** Theme variables exist for a reason. The pane already sits on the app's editor background — leave the background alone.
- **Don't import outside the allowlist.** `@hermes/plugin-sdk`, `react`, `react/jsx-runtime` only. Other specifiers fail to resolve.
- **Pane `data.width` / `data.height` are CSS strings**, e.g. `'320px'`, not numbers.
- **`defaultEnabled: false`** on the default export ships an opt-in plugin: it inventories in Settings → Plugins, off until the user flips it on.

## Verification

- The chip / pane / ⌘K command appears within ~2s of save (most cases no manual reload needed).
- No error toast naming the failure. If one appears, the message is the fix.
- For panes: drag from the right zone into view; the pane renders identically to a core pane.
- For ⌘K: open the palette, type a keyword from your `keywords` array, the row appears.
- For live data: send a message, watch the chip / pane update without a refresh.

## See also

- **Full API reference + capabilities table**: `~/.hermes/skills/autonomous-ai-agents/hermes-agent/references/desktop-plugins.md` (hub skill)
- **Template**: `~/.hermes/skills/autonomous-ai-agents/hermes-agent/templates/plugin.js`
- **SDK source** (always read for the real schema): `~/.hermes/hermes-agent/apps/desktop/src/sdk/index.ts`
- **Types**: `~/.hermes/hermes-agent/apps/desktop/src/types/hermes.ts`
- **Built-in context chip / breakdown panel** (use as a styling and copy reference for any "usage / metrics" plugin): `apps/desktop/src/app/shell/hooks/use-statusbar-items.tsx`, `apps/desktop/src/app/shell/context-usage-panel.tsx`
