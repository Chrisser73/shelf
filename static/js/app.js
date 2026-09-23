// --- Scan result card: the one reader of a scan fragment ---
//
// Both consumers of `fragments/scan_result.html` — the typed/Enter path's
// toast below, and the camera overlay in scan.js — used to re-derive the
// outcome by substring-matching Tailwind class names out of the raw HTML
// (`html.indexOf('bg-shelf-warning')`) and to pull fields by first-match-in-
// DOM-order (`.font-medium` -> title, `.text-sm.text-shelf-muted` -> authors).
//
// Two copies of the same guess, and both are one class token away from being
// wrong: any element inside a *successful* card that happens to carry a
// `bg-shelf-warning` background flips the whole card to a failure, and any
// muted small-text paragraph added above the authors line becomes the author.
// The card now states its outcome outright in `data-scan-status`, and names
// each field it wants read. This function is the only place that knows how.
// `data-scan-error` (issue #50) was the last field still read by class: the
// toast picked its text with `.text-shelf-error:not(span)`, which also matched
// the empty `x-text="copyError"` paragraph in the not_found arm's manual-add
// form and rendered a blank pill. Nothing here matches a class any more.
//
// Keep the status lists below in step with the badge's class ternary at the
// foot of fragments/scan_result.html — and with two more consumers that
// classify the same status: the camera overlay's :class ternary in
// scan.html, and the persisted history row in fragments/recent_scans.html.
// All four are halves of one contract, and three of them treat an unlisted
// status as an ERROR, so a status added here and nowhere else renders a
// successful scan in red (issue #116).
var SCAN_OK_STATUSES = [
    'added', 'wishlisted', 'returned', 'confirmed', 'marked_read',
    'checked_out', 'moved', 'found', 'relocated', 'promoted'
];
var SCAN_WARN_STATUSES = [
    'duplicate', 'already_checked_out', 'not_checked_out', 'legacy_ambiguous',
    'legacy_incomplete'
];
// Neither success nor failure: the scan worked and the answer is a report.
// 'elsewhere' is Inventory mode declining to guess which of several copies
// the barcode named, which is the correct outcome, not a warning.
var SCAN_INFO_STATUSES = ['elsewhere'];

function scanCardOutcome(root) {
    if (!root) return null;
    var status = root.getAttribute('data-scan-status') || '';
    var titleEl = root.querySelector('[data-scan-title]');
    var authorsEl = root.querySelector('[data-scan-authors]');
    var coverEl = root.querySelector('[data-scan-cover]');
    var badgeEl = root.querySelector('[data-scan-badge]');
    var detailEl = root.querySelector('[data-scan-detail]');
    return {
        status: status,
        ok: SCAN_OK_STATUSES.indexOf(status) !== -1,
        warn: SCAN_WARN_STATUSES.indexOf(status) !== -1,
        info: SCAN_INFO_STATUSES.indexOf(status) !== -1,
        label: badgeEl ? badgeEl.textContent.trim() : '',
        title: titleEl ? titleEl.textContent.trim() : null,
        authors: authorsEl ? authorsEl.textContent.trim() : null,
        detail: detailEl ? detailEl.textContent.trim() : null,
        cover: coverEl ? coverEl.getAttribute('src') : null
    };
}

// Build the typed-scan toast from a card. Split out of the clear-scan-input
// handler so it is reachable from a test without driving a real scan — the
// same reason scanCardOutcome is a named function rather than inline.
function scanCardToast(root) {
    var outcome = scanCardOutcome(root);
    // The error arm declares its own line; it replaces the assembled string
    // rather than appending to it, because it IS the whole message.
    var errEl = root.querySelector('[data-scan-error]');
    var label = outcome.label || 'Done';
    // The badge reads lower-case ('added', 'lent'); the toast is a sentence,
    // so it opens capitalised the way the server string did.
    label = label.charAt(0).toUpperCase() + label.slice(1);
    var text;
    if (errEl) {
        text = errEl.textContent.trim();
    } else {
        text = label + (outcome.title ? ': ' + outcome.title : '');
        // The detail line carries the second party the title cannot: the
        // borrower on a lend, the destination on a move, the shelf on a find.
        if (outcome.detail) text += ' — ' + outcome.detail;
    }
    // A card is a failure when its own status says so — not when some element
    // inside it happens to be styled with a warning colour. 'info' is the
    // third answer: the scan worked and reported something, so styling it as
    // a warning would be as wrong as styling it as an error.
    var type = 'warning';
    if (outcome.ok) type = 'success';
    else if (outcome.info) type = 'info';
    return {text: text, type: type};
}

// --- Toast notifications ---
function showToast(message, type) {
    var container = document.getElementById('toast-container');
    if (!container) return;
    var variants = {
        success: { title: 'Success', accent: 'border-l-shelf-success', icon: 'text-shelf-success', ring: 'border-shelf-success/35' },
        error: { title: 'Error', accent: 'border-l-shelf-error', icon: 'text-shelf-error', ring: 'border-shelf-error/35' },
        warning: { title: 'Warning', accent: 'border-l-shelf-warning', icon: 'text-shelf-warning', ring: 'border-shelf-warning/35' },
        info: { title: 'Info', accent: 'border-l-shelf-accent', icon: 'text-shelf-accent2', ring: 'border-shelf-accent/35' }
    };
    var variant = variants[type] || variants.success;
    var el = document.createElement('div');
    el.setAttribute('role', type === 'error' || type === 'warning' ? 'alert' : 'status');
    el.className = 'pointer-events-auto flex items-start gap-3 rounded-lg border border-l-4 bg-shelf-card p-4 shadow-xl transition-all duration-300 ease-out -translate-y-4 opacity-0 ' + variant.accent + ' ' + variant.ring;

    var icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    icon.setAttribute('viewBox', '0 0 20 20');
    icon.setAttribute('fill', 'currentColor');
    icon.setAttribute('aria-hidden', 'true');
    icon.setAttribute('class', 'mt-0.5 h-5 w-5 shrink-0 ' + variant.icon);
    var path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    if (type === 'error') {
        path.setAttribute('fill-rule', 'evenodd'); path.setAttribute('d', 'M10 18a8 8 0 100-16 8 8 0 000 16zm-1.06-10.94a1.5 1.5 0 112.12 2.12L10 10.24l1.06 1.06a1.5 1.5 0 11-2.12 2.12L7.88 12.36 6.82 13.42A1.5 1.5 0 114.7 11.3l1.06-1.06L4.7 9.18A1.5 1.5 0 116.82 7.06l1.06 1.06 1.06-1.06z');
    } else if (type === 'warning') {
        path.setAttribute('fill-rule', 'evenodd'); path.setAttribute('d', 'M8.257 3.099c.765-1.36 2.72-1.36 3.486 0l6.518 11.59C19.01 16.02 18.05 17.5 16.52 17.5H3.48c-1.53 0-2.49-1.48-1.74-2.81l6.517-11.59zM10 7a1 1 0 00-1 1v3a1 1 0 002 0V8a1 1 0 00-1-1zm0 7a1.125 1.125 0 100-2.25A1.125 1.125 0 0010 14z');
    } else if (type === 'info') {
        path.setAttribute('fill-rule', 'evenodd'); path.setAttribute('d', 'M18 10A8 8 0 112 10a8 8 0 0116 0zm-7-3a1 1 0 10-2 0 1 1 0 002 0zm-2 3a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2h-.5v-3a1 1 0 00-1-1H9z');
    } else {
        path.setAttribute('fill-rule', 'evenodd'); path.setAttribute('d', 'M16.707 5.293a1 1 0 010 1.414l-7.5 7.5a1 1 0 01-1.414 0l-3.5-3.5a1 1 0 011.414-1.414l2.793 2.793 6.793-6.793a1 1 0 011.414 0z');
    }
    path.setAttribute('clip-rule', 'evenodd');
    icon.appendChild(path);
    el.appendChild(icon);

    var copy = document.createElement('div');
    copy.className = 'min-w-0 flex-1';
    var heading = document.createElement('p');
    heading.className = 'text-sm font-semibold text-shelf-text';
    heading.textContent = variant.title;
    copy.appendChild(heading);
    var detail = document.createElement('p');
    detail.className = 'mt-0.5 text-sm text-shelf-muted';
    // Structural, not belt-and-braces: makes a pill with nothing in it impossible from any caller.
    message = (message || '').toString().trim() || 'Done';
    detail.textContent = message;
    copy.appendChild(detail);
    el.appendChild(copy);

    var dismiss = document.createElement('button');
    dismiss.type = 'button'; dismiss.setAttribute('aria-label', 'Dismiss notification');
    dismiss.className = 'shrink-0 rounded p-1 text-shelf-muted hover:bg-shelf-hover hover:text-shelf-text transition-colors';
    dismiss.textContent = '×';
    dismiss.addEventListener('click', function () { dismissToast(); });
    el.appendChild(dismiss);
    container.appendChild(el);
    requestAnimationFrame(function () { el.classList.remove('-translate-y-4', 'opacity-0'); });
    var removed = false;
    function dismissToast() {
        if (removed) return;
        removed = true;
        el.classList.add('-translate-y-4', 'opacity-0');
        setTimeout(function () { el.remove(); }, 300);
    }
    // A short entrance, 2.5 seconds of reading time, then a matching exit.
    setTimeout(dismissToast, 2800);
}

// Listen for HX-Trigger showToast events from server
document.body.addEventListener('showToast', function(e) {
    var d = e.detail || {};
    showToast(d.message || 'Done', d.type || 'success');
});

// --- Loading bar ---
(function() {
    var bar = document.getElementById('htmx-indicator');
    document.body.addEventListener('htmx:beforeRequest', function() {
        bar.style.opacity = '1';
        bar.style.width = (30 + Math.random() * 30) + '%';
    });
    document.body.addEventListener('htmx:afterRequest', function() {
        bar.style.width = '100%';
        setTimeout(function() { bar.style.opacity = '0'; bar.style.width = '0'; }, 300);
    });
})();

// --- Keyboard shortcuts ---
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        var shortcutModal = document.getElementById('shortcut-modal');
        if (shortcutModal && !shortcutModal.classList.contains('hidden')) {
            shortcutModal.classList.add('hidden');
            return;
        }
    }

    var tag = document.activeElement.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
    if (e.key === '/' ) { e.preventDefault(); var q = document.querySelector('[name="q"]'); if (q) q.focus(); }
    else if (e.key === 's') { window.location.href = '/scan'; }
    else if (e.key === 'b') { window.location.href = '/browse'; }
    else if (e.key === '?') { document.getElementById('shortcut-modal').classList.toggle('hidden'); }
});

// The visible shortcut-help controls used inline onclick handlers. Shelf's
// script-src 'self' CSP refuses those handlers, so the button and both close
// surfaces looked clickable but did nothing. Bind the same behaviour from this
// external script instead. Remove the inert inline attributes before a user can
// click them so browsers do not report a CSP violation for the dead handler.
(function() {
    var modal = document.getElementById('shortcut-modal');
    var trigger = document.querySelector('[title="Keyboard shortcuts (?)"]');
    if (!modal || !trigger) return;

    trigger.removeAttribute('onclick');
    trigger.addEventListener('click', function() {
        modal.classList.toggle('hidden');
    });

    modal.removeAttribute('onclick');
    modal.addEventListener('click', function(e) {
        if (e.target === modal) modal.classList.add('hidden');
    });

    var close = modal.querySelector('button[onclick]');
    if (close) {
        close.removeAttribute('onclick');
        close.addEventListener('click', function() {
            modal.classList.add('hidden');
        });
    }
})();

// --- Search-result form sync ---
// Replaces the inline scripts formerly embedded in the book/dvd/game
// search-result fragments (inline scripts cannot execute under the CSP).
document.body.addEventListener('htmx:afterSwap', function() {
    var loc = document.getElementById('location');
    var plat = document.getElementById('platform');
    if (loc) {
        document.querySelectorAll('.book-loc-sync, .dvd-loc-sync, .game-loc-sync').forEach(function(el) {
            el.value = loc.value;
        });
    }
    if (plat) {
        document.querySelectorAll('.game-platform-sync').forEach(function(el) {
            el.value = plat.value;
        });
    }
});

// CSP: hx-on:: attributes and hx-vals='js:...' need unsafe-eval, which the CSP
// forbids — equivalent behavior via delegated listeners keyed by data attributes.
htmx.config.allowEval = false;

document.body.addEventListener('htmx:afterRequest', function (evt) {
    var el = evt.detail.elt;
    if (!el || !el.getAttribute) return;
    var action = el.getAttribute('data-after-request');
    if (!action) return;
    var ok = evt.detail.successful;
    if (action === 'clear-scan-input') {
        var input = el.querySelector('#isbn-input');
        if (input) { input.value = ''; input.focus(); }
        // This handler is the SOLE owner of the typed-scan toast: /api/scan
        // sets no HX-Trigger on any branch, so nothing else toasts here.
        // Typed/Enter entry has no camera overlay and the result card lands in
        // #scan-results below the fold, so without this the submit looks like
        // a silent no-op. The card is the only input — see GOTCHAS "When
        // adding a response branch to /api/scan".
        var card = ok && document.querySelector('#scan-results > :first-child');
        if (card) {
            var t = scanCardToast(card);
            showToast(t.text, t.type);
        }
    } else if (action === 'clear-title-search' && ok) {
        var si = document.getElementById('title-search-input') || document.getElementById('game-search-input');
        if (si) si.value = '';
        var sr = document.getElementById('title-search-results') || document.getElementById('game-search-results');
        if (sr) sr.innerHTML = '';
    } else if (action === 'reload' && ok) {
        location.reload();
    } else if (action === 'goto-browse' && ok) {
        window.location = '/browse';
    } else if (action === 'toast-reload' && ok) {
        showToast('Details saved', 'success');
        window.setTimeout(function () { window.location.reload(); }, 350);
    }
});

// Replaces hx-vals='js:...' on the recent-scans panel (dynamic localStorage value)
document.body.addEventListener('htmx:configRequest', function (evt) {
    var el = evt.detail.elt;
    if (el && el.getAttribute && el.getAttribute('data-vals-scan-mode') !== null) {
        evt.detail.parameters.mode = localStorage.getItem('shelf_scan_mode') || 'add';
    }
});

document.addEventListener('click', function (evt) {
    var button = evt.target.closest('[data-retry-missing-covers]');
    if (!button || button.disabled) return;
    button.disabled = true;
    var icon = button.querySelector('svg, i');
    if (icon) icon.classList.add('animate-spin');
    var es = new EventSource('/api/covers/bulk-retry/stream');
    es.onmessage = function (event) {
        var data = JSON.parse(event.data);
        if (data.type === 'done') {
            es.close();
            showToast('Cover retry finished: ' + data.success + ' found, ' + data.failed + ' not found', data.failed ? 'warning' : 'success');
            window.setTimeout(function () { window.location.reload(); }, 1000);
        } else if (data.type === 'error') {
            es.close(); button.disabled = false;
            if (icon) icon.classList.remove('animate-spin');
            showToast(data.message || 'Cover retry failed', 'error');
        }
    };
    es.onerror = function () {
        es.close(); button.disabled = false;
        if (icon) icon.classList.remove('animate-spin');
        showToast('Cover retry connection lost', 'error');
    };
});
