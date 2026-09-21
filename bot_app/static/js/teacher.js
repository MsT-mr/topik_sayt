document.addEventListener('click', async event => {
    const button = event.target.closest('[data-copy]');
    if (!button) return;
    try { await navigator.clipboard.writeText(button.dataset.copy); button.textContent = 'Nusxalandi ✓'; }
    catch { const range = document.createRange(); range.selectNodeContents(button.previousElementSibling); window.getSelection().removeAllRanges(); window.getSelection().addRange(range); button.textContent = 'ID belgilandi — nusxalang'; }
});
