/*
 * Shelf's small navigation subset, rendered by Lucide's official
 * `data-lucide` + `createIcons` API. Keeping the list explicit avoids
 * handing the full icon registry to the page unnecessarily.
 */
(function () {
    function renderNavigationIcons() {
        if (!window.lucide) return;
        window.lucide.createIcons({
            icons: {
                Layers2: window.lucide.Layers2,
                ScanLine: window.lucide.ScanLine,
                Camera: window.lucide.Camera,
                PackagePlus: window.lucide.PackagePlus,
                ShoppingBag: window.lucide.ShoppingBag,
                BookOpen: window.lucide.BookOpen,
                Music: window.lucide.Music,
                Newspaper: window.lucide.Newspaper,
                Compass: window.lucide.Compass,
                ChartNoAxesColumn: window.lucide.ChartNoAxesColumn,
                RefreshCw: window.lucide.RefreshCw,
                PenLine: window.lucide.PenLine,
                Heart: window.lucide.Heart,
                Search: window.lucide.Search,
                ListFilter: window.lucide.ListFilter,
                ArrowDownUp: window.lucide.ArrowDownUp,
                Save: window.lucide.Save,
                DatabaseZap: window.lucide.DatabaseZap,
                FilePenLine: window.lucide.FilePenLine,
                ChevronDown: window.lucide.ChevronDown,
                ArrowUp: window.lucide.ArrowUp,
                ArrowDown: window.lucide.ArrowDown,
            },
            attrs: {width: 20, height: 20, 'stroke-width': 2},
        });
    }
    // Templates such as Browse's list view are cloned by Alpine after htmx
    // has finished its own swap. Expose the small, whitelisted renderer so
    // that code can render icons after those clones actually exist.
    window.renderShelfLucideIcons = renderNavigationIcons;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', renderNavigationIcons);
    } else {
        renderNavigationIcons();
    }
    // Browse replaces the list header through htmx. Render its newly inserted
    // data-lucide placeholders as well, without shipping the whole registry.
    document.body.addEventListener('htmx:afterSwap', renderNavigationIcons);
}());
