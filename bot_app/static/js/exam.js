(function () {
    "use strict";

    const tg = window.Telegram?.WebApp ?? null;

    let currentExam = null;
    let examQuestions = [];
    let currentIndex = 0;
    let userAnswers = {};
    let isSubmitting = false;

    window.topikOpenExam = async function () {
        const appShell = document.querySelector(".app-shell");
        const vocabularyScreen = document.getElementById("vocabularyScreen");
        const examScreen = document.getElementById("examScreen");

        if (!appShell || !examScreen) return;

        if (vocabularyScreen) vocabularyScreen.style.display = "none";

        appShell.querySelectorAll(":scope > *").forEach(child => {
            if (child !== examScreen && !child.classList.contains("top-header")) {
                child.style.display = "none";
            }
        });

        examScreen.style.display = "block";

        // Telegram WebApp Native BackButton & closing confirmation
        if (tg?.BackButton) {
            tg.BackButton.show();
            tg.BackButton.onClick(window.topikShowDashboard);
        }
        if (tg?.enableClosingConfirmation) {
            tg.enableClosingConfirmation();
        }

        window.scrollTo({ top: 0, behavior: "smooth" });

        await loadAndStartExam();
    };

    async function loadAndStartExam() {
        const screen = document.getElementById("examScreen");
        if (!screen) return;

        screen.innerHTML = `
            <div class="exam-header">
                <button type="button" class="exam-back" id="examBackBtn" aria-label="Orqaga">‹</button>
                <div class="exam-title-box">
                    <span>TOPIK TEST</span>
                    <strong>Savollar yuklanmoqda...</strong>
                </div>
                <div style="width:44px"></div>
            </div>
            <div style="text-align:center; padding: 40px; color: var(--muted, #666);">
                <div class="login-loader" style="display:inline-block; margin-bottom:12px;"></div>
                <p>Test savollari serverdan olinmoqda...</p>
            </div>
        `;

        document.getElementById("examBackBtn")?.addEventListener("click", window.topikShowDashboard);

        try {
            const res = await fetch("/api/exams/");
            const exams = await res.json();

            if (!exams || exams.length === 0) {
                renderNoExam();
                return;
            }

            // Hozirgi faol 1-imtihonni olamiz
            const examId = exams[0].id;
            const detailRes = await fetch(`/api/exams/${examId}/`);
            const detail = await detailRes.json();

            currentExam = detail.exam;
            examQuestions = detail.questions;
            currentIndex = 0;
            userAnswers = {};
            isSubmitting = false;

            if (!examQuestions || examQuestions.length === 0) {
                renderNoExam();
                return;
            }

            renderQuestion();

        } catch (e) {
            console.error("Exam load error:", e);
            screen.innerHTML = `
                <div class="exam-header">
                    <button type="button" class="exam-back" onclick="window.topikShowDashboard()">‹</button>
                    <div class="exam-title-box"><span>XATOLIK</span><strong>Yuklab bo'lmadi</strong></div>
                    <div style="width:44px"></div>
                </div>
                <div style="text-align:center; padding:40px;">
                    <p style="color:#ef4444; margin-bottom:16px;">Server bilan ulanishda xatolik yuz berdi.</p>
                    <button class="exam-btn exam-btn-primary" onclick="window.topikOpenExam()">Qaytadan urinish</button>
                </div>
            `;
        }
    }

    function renderNoExam() {
        const screen = document.getElementById("examScreen");
        if (!screen) return;
        screen.innerHTML = `
            <div class="exam-header">
                <button type="button" class="exam-back" onclick="window.topikShowDashboard()">‹</button>
                <div class="exam-title-box"><span>TOPIK TEST</span><strong>Mavjud emas</strong></div>
                <div style="width:44px"></div>
            </div>
            <div style="text-align:center; padding:40px;">
                <p>Hozircha faol imtihonlar mavjud emas. Tez orada yangi testlar joylanadi!</p>
            </div>
        `;
    }

    function renderQuestion() {
        const screen = document.getElementById("examScreen");
        if (!screen || !currentExam) return;

        const q = examQuestions[currentIndex];
        const progressPercent = Math.round(((currentIndex + 1) / examQuestions.length) * 100);
        const selectedOption = userAnswers[q.id] || "";

        screen.innerHTML = `
            <div class="exam-header">
                <button type="button" class="exam-back" id="examBackBtn">‹</button>
                <div class="exam-title-box">
                    <span>${escapeHtml(currentExam.title)}</span>
                    <strong>Savol ${currentIndex + 1} / ${examQuestions.length}</strong>
                </div>
                <div style="width:44px"></div>
            </div>

            <div class="exam-progress-bar-wrap">
                <div class="exam-progress-bar-fill" style="width: ${progressPercent}%;"></div>
            </div>

            <div class="exam-card-box">
                <div class="exam-q-number">${q.question_type_display || q.question_type}</div>
                <div class="exam-q-text">${escapeHtml(q.question_text)}</div>

                <div class="exam-options-grid">
                    ${["A", "B", "C", "D"].map(opt => `
                        <button type="button" class="exam-option-btn ${selectedOption === opt ? 'selected' : ''}" data-option="${opt}">
                            <span class="exam-option-letter">${opt}</span>
                            <span>${escapeHtml(q.options[opt] || "")}</span>
                        </button>
                    `).join("")}
                </div>

                <div class="exam-actions">
                    ${currentIndex > 0 ? `
                        <button type="button" class="exam-btn" id="examPrevBtn" style="background:#e5e7eb; color:#374151;">← Oldingi</button>
                    ` : `<div></div>`}

                    <button type="button" class="exam-btn exam-btn-primary" id="examNextBtn" ${!selectedOption ? 'disabled' : ''}>
                        ${currentIndex === examQuestions.length - 1 ? 'Natijani topshirish 🚀' : 'Keyingi savol →'}
                    </button>
                </div>
            </div>
        `;

        document.getElementById("examBackBtn")?.addEventListener("click", window.topikShowDashboard);

        // Variant tanlash
        screen.querySelectorAll(".exam-option-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                const opt = btn.dataset.option;
                userAnswers[q.id] = opt;

                // Telegram haptic
                tg?.HapticFeedback?.selectionChanged?.();

                screen.querySelectorAll(".exam-option-btn").forEach(b => b.classList.remove("selected"));
                btn.classList.add("selected");

                const nextBtn = document.getElementById("examNextBtn");
                if (nextBtn) nextBtn.disabled = false;
            });
        });

        document.getElementById("examPrevBtn")?.addEventListener("click", () => {
            if (currentIndex > 0) {
                currentIndex--;
                tg?.HapticFeedback?.impactOccurred?.("light");
                renderQuestion();
            }
        });

        document.getElementById("examNextBtn")?.addEventListener("click", () => {
            if (currentIndex < examQuestions.length - 1) {
                currentIndex++;
                tg?.HapticFeedback?.impactOccurred?.("light");
                renderQuestion();
            } else {
                submitExam();
            }
        });
    }

    async function submitExam() {
        if (isSubmitting) return;
        isSubmitting = true;

        const screen = document.getElementById("examScreen");
        const nextBtn = document.getElementById("examNextBtn");
        if (nextBtn) {
            nextBtn.disabled = true;
            nextBtn.textContent = "Tekshirilmoqda...";
        }

        tg?.HapticFeedback?.impactOccurred?.("medium");

        // Talaba ID sini olamiz
        let studentId = "";
        try {
            studentId = localStorage.getItem("topik_student_id") || "";
        } catch (e) {}

        const payload = {
            student_id: studentId,
            telegram_id: tg?.initDataUnsafe?.user?.id || null,
            answers: userAnswers
        };

        try {
            const res = await fetch(`/api/exams/${currentExam.id}/submit/`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.detail || "Serverda xatolik yuz berdi.");
            }

            renderResult(data);

        } catch (e) {
            console.error("Submit error:", e);
            alert("Natijani topshirishda xatolik: " + e.message);
            isSubmitting = false;
            if (nextBtn) {
                nextBtn.disabled = false;
                nextBtn.textContent = "Qaytadan topshirish";
            }
        }
    }

    function renderResult(data) {
        const screen = document.getElementById("examScreen");
        if (!screen) return;

        if (data.passed) {
            tg?.HapticFeedback?.notificationOccurred?.("success");
        } else {
            tg?.HapticFeedback?.notificationOccurred?.("warning");
        }

        // Bosh sahifadagi statistikalarni yangilash
        if (data.student_stats) {
            const testEl = document.getElementById("testValue");
            if (testEl && data.student_stats.tests_completed !== undefined) {
                testEl.textContent = String(data.student_stats.tests_completed);
            }
            const streakEl = document.getElementById("streakValue");
            if (streakEl && data.student_stats.streak !== undefined) {
                streakEl.textContent = String(data.student_stats.streak);
            }
        }

        screen.innerHTML = `
            <div class="exam-header">
                <button type="button" class="exam-back" onclick="window.topikShowDashboard()">‹</button>
                <div class="exam-title-box">
                    <span>NATIJA</span>
                    <strong>${escapeHtml(data.exam_title)}</strong>
                </div>
                <div style="width:44px"></div>
            </div>

            <div class="exam-result-card">
                <div class="exam-result-badge">${data.passed ? "🏆" : "📚"}</div>
                <h3 style="font-size:22px; margin-bottom:4px;">
                    ${data.passed ? "Tabriklaymiz, imtihondan o'tdingiz!" : "Harakatni davom ettiring!"}
                </h3>
                <div class="exam-result-score">${data.score_percentage}%</div>
                <p class="exam-result-text">
                    ${data.total_questions} ta savoldan <strong>${data.correct_answers}</strong> tasiga to'g'ri javob berildi.
                </p>

                <div style="margin-bottom:24px;">
                    <button type="button" class="exam-btn exam-btn-primary" onclick="window.topikOpenExam()">
                        Qaytadan yechish 🔄
                    </button>
                    <button type="button" class="exam-btn" style="background:#f1f5f9; margin-top:8px; width:100%;" onclick="window.topikShowDashboard()">
                        Bosh sahifaga qaytish
                    </button>
                </div>

                <div style="text-align:left; margin-top:28px;">
                    <h4 style="font-size:17px; margin-bottom:14px;">🧠 AI Tutor Xatolar Tahlili:</h4>
                    ${data.review.map(r => `
                        <div class="exam-review-item ${r.is_correct ? 'review-correct' : 'review-wrong'}">
                            <div style="font-weight:600; margin-bottom:6px; font-size:15px;">
                                #${r.order}. ${r.is_correct ? '✅ To‘g‘ri' : '❌ Noto‘g‘ri'}
                            </div>
                            <div style="font-size:14px; margin-bottom:4px; color:#374151;">
                                ${escapeHtml(r.question_text)}
                            </div>
                            <div style="font-size:13px; font-weight:600;">
                                Sizning javob: <span style="color:${r.is_correct ? '#16a34a' : '#dc2626'}">${r.user_answer || "Belgilanmagan"}</span> | To'g'ri: <span style="color:#16a34a">${r.correct_answer}</span>
                            </div>
                            <div class="exam-review-exp">
                                💡 <strong>Izoh:</strong> ${escapeHtml(r.explanation)}
                            </div>
                        </div>
                    `).join("")}
                </div>
            </div>
        `;
    }

    function escapeHtml(text) {
        if (!text) return "";
        return String(text)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

})();
