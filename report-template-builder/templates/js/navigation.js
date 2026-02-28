/**
 * Navigation Module
 * Handles navigation between differences and keyboard shortcuts
 */

// Navigation state
let currentDiffIndex = -1;

/**
 * Navigate to next or previous difference
 * @param {string} direction - 'next' or 'prev'
 */
function navigateToDiff(direction) {
    // Get visible diffs based on current view
    const visibleDiffs = (typeof diffRows !== 'undefined' ? diffRows : []).filter(row => {
        if (row.classList.contains('hidden-row')) {
            return false;
        }

        const table = row.closest('table');
        if (!table) return false;

        const container = table.closest('.table-container, .pane-content');
        if (!container) return false;

        const computedStyle = window.getComputedStyle(container);
        return computedStyle.display !== 'none';
    });

    if (visibleDiffs.length === 0) {
        showNavToast('No differences found in current view', 2000);
        return;
    }

    if (direction === 'next') {
        currentDiffIndex = (currentDiffIndex + 1) % visibleDiffs.length;
    } else {
        currentDiffIndex = (currentDiffIndex - 1 + visibleDiffs.length) % visibleDiffs.length;
    }

    const targetRow = visibleDiffs[currentDiffIndex];

    // Remove previous highlight
    document.querySelectorAll('.highlighted').forEach(r => r.classList.remove('highlighted'));

    // Highlight row
    targetRow.classList.add('highlighted');

    // Scroll to row within the appropriate container
    const scrollContainer = targetRow.closest('.table-container, .pane-content');
    if (scrollContainer) {
        const rowTop = targetRow.offsetTop;
        const containerHeight = scrollContainer.clientHeight;
        const rowHeight = targetRow.clientHeight;

        scrollContainer.scrollTop = rowTop - (containerHeight / 2) + (rowHeight / 2);
    } else {
        targetRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    showNavToast(`Difference ${currentDiffIndex + 1} of ${visibleDiffs.length}`, 1500);

    console.log(`🎯 Navigated to difference ${currentDiffIndex + 1}/${visibleDiffs.length}`);
}

/**
 * Show navigation toast notification
 * @param {string} message - Message to display
 * @param {number} duration - Duration in milliseconds
 */
function showNavToast(message, duration = 1500) {
    const toast = document.getElementById('navCounterToast');
    if (!toast) return;

    toast.textContent = message;
    toast.style.display = 'block';

    if (window.navToastTimeout) {
        clearTimeout(window.navToastTimeout);
    }

    window.navToastTimeout = setTimeout(() => {
        toast.style.display = 'none';
    }, duration);
}

/**
 * Copy Job ID to clipboard
 * @param {string} jobId - Job ID to copy
 */
function copyJobId(jobId) {
    const btn = document.querySelector('.job-id-section .job-id-row .copy-btn');
    navigator.clipboard.writeText(jobId).then(() => {
        showNavToast('✓ Job ID copied to clipboard!', 2000);
        console.log(`📋 Copied Job ID: ${jobId}`);
        if (btn) {
            btn.classList.add('copied');
            btn.textContent = '✅ Copied!';
            setTimeout(() => {
                btn.classList.remove('copied');
                btn.textContent = '📋 Copy';
            }, 2000);
        }
    }).catch(err => {
        console.error('Failed to copy Job ID:', err);
        const textArea = document.createElement('textarea');
        textArea.value = jobId;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        document.body.appendChild(textArea);
        textArea.select();
        try {
            document.execCommand('copy');
            showNavToast('✓ Job ID copied to clipboard!', 2000);
            if (btn) {
                btn.classList.add('copied');
                btn.textContent = '✅ Copied!';
                setTimeout(() => {
                    btn.classList.remove('copied');
                    btn.textContent = '📋 Copy';
                }, 2000);
            }
        } catch (err) {
            showNavToast('✗ Failed to copy Job ID', 2000);
        }
        document.body.removeChild(textArea);
    });
}

/**
 * Setup keyboard shortcuts
 */
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', function (e) {
        const isInputField = e.target.tagName === 'INPUT' ||
            e.target.tagName === 'TEXTAREA' ||
            e.target.isContentEditable;

        if (isInputField && e.key !== 'Escape') {
            return;
        }

        // Ctrl+F - Focus search
        if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
            e.preventDefault();
            const searchInput = document.getElementById('globalSearch');
            if (searchInput) {
                searchInput.focus();
                searchInput.select();
            }
            return;
        }

        // Ctrl+D - Toggle dark mode
        if ((e.ctrlKey || e.metaKey) && e.key === 'd') {
            e.preventDefault();
            if (typeof toggleDarkMode === 'function') {
                toggleDarkMode();
            }
            return;
        }

        // Ctrl+Down Arrow - Next difference
        if ((e.ctrlKey || e.metaKey) && e.key === 'ArrowDown') {
            e.preventDefault();
            e.stopPropagation();
            navigateToDiff('next');
            return;
        }

        // Ctrl+Up Arrow - Previous difference
        if ((e.ctrlKey || e.metaKey) && e.key === 'ArrowUp') {
            e.preventDefault();
            e.stopPropagation();
            navigateToDiff('prev');
            return;
        }

        // Escape - Close modal
        if (e.key === 'Escape') {
            e.preventDefault();
            if (typeof closeCharDetailModal === 'function') {
                closeCharDetailModal();
            }
            const searchInput = document.getElementById('globalSearch');
            if (searchInput && searchInput.value) {
                searchInput.value = '';
                if (typeof performGlobalSearch === 'function') {
                    performGlobalSearch('');
                }
            }
            return;
        }

        // ? - Show shortcuts help
        if (e.key === '?' && !e.shiftKey && !isInputField) {
            e.preventDefault();
            toggleShortcutsHelp();
            return;
        }
    });

    console.log('⌨️ Keyboard shortcuts enabled');
}

/**
 * Toggle shortcuts help panel
 */
function toggleShortcutsHelp() {
    const help = document.getElementById('shortcutsHelp');
    if (help.style.display === 'none' || !help.style.display) {
        help.style.display = 'block';
        setTimeout(() => {
            help.style.display = 'none';
        }, 5000);
    } else {
        help.style.display = 'none';
    }
}

/**
 * Setup navigation button listeners
 */
function setupNavigationListeners() {
    const prevBtn = document.getElementById('prevDiff');
    const nextBtn = document.getElementById('nextDiff');
    if (prevBtn) prevBtn.addEventListener('click', () => navigateToDiff('prev'));
    if (nextBtn) nextBtn.addEventListener('click', () => navigateToDiff('next'));
}

/**
 * Setup row highlighting on hover
 */
function setupRowHighlighting() {
    if (typeof allRows !== 'undefined') {
        allRows.forEach(rowData => {
            const row = rowData.element;
            row.addEventListener('mouseenter', function () {
                this.classList.add('highlighted');
            });
            row.addEventListener('mouseleave', function () {
                this.classList.remove('highlighted');
            });
        });
    }
}


