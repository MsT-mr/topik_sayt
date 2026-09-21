(() => {
    const $ = id => document.getElementById(id);
    let version = 0, owner = null, busy = false;
    function controls(disabled) {
        ['explainLesson', 'generateAITest', 'askTutor', 'aiLesson'].forEach(id => $(id).disabled = disabled);
    }
    window.topikResetTutor = () => {
        ++version; owner = null; busy = false;
        $('tutorMessages').replaceChildren(); $('tutorQuestion').value = ''; $('tutorStatus').textContent = '';
        controls(false);
    };
    window.topikTutorLessons = (lessons, student) => {
        if (owner !== student) { window.topikResetTutor(); owner = student; }
        const selected = $('aiLesson').value;
        $('aiLesson').replaceChildren(...lessons.map(l => new Option(l.title, l.id)));
        if (lessons.some(l => String(l.id) === selected)) $('aiLesson').value = selected;
        controls(busy || !lessons.length);
    };
    $('aiLesson').onchange = () => { ++version; $('tutorMessages').replaceChildren(); $('tutorStatus').textContent = ''; };
    function append(label, text) {
        const item = document.createElement('p');
        const title = document.createElement('strong'); title.textContent = label;
        item.append(title, document.createTextNode('\n' + text));
        $('tutorMessages').append(item); item.scrollIntoView({block:'nearest'});
    }
    async function send(mode) {
        if (busy) return;
        const lesson = Number($('aiLesson').value);
        if (!lesson) { $('tutorStatus').textContent = 'Avval darsni tanlang.'; return; }
        const message = $('tutorQuestion').value.trim();
        if (mode === 'chat' && !message) return;
        const current = version;
        busy = true; controls(true);
        $('tutorStatus').textContent = mode === 'test' ? 'AI 5 ta yangi test tayyorlamoqda…' : 'AI javob tayyorlamoqda…';
        try {
            const csrf = decodeURIComponent(document.cookie.split('; ').find(c=>c.startsWith('csrftoken='))?.slice(10)||'');
            const response = await fetch(mode === 'test' ? '/api/ai/test/' : '/api/ai/tutor/', {
                method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':csrf},
                body:JSON.stringify({lesson_id:lesson, mode, message})
            });
            const data = await response.json();
            if (current !== version) return;
            if (!response.ok) throw Error(data.detail || 'AI bilan ulanishda xatolik.');
            $('tutorStatus').textContent = '';
            if (mode === 'test') { window.topikStartAIPractice(data); return; }
            append('Siz', mode === 'lesson' ? 'Darsni tushuntiring.' : message);
            append('AI ustoz', data.text);
            if (mode === 'chat') $('tutorQuestion').value = '';
        } catch (error) {
            if (current === version) $('tutorStatus').textContent = error.message;
        } finally {
            if (current === version) { busy = false; controls(false); }
        }
    }
    $('tutorForm').onsubmit = event => { event.preventDefault(); send('chat'); };
    $('explainLesson').onclick = () => send('lesson');
    $('generateAITest').onclick = () => send('test');
})();
