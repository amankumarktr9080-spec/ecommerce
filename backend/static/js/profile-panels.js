function initProfilePanels() {
    const toggles = document.querySelectorAll('[data-profile-panel-toggle]');
    const panels = Array.from(toggles)
        .map(button => document.getElementById(button.dataset.profilePanelToggle))
        .filter(Boolean);

    toggles.forEach(function (button) {
        const controlledPanel = document.getElementById(button.dataset.profilePanelToggle);
        button.setAttribute('aria-expanded', controlledPanel && controlledPanel.style.display !== 'none' ? 'true' : 'false');
        button.addEventListener('click', function () {
            const target = document.getElementById(button.dataset.profilePanelToggle);
            const shouldOpen = target.style.display === 'none' || !target.style.display;
            panels.forEach(function (panel) {
                panel.style.display = panel === target && shouldOpen ? 'block' : 'none';
            });
            toggles.forEach(function (toggle) {
                toggle.setAttribute('aria-expanded', toggle === button && shouldOpen ? 'true' : 'false');
            });
            if (shouldOpen) target.scrollIntoView({behavior: 'smooth', block: 'nearest'});
        });
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initProfilePanels, {once: true});
} else {
    initProfilePanels();
}