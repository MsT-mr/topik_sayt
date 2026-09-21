(() => {
    const root = document.documentElement;
    const read = key => { try { return localStorage.getItem(key); } catch { return null; } };
    const save = (key,value) => { try { localStorage.setItem(key,value); } catch {} };
    const systemTheme = matchMedia('(prefers-color-scheme: dark)');
    const reduced = matchMedia('(prefers-reduced-motion: reduce)');
    function apply() {
        const theme = read('topik-theme') || (systemTheme.matches ? 'dark' : 'light');
        root.dataset.theme = theme;
        root.dataset.motion = reduced.matches || read('topik-motion') === 'off' ? 'off' : 'on';
        document.querySelectorAll('[data-toggle-theme]').forEach(button => {
            button.textContent = theme === 'dark' ? '☀ Yorug‘' : '☾ Qorong‘i';
            button.setAttribute('aria-label', theme === 'dark' ? 'Yorug‘ rejimga o‘tish' : 'Qorong‘i rejimga o‘tish');
        });
        document.querySelectorAll('[data-toggle-motion]').forEach(button => {
            const on = root.dataset.motion === 'on';
            button.textContent = on ? '✦ Animatsiya' : '◇ Animatsiya o‘chiq';
            button.setAttribute('aria-pressed', String(on));
            button.title = reduced.matches ? 'Qurilmangiz harakatlarni kamaytirishni so‘ragan.' : 'Animatsiyalarni yoqish yoki o‘chirish';
        });
    }
    apply();
    document.addEventListener('DOMContentLoaded', apply);
    systemTheme.addEventListener('change', apply);
    reduced.addEventListener('change', apply);
    document.addEventListener('click', event => {
        if (event.target.closest('[data-toggle-theme]')) { save('topik-theme', root.dataset.theme === 'dark' ? 'light' : 'dark'); apply(); }
        if (event.target.closest('[data-toggle-motion]')) { save('topik-motion', root.dataset.motion === 'on' ? 'off' : 'on'); apply(); }
    });
    window.topikRevealCard = async function (card, reveal) {
        if (!card || root.dataset.motion === 'off' || !card.animate) { reveal(); return; }
        const amplitude = innerWidth < 500 ? 26 : 38;
        const frames = [0,-1,1,-.85,.85,-.6,.6,-.35,.35,-.12,.12,0].map((n,i) => ({transform:`translateX(${n*amplitude}px) rotate(${n*4.5}deg) scale(${i>0&&i<10?1.015:1})`}));
        const animation = card.animate(frames,{duration:760,easing:'ease-in-out'});
        const timer = setTimeout(() => { if(card.isConnected) reveal(); },280);
        try { await animation.finished; } catch {} finally { clearTimeout(timer); if(card.isConnected) reveal(); }
    };
})();
