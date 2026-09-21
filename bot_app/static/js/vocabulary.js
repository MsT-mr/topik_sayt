(function () {
    "use strict";

    let vocabularyWords = [
        { korean: "학교", translation: "maktab" },
        { korean: "학생", translation: "o‘quvchi" },
        { korean: "공부하다", translation: "o‘qimoq" },
        { korean: "친구", translation: "do‘st" },
        { korean: "사랑", translation: "sevgi" }
    ];

    async function loadWordsFromServer() {
        try {
            const response = await fetch("/api/vocabulary/");
            if (response.ok) {
                const data = await response.json();
                if (Array.isArray(data) && data.length > 0) {
                    vocabularyWords = data;
                }
            }
        } catch (e) {
            console.warn("Lug'at serverdan yuklanmadi, standart so'zlar ishlatiladi:", e);
        }
    }

    const colors = [
        "#4F7CFF",
        "#35A86B",
        "#E7A927",
        "#8B5CF6",
        "#E86A33",
        "#D9578A"
    ];

    let currentRound = [];
    let currentIndex = 0;
    let passedWords = [];
    let retryWords = [];
    let showingTranslation = false;
    let isAnimating = false;

    window.topikOpenVocabulary = async function () {
        await loadWordsFromServer();
        startFullLesson();
    };

    function startFullLesson() {
        currentRound = vocabularyWords.map(word => ({ ...word }));
        currentIndex = 0;
        passedWords = [];
        retryWords = [];
        showingTranslation = false;
        isAnimating = false;
        renderVocabulary();
    }

    function renderVocabulary() {
        const screen = document.getElementById("vocabularyScreen");

        if (!screen) {
            console.error("TOPIK: #vocabularyScreen topilmadi.");
            return;
        }

        screen.innerHTML = `
            <div class="vocabulary-header">
                <button
                    type="button"
                    class="vocabulary-back"
                    id="vocabularyBack"
                    aria-label="Dashboardga qaytish"
                >‹</button>

                <div class="vocabulary-title">
                    <span>LUG‘AT</span>
                    <strong>Flashcards</strong>
                </div>

                <div class="vocabulary-spacer"></div>
            </div>

            <div id="vocabularyFlashcardArea"></div>
        `;

        const backButton = document.getElementById("vocabularyBack");

        if (backButton) {
            backButton.addEventListener("click", function () {
                window.topikShowDashboard?.();
            });
        }

        renderCard();
    }

    function renderCard(direction) {
        const area = document.getElementById("vocabularyFlashcardArea");

        if (!area) return;

        const word = currentRound[currentIndex];

        if (!word) {
            showResult();
            return;
        }

        showingTranslation = false;
        isAnimating = false;

        area.innerHTML = `
            <div class="vocabulary-counter">
                ${currentIndex + 1} / ${currentRound.length}
            </div>

            <div class="vocabulary-scene">

                <!--
                    SHAKE LAYER:
                    Butun Flashcard shu qatlam bilan silkinadi.
                    Swipe esa ichki CARD transformidan foydalanadi.
                -->
                <div
                    class="vocabulary-shake-layer"
                    id="vocabularyShakeLayer"
                >
                    <div
                        class="vocabulary-card"
                        id="vocabularyCard"
                        tabindex="0"
                        role="button"
                        aria-label="Flashcardni ochish"
                    >
                        <div class="vocabulary-card-content">

                            <span class="vocabulary-korean">
                                ${escapeHtml(word.korean)}
                            </span>

                            <span class="vocabulary-translation">
                                ${escapeHtml(word.translation)}
                            </span>

    
                        </div>
                    </div>
                </div>

            </div>

            <div class="vocabulary-swipe-hints">
                <span class="vocabulary-retry">← RETRY</span>
                <span class="vocabulary-pass">PASS →</span>
            </div>
        `;

        const card = document.getElementById("vocabularyCard");

        if (!card) return;

        card.style.background =
            colors[currentIndex % colors.length];

        if (direction === "right") {
            card.classList.add("vocabulary-enter-right");
        }

        if (direction === "left") {
            card.classList.add("vocabulary-enter-left");
        }

        setupCard(card);
    }

    function setupCard(card) {
        let active = false;
        let startX = 0;
        let startY = 0;
        let swiping = false;

        card.addEventListener("pointerdown", function (event) {
            if (isAnimating) return;

            if (
                event.pointerType === "mouse" &&
                event.button !== 0
            ) {
                return;
            }

            active = true;
            swiping = false;

            startX = event.clientX;
            startY = event.clientY;

            card.classList.add("vocabulary-dragging");

            try {
                card.setPointerCapture(event.pointerId);
            } catch (error) {}
        });

        card.addEventListener("pointermove", function (event) {
            if (!active || isAnimating) return;

            const dx = event.clientX - startX;
            const dy = event.clientY - startY;

            if (
                !swiping &&
                Math.abs(dx) > 12 &&
                Math.abs(dx) > Math.abs(dy)
            ) {
                swiping = true;
            }

            if (!swiping) return;

            event.preventDefault();

            const rotation =
                Math.max(-18, Math.min(18, dx / 14));

            const opacity =
                Math.max(0.55, 1 - Math.abs(dx) / 600);

            card.style.transform =
                `translate3d(${dx}px, 0, 0) rotate(${rotation}deg)`;

            card.style.opacity = String(opacity);
        });

        card.addEventListener("pointerup", function (event) {
            if (!active || isAnimating) return;

            active = false;

            card.classList.remove("vocabulary-dragging");

            const dx = event.clientX - startX;
            const dy = event.clientY - startY;

            if (
                swiping &&
                Math.abs(dx) >= 90 &&
                Math.abs(dx) > Math.abs(dy)
            ) {
                if (dx > 0) {
                    completeCard("PASS");
                } else {
                    completeCard("RETRY");
                }

                return;
            }

            card.style.transform = "";
            card.style.opacity = "";

            if (
                !swiping &&
                Math.abs(dx) < 30 &&
                Math.abs(dy) < 30
            ) {
                toggleTranslation(card);
            }
        });

        card.addEventListener("pointercancel", function () {
            active = false;
            swiping = false;

            card.classList.remove("vocabulary-dragging");

            card.style.transform = "";
            card.style.opacity = "";
        });

        card.addEventListener("keydown", function (event) {
            if (isAnimating) return;

            if (
                event.key === "Enter" ||
                event.key === " "
            ) {
                event.preventDefault();
                toggleTranslation(card);
            }
        });
    }

    /*
     * IMPORTANT:
     *
     * Endi matn emas,
     * BUTUN FLASHCARD SHAKE LAYER orqali silkinadi.
     *
     * Card transform = swipe
     * Shake layer = click shake
     * Content = text/reveal
     */
    function toggleTranslation(card) {
        if (!card || isAnimating) return;

        window.Telegram?.WebApp?.HapticFeedback?.impactOccurred?.("light");

        const shakeLayer =
            document.getElementById("vocabularyShakeLayer");

        if (!shakeLayer) return;

        isAnimating = true;

        shakeLayer.animate(
            [
                {
                    transform: "translateX(0)"
                },
                {
                    transform: "translateX(-24px)"
                },
                {
                    transform: "translateX(24px)"
                },
                {
                    transform: "translateX(-21px)"
                },
                {
                    transform: "translateX(21px)"
                },
                {
                    transform: "translateX(-18px)"
                },
                {
                    transform: "translateX(18px)"
                },
                {
                    transform: "translateX(-14px)"
                },
                {
                    transform: "translateX(14px)"
                },
                {
                    transform: "translateX(-10px)"
                },
                {
                    transform: "translateX(10px)"
                },
                {
                    transform: "translateX(-6px)"
                },
                {
                    transform: "translateX(6px)"
                },
                {
                    transform: "translateX(0)"
                }
            ],
            {
                duration: 620,
                easing: "cubic-bezier(.36,.07,.19,.97)",
                iterations: 1,
                fill: "none"
            }
        );

        setTimeout(function () {
            showingTranslation = !showingTranslation;

            card.classList.toggle(
                "show-translation",
                showingTranslation
            );
        }, 240);

        setTimeout(function () {
            isAnimating = false;
        }, 660);
    }

    function completeCard(result) {
        if (isAnimating) return;

        const word = currentRound[currentIndex];

        if (!word) return;

        isAnimating = true;

        if (result === "PASS") {
            window.Telegram?.WebApp?.HapticFeedback?.impactOccurred?.("medium");

            const alreadyPassed =
                passedWords.some(
                    item => item.korean === word.korean
                );

            if (!alreadyPassed) {
                passedWords.push({ ...word });
            }

            retryWords = retryWords.filter(
                item => item.korean !== word.korean
            );
        }

        if (result === "RETRY") {
            window.Telegram?.WebApp?.HapticFeedback?.impactOccurred?.("light");

            retryWords = retryWords.filter(
                item => item.korean !== word.korean
            );

            retryWords.push({ ...word });

            passedWords = passedWords.filter(
                item => item.korean !== word.korean
            );
        }

        const card =
            document.getElementById("vocabularyCard");

        if (!card) {
            isAnimating = false;
            return;
        }

        const direction =
            result === "PASS"
                ? "right"
                : "left";

        card.classList.add(
            direction === "right"
                ? "vocabulary-exit-right"
                : "vocabulary-exit-left"
        );

        setTimeout(function () {
            currentIndex++;
            isAnimating = false;

            if (
                currentIndex >=
                currentRound.length
            ) {
                showResult();
                return;
            }

            renderCard(direction);
        }, 300);
    }

    function showResult() {
        const screen =
            document.getElementById("vocabularyScreen");

        if (!screen) return;

        const passCount = passedWords.length;
        const retryCount = retryWords.length;
        const total = vocabularyWords.length;

        const allPassed =
            retryCount === 0 &&
            passCount === total;

        screen.innerHTML = `
            <div class="vocabulary-result">

                <div class="vocabulary-result-icon">
                    ${allPassed ? "🎉" : "📚"}
                </div>

                <div class="vocabulary-result-label">
                    NATIJA
                </div>

                <h2>
                    ${allPassed ? "Ajoyib!" : "Dars tugadi"}
                </h2>

                <div class="vocabulary-result-stats">

                    <div class="vocabulary-result-pass">
                        <strong>${passCount}</strong>
                        <span>PASS</span>
                    </div>

                    <div class="vocabulary-result-retry">
                        <strong>${retryCount}</strong>
                        <span>RETRY</span>
                    </div>

                </div>

                <div class="vocabulary-result-actions">

                    <button
                        type="button"
                        class="vocabulary-result-primary"
                        id="vocabularyRestart"
                    >
                        Qayta boshlash
                    </button>

                    <button
                        type="button"
                        class="vocabulary-result-secondary"
                        id="vocabularyContinue"
                    >
                        Davom ettirish
                    </button>

                </div>

            </div>
        `;

        const restart =
            document.getElementById(
                "vocabularyRestart"
            );

        const continueButton =
            document.getElementById(
                "vocabularyContinue"
            );

        if (restart) {
            restart.addEventListener(
                "click",
                restartLesson
            );
        }

        if (continueButton) {
            continueButton.addEventListener(
                "click",
                function () {
                    window.topikShowDashboard?.();
                }
            );
        }
    }

    function restartLesson() {
        if (retryWords.length > 0) {
            currentRound =
                retryWords.map(
                    word => ({ ...word })
                );
        } else {
            currentRound =
                vocabularyWords.map(
                    word => ({ ...word })
                );

            passedWords = [];
        }

        currentIndex = 0;
        retryWords = [];
        showingTranslation = false;
        isAnimating = false;

        renderVocabulary();
    }

    function escapeHtml(value) {
        return String(value)
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }

})();
