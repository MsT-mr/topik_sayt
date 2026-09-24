(() => {
    const $=id=>document.getElementById(id);
    const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    let attempt=null, answers={}, index=0, sending=false, pageVersion=0;
    const csrf=()=>decodeURIComponent(document.cookie.split('; ').find(c=>c.startsWith('csrftoken='))?.slice(10)||'');
    async function api(url,data){const response=await fetch(url,data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf()},body:JSON.stringify(data)});const body=await response.json();if(!response.ok)throw Error(body.detail||'Ulanishda xatolik. Qayta urinib ko‘ring.');return body;}
    function showScreen(){ $('dashboard').hidden=true;$('lessonScreen').hidden=true;$('examScreen').style.display='block';window.Telegram?.WebApp?.BackButton?.show(); }
    function header(title,level){return `<button class="back-link" id="practiceBack">← Darslarga qaytish</button><div class="practice-heading"><p class="eyebrow">${esc(level)} · 서울대 한국어</p><h1>${esc(title)}</h1></div>`;}
    function bindBack(){ $('practiceBack').onclick=()=>{++pageVersion;window.topikShowDashboard?.()}; }
    window.topikCancelPractice=()=>{++pageVersion;};
    async function openVocabularyReview(version){
        showScreen();
        $('examScreen').innerHTML='<p class="empty-state">Lug‘atlar aralashtirilmoqda…</p>';
        try{
            const data=await api('/api/practice/vocabulary/');
            if(version!==pageVersion)return;
            let words=data.words||[], i=0, revealed=false, busy=false;
            if(!words.length){
                $('examScreen').innerHTML=header('Lug‘at takrorlash',data.book_level||'')+'<p class="empty-state">Takrorlash uchun lug‘at topilmadi.</p>';
                bindBack(); return;
            }
            const render=()=>{
                const word=words[i];
                if(!word){
                    $('examScreen').innerHTML=header('Lug‘at takrorlash',data.book_level)+'<div class="practice-score"><span>잘했어요!</span><h2>Tugadi ✓</h2><p>Eski va yangi lug‘atlar aralash takrorlandi.</p><button class="primary" id="vocabAgain">Yana aralashtirish ↻</button></div>';
                    bindBack(); $('vocabAgain').onclick=()=>window.topikOpenExam('vocabulary'); return;
                }
                $('examScreen').innerHTML=header('Lug‘at takrorlash',data.book_level)+
                    `<div class="practice-progress"><span>${i+1} / ${words.length}</span><div><i style="width:${(i+1)/words.length*100}%"></i></div><span>${esc(word.book_level)} · ${word.lesson??'-'}-dars</span></div>`+
                    `<div class="flash-card"><div class="flash-count">${esc(word.book_level)} · ${word.lesson??'-'}-dars</div>`+
                    `<button class="flash-face" id="reviewReveal" aria-expanded="false"><span lang="ko">${esc(word.korean)}</span><small>${revealed?esc(word.translation):'Tarjimasini ko‘rish uchun bosing'}</small></button>`+
                    `<div class="flash-actions"><button class="secondary" id="reviewAgain" ${revealed?'':'disabled'}>Yana takrorlayman</button>`+
                    `<button class="primary" id="reviewLearned" ${revealed?'':'disabled'}>Yodladim ✓</button></div>`+
                    `<p class="subtle">Takrorlash bosqichlari: ${data.review_levels.map(esc).join(' + ')}</p><p id="reviewError" role="alert"></p></div>`;
                bindBack();
                $('reviewReveal').onclick=()=>{
                    if(busy||revealed)return;
                    revealed=true;
                    $('reviewReveal').querySelector('small').textContent=word.translation;
                    $('reviewReveal').setAttribute('aria-expanded','true');
                    $('reviewAgain').disabled=false; $('reviewLearned').disabled=false;
                    window.Telegram?.WebApp?.HapticFeedback?.impactOccurred?.('medium');
                };
                const next=async learned=>{
                    if(busy)return; busy=true;
                    $('reviewAgain').disabled=true; $('reviewLearned').disabled=true;
                    try{
                        await api(`/api/words/${word.id}/progress/`,{learned});
                        i++; revealed=false; busy=false; render();
                    }catch(e){
                        busy=false; $('reviewError').textContent=e.message;
                        $('reviewAgain').disabled=false; $('reviewLearned').disabled=false;
                    }
                };
                $('reviewAgain').onclick=()=>next(false);
                $('reviewLearned').onclick=()=>next(true);
            };
            render();
        }catch(e){
            if(version!==pageVersion)return;
            $('examScreen').innerHTML=header('Lug‘at takrorlash','')+`<p class="empty-state">${esc(e.message)}</p>`;
            bindBack();
        }
    }
    window.topikOpenExam=async function(mode='grammar'){
        showScreen();const version=++pageVersion;
        if(mode==='vocabulary'){await openVocabularyReview(version);return;}
        $('examScreen').innerHTML='<p class="empty-state">Darajangizdagi mashqlar yuklanmoqda…</p>';
        try{
            const [catalog,data]=await Promise.all([api('/api/practice/'),api('/api/lessons/')]);
            if(version!==pageVersion)return;
            const vocabulary=mode==='vocabulary';
            $('examScreen').innerHTML=header(vocabulary?'Lug‘at flashkartalari':'Grammatika mashqi',catalog.book_level)+`<div class="practice-intro"><span class="practice-symbol">${vocabulary?'단어':'문법'}</span><h2>${vocabulary?'So‘zni eslang. Kartani oching.':'Gapdagi bo‘sh joyni to‘ldiring.'}</h2><p>${vocabulary?'Kartani bosing: u silkinadi va tarjimasi ochiladi. Keyin yodlaganingizni belgilang.':'O‘zbekcha ma’noga mos variantni tanlab, koreyscha gapni tugating.'}</p><label for="practiceLesson">Darsni tanlang</label><select id="practiceLesson">${vocabulary?'':'<option value="">Barcha darslar — darajamga mos test</option>'}${data.lessons.map(l=>`<option value="${l.id}">${esc(l.title)} · ${vocabulary?l.word_count+' so‘z':l.grammar_count+' qoida'}</option>`).join('')}</select><button class="primary" id="beginPractice" ${(!data.lessons.length||(!vocabulary&&!catalog.grammar_count))?'disabled':''}>${vocabulary?'Kartochkalarni ochish':'Testni boshlash'} →</button><p id="practiceError" role="alert"></p><small>${vocabulary?'O‘z bahoyingiz saqlanadi; bu avtomatik bilim testi emas.':catalog.grammar_count+' ta mavjud mashq · javoblar serverda tekshiriladi'}</small></div>`;
            bindBack();
            $('beginPractice').onclick=async()=>{
                const button=$('beginPractice');button.disabled=true;
                const lesson=Number($('practiceLesson').value)||null;
                if(vocabulary){++pageVersion;await window.topikOpenVocabularyLesson?.(lesson);return;}
                try{const result=await api('/api/practice/start/',{lesson_id:lesson});if(version!==pageVersion)return;attempt=result;answers={};index=0;sending=false;renderQuestion();}
                catch(e){if(version===pageVersion){$('practiceError').textContent=e.message;button.disabled=false;}}
            };
        }catch(e){if(version!==pageVersion)return;$('examScreen').innerHTML=header('Mashqni yuklab bo‘lmadi','')+`<p class="empty-state">${esc(e.message)}</p>`;bindBack();}
    };
    window.topikStartAIPractice = result => { showScreen(); ++pageVersion; attempt=result; answers={}; index=0; sending=false; renderQuestion(); };
    function renderQuestion(){
        const question=attempt.questions[index], choice=answers[index];
        const pieces=question.sentence.split('___');
        $('examScreen').innerHTML=header('Grammatika · bo‘sh joyni to‘ldiring',attempt.book_level)+`<div class="practice-progress"><span>${index+1} / ${attempt.questions.length}</span><div><i style="width:${(index+1)/attempt.questions.length*100}%"></i></div><span>${question.lesson}-dars</span></div><div class="grammar-question"><p class="eyebrow">GAPNI TUGATING</p><p class="question-sentence" lang="ko">${esc(pieces[0])}<span class="sentence-gap ${choice===undefined?'':'filled'}">${choice===undefined?'…':esc(question.options[choice])}</span>${esc(pieces[1])}</p><p class="question-translation">${esc(question.translation)}</p><div class="answer-chips">${question.options.map((option,i)=>`<button class="answer-chip ${choice===i?'chosen':''}" data-choice="${i}" aria-pressed="${choice===i}"><small>${i+1}</small><span lang="ko">${esc(option)}</span></button>`).join('')}</div><div class="question-actions"><button class="secondary" id="previousQuestion" ${index===0?'disabled':''}>← Oldingi</button><button class="primary" id="nextQuestion" ${choice===undefined?'disabled':''}>${index===attempt.questions.length-1?'Natijani ko‘rish':'Keyingi →'}</button></div><p id="questionError" role="alert"></p></div>`;
        bindBack();
        document.querySelectorAll('[data-choice]').forEach(button=>button.onclick=()=>{answers[index]=Number(button.dataset.choice);window.Telegram?.WebApp?.HapticFeedback?.selectionChanged?.();renderQuestion()});
        $('previousQuestion').onclick=()=>{if(index>0){index--;renderQuestion()}};
        $('nextQuestion').onclick=async()=>{if(index<attempt.questions.length-1){index++;renderQuestion();return;}if(sending)return;sending=true;const version=pageVersion;$('nextQuestion').disabled=true;$('nextQuestion').textContent='Tekshirilmoqda…';try{const result=await api(`/api/practice/${attempt.id}/submit/`,{answers});if(version===pageVersion)renderResult(result);}catch(e){if(version===pageVersion){$('questionError').textContent=e.message;$('nextQuestion').disabled=false;$('nextQuestion').textContent='Qayta yuborish'}}finally{sending=false}};
    }
    function renderResult(result){
        $('examScreen').innerHTML=header('Mashq natijasi',result.book_level)+`<div class="practice-score"><span>잘했어요!</span><h2>${result.percentage}%</h2><p>${result.total} ta gapdan ${result.score} tasi to‘g‘ri.</p><small>Bu mashq natijasi — rasmiy TOPIK darajasi emas.</small><button class="primary" id="practiceAgain">Yana mashq qilish ↻</button></div><section class="ai-panel"><div><p class="eyebrow">GEMINI · AI USTOZ</p><h3>Xatolaringizdan o‘rganing</h3><p>Qaysi qoidani takrorlashni birga aniqlaymiz.</p></div><button class="secondary" id="resultAI" ${!result.ai_available&&!result.ai_analysis?'disabled':''}>${result.ai_analysis?'Tahlil tayyor':'AI bilan tahlil qilish ✦'}</button><p class="ai-text" id="resultAIText" aria-live="polite"></p></section><div class="practice-review">${result.review.map(r=>`<details class="review-row ${r.is_correct?'correct':'incorrect'}"><summary><span>${r.is_correct?'✓':'↻'}</span><strong lang="ko">${esc(r.sentence.replace('___',r.correct))}</strong><small>${r.lesson}-dars</small></summary><div><p>${esc(r.translation)}</p><p>Sizning javobingiz: <b>${esc(r.chosen)}</b> · To‘g‘risi: <b>${esc(r.correct)}</b></p><p>${esc(r.explanation)}</p></div></details>`).join('')}</div>`;
        bindBack();$('practiceAgain').onclick=()=>window.topikOpenExam('grammar');
        $('resultAIText').textContent=result.ai_analysis||(!result.ai_available?'AI hali ulanmagan. Hozircha har bir javob ostidagi izohlardan foydalaning.':'');
        $('resultAI').onclick=()=>loadAI($('resultAI'),$('resultAIText'),`/api/practice/${result.id}/ai/`);
        if(result.ai_analysis)$('resultAI').disabled=true;
        window.scrollTo({top:0,behavior:'smooth'});
    }
    async function loadAI(button,output,url){button.disabled=true;output.textContent='AI natijangizni tahlil qilyapti…';try{const data=await api(url,{});output.textContent=data.text;button.textContent='Tahlil tayyor ✓'}catch(e){output.textContent=e.message;button.disabled=false;button.textContent='Qayta urinish'}}
    document.addEventListener('DOMContentLoaded',()=>{const button=$('studyAI');if(button)button.onclick=()=>loadAI(button,$('studyAIText'),'/api/ai/study/');});
})();
