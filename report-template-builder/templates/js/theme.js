/**
 * Theme Module
 * Handles dark mode toggle and theme preferences
 */

/**
 * Toggle dark mode
 */
function toggleDarkMode() {
    document.body.classList.toggle('dark-mode');
    const isDark = document.body.classList.contains('dark-mode');
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        themeToggle.textContent = isDark ? '☀️' : '🌙';
    }

    applyFileNamingDarkMode(isDark);

    localStorage.setItem('darkMode', isDark);
    console.log(`🌓 Dark mode: ${isDark ? 'ON' : 'OFF'}`);
}

/**
 * Apply File Naming Convention dark mode styling
 * @param {boolean} isDark - Whether dark mode is active
 */
function applyFileNamingDarkMode(isDark) {
    const summaryDivs = document.querySelectorAll('.summary');

    summaryDivs.forEach(div => {
        const h3 = div.querySelector('h3');
        if (h3 && h3.textContent.includes('File Naming Convention')) {
            if (isDark) {
                // Main paragraph text
                const paragraphs = div.querySelectorAll('p');
                paragraphs.forEach(p => {
                    p.style.color = '#b0b0b0';
                });

                // Source file card
                const sourceCards = div.querySelectorAll('[style*="fff5f5"]');
                sourceCards.forEach(card => {
                    card.style.background = 'linear-gradient(135deg, #3a2020 0%, #2d1818 100%)';

                    const h4 = card.querySelector('h4');
                    if (h4) h4.style.color = '#ff6b6b';

                    const filenameDivs = card.querySelectorAll('div[style*="background: white"]');
                    filenameDivs.forEach(fdiv => {
                        fdiv.style.background = '#1a1a1a';
                        fdiv.style.color = '#e0e0e0';
                    });

                    const textDivs = card.querySelectorAll('div[style*="color: #7f8c8d"]');
                    textDivs.forEach(tdiv => {
                        tdiv.style.color = '#b0b0b0';
                        const strong = tdiv.querySelector('strong');
                        if (strong) strong.style.color = '#4fc3f7';
                    });

                    const codes = card.querySelectorAll('code');
                    codes.forEach(code => {
                        code.style.background = '#0d0d0d';
                        code.style.color = '#e0e0e0';
                    });
                });

                // Target file card
                const targetCards = div.querySelectorAll('[style*="e8f5ff"]');
                targetCards.forEach(card => {
                    card.style.background = 'linear-gradient(135deg, #1a2a3a 0%, #152030 100%)';

                    const h4 = card.querySelector('h4');
                    if (h4) h4.style.color = '#64b5f6';

                    const filenameDivs = card.querySelectorAll('div[style*="background: white"]');
                    filenameDivs.forEach(fdiv => {
                        fdiv.style.background = '#1a1a1a';
                        fdiv.style.color = '#e0e0e0';
                    });

                    const textDivs = card.querySelectorAll('div[style*="color: #7f8c8d"]');
                    textDivs.forEach(tdiv => {
                        tdiv.style.color = '#b0b0b0';
                        const strong = tdiv.querySelector('strong');
                        if (strong) strong.style.color = '#4fc3f7';
                    });

                    const codes = card.querySelectorAll('code');
                    codes.forEach(code => {
                        code.style.background = '#0d0d0d';
                        code.style.color = '#e0e0e0';
                    });
                });

                // Filename Analysis section
                const analysisDivs = div.querySelectorAll('.filename-analysis-section, [style*="background: #f8f9fa"]');
                analysisDivs.forEach(adiv => {
                    const h4 = adiv.querySelector('h4');
                    const isFilenameAnalysis = adiv.classList.contains('filename-analysis-section') ||
                                              (h4 && h4.textContent.includes('Filename Pattern Analysis'));

                    if (isFilenameAnalysis) {
                        adiv.style.background = '#2d2d2d';
                        adiv.style.borderColor = '#404040';

                        if (h4) h4.style.color = '#e0e0e0';

                        const table = adiv.querySelector('table');
                        if (table) {
                            table.style.color = '#e0e0e0';

                            const ths = table.querySelectorAll('th');
                            ths.forEach(th => {
                                th.style.backgroundColor = '#1a1a1a';
                                th.style.color = '#e0e0e0';
                            });

                            const labelCells = table.querySelectorAll('.filename-label, td:first-child');
                            labelCells.forEach(td => {
                                td.style.color = '#4fc3f7';
                                td.style.borderColor = '#404040';
                            });

                            const valueCells = table.querySelectorAll('.filename-value');
                            valueCells.forEach(td => {
                                td.style.color = '#e0e0e0';
                                td.style.borderColor = '#404040';
                            });

                            const tds = table.querySelectorAll('td');
                            tds.forEach(td => {
                                if (!td.classList.contains('filename-label') && !td.classList.contains('filename-value')) {
                                    td.style.borderColor = '#404040';
                                }
                            });

                            const rows = table.querySelectorAll('.filename-row');
                            rows.forEach((row, idx) => {
                                row.style.background = idx % 2 === 0 ? '#2d2d2d' : '#252525';
                            });
                        }
                    }
                });

                // Common Naming Conventions info box
                const infoDivs = div.querySelectorAll('[style*="background: #e3f2fd"]');
                infoDivs.forEach(idiv => {
                    idiv.style.background = '#1a2a3a';
                    idiv.style.borderColor = '#2196f3';

                    const strong = idiv.querySelector('strong');
                    if (strong) strong.style.color = '#4fc3f7';

                    const ul = idiv.querySelector('ul');
                    if (ul) ul.style.color = '#b0b0b0';

                    const codes = idiv.querySelectorAll('code');
                    codes.forEach(code => {
                        code.style.background = '#0d0d0d';
                        code.style.color = '#64b5f6';
                    });
                });
            } else {
                // Light mode - reset
                div.classList.add('light-mode-reset');
                setTimeout(() => div.classList.remove('light-mode-reset'), 10);
            }
        }
    });
}

/**
 * Load user preferences from localStorage
 */
function loadUserPreferences() {
    // Load dark mode preference - default is LIGHT mode
    const darkMode = localStorage.getItem('darkMode') === 'true';

    // Ensure light mode is the default - remove dark-mode class if present
    document.body.classList.remove('dark-mode');
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        themeToggle.textContent = '🌙';  // Moon icon = light mode active
    }

    // Only apply dark mode if explicitly saved as preference
    if (darkMode) {
        document.body.classList.add('dark-mode');
        if (themeToggle) {
            themeToggle.textContent = '☀️';  // Sun icon = dark mode active
        }
        applyFileNamingDarkMode(true);
    }

    console.log(`💾 User preferences loaded - Theme: ${darkMode ? 'Dark' : 'Light'}`);
}

/**
 * Setup theme toggle listener
 */
function setupThemeToggle() {
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleDarkMode);
    }
}

