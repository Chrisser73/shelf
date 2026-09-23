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
            },
            attrs: {width: 20, height: 20, 'stroke-width': 2},
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', renderNavigationIcons);
    } else {
        renderNavigationIcons();
    }
}());
