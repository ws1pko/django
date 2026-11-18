const buttons = document.querySelectorAll('.detail-tabs .tab-button');
const sections = ['about', 'updates', 'reports', 'organization']
    .map((id) => document.getElementById(id))
    .filter(Boolean);

buttons.forEach((button) => {
    button.addEventListener('click', () => {
        const selectedId = button.dataset.tab;

        sections.forEach((section) => {
            section.hidden = section.id !== selectedId;
        });

        buttons.forEach((item) => {
            item.classList.toggle('active', item === button);
        });
    });
});

const requestedTab = window.location.hash.slice(1);
if (requestedTab && sections.some((section) => section.id === requestedTab)) {
    const button = document.querySelector(`.detail-tabs .tab-button[data-tab="${requestedTab}"]`);
    if (button) button.click();
}
