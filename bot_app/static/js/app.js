(() => {
    'use strict';
    const $ = id => document.getElementById(id);
    const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    let student = null, activeLesson = null, activeTab = 'words', flashIndex = 0, revealed = false;
    let lessonRequest = 0, busy = false;
    const csrf = () => decodeURIComponent(document.cookie.split('; ').find(c => c.startsWith('csrftoken='))?.slice(10) || '');
    async function api(url, data) {
        const res = await fetch(url, data === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:JSON.stringify(data)});
        const body = await res.json();
        if (res.status === 401) showLogin();
        if (!res.ok) throw new Error(body.detail || 'Yuklashda xatolik. Qayta urinib ko‘ring.');
        return body;
    }
    function showLogin() {
        window.topikResetTutor?.();
        window.topikCancelPractice?.();
        $('studentApp').hidden = true; $('loginScreen').hidden = false;
        document.body.classList.remove('authenticated');
    }
    function renderStudent(data) {
        student = data;
        $('studentName').textContent = data.name;
        $('studentIdLabel').textContent = data.id;
        $('headerLevel').textContent = data.book_level;
        $('studentGroup').textContent = data.group || `${data.book_level} bosqichi`;
        $('courseTitle').textContent = `서울대 한국어 ${data.book_level}`;
        $('wordValue').textContent = data.words;
        $('streakValue').textContent = data.streak;
        $('testValue').textContent = data.tests;
        $('progressPercent').textContent = `${data.progress}%`;
        $('progressBar').style.width = `${data.progress}%`;
        $('progressDescription').textContent = `${data.level_words} / ${data.total_words} ta so‘z yodlangan`;
    }
    async function dashboard() {
        ++lessonRequest;
        window.topikCancelPractice?.();
        $('dashboard').hidden = false; $('dashboard').style.display = '';
        $('lessonScreen').hidden = true; $('lessonScreen').style.display = '';
        $('examScreen').style.display = 'none';
        document.querySelector('footer').style.display = '';
        window.Telegram?.WebApp?.BackButton?.hide();
        window.Telegram?.WebApp?.disableClosingConfirmation?.();
        $('lessonGrid').innerHTML = '<p class="empty-state">Darslar yuklanmoqda…</p>';
        try {
            const data = await api('/api/lessons/');
            renderStudent(data.student);
            window.topikTutorLessons?.(data.lessons, data.student.id);
            $('lessonCount').textContent = `${data.lessons.length} ta dars`;
            $('lessonGrid').innerHTML = data.lessons.length ? data.lessons.map(l => `<button class="lesson-card" data-lesson="${l.id}"><div class="lesson-top"><span class="lesson-number">${String(l.number).padStart(2,'0')}</span><span class="lesson-arrow">↗</span></div><h3>${escape(l.title)}</h3><p>${l.word_count} ta so‘z <span>·</span> ${l.grammar_count} ta qoida</p><div class="lesson-progress"><i style="width:${l.word_count ? Math.round(l.learned/l.word_count*100) : 0}%"></i></div><small>${l.learned} ta yodlangan · ${l.grammar_read} ta qoida o‘qilgan</small></button>`).join('') : '<p class="empty-state">Ustozingiz bu daraja uchun darslarni hali qo‘shmagan.</p>';
            $('lessonGrid').querySelectorAll('[data-lesson]').forEach(button => button.onclick=()=>openLesson(button.dataset.lesson));
            window.topikLoadMessages?.();
        } catch (e) { $('lessonGrid').innerHTML=`<div class="empty-state">${escape(e.message)} <button class="secondary" id="retryLessons">Qayta urinish</button></div>`; $('retryLessons').onclick=dashboard; }
    }
    window.topikShowDashboard = dashboard;
    async function enter(data) {
        renderStudent(data.student);
        $('loginScreen').hidden = true; $('studentApp').hidden = false;
        document.body.classList.add('authenticated');
        try { localStorage.setItem('topik_student_id', data.student.id); } catch {}
        await dashboard();
    }
    $('loginForm').onsubmit = async event => {
        event.preventDefault(); $('loginButton').disabled=true; $('loginMessage').textContent='';
        try { await enter(await api('/auth/login/', {student_id:$('studentIdInput').value.trim().toUpperCase()})); }
        catch(e){$('loginMessage').textContent=e.message;}
        finally{$('loginButton').disabled=false;}
    };
    $('logoutButton').onclick=async()=>{try{await api('/auth/logout/',{});try{localStorage.removeItem('topik_student_id');}catch{}student=null;showLogin();$('studentIdInput').value='';}catch(e){alert(e.message)}};
    document.querySelectorAll('[data-practice]').forEach(button=>button.onclick=()=>window.topikOpenExam?.(button.dataset.practice));
    window.topikOpenVocabularyLesson = id => openLesson(id, true);
    async function openLesson(id, flash=false) {
        $('examScreen').style.display='none';
        const request=++lessonRequest;
        $('dashboard').hidden=true; $('lessonScreen').hidden=false;
        $('lessonScreen').innerHTML='<p class="empty-state">Dars yuklanmoqda…</p>';
        try {
            const data=await api(`/api/lessons/${id}/`);
            if(request!==lessonRequest)return;
            activeLesson=data;activeTab=data.guide?'guide':'words';renderLesson();
            if(flash){flashIndex=0;revealed=false;renderFlash();}
            const tg=window.Telegram?.WebApp;
            tg?.BackButton?.show();
        } catch(e) {
            if(request!==lessonRequest)return;
            $('lessonScreen').innerHTML=`<p class="empty-state">${escape(e.message)}</p><button class="secondary" id="backFromError">Darslarga qaytish</button>`;
            $('backFromError').onclick=dashboard;
        }
    }
    function renderLesson() {
        const {lesson,words,grammar}=activeLesson;
        $('lessonScreen').innerHTML=`<button class="back-link" id="backToLessons">← Barcha darslar</button><div class="lesson-heading"><p class="eyebrow">${escape(lesson.book_level)} · 서울대 한국어</p><h1>${escape(lesson.title)}</h1><p>${words.length} ta so‘z va ${grammar.length} ta grammatika qoidasi</p></div><div class="lesson-tabs">${activeLesson.guide?`<button data-tab="guide" class="${activeTab==='guide'?'selected':''}">Darsni o‘rganish</button>`:''}<button data-tab="words" class="${activeTab==='words'?'selected':''}">Lug‘at <span>${words.length}</span></button><button data-tab="grammar" class="${activeTab==='grammar'?'selected':''}">Grammatika <span>${grammar.length}</span></button></div><div id="lessonContent"></div>`;
        $('backToLessons').onclick=dashboard;
        document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{activeTab=b.dataset.tab;renderLesson()});
        if(activeTab==='guide') renderGuide(); else if(activeTab==='grammar') renderGrammar(); else renderWords();
        window.scrollTo({top:0,behavior:'smooth'});
    }
    function renderGuide() {
        const guide=activeLesson.guide;
        $('lessonContent').innerHTML=`<section class="study-guide"><p class="eyebrow">DARS MAQSADI</p><h2>Bu darsda nimalarni o‘rganasiz?</h2><p>${escape(guide.overview)}</p><ul>${guide.goals.map(g=>`<li>${escape(g)}</li>`).join('')}</ul><div class="study-steps"><div><strong>1. Tushuning</strong><p>Qoidani o‘qing va misollarda qo‘shimchani ajrating.</p></div><div><strong>2. Qo‘llang</strong><p>Har qoida bilan o‘zingiz haqingizda 2 ta gap yozing.</p></div><div><strong>3. Tekshiring</strong><p>Mashqni mustaqil bajaring, keyin javobini oching.</p></div></div><button class="primary" id="guideGrammar">Batafsil grammatikani o‘rganish →</button></section><section class="study-guide"><p class="eyebrow">KUNDALIK SUHBAT</p><h2>O‘qing va rollarga bo‘lib takrorlang</h2><div class="study-dialogue">${guide.dialogue.map(line=>`<div><strong>${escape(line.speaker)}</strong><p lang="ko">${escape(line.ko)}</p><p>${escape(line.uz)}</p></div>`).join('')}</div></section><section class="study-guide"><h2>Mustaqil mashqlar</h2>${guide.rules.map((r,i)=>`<div class="study-exercise"><h3>${i+1}-mashq</h3><p>${escape(r.exercise.question)}</p><details><summary>Javob va izohni ko‘rish</summary><p lang="ko">${escape(r.exercise.answer)}</p><p>${escape(r.exercise.explanation)}</p></details></div>`).join('')}<p class="subtle">${escape(guide.origin)}. Noaniq joylarni ustozingiz bilan tekshiring.</p></section>`;
        $('guideGrammar').onclick=()=>{activeTab='grammar';renderLesson()};
    }
    function expandedRule(rule) {
        const detail=activeLesson.guide?.rules.find(r=>r.source_key===rule.source_key);
        if(!detail)return '';
        return `<div class="rule-detail"><h3>Batafsil tushuntirish</h3><p>${escape(detail.meaning)}</p><h4>Qanday yasaladi?</h4><p>${escape(detail.formation)}</p><h4>Qachon ishlatiladi?</h4><p>${escape(detail.usage)}</p><h4>Yana 3 ta misol</h4>${detail.examples.map(e=>`<div class="study-example"><p lang="ko">${escape(e.ko)}</p><p>${escape(e.uz)}</p></div>`).join('')}<div class="study-mistake"><h4>Xatoga yo‘l qo‘ymang</h4><p>${escape(detail.mistake)}</p></div><h4>O‘zingiz bajaring</h4><p>${escape(detail.exercise.question)}</p><details class="study-answer"><summary>Javobni tekshirish</summary><p>${escape(detail.exercise.answer)}</p><p>${escape(detail.exercise.explanation)}</p></details></div>`;
    }
    function renderWords() {
        const words=activeLesson.words;
        $('lessonContent').innerHTML=`<div class="words-toolbar"><p>So‘zlarni o‘qing yoki kartochkalar bilan mashq qiling.</p><button class="primary" id="startFlash" ${words.length?'':'disabled'}>Kartochkalar bilan mashq →</button></div><div id="flashArea"></div><div class="word-list">${words.map((w,i)=>`<div class="word-row"><span class="word-number">${i+1}</span><strong lang="ko">${escape(w.korean)}</strong><span>${escape(w.translation)}</span><button class="word-status ${w.learned?'learned':''}" data-word="${w.id}" aria-label="${escape(w.korean)}: ${w.learned?'takrorlash kerak':'yodladim'}">${w.learned?'✓ Yodlangan':'Yodladim'}</button></div>`).join('') || '<p class="empty-state">Bu darsga lug‘at hali qo‘shilmagan.</p>'}</div>`;
        $('startFlash').onclick=()=>{flashIndex=0;revealed=false;renderFlash()};
        document.querySelectorAll('[data-word]').forEach(button=>button.onclick=async()=>{
            const word=words.find(w=>w.id===Number(button.dataset.word));button.disabled=true;
            try{await saveWord(word,!word.learned);renderWords()}catch(e){button.disabled=false;alert(e.message)}
        });
    }
    async function saveWord(word, learned) {
        const data=await api(`/api/words/${word.id}/progress/`,{learned});
        word.learned=learned;renderStudent(data.student);
    }
    function renderFlash() {
        const word=activeLesson.words[flashIndex];
        const area=$('flashArea');
        if(!area)return;
        if(!word){renderWords();$('flashArea').innerHTML='<div class="practice-done">Mashq tugadi! Natijangiz ustoz panelida ham saqlandi.</div>';return;}
        area.innerHTML=`<div class="flash-card"><div class="flash-count">${flashIndex+1} / ${activeLesson.words.length}<button id="closeFlash" aria-label="Mashqni yopish">×</button></div><button class="flash-face" id="revealFlash" aria-expanded="false"><span lang="ko">${escape(word.korean)}</span><small aria-live="polite">${revealed?escape(word.translation):'Tarjimasini ko‘rish uchun bosing'}</small></button><div class="flash-actions"><button class="secondary" id="retryWord" ${revealed?'':'disabled'}>Yana takrorlayman</button><button class="primary" id="passWord" ${revealed?'':'disabled'}>Yodladim ✓</button></div><p id="flashError" role="alert"></p></div>`;
        $('revealFlash').onclick=async()=>{
            if(busy || revealed)return;
            busy=true;
            const face=$('revealFlash'), card=face.closest('.flash-card');
            window.Telegram?.WebApp?.HapticFeedback?.impactOccurred?.('heavy');
            try{await window.topikRevealCard(card,()=>{
                revealed=true;
                face.querySelector('small').textContent=word.translation;
                face.querySelector('small').classList.add('translation-reveal');
                face.setAttribute('aria-expanded','true');
            });}finally{busy=false;if(card.isConnected){$('retryWord').disabled=false;$('passWord').disabled=false;}}
        };
        $('closeFlash').onclick=()=>{if(!busy)renderWords()};
        async function next(learned){if(busy)return;busy=true;$('retryWord').disabled=true;$('passWord').disabled=true;try{await saveWord(word,learned);flashIndex++;revealed=false;renderFlash()}catch(e){$('flashError').textContent=e.message;$('retryWord').disabled=false;$('passWord').disabled=false}finally{busy=false}}
        $('retryWord').onclick=()=>next(false);$('passWord').onclick=()=>next(true);
    }
    function renderGrammar() {
        const rules=activeLesson.grammar;
        $('lessonContent').innerHTML=`<p class="grammar-help">Ot — ot, F — fe’l, S — sifat. Qoidani ochib, izoh va misollarni o‘qing.</p><div class="grammar-list">${rules.map((g,i)=>`<details class="grammar-card"><summary><span class="lesson-number">${i+1}</span><strong lang="ko">${escape(g.title)}</strong><span>${g.read?'✓':'＋'}</span></summary><div class="grammar-body"><p class="eyebrow">MA’NOSI</p><p>${escape(g.explanation || 'Manba PDF’da izoh berilmagan. Ustozdan so‘rang.')}</p><div class="grammar-example"><p class="eyebrow">MISOLLAR</p><p lang="ko">${escape(g.examples || 'Misol hali qo‘shilmagan.')}</p></div>${expandedRule(g)}<button class="${g.read?'secondary':'primary'}" data-grammar="${g.id}" ${g.read?'disabled':''}>${g.read?'✓ O‘qilgan':'O‘qib chiqdim ✓'}</button></div></details>`).join('') || '<p class="empty-state">Bu darsga grammatika hali qo‘shilmagan.</p>'}</div>`;
        document.querySelectorAll('[data-grammar]').forEach(button=>button.onclick=async()=>{button.disabled=true;try{await api(`/api/grammar/${button.dataset.grammar}/progress/`,{});rules.find(g=>g.id===Number(button.dataset.grammar)).read=true;button.textContent='✓ O‘qilgan';button.className='secondary';button.closest('details').querySelector('summary > span:last-child').textContent='✓'}catch(e){button.disabled=false;alert(e.message)}});
    }
    async function init(){
        window.Telegram?.WebApp?.ready();window.Telegram?.WebApp?.expand();
        window.Telegram?.WebApp?.BackButton?.onClick(dashboard);
        try{const data=await api('/auth/me/');await enter(data);return;}catch{}
        let saved='';try{saved=localStorage.getItem('topik_student_id')||''}catch{}
        if(saved){$('studentIdInput').value=saved;try{await enter(await api('/auth/login/',{student_id:saved}));return}catch(e){$('loginMessage').textContent=e.message}}
        showLogin();
    }
    init();
})();
