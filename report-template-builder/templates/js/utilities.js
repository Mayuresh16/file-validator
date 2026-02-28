/**
 * Utilities Module
 * Common utility functions and enhancements
 */

/**
 * Add copy buttons to data cells
 */
function addCopyButtons() {
    const cells = document.querySelectorAll('.cell-source, .cell-target, .cell-match');
    cells.forEach(cell => {
        if (!cell.querySelector('.copy-btn')) {
            const copyBtn = document.createElement('button');
            copyBtn.className = 'copy-btn';
            copyBtn.textContent = '📋';
            copyBtn.title = 'Copy to clipboard';
            copyBtn.onclick = function (e) {
                e.stopPropagation();
                copyToClipboard(cell.textContent, copyBtn);
            };
            cell.style.position = 'relative';
            cell.appendChild(copyBtn);
        }
    });
}

/**
 * Copy text to clipboard
 * @param {string} text - Text to copy
 * @param {HTMLElement} button - Button element for feedback
 */
function copyToClipboard(text, button) {
    navigator.clipboard.writeText(text).then(() => {
        button.textContent = '✓';
        button.classList.add('copied');
        setTimeout(() => {
            button.textContent = '📋';
            button.classList.remove('copied');
        }, 2000);
    }).catch(err => {
        console.error('Copy failed:', err);
        alert('Failed to copy to clipboard');
    });
}

/**
 * Add row numbers to tables
 */
function addRowNumbers() {
    const tables = document.querySelectorAll('tbody');
    tables.forEach(table => {
        const rows = table.querySelectorAll('tr');
        rows.forEach((row, index) => {
            if (!row.querySelector('.row-number')) {
                const numberCell = document.createElement('td');
                numberCell.className = 'row-number';
                numberCell.textContent = index + 1;
                row.insertBefore(numberCell, row.firstChild);
            }
        });
    });

    const headerRows = document.querySelectorAll('thead tr');
    headerRows.forEach(headerRow => {
        if (!headerRow.querySelector('.row-number')) {
            const th = document.createElement('th');
            th.className = 'row-number';
            th.textContent = '#';
            headerRow.insertBefore(th, headerRow.firstChild);
        }
    });
}

/**
 * Setup Intersection Observer for lazy loading
 */
function setupLazyLoading() {
    if ('IntersectionObserver' in window && typeof allRows !== 'undefined') {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                }
            });
        }, { rootMargin: '50px' });

        if (allRows.length > 500) {
            allRows.forEach(rowData => {
                observer.observe(rowData.element);
            });
        }
    }
}

/**
 * Show or hide loading overlay
 * @param {boolean} show - Whether to show the overlay
 */
function showLoading(show) {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        overlay.style.display = show ? 'flex' : 'none';
    }
}

/**
 * Add button hover effects
 */
function addButtonHoverEffects() {
    document.querySelectorAll('button').forEach(btn => {
        btn.addEventListener('mouseenter', function () {
            this.style.transform = 'translateY(-2px)';
            this.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
        });
        btn.addEventListener('mouseleave', function () {
            this.style.transform = 'translateY(0)';
            this.style.boxShadow = '0 2px 8px rgba(0,0,0,0.1)';
        });
    });
}


