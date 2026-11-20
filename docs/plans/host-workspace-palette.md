# White workspace and warm sidebar

Josef approved the laptop Dashboard and tablet Stays previews on 20 November 2026. Apply the palette through the shared signed-in host shell so it follows the host across the app, including Dashboard, Calendar, Stays, Properties, Cleaning, Stay fees, Settings and their subpages.

| Surface | Approved color |
|---|---|
| Workspace canvas | White `#FFFFFF` |
| Sidebar or tablet rail where shown | Warm off-white `#FCF8F5` |

Use the existing tablet breakpoint at 768 CSS px. Keep the existing geometry, sidebar dividers, selected coral navigation, controls, cards and alerts. The approved screenshots also illustrated spacing and outline ideas. This pass covers the two shell colors only. Phone layouts, guest and public pages, sign-in, and the separate operator workspace are outside scope.

1. Use the shared shell rules for both current and legacy host pages. Publish matching stylesheet versions from the Python and Go layouts.
2. Verify the computed colors on laptop and tablet across the host navigation, including a legacy host screen if present. Verify existing phone colors at 390 px and the breakpoint at 767/768 px.
3. Open the browser screenshots and review the one draft PR using the repository's host UX gate. Rollback is a revert of the palette PR.

One CSS task is sufficient. [1865 executor brief](../tasks/1865-host-workspace-palette.md)
