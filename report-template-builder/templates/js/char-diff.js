/**
 * Character Diff Module
 * Handles character-level difference highlighting and modal display
 */

/**
 * Highlight character differences between source and target text
 * @param {string} sourceText - Source text to compare
 * @param {string} targetText - Target text to compare
 * @returns {object} Object with source and target HTML with diff highlights
 */
function highlightCharDiff(sourceText, targetText) {
    if (!sourceText || !targetText) {
        return {
            source: sourceText || '',
            target: targetText || ''
        };
    }

    sourceText = String(sourceText);
    targetText = String(targetText);

    const maxLen = Math.max(sourceText.length, targetText.length);
    let sourceHTML = '';
    let targetHTML = '';

    for (let i = 0; i < maxLen; i++) {
        const sChar = sourceText[i];
        const tChar = targetText[i];

        if (sChar === undefined) {
            targetHTML += `<span class="char-added">${renderWhitespace(tChar)}</span>`;
        } else if (tChar === undefined) {
            sourceHTML += `<span class="char-removed">${renderWhitespace(sChar)}</span>`;
        } else if (sChar === tChar) {
            sourceHTML += `<span class="char-same">${renderWhitespace(sChar)}</span>`;
            targetHTML += `<span class="char-same">${renderWhitespace(tChar)}</span>`;
        } else {
            sourceHTML += `<span class="char-diff">${renderWhitespace(sChar)}</span>`;
            targetHTML += `<span class="char-diff">${renderWhitespace(tChar)}</span>`;
        }
    }

    return {
        source: sourceHTML,
        target: targetHTML
    };
}

/**
 * Render whitespace characters visually
 * @param {string} char - Character to render
 * @returns {string} HTML representation of the character
 */
function renderWhitespace(char) {
    if (char === ' ') {
        return '<span class="whitespace-char" title="Space">␣</span>';
    } else if (char === '\t') {
        return '<span class="whitespace-char" title="Tab">⇥</span>';
    } else if (char === '\n') {
        return '<span class="whitespace-char" title="Newline">⏎</span>';
    } else if (char === '\r') {
        return '<span class="whitespace-char" title="Carriage Return">↵</span>';
    } else {
        return escapeHtml(char);
    }
}

/**
 * Escape HTML special characters
 * @param {string} text - Text to escape
 * @returns {string} Escaped HTML
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Visualize whitespace in raw text display
 * @param {string} text - Text to visualize
 * @returns {string} HTML with visible whitespace
 */
function visualizeWhitespace(text) {
    if (!text) return '';

    let result = '';
    for (let i = 0; i < text.length; i++) {
        const char = text[i];
        if (char === ' ') {
            result += '<span class="whitespace-char" title="Space">␣</span>';
        } else if (char === '\t') {
            result += '<span class="whitespace-char" title="Tab">⇥</span>';
        } else if (char === '\n') {
            result += '<span class="whitespace-char" title="Newline">⏎</span><br>';
        } else if (char === '\r') {
            result += '<span class="whitespace-char" title="Carriage Return">↵</span>';
        } else {
            result += escapeHtml(char);
        }
    }
    return result;
}

/**
 * Generate character-by-character analysis
 * @param {string} srcText - Source text
 * @param {string} tgtText - Target text
 * @returns {object} Analysis results with rows and stats
 */
function generateCharAnalysis(srcText, tgtText) {
    const maxLen = Math.max(srcText.length, tgtText.length);
    const rows = [];
    let matchingChars = 0;
    let differentChars = 0;
    let removedChars = 0;
    let addedChars = 0;

    for (let i = 0; i < maxLen; i++) {
        const srcChar = srcText[i];
        const tgtChar = tgtText[i];

        let status = '';
        let statusClass = '';

        if (srcChar === undefined) {
            status = 'ADDED IN TARGET';
            statusClass = 'char-status-added';
            addedChars++;
        } else if (tgtChar === undefined) {
            status = 'REMOVED FROM SOURCE';
            statusClass = 'char-status-removed';
            removedChars++;
        } else if (srcChar === tgtChar) {
            status = '✓ MATCH';
            statusClass = 'char-status-match';
            matchingChars++;
        } else {
            status = '✗ DIFFERENT';
            statusClass = 'char-status-diff';
            differentChars++;
        }

        const displaySrcChar = srcChar !== undefined ?
            (srcChar === ' ' ? '<span class="whitespace-char" title="Space">␣</span>' :
             (srcChar === '\t' ? '<span class="whitespace-char" title="Tab">⇥</span>' :
              (srcChar === '\n' ? '<span class="whitespace-char" title="Newline">⏎</span>' :
               (srcChar === '\r' ? '<span class="whitespace-char" title="Carriage Return">↵</span>' :
                escapeHtml(srcChar))))) :
            '-';

        const displayTgtChar = tgtChar !== undefined ?
            (tgtChar === ' ' ? '<span class="whitespace-char" title="Space">␣</span>' :
             (tgtChar === '\t' ? '<span class="whitespace-char" title="Tab">⇥</span>' :
              (tgtChar === '\n' ? '<span class="whitespace-char" title="Newline">⏎</span>' :
               (tgtChar === '\r' ? '<span class="whitespace-char" title="Carriage Return">↵</span>' :
                escapeHtml(tgtChar))))) :
            '-';

        const srcCode = srcChar !== undefined ?
            `U+${srcChar.charCodeAt(0).toString(16).toUpperCase().padStart(4, '0')}` :
            '-';
        const tgtCode = tgtChar !== undefined ?
            `U+${tgtChar.charCodeAt(0).toString(16).toUpperCase().padStart(4, '0')}` :
            '-';

        const srcCharName = srcChar !== undefined ? getCharName(srcChar) : '';
        const tgtCharName = tgtChar !== undefined ? getCharName(tgtChar) : '';

        rows.push(`
            <tr>
                <td class="char-pos">${i}</td>
                <td class="char-display">${displaySrcChar}${srcCharName ? `<br><small style="color: #9c27b0; font-size: 10px;">${srcCharName}</small>` : ''}</td>
                <td class="char-code">${srcCode}</td>
                <td class="char-display">${displayTgtChar}${tgtCharName ? `<br><small style="color: #9c27b0; font-size: 10px;">${tgtCharName}</small>` : ''}</td>
                <td class="char-code">${tgtCode}</td>
                <td class="char-status"><span class="${statusClass}">${status}</span></td>
            </tr>
        `);
    }

    return {
        rows: rows,
        stats: {
            matchingChars: matchingChars,
            differentChars: differentChars,
            removedChars: removedChars,
            addedChars: addedChars
        }
    };
}

/**
 * Get character name for common whitespace characters
 * @param {string} char - Character to identify
 * @returns {string} Character name
 */
function getCharName(char) {
    const charNames = {
        ' ': 'SPACE',
        '\t': 'TAB',
        '\n': 'NEWLINE',
        '\r': 'CR',
        '\v': 'VTAB',
        '\f': 'FORM FEED'
    };
    return charNames[char] || '';
}

/**
 * Show character detail modal
 * @param {string} sourceValue - Source value
 * @param {string} targetValue - Target value
 * @param {string} columnName - Column name
 */
function showCharacterDetail(sourceValue, targetValue, columnName) {
    const modal = document.getElementById('charDetailModal');
    const modalBody = document.getElementById('charDetailBody');

    const srcText = sourceValue ? String(sourceValue) : '';
    const tgtText = targetValue ? String(targetValue) : '';

    document.getElementById('charDetailColumnName').textContent = columnName;

    const charAnalysis = generateCharAnalysis(srcText, tgtText);

    modalBody.innerHTML = `
        <!-- Summary Statistics -->
        <div class="char-detail-section">
            <h3>📊 Summary Statistics</h3>
            <div class="char-summary">
                <div class="char-summary-item" style="background: linear-gradient(135deg, #28a745 0%, #20c997 100%);">
                    <div class="char-summary-value">${charAnalysis.stats.matchingChars}</div>
                    <div class="char-summary-label">Matching Characters</div>
                </div>
                <div class="char-summary-item" style="background: linear-gradient(135deg, #ffc107 0%, #ff9800 100%);">
                    <div class="char-summary-value">${charAnalysis.stats.differentChars}</div>
                    <div class="char-summary-label">Different Characters</div>
                </div>
                <div class="char-summary-item" style="background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);">
                    <div class="char-summary-value">${charAnalysis.stats.removedChars}</div>
                    <div class="char-summary-label">Removed Characters</div>
                </div>
                <div class="char-summary-item" style="background: linear-gradient(135deg, #17a2b8 0%, #138496 100%);">
                    <div class="char-summary-value">${charAnalysis.stats.addedChars}</div>
                    <div class="char-summary-label">Added Characters</div>
                </div>
            </div>
        </div>

        <!-- Value Display -->
        <div class="char-detail-section">
            <h3>📝 Raw Values</h3>
            <div class="char-value-display source-display">
                <div class="char-value-label">🔴 Source Value (${srcText.length} characters)</div>
                <div class="char-value-text">${visualizeWhitespace(srcText) || '<em style="color: #999;">EMPTY</em>'}</div>
            </div>
            <div class="char-value-display target-display">
                <div class="char-value-label">🔵 Target Value (${tgtText.length} characters)</div>
                <div class="char-value-text">${visualizeWhitespace(tgtText) || '<em style="color: #999;">EMPTY</em>'}</div>
            </div>
        </div>

        <!-- Character-by-Character Comparison -->
        <div class="char-detail-section">
            <h3>🔬 Character-by-Character Analysis</h3>
            <table class="char-detail-table">
                <thead>
                    <tr>
                        <th>Position</th>
                        <th>Source Char</th>
                        <th>Source Code</th>
                        <th>Target Char</th>
                        <th>Target Code</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    ${charAnalysis.rows.join('')}
                </tbody>
            </table>
        </div>
    `;

    modal.style.display = 'block';
}

/**
 * Close character detail modal
 */
function closeCharDetailModal() {
    document.getElementById('charDetailModal').style.display = 'none';
}

/**
 * Make mismatch cells clickable
 */
function makeClickableMismatchCells() {
    // Side-by-side and stacked views
    const sourceCells = document.querySelectorAll('.cell-source');
    const targetCells = document.querySelectorAll('.cell-target');

    for (let i = 0; i < sourceCells.length; i++) {
        if (targetCells[i]) {
            const sourceCell = sourceCells[i];
            const targetCell = targetCells[i];

            const columnIndex = Array.from(sourceCell.parentElement.children).indexOf(sourceCell);
            const headerRow = sourceCell.closest('table').querySelector('thead tr');
            const columnName = headerRow ? headerRow.children[columnIndex]?.textContent.trim() : 'Column';

            const sourceValue = sourceCell.textContent.trim();
            const targetValue = targetCell.textContent.trim();

            sourceCell.classList.add('mismatch-cell-clickable');
            targetCell.classList.add('mismatch-cell-clickable');

            sourceCell.onclick = () => showCharacterDetail(sourceValue, targetValue, columnName);
            targetCell.onclick = () => showCharacterDetail(sourceValue, targetValue, columnName);
        }
    }

    // Inline view
    const inlineComparisons = document.querySelectorAll('.inline-comparison');
    inlineComparisons.forEach(comparison => {
        const sourceRow = comparison.querySelector('.source-row .inline-value');
        const targetRow = comparison.querySelector('.target-row .inline-value');

        if (sourceRow && targetRow) {
            const cell = comparison.closest('td');
            const colIndex = Array.from(cell.parentElement.children).indexOf(cell);
            const headerRow = cell.closest('table').querySelector('thead tr');
            const columnName = headerRow ? headerRow.children[colIndex]?.textContent.trim() : 'Column';

            const sourceText = sourceRow.textContent.replace(/^(SOURCE:|✓)\s*/, '').trim();
            const targetText = targetRow.textContent.replace(/^(TARGET:|✓)\s*/, '').trim();

            comparison.classList.add('mismatch-cell-clickable');
            comparison.style.cursor = 'pointer';
            comparison.onclick = () => showCharacterDetail(sourceText, targetText, columnName);
        }
    });
}

/**
 * Apply character-level diff to inline view mismatches
 */
function applyCharDiffToInlineView() {
    const inlineComparisons = document.querySelectorAll('.inline-comparison');

    inlineComparisons.forEach(comparison => {
        const sourceRow = comparison.querySelector('.source-row .inline-value');
        const targetRow = comparison.querySelector('.target-row .inline-value');

        if (sourceRow && targetRow) {
            const sourceText = sourceRow.textContent.trim();
            const targetText = targetRow.textContent.trim();

            if (sourceText && targetText && sourceText !== targetText &&
                sourceText !== 'NULL' && targetText !== 'NULL') {
                const diff = highlightCharDiff(sourceText, targetText);
                sourceRow.innerHTML = diff.source;
                targetRow.innerHTML = diff.target;
            }
        }
    });
}

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('charDetailModal');
    if (event.target === modal) {
        closeCharDetailModal();
    }
};


