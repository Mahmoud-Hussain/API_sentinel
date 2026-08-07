/**
 * API Sentinel Developer Dashboard Client Controller
 */

document.addEventListener('DOMContentLoaded', () => {
    // Initialize Lucide icons if available
    if (window.lucide) {
        window.lucide.createIcons();
    }

    const searchInput = document.getElementById('global-search-input');
    const tableSearchInput = document.getElementById('filter-endpoint');
    const methodSelect = document.getElementById('filter-method');
    const statusSelect = document.getElementById('filter-status');
    const severitySelect = document.getElementById('filter-severity');
    const tableBody = document.getElementById('endpoint-table-rows');

    if (!tableBody) return;

    function applyFilters() {
        const query = (searchInput ? searchInput.value : (tableSearchInput ? tableSearchInput.value : '')).toLowerCase().trim();
        const selectedMethod = methodSelect ? methodSelect.value : 'ALL';
        const selectedStatus = statusSelect ? statusSelect.value : 'ALL';
        const selectedSeverity = severitySelect ? severitySelect.value : 'ALL';

        const rows = tableBody.querySelectorAll('tr.endpoint-row');
        let visibleCount = 0;

        rows.forEach(row => {
            const endpoint = row.dataset.endpoint ? row.dataset.endpoint.toLowerCase() : '';
            const method = row.dataset.method ? row.dataset.method.toUpperCase() : '';
            const status = row.dataset.status ? row.dataset.status.toUpperCase() : '';
            const severity = row.dataset.severity ? row.dataset.severity.toUpperCase() : 'NONE';

            const matchesSearch = !query || endpoint.includes(query);
            const matchesMethod = selectedMethod === 'ALL' || method === selectedMethod;
            const matchesStatus = selectedStatus === 'ALL' || status === selectedStatus;
            const matchesSeverity = selectedSeverity === 'ALL' || severity === selectedSeverity;

            if (matchesSearch && matchesMethod && matchesStatus && matchesSeverity) {
                row.style.display = '';
                visibleCount++;
            } else {
                row.style.display = 'none';
            }
        });

        const noResultsRow = document.getElementById('no-results-row');
        if (noResultsRow) {
            noResultsRow.style.display = visibleCount === 0 ? '' : 'none';
        }
    }

    if (searchInput) searchInput.addEventListener('input', applyFilters);
    if (tableSearchInput) tableSearchInput.addEventListener('input', applyFilters);
    if (methodSelect) methodSelect.addEventListener('change', applyFilters);
    if (statusSelect) statusSelect.addEventListener('change', applyFilters);
    if (severitySelect) severitySelect.addEventListener('change', applyFilters);
});
