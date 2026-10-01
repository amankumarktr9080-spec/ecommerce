document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-notification-selection]').forEach(function (panel) {
        const checkboxes = Array.from(panel.querySelectorAll('.notification-select'));
        const selectAll = panel.querySelector('[data-select-all]');
        const selectAllLabel = panel.querySelector('[data-select-all-label]');
        const deleteModeButton = panel.querySelector('[data-delete-mode]');
        const deleteSelectedButton = panel.querySelector('[data-delete-selected]');
        const cancelButton = panel.querySelector('[data-cancel-selection]');

        if (!checkboxes.length || !selectAll || !deleteModeButton || !deleteSelectedButton || !cancelButton) {
            return;
        }

        function updateSelection() {
            const selectedCount = checkboxes.filter(function (checkbox) {
                return checkbox.checked;
            }).length;
            deleteSelectedButton.disabled = selectedCount === 0;
            selectAll.checked = selectedCount === checkboxes.length;
            selectAll.indeterminate = selectedCount > 0 && selectedCount < checkboxes.length;
            deleteSelectedButton.innerHTML = '<i class="fa-solid fa-trash" aria-hidden="true"></i> Delete selected (' + selectedCount + ')';
        }

        function setVisibility(element, visible, displayValue) {
            element.hidden = !visible;
            element.style.display = visible ? displayValue : 'none';
        }

        function setSelectionMode(enabled) {
            setVisibility(deleteModeButton, !enabled, 'inline-flex');
            setVisibility(selectAllLabel, enabled, 'inline-flex');
            setVisibility(deleteSelectedButton, enabled, 'inline-flex');
            setVisibility(cancelButton, enabled, 'inline-flex');
            checkboxes.forEach(function (checkbox) {
                checkbox.disabled = !enabled;
                checkbox.style.visibility = enabled ? 'visible' : 'hidden';
                checkbox.checked = false;
            });
            selectAll.checked = false;
            selectAll.indeterminate = false;
            updateSelection();
        }

        deleteModeButton.addEventListener('click', function () {
            setSelectionMode(true);
        });
        cancelButton.addEventListener('click', function () {
            setSelectionMode(false);
        });
        selectAll.addEventListener('change', function () {
            checkboxes.forEach(function (checkbox) {
                checkbox.checked = selectAll.checked;
            });
            updateSelection();
        });
        checkboxes.forEach(function (checkbox) {
            checkbox.addEventListener('change', updateSelection);
        });
        const deleteForm = deleteSelectedButton.form;
        if (deleteForm) {
            deleteForm.addEventListener('submit', function (event) {
                const selectedCount = checkboxes.filter(function (checkbox) {
                    return checkbox.checked;
                }).length;
                if (!selectedCount || !window.confirm('Delete ' + selectedCount + ' selected notification(s)?')) {
                    event.preventDefault();
                }
            });
        }
        setSelectionMode(false);
    });
});