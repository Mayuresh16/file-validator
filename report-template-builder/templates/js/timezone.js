/**
 * Timezone Module
 * Handles timezone switching for report timestamps
 */

// Note: timezoneData, localTzName, and localTzAbbr are defined in the main template
// before this script is loaded, so we don't redeclare them here.

/**
 * Switch timezone display
 * @param {string} timezone - Timezone to switch to (local, utc, ist, et)
 */
function switchTimezone(timezone) {
    // Use globally defined timezoneData from template
    const data = (typeof timezoneData !== 'undefined') ? timezoneData : {};
    const displayElement = document.getElementById('displayedTime');

    if (displayElement && data[timezone]) {
        displayElement.textContent = data[timezone];
    }

    const buttons = document.querySelectorAll('.timezone-btn');
    buttons.forEach(btn => {
        if (btn.dataset.timezone === timezone) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    localStorage.setItem('preferredTimezone', timezone);
    console.log(`🌍 Switched to timezone: ${timezone.toUpperCase()}`);
}

/**
 * Initialize timezone from localStorage or default to LOCAL
 */
function initializeTimezone() {
    const savedTimezone = localStorage.getItem('preferredTimezone') || 'local';
    switchTimezone(savedTimezone);

    const tzName = (typeof localTzName !== 'undefined') ? localTzName : 'Unknown';
    const tzAbbr = (typeof localTzAbbr !== 'undefined') ? localTzAbbr : '';
    console.log(`🌍 Initialized timezone: ${savedTimezone.toUpperCase()}`);
    console.log(`📍 Local timezone: ${tzName} (${tzAbbr})`);
}

