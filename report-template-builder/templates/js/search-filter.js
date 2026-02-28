/**
 * Search and Filter Module
 * Handles global search and filtering functionality
 */

// Global variables
let currentFilter = 'all';
let allRows = [];
let diffRows = [];

/**
 * Collect all rows from all tables
 */
function collectAllRows() {
    const tables = document.querySelectorAll('tbody');
    allRows = [];
    diffRows = [];

    tables.forEach(table => {
        const rows = table.querySelectorAll('tr');
        rows.forEach((row, index) => {
            if (row.classList.contains('no-results') || row.classList.contains('pagination-row')) {
                return;
            }

            allRows.push({
                element: row,
                index: index,
                table: table
            });

            const statusCell = row.querySelector('.status-cell');
            const hasMismatchCells = row.querySelectorAll('.mismatch-cell, .mismatch-cell-clickable').length > 0;
            const isMissingRow = row.classList.contains('missing-row') || row.classList.contains('extra-row');

            if (hasMismatchCells || isMissingRow ||
                (statusCell && (statusCell.textContent.includes('Found in Both') ||
                               statusCell.textContent.includes('MISMATCH') ||
                               statusCell.textContent.includes('Missing') ||
                               statusCell.textContent.includes('Extra')))) {
                diffRows.push(row);
            }
        });
    });

    console.log(`📊 Collected ${allRows.length} total rows, ${diffRows.length} with differences`);
}

/**
 * Handle global search input
 * @param {Event} e - Input event
 */
function handleSearch(e) {
    const searchTerm = e.target.value.toLowerCase().trim();
    const clearBtn = document.getElementById('clearSearch');

    if (searchTerm.length > 0) {
        clearBtn.style.display = 'block';
    } else {
        clearBtn.style.display = 'none';
    }

    let visibleCount = 0;

    allRows.forEach(rowData => {
        const row = rowData.element;
        const rowText = row.textContent.toLowerCase();

        if (searchTerm === '' || rowText.includes(searchTerm)) {
            row.classList.remove('hidden-row');
            visibleCount++;
        } else {
            row.classList.add('hidden-row');
        }
    });

    updateSearchStats(visibleCount, allRows.length);
    checkNoResults(visibleCount);

    console.log(`🔍 Search: "${searchTerm}" - ${visibleCount} results`);
}

/**
 * Clear search input
 */
function clearSearchInput() {
    const searchInput = document.getElementById('globalSearch');
    searchInput.value = '';
    searchInput.dispatchEvent(new Event('input'));
    document.getElementById('clearSearch').style.display = 'none';
    searchInput.focus();
}

/**
 * Show clear button when input has content
 */
function showClearButton() {
    const searchInput = document.getElementById('globalSearch');
    if (searchInput.value.length > 0) {
        document.getElementById('clearSearch').style.display = 'block';
    }
}

/**
 * Handle filter button clicks
 * @param {Event} e - Click event
 */
function handleFilter(e) {
    const filterType = e.currentTarget.dataset.filter;
    currentFilter = filterType;

    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    e.currentTarget.classList.add('active');

    let visibleCount = 0;

    allRows.forEach(rowData => {
        const row = rowData.element;
        const statusCell = row.querySelector('.status-cell');
        let shouldShow = false;

        if (filterType === 'all') {
            shouldShow = true;
        } else if (filterType === 'mismatch') {
            shouldShow = statusCell && statusCell.textContent.includes('Found in Both');
        } else if (filterType === 'match') {
            shouldShow = statusCell && statusCell.textContent.includes('MATCH');
        } else if (filterType === 'missing-source') {
            shouldShow = row.classList.contains('row-missing-source');
        } else if (filterType === 'missing-target') {
            shouldShow = row.classList.contains('row-missing-target');
        }

        if (shouldShow) {
            row.classList.remove('hidden-row');
            visibleCount++;
        } else {
            row.classList.add('hidden-row');
        }
    });

    updateSearchStats(visibleCount, allRows.length);
    checkNoResults(visibleCount);

    console.log(`🔽 Filter: ${filterType} - ${visibleCount} results`);
}

/**
 * Update search statistics display
 * @param {number} visible - Number of visible rows
 * @param {number} total - Total number of rows
 */
function updateSearchStats(visible, total) {
    const visibleEl = document.getElementById('visibleRows');
    const totalEl = document.getElementById('totalRows');
    if (visibleEl) visibleEl.textContent = visible;
    if (totalEl) totalEl.textContent = total;
}

/**
 * Check if no results and show message
 * @param {number} visibleCount - Number of visible rows
 */
function checkNoResults(visibleCount) {
    document.querySelectorAll('.no-results').forEach(el => el.remove());

    if (visibleCount === 0) {
        const tables = document.querySelectorAll('tbody');
        tables.forEach(table => {
            const noResults = document.createElement('tr');
            noResults.className = 'no-results';
            noResults.innerHTML = '<td colspan="100">😕 No results found. Try adjusting your search or filter.</td>';
            table.appendChild(noResults);
        });
    }
}

/**
 * Debounce utility function
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in milliseconds
 * @returns {Function} Debounced function
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Setup search and filter event listeners
 */
function setupSearchFilterListeners() {
    const searchInput = document.getElementById('globalSearch');
    if (searchInput) {
        searchInput.addEventListener('input', debounce(handleSearch, 300));
        searchInput.addEventListener('focus', showClearButton);
    }

    const clearSearch = document.getElementById('clearSearch');
    if (clearSearch) {
        clearSearch.addEventListener('click', clearSearchInput);
    }

    const filterButtons = document.querySelectorAll('.filter-btn');
    filterButtons.forEach(btn => {
        if (!btn.classList.contains('export-btn')) {
            btn.addEventListener('click', handleFilter);
        }
    });
}


