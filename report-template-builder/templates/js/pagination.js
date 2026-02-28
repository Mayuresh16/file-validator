/**
 * Pagination Module
 * Handles lazy loading and pagination of table rows
 */

// Pagination variables are defined in the main template before this script

/**
 * Load more rows for side-by-side view (20 at a time)
 */
function loadMoreSideRows() {
    const tbody = document.getElementById('side-by-side-tbody');
    if (!tbody) return;

    const hiddenRows = tbody.querySelectorAll('.hidden-row[style*="display: none"]');

    let loadedCount = 0;
    for (let i = 0; i < hiddenRows.length && loadedCount < 20; i++) {
        hiddenRows[i].style.display = '';
        loadedCount++;
    }

    if (typeof sideCurrentlyVisible !== 'undefined') {
        sideCurrentlyVisible += loadedCount;
        updateSideCounters();
    }

    // Hide button if all rows are shown
    if (typeof sideTotalRecords !== 'undefined' && sideCurrentlyVisible >= sideTotalRecords) {
        const btn = document.getElementById('load-more-side-btn');
        if (btn) btn.style.display = 'none';
    }
}

/**
 * Show all rows for side-by-side view
 */
function showAllSideRows() {
    const tbody = document.getElementById('side-by-side-tbody');
    if (!tbody) return;

    const hiddenRows = tbody.querySelectorAll('.hidden-row');

    hiddenRows.forEach(row => {
        row.style.display = '';
    });

    if (typeof sideTotalRecords !== 'undefined') {
        sideCurrentlyVisible = sideTotalRecords;
        updateSideCounters();
    }

    // Hide both buttons
    const loadMoreBtn = document.getElementById('load-more-side-btn');
    const showAllBtn = document.getElementById('show-all-side-btn');
    if (loadMoreBtn) loadMoreBtn.style.display = 'none';
    if (showAllBtn) showAllBtn.style.display = 'none';
}

/**
 * Update counter displays for side-by-side view
 */
function updateSideCounters() {
    const visibleCount = document.getElementById('side-visible-count');
    const showingCount = document.getElementById('side-showing-count');
    if (visibleCount && typeof sideCurrentlyVisible !== 'undefined') {
        visibleCount.textContent = sideCurrentlyVisible;
    }
    if (showingCount && typeof sideCurrentlyVisible !== 'undefined') {
        showingCount.textContent = sideCurrentlyVisible;
    }
}

/**
 * Load more rows for inline view (20 at a time)
 */
function loadMoreInlineRows() {
    const tbody = document.getElementById('inline-tbody');
    if (!tbody) return;

    const hiddenRows = tbody.querySelectorAll('.hidden-row[style*="display: none"]');

    let loadedCount = 0;
    for (let i = 0; i < hiddenRows.length && loadedCount < 20; i++) {
        hiddenRows[i].style.display = '';
        loadedCount++;
    }

    if (typeof inlineCurrentlyVisible !== 'undefined') {
        inlineCurrentlyVisible += loadedCount;
        updateInlineCounters();
    }

    // Hide button if all rows are shown
    if (typeof inlineTotalRecords !== 'undefined' && inlineCurrentlyVisible >= inlineTotalRecords) {
        const btn = document.getElementById('load-more-inline-btn');
        if (btn) btn.style.display = 'none';
    }
}

/**
 * Show all rows for inline view
 */
function showAllInlineRows() {
    const tbody = document.getElementById('inline-tbody');
    if (!tbody) return;

    const hiddenRows = tbody.querySelectorAll('.hidden-row');

    hiddenRows.forEach(row => {
        row.style.display = '';
    });

    if (typeof inlineTotalRecords !== 'undefined') {
        inlineCurrentlyVisible = inlineTotalRecords;
        updateInlineCounters();
    }

    // Hide both buttons
    const loadMoreBtn = document.getElementById('load-more-inline-btn');
    const showAllBtn = document.getElementById('show-all-inline-btn');
    if (loadMoreBtn) loadMoreBtn.style.display = 'none';
    if (showAllBtn) showAllBtn.style.display = 'none';
}

/**
 * Update counter displays for inline view
 */
function updateInlineCounters() {
    const visibleCount = document.getElementById('inline-visible-count');
    const showingCount = document.getElementById('inline-showing-count');
    if (visibleCount && typeof inlineCurrentlyVisible !== 'undefined') {
        visibleCount.textContent = inlineCurrentlyVisible;
    }
    if (showingCount && typeof inlineCurrentlyVisible !== 'undefined') {
        showingCount.textContent = inlineCurrentlyVisible;
    }
}

