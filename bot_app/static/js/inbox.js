(() => {
    let loading = false;
    window.topikLoadMessages = async function () {
        if (loading) return;
        loading = true;
        try {
            const res = await fetch('/api/messages/');
            if (!res.ok) return;
            const data = await res.json();
            const root = document.getElementById('studentInbox');
            const items = document.getElementById('inboxItems');
            if (!root || !items) return;
            root.hidden = false;
            document.getElementById('inboxCount').textContent = `(${data.messages.filter(m => !m.read).length} yangi)`;
            items.replaceChildren();
            if (!data.messages.length) items.textContent = 'Hozircha xabar yo‘q.';
            data.messages.forEach(message => {
                const article = document.createElement('article');
                article.style.cssText = 'padding:14px 0;border-bottom:1px solid var(--border)';
                const date = document.createElement('small');
                date.textContent = message.created_at;
                const body = document.createElement('p');
                body.style.cssText = 'white-space:pre-wrap;margin:8px 0;overflow-wrap:anywhere';
                body.textContent = message.text;
                article.append(date, body);
                if (!message.read) {
                    const button = document.createElement('button');
                    button.textContent = 'O‘qidim ✓';
                    button.style.cssText = 'padding:8px 12px;cursor:pointer;border-radius:8px';
                    button.onclick = async () => {
                        button.disabled = true;
                        try {
                            const token = document.cookie.split('; ').find(c => c.startsWith('csrftoken='))?.slice(10) || '';
                            const response = await fetch(`/api/messages/${message.id}/read/`, {method:'POST',headers:{'X-CSRFToken':decodeURIComponent(token)}});
                            if (!response.ok) throw Error();
                            await window.topikLoadMessages();
                        } catch {
                            button.disabled = false;
                            button.textContent = 'Qayta urinish';
                        }
                    };
                    article.append(button);
                }
                items.append(article);
            });
        } catch (e) {
            console.warn('Xabarlarni yuklash amalga oshmadi.');
        } finally {
            loading = false;
        }
    };
    setInterval(() => {
        if (!document.hidden && document.body.classList.contains('authenticated') && !document.getElementById('inboxDetails')?.open) window.topikLoadMessages();
    }, 30000);
})();
