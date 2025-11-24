console.log('AI Tester v1.4.0 loaded - Multi-page AI import with page indicators');
let tests = [];
let currentTest = null;
let currentQuestionIndex = 0;
let userAnswers = [];
let selectedTestIndex = null;
let testMode = 'test'; // 'test' alebo 'learn'
let timerInterval = null;
let timeLeft = 0;
let testStartTime = null;
let showAnswersMode = 'each'; // 'each', 'end', 'retry'
let questionAnswered = false; // Pre režim 'each' - či už bola ukázaná odpoveď
let retryStatisticsSaved = false; // Či už boli uložené štatistiky pre retry mode (pri prvom odovzdaní)
let originalTestQuestionCount = 0; // Pôvodný počet otázok v teste (pred retry)
let originalTestTitle = ''; // Pôvodný názov testu (bez " (Opakovanie)")

// Načítanie testov pri štarte
window.onload = function() {
    loadTests();
};

async function loadTests() {
    try {
        const response = await fetch('/api/tests');
        tests = await response.json();
        displayTestList();
    } catch (error) {
        console.error('Chyba pri načítaní testov:', error);
    }
}

function displayTestList() {
    const testList = document.getElementById('testList');

    if (tests.length === 0) {
        testList.innerHTML = '<p style="color: #999;">Žiadne testy. Nahrajte JSON súbor s testami.</p>';
        return;
    }

    testList.innerHTML = tests.map((test, index) => {
        const stats = getTestStatistics(test.title || 'Test ' + (index + 1));
        const filename = test.filename || '';

        return `
            <div class="test-item-wrapper">
                <input type="checkbox" class="test-checkbox" id="test-${index}"
                       onchange="updateMultiTestButton()">
                <div class="test-item" onclick="showTestSettings(${index})">
                    <div class="test-main-info">
                        <h3>${test.title || 'Test ' + (index + 1)}</h3>
                        <p>${test.description || ''}</p>
                        <p><strong>${test.questions ? test.questions.length : 0} otázok</strong></p>
                    </div>
                    <div class="test-stats">
                        ${stats.count > 0 ? `
                            <div class="stat-badge">
                                <span class="stat-label">Absolvované:</span>
                                <span class="stat-value">${stats.count}x</span>
                            </div>
                            <div class="stat-badge">
                                <span class="stat-label">Posledný:</span>
                                <span class="stat-value ${stats.lastPercentage >= 75 ? 'good' : stats.lastPercentage >= 50 ? 'medium' : 'bad'}">
                                    ${stats.lastPercentage}%
                                </span>
                            </div>
                            <div class="stat-badge">
                                <span class="stat-label">Priemer:</span>
                                <span class="stat-value ${stats.avgPercentage >= 75 ? 'good' : stats.avgPercentage >= 50 ? 'medium' : 'bad'}">
                                    ${stats.avgPercentage}%
                                </span>
                            </div>
                        ` : '<div class="no-stats">Zatiaľ neabsolvované</div>'}
                    </div>
                </div>
                <button class="btn-edit" onclick="event.stopPropagation(); editTest('${filename}')" title="Upraviť test">
                    ✏️ Upraviť
                </button>
            </div>
        `;
    }).join('');
}

function getTestStatistics(testName) {
    const results = JSON.parse(localStorage.getItem('testResults') || '[]');
    const testResults = results.filter(r => r.testName === testName);

    if (testResults.length === 0) {
        return { count: 0 };
    }

    const lastResult = testResults[testResults.length - 1];
    const avgPercentage = Math.round(
        testResults.reduce((sum, r) => sum + r.percentage, 0) / testResults.length
    );

    return {
        count: testResults.length,
        lastPercentage: lastResult.percentage,
        avgPercentage: avgPercentage
    };
}

function updateMultiTestButton() {
    const checkboxes = document.querySelectorAll('.test-checkbox:checked');
    const button = document.getElementById('startMultiBtn');

    if (checkboxes.length > 1) {
        button.style.display = 'inline-block';
        button.textContent = `Spustiť vybrané testy (${checkboxes.length})`;
    } else {
        button.style.display = 'none';
    }
}

function showVersionInfo() {
    document.querySelector('.section').style.display = 'none';
    document.getElementById('versionPage').style.display = 'block';
}

function showHelpPage() {
    document.querySelector('.section').style.display = 'none';
    document.getElementById('helpPage').style.display = 'block';
}

function showImportPage() {
    document.querySelector('.section').style.display = 'none';
    document.getElementById('importPage').style.display = 'block';
    loadFilesList();
    loadExistingTestsList();
}

async function loadExistingTestsList() {
    try {
        const response = await fetch('/api/tests');
        const testsList = await response.json();
        const container = document.getElementById('existingTestsContent');

        if (!testsList || testsList.length === 0) {
            container.innerHTML = '<p style="color: #999; text-align: center; font-style: italic;">Žiadne testy v priečinku</p>';
            return;
        }

        // Zoskupiť podľa filename (každý súbor môže obsahovať viac testov)
        const fileGroups = {};
        testsList.forEach(test => {
            const filename = test.filename || 'Neznámy súbor';
            if (!fileGroups[filename]) {
                fileGroups[filename] = [];
            }
            fileGroups[filename].push(test);
        });

        let html = '';
        Object.keys(fileGroups).sort().forEach(filename => {
            const tests = fileGroups[filename];
            const totalQuestions = tests.reduce((sum, test) => sum + (test.questions?.length || 0), 0);

            html += `
                <div style="padding: 10px; margin-bottom: 8px; background: white; border-radius: 6px; border-left: 4px solid #2196F3;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <strong style="color: #333;">${tests[0].title || filename}</strong>
                            <div style="font-size: 0.85em; color: #666; margin-top: 4px;">
                                📄 ${filename}
                            </div>
                        </div>
                        <div style="text-align: right;">
                            <span style="background: #2196F3; color: white; padding: 4px 10px; border-radius: 12px; font-size: 0.85em; font-weight: bold;">
                                ${totalQuestions} otázok
                            </span>
                        </div>
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;
    } catch (error) {
        console.error('Chyba pri načítaní testov:', error);
        document.getElementById('existingTestsContent').innerHTML =
            '<p style="color: #f44336; text-align: center;">Chyba pri načítaní zoznamu testov</p>';
    }
}

async function loadFilesList() {
    try {
        const response = await fetch('/api/list-files', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ folder: 'testy' })
        });

        const result = await response.json();
        const filesList = document.getElementById('filesList');

        if (result.error) {
            filesList.innerHTML = `<p style="color: #f44336; font-style: italic;">${result.error}</p>`;
            return;
        }

        if (result.files && result.files.length > 0) {
            filesList.innerHTML = `
                <p style="margin: 10px 0; color: #666;">Nájdené súbory v priečinku <strong>testy/</strong>:</p>
                <ul class="files-list-items">
                    ${result.files.map(file => `<li>📄 ${file}</li>`).join('')}
                </ul>
            `;
        } else {
            filesList.innerHTML = `
                <p style="color: #999; font-style: italic;">Priečinok testy/ je prázdny</p>
                <p style="margin-top: 10px; color: #666;">Vytvorte JSON súbory v priečinku <code>testy/</code></p>
            `;
        }
    } catch (error) {
        console.error('Chyba pri načítaní zoznamu súborov:', error);
        document.getElementById('filesList').innerHTML =
            `<p style="color: #f44336;">Chyba: ${error}</p>`;
    }
}

async function loadFromFolder() {
    try {
        const response = await fetch('/api/load-from-folder', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ folder: 'testy' })
        });

        const result = await response.json();

        if (result.success) {
            alert(result.message || 'Testy úspešne načítané!');
            loadTests();
            backToList();
        } else {
            alert('Chyba: ' + (result.error || 'Neznáma chyba'));
        }
    } catch (error) {
        alert('Chyba pri načítaní testov: ' + error);
    }
}

function showExample() {
    document.getElementById('importPage').style.display = 'none';
    document.getElementById('examplePage').style.display = 'block';
}

function backToImport() {
    document.getElementById('examplePage').style.display = 'none';
    document.getElementById('importPage').style.display = 'block';
    loadFilesList();
}

async function importTests() {
    const fileInput = document.getElementById('fileInput');
    const file = fileInput.files[0];

    if (!file) {
        alert('Vyberte súbor!');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/import', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (result.success) {
            alert('Testy úspešne nahrané!');
            loadTests();
            loadExistingTestsList();
            fileInput.value = '';
            backToList();
        } else {
            alert('Chyba: ' + result.error);
        }
    } catch (error) {
        alert('Chyba pri nahrávaní: ' + error);
    }
}

async function clearTests() {
    if (!confirm('Naozaj chcete vymazať všetky testy z pamäte?')) {
        return;
    }

    try {
        await fetch('/api/clear', { method: 'POST' });
        tests = [];
        displayTestList();
        alert('Všetky testy boli vymazané z pamäte');
        backToList();
    } catch (error) {
        alert('Chyba pri mazaní testov');
    }
}

function startMultipleTests() {
    const checkboxes = document.querySelectorAll('.test-checkbox:checked');
    const selectedIndexes = Array.from(checkboxes).map(cb => {
        return parseInt(cb.id.replace('test-', ''));
    });

    if (selectedIndexes.length < 2) {
        alert('Vyberte aspoň 2 testy!');
        return;
    }

    // Zlúčiť testy
    const mergedTest = {
        title: `Zlúčené testy (${selectedIndexes.length})`,
        description: tests.filter((_, i) => selectedIndexes.includes(i))
            .map(t => t.title || 'Test').join(', '),
        questions: []
    };

    // Pridať otázky zo všetkých vybraných testov
    selectedIndexes.forEach(index => {
        const test = tests[index];
        mergedTest.questions.push(...test.questions);
    });

    // Uložiť zlúčený test
    selectedTestIndex = -1; // Špeciálny flag pre zlúčený test
    tests.push(mergedTest);
    const mergedIndex = tests.length - 1;

    showTestSettings(mergedIndex);
}

function showTestSettings(index) {
    selectedTestIndex = index;
    const test = tests[index];

    document.querySelector('.section').style.display = 'none';
    document.getElementById('testList').parentElement.style.display = 'none';
    document.getElementById('testSettings').style.display = 'block';
    document.getElementById('settingsTitle').textContent = test.title || 'Test';

    // Nastaviť max rozsah otázok
    const totalQuestions = test.questions.length;
    document.getElementById('questionTo').value = totalQuestions;
    document.getElementById('questionTo').max = totalQuestions;
    document.getElementById('questionFrom').max = totalQuestions;
    document.getElementById('randomCount').max = totalQuestions;
    document.getElementById('randomCount').value = Math.min(20, totalQuestions);
}

function startTestWithSettings() {
    const timeLimit = parseInt(document.querySelector('input[name="time"]:checked').value);
    const shuffle = document.querySelector('input[name="shuffle"]:checked').value === 'true';
    const questionMode = document.querySelector('input[name="questionMode"]:checked').value;
    showAnswersMode = document.querySelector('input[name="showAnswers"]:checked').value;

    testMode = 'test';
    questionAnswered = false;
    retryStatisticsSaved = false; // Reset pre nový test
    currentTest = JSON.parse(JSON.stringify(tests[selectedTestIndex])); // Deep copy

    // Výber otázok podľa módu
    if (questionMode === 'range') {
        // Rozsah otázok
        const questionFrom = parseInt(document.getElementById('questionFrom').value) - 1;
        const questionTo = parseInt(document.getElementById('questionTo').value);
        currentTest.questions = currentTest.questions.slice(questionFrom, questionTo);
    } else {
        // Náhodný výber
        const randomCount = parseInt(document.getElementById('randomCount').value);
        currentTest.questions = getRandomQuestions(currentTest.questions, randomCount);
    }

    // Ulož pôvodný počet otázok a názov (pre retry mode)
    originalTestQuestionCount = currentTest.questions.length;
    originalTestTitle = currentTest.title;

    if (currentTest.questions.length === 0) {
        alert('Neplatný rozsah otázok!');
        return;
    }

    // Mixáž otázok a odpovedí
    if (shuffle) {
        // Zamixuj poradie otázok
        currentTest.questions = shuffleArray(currentTest.questions);

        // Zamixuj aj odpovede v každej otázke
        currentTest.questions = currentTest.questions.map(question => shuffleAnswers(question));
    }

    currentQuestionIndex = 0;
    // Vždy používať pole pre odpovede (možnosť vybrať viacero)
    userAnswers = currentTest.questions.map(q => []);

    document.getElementById('testSettings').style.display = 'none';
    document.getElementById('testInterface').style.display = 'block';
    document.getElementById('testTitle').textContent = currentTest.title || 'Test';
    document.getElementById('submitBtn').textContent = 'Odovzdať test'; // Reset tlačidla

    // Nastaviť časovač
    if (timeLimit > 0) {
        timeLeft = timeLimit * 60;
        testStartTime = Date.now();
        document.getElementById('timer').style.display = 'block';
        startTimer();
    } else {
        document.getElementById('timer').style.display = 'none';
    }

    showQuestion();
}

function showLearnMode() {
    const test = tests[selectedTestIndex];

    document.getElementById('testSettings').style.display = 'none';
    document.getElementById('learnMode').style.display = 'block';
    document.getElementById('learnModeTitle').textContent = test.title || 'Test';

    // Zobraziť všetky otázky naraz
    const container = document.getElementById('learnModeContainer');
    container.innerHTML = test.questions.map((question, qIndex) => {
        const isMultiple = Array.isArray(question.correct) && question.correct.length > 1;

        return `
            <div class="learn-question">
                <h3>Otázka ${qIndex + 1}: ${question.question}</h3>
                ${isMultiple ? '<p class="multiple-note">Viacero správnych odpovedí</p>' : ''}
                <div class="learn-answers">
                    ${question.answers.map((answer, aIndex) => {
                        const isCorrect = isMultiple
                            ? question.correct.includes(aIndex)
                            : (Array.isArray(question.correct) ? question.correct.includes(aIndex) : question.correct === aIndex);

                        return `
                            <div class="learn-answer ${isCorrect ? 'learn-answer-correct' : 'learn-answer-wrong'}">
                                ${answer}
                                ${isCorrect ? ' <span class="checkmark">✓ SPRÁVNE</span>' : ''}
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>
        `;
    }).join('');
}

function shuffleArray(array) {
    const arr = [...array];
    for (let i = arr.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
}

function toggleQuestionMode() {
    const mode = document.querySelector('input[name="questionMode"]:checked').value;
    if (mode === 'range') {
        document.getElementById('rangeInputs').style.display = 'block';
        document.getElementById('randomInputs').style.display = 'none';
    } else {
        document.getElementById('rangeInputs').style.display = 'none';
        document.getElementById('randomInputs').style.display = 'block';
    }
}

function shuffleAnswers(question) {
    // Vytvor kópiu otázky
    const shuffledQuestion = JSON.parse(JSON.stringify(question));

    // Vytvor mapu starých indexov na nové
    const indexMap = {};
    const shuffledAnswers = [];
    const indices = question.answers.map((_, i) => i);

    // Zamixuj indexy
    const shuffledIndices = shuffleArray(indices);

    // Preusporiadaj odpovede a vytvor mapu
    shuffledIndices.forEach((oldIndex, newIndex) => {
        shuffledAnswers[newIndex] = question.answers[oldIndex];
        indexMap[oldIndex] = newIndex;
    });

    shuffledQuestion.answers = shuffledAnswers;

    // Aktualizuj správne odpovede
    if (Array.isArray(question.correct)) {
        shuffledQuestion.correct = question.correct.map(oldIndex => indexMap[oldIndex]);
    } else {
        shuffledQuestion.correct = indexMap[question.correct];
    }

    return shuffledQuestion;
}

function getRandomQuestions(questions, count) {
    // Ak chceme viac otázok ako je dostupných, vráť všetky
    if (count >= questions.length) {
        return shuffleArray(questions);
    }

    // Náhodný výber N otázok
    const shuffled = shuffleArray(questions);
    return shuffled.slice(0, count);
}

function startTimer() {
    updateTimerDisplay();
    timerInterval = setInterval(() => {
        timeLeft--;
        updateTimerDisplay();

        if (timeLeft <= 0) {
            clearInterval(timerInterval);
            alert('Čas vypršal!');
            submitTest();
        }
    }, 1000);
}

function updateTimerDisplay() {
    const minutes = Math.floor(timeLeft / 60);
    const seconds = timeLeft % 60;
    document.getElementById('timer').textContent =
        `Zostáva: ${minutes}:${seconds.toString().padStart(2, '0')}`;

    // Červené zvýraznenie v poslednej minúte
    if (timeLeft < 60) {
        document.getElementById('timer').style.color = '#f44336';
    }
}

function showQuestion() {
    const question = currentTest.questions[currentQuestionIndex];
    const container = document.getElementById('questionContainer');
    const isMultiple = Array.isArray(question.correct) && question.correct.length > 1;
    const userAnswer = userAnswers[currentQuestionIndex];

    // Ak je už zodpovedané a režim "each" alebo "retry", zobraz feedback
    const showFeedback = questionAnswered && (showAnswersMode === 'each' || showAnswersMode === 'retry');

    let questionHTML = `
        <div class="question">
            <h3>Otázka ${currentQuestionIndex + 1}: ${question.question}</h3>
            ${question.answers.map((answer, index) => {
                const isSelected = userAnswer.includes(index);
                // Handle both old (number) and new (array) format
                const isCorrect = isMultiple
                    ? question.correct.includes(index)
                    : (Array.isArray(question.correct) ? question.correct.includes(index) : question.correct === index);

                let cssClass = '';
                let icon = '';

                if (showFeedback) {
                    // Zobraz feedback - zelená správna, červená nesprávna
                    if (isCorrect && isSelected) {
                        cssClass = 'answer-correct-selected';
                        icon = ' ✓';
                    } else if (isCorrect && !isSelected) {
                        cssClass = 'answer-correct-missed';
                        icon = ' ✓ (správne)';
                    } else if (!isCorrect && isSelected) {
                        cssClass = 'answer-wrong-selected';
                        icon = ' ✗';
                    } else {
                        cssClass = 'answer-neutral';
                    }

                    return `
                        <div class="answer ${cssClass}">
                            ${answer}${icon}
                        </div>
                    `;
                } else {
                    // Normálne zobrazenie s možnosťou klikať
                    const inputIcon = isSelected ? '☑' : '☐';  // Vždy checkbox

                    return `
                        <div class="answer ${isSelected ? 'selected' : ''}" onclick="selectAnswer(${index})">
                            <span class="answer-icon">${inputIcon}</span> ${answer}
                        </div>
                    `;
                }
            }).join('')}
        </div>
    `;

    container.innerHTML = questionHTML;

    document.getElementById('questionNumber').textContent =
        `${currentQuestionIndex + 1} / ${currentTest.questions.length}`;

    document.getElementById('prevBtn').disabled = currentQuestionIndex === 0;
    document.getElementById('nextBtn').style.display =
        currentQuestionIndex === currentTest.questions.length - 1 ? 'none' : 'inline-block';
    document.getElementById('submitBtn').style.display =
        currentQuestionIndex === currentTest.questions.length - 1 ? 'inline-block' : 'none';
}

function selectAnswer(answerIndex) {
    const currentAnswers = userAnswers[currentQuestionIndex];

    // Vždy checkbox správanie (toggle) - dá sa vybrať viacero
    const idx = currentAnswers.indexOf(answerIndex);
    if (idx > -1) {
        currentAnswers.splice(idx, 1);
    } else {
        currentAnswers.push(answerIndex);
    }

    showQuestion();
}

function previousQuestion() {
    if (currentQuestionIndex > 0) {
        currentQuestionIndex--;
        questionAnswered = false; // Reset feedback
        showQuestion();
    }
}

function nextQuestion() {
    // Ak je režim "each" alebo "retry" a ešte nebola ukázaná odpoveď, ukáž feedback
    if ((showAnswersMode === 'each' || showAnswersMode === 'retry') && !questionAnswered) {
        questionAnswered = true;
        showQuestion(); // Znova vykreslí otázku s vizuálnym feedbackom
        return;
    }

    // Pokračuj na ďalšiu otázku
    if (currentQuestionIndex < currentTest.questions.length - 1) {
        currentQuestionIndex++;
        questionAnswered = false;
        showQuestion();
    }
}

function submitTest() {
    // Ak je režim "each" alebo "retry" a posledná otázka nebola ešte ukázaná, ukáž ju najprv
    if ((showAnswersMode === 'each' || showAnswersMode === 'retry') && !questionAnswered) {
        questionAnswered = true;
        showQuestion();
        // Zmeň tlačidlo Submit na "Dokončiť" po zobrazení feedbacku
        document.getElementById('submitBtn').textContent = 'Dokončiť test';
        return;
    }

    const hasUnanswered = userAnswers.some(answer =>
        answer === null || (Array.isArray(answer) && answer.length === 0)
    );

    if (hasUnanswered) {
        if (!confirm('Niektoré otázky nie sú zodpovedané. Chcete naozaj odovzdať test?')) {
            return;
        }
    }

    // Režim "retry" - opakuj nesprávne otázky
    if (showAnswersMode === 'retry') {
        const incorrectQuestions = [];
        let correctCount = 0;

        currentTest.questions.forEach((question, index) => {
            const userAnswer = userAnswers[index];
            const isMultiple = Array.isArray(question.correct) && question.correct.length > 1;
            let correct = false;

            if (isMultiple) {
                const sortedUser = userAnswer ? [...userAnswer].sort() : [];
                const sortedCorrect = [...question.correct].sort();
                correct = JSON.stringify(sortedUser) === JSON.stringify(sortedCorrect);
            } else {
                const correctAnswer = Array.isArray(question.correct) ? question.correct[0] : question.correct;
                correct = userAnswer.length === 1 && userAnswer[0] === correctAnswer;
            }

            if (correct) {
                correctCount++;
            } else {
                incorrectQuestions.push({ question, originalIndex: index });
            }
        });

        // Ak sú nesprávne otázky, opakuj ich
        if (incorrectQuestions.length > 0) {
            // Ulož štatistiky po prvom odovzdaní (iba raz)
            if (!retryStatisticsSaved) {
                const totalQuestions = currentTest.questions.length;
                const percentage = Math.round((correctCount / totalQuestions) * 100);

                // Zisti pôvodný názov testu (bez " (Opakovanie)")
                const originalTitle = currentTest.title.replace(' (Opakovanie)', '');

                saveTestResult({
                    testName: originalTitle,
                    date: new Date().toISOString(),
                    score: correctCount,
                    total: totalQuestions,
                    percentage: percentage
                });

                retryStatisticsSaved = true;
                displayTestList(); // Obnoviť zobrazenie testov so štatistikami
                console.log(`Štatistiky uložené: ${correctCount}/${totalQuestions} (${percentage}%)`);
            }

            alert(`Máte ${incorrectQuestions.length} nesprávnych odpovedí. Budete ich teraz opakovať.`);

            // Vytvor nový test len s nesprávnymi otázkami
            const retryTest = {
                title: currentTest.title.includes('(Opakovanie)')
                    ? currentTest.title
                    : currentTest.title + ' (Opakovanie)',
                questions: incorrectQuestions.map(item => item.question)
            };

            currentTest = retryTest;
            currentQuestionIndex = 0;
            userAnswers = currentTest.questions.map(q => []);
            questionAnswered = false;

            document.getElementById('submitBtn').textContent = 'Odovzdať test';
            showQuestion();
            return;
        }
    }

    // Zastaviť časovač
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }

    showResults();
}

function showResults() {
    let correctCount = 0;
    const results = currentTest.questions.map((question, index) => {
        const userAnswer = userAnswers[index]; // Vždy pole
        const isMultiple = Array.isArray(question.correct) && question.correct.length > 1;
        let correct = false;
        let userAnswerText = '';
        let correctAnswerText = '';

        if (isMultiple) {
            // Viacero správnych odpovedí
            const sortedUser = userAnswer ? [...userAnswer].sort() : [];
            const sortedCorrect = [...question.correct].sort();
            correct = JSON.stringify(sortedUser) === JSON.stringify(sortedCorrect);

            userAnswerText = userAnswer && userAnswer.length > 0
                ? userAnswer.map(i => question.answers[i]).join(', ')
                : 'Nezodpovedané';
            correctAnswerText = question.correct.map(i => question.answers[i]).join(', ');
        } else {
            // Jedna správna odpoveď - correct môže byť číslo alebo array s 1 prvkom
            const correctAnswer = Array.isArray(question.correct) ? question.correct[0] : question.correct;
            correct = userAnswer.length === 1 && userAnswer[0] === correctAnswer;

            userAnswerText = userAnswer && userAnswer.length > 0
                ? userAnswer.map(i => question.answers[i]).join(', ')
                : 'Nezodpovedané';
            correctAnswerText = question.answers[correctAnswer];
        }

        if (correct) correctCount++;

        return {
            question: question.question,
            userAnswer: userAnswerText,
            correctAnswer: correctAnswerText,
            correct: correct
        };
    });

    const percentage = Math.round((correctCount / currentTest.questions.length) * 100);

    // Uložiť výsledok
    // Ak sme v retry mode a všetky otázky v tomto kole boli správne, ulož výsledok s pôvodným počtom otázok
    if (retryStatisticsSaved && correctCount === currentTest.questions.length) {
        // Retry mode skončil úspešne - všetky otázky správne
        saveTestResult({
            testName: originalTestTitle,
            date: new Date().toISOString(),
            score: originalTestQuestionCount,
            total: originalTestQuestionCount,
            percentage: 100
        });
    } else {
        // Normálny režim alebo retry s chybami
        saveTestResult({
            testName: currentTest.title,
            date: new Date().toISOString(),
            score: correctCount,
            total: currentTest.questions.length,
            percentage: percentage
        });
    }

    document.getElementById('testInterface').style.display = 'none';
    document.getElementById('results').style.display = 'block';

    // Určiť ktorý výsledok zobrazíme - ak je retry mode úspešný, zobraz pôvodný počet
    const displayScore = (retryStatisticsSaved && correctCount === currentTest.questions.length)
        ? originalTestQuestionCount
        : correctCount;
    const displayTotal = (retryStatisticsSaved && correctCount === currentTest.questions.length)
        ? originalTestQuestionCount
        : currentTest.questions.length;
    const displayPercentage = (retryStatisticsSaved && correctCount === currentTest.questions.length)
        ? 100
        : percentage;

    // Zobraz výsledky podobne ako learn mode - všetky otázky s odpoveďami
    document.getElementById('resultsContainer').innerHTML = `
        <div class="results-summary">
            <h3>Výsledok: ${displayScore} / ${displayTotal}</h3>
            <p style="font-size: 1.2em; margin-top: 10px;">${displayPercentage}%</p>
            ${(retryStatisticsSaved && correctCount === currentTest.questions.length)
                ? '<p style="font-size: 0.9em; color: #4CAF50; margin-top: 5px;">🎉 Všetky otázky správne po opakovaní!</p>'
                : ''}
        </div>
        ${currentTest.questions.map((question, qIndex) => {
            const userAnswer = userAnswers[qIndex];
            const isMultiple = Array.isArray(question.correct) && question.correct.length > 1;

            // Vypočítaj správnosť tejto otázky
            let questionCorrect = false;
            if (isMultiple) {
                const sortedUser = userAnswer ? [...userAnswer].sort() : [];
                const sortedCorrect = [...question.correct].sort();
                questionCorrect = JSON.stringify(sortedUser) === JSON.stringify(sortedCorrect);
            } else {
                const correctAnswer = Array.isArray(question.correct) ? question.correct[0] : question.correct;
                questionCorrect = userAnswer.length === 1 && userAnswer[0] === correctAnswer;
            }

            return `
                <div class="result-question ${questionCorrect ? 'result-correct' : 'result-incorrect'}">
                    <h4>Otázka ${qIndex + 1}: ${question.question}</h4>
                    ${isMultiple ? '<p class="multiple-note">Viacero správnych odpovedí</p>' : ''}
                    <div class="result-answers">
                        ${question.answers.map((answer, aIndex) => {
                            const isCorrect = isMultiple
                                ? question.correct.includes(aIndex)
                                : (Array.isArray(question.correct) ? question.correct.includes(aIndex) : question.correct === aIndex);
                            const isUserAnswer = userAnswer && userAnswer.includes(aIndex);

                            let cssClass = '';
                            let label = '';

                            // Zobraz detailný feedback (všetky režimy)
                            if (isCorrect && isUserAnswer) {
                                cssClass = 'result-answer-correct-selected';
                                label = ' ✓ SPRÁVNE - Vaša odpoveď';
                            } else if (isCorrect && !isUserAnswer) {
                                cssClass = 'result-answer-correct-missed';
                                label = ' ✓ SPRÁVNE';
                            } else if (!isCorrect && isUserAnswer) {
                                cssClass = 'result-answer-wrong-selected';
                                label = ' ✗ NESPRÁVNE - Vaša odpoveď';
                            } else {
                                cssClass = 'result-answer-neutral';
                            }

                            return `
                                <div class="result-answer ${cssClass}">
                                    ${answer}${label}
                                </div>
                            `;
                        }).join('')}
                    </div>
                </div>
            `;
        }).join('')}
    `;

    // Obnoviť zobrazenie testov so štatistikami
    displayTestList();
}

function saveTestResult(result) {
    let results = JSON.parse(localStorage.getItem('testResults') || '[]');
    results.push(result);
    // Uložiť len posledných 200 výsledkov
    if (results.length > 200) {
        results = results.slice(-200);
    }
    localStorage.setItem('testResults', JSON.stringify(results));
}

function clearStatistics() {
    if (!confirm('Naozaj chcete vymazať všetky štatistiky?')) {
        return;
    }
    localStorage.removeItem('testResults');
    displayTestList();
    alert('Štatistiky boli vymazané');
}

function backToList() {
    // Zastaviť časovač
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }

    document.getElementById('testInterface').style.display = 'none';
    document.getElementById('results').style.display = 'none';
    document.getElementById('testSettings').style.display = 'none';
    document.getElementById('learnMode').style.display = 'none';
    document.getElementById('importPage').style.display = 'none';
    document.getElementById('examplePage').style.display = 'none';
    document.getElementById('helpPage').style.display = 'none';
    document.getElementById('aiImportPage').style.display = 'none';
    document.getElementById('editTestPage').style.display = 'none';
    document.getElementById('versionPage').style.display = 'none';
    document.querySelector('.section').style.display = 'block';
    currentTest = null;
    testMode = 'test';
    showAnswersMode = 'each';
    questionAnswered = false;

    // Odznačiť všetky checkboxy
    document.querySelectorAll('.test-checkbox').forEach(cb => cb.checked = false);
    updateMultiTestButton();

    // Obnoviť zoznam testov (odstrániť zlúčené testy)
    loadTests();
}

// ============================================
// AI IMPORT FUNKCIE
// ============================================

let aiImportedData = null;
let originalImages = []; // Uložiť pôvodné fotky pre zobrazenie
let imageRotations = []; // Rotácia pre každú fotku (0, 90, 180, 270)
let compressedFiles = []; // Komprimované súbory na upload
let aiProcessingTimer = null; // Interval pre časovač spracovania
let aiProcessingStartTime = null; // Čas začiatku spracovania

function showAIImportPage() {
    document.querySelector('.section').style.display = 'none';
    document.getElementById('aiImportPage').style.display = 'block';

    // Skontrolovať localStorage pre uložený stav
    const savedState = localStorage.getItem('aiImportState');

    if (savedState) {
        try {
            const state = JSON.parse(savedState);

            // Skontrolovať či nie je stav príliš starý (napr. viac ako 1 hodinu)
            const hourInMs = 60 * 60 * 1000;
            if (Date.now() - state.timestamp > hourInMs) {
                // Stav je príliš starý, vymazať
                localStorage.removeItem('aiImportState');
                resetAIImportPage();
                return;
            }

            if (state.step === 'completed' && state.data) {
                // Obnoviť dokončený import
                aiImportedData = state.data;
                originalImages = state.originalImages || [];

                // Zobraziť výsledky
                document.getElementById('aiStep1').style.display = 'none';
                document.getElementById('aiStep2').style.display = 'none';
                document.getElementById('aiStep3').style.display = 'block';
                document.getElementById('aiStep4').style.display = 'block';

                displayAIQuestions();

                // Zobraziť obrázky len ak existujú
                if (aiImportedData.processedImage || originalImages.length > 0) {
                    displayProcessedAndOriginalImages();
                }
                return;
            } else if (state.step === 'processing') {
                // Stále sa spracováva (užívateľ sa vrátil počas spracovania)
                document.getElementById('aiStep1').style.display = 'none';
                document.getElementById('aiStep2').style.display = 'block';
                document.getElementById('aiStep3').style.display = 'none';
                document.getElementById('aiStep4').style.display = 'none';
                return;
            }
        } catch (e) {
            console.error('Chyba pri načítaní uloženého stavu AI importu:', e);
            localStorage.removeItem('aiImportState');
        }
    }

    // Default: reset workflow
    resetAIImportPage();
}

function resetAIImportPage() {
    // Reset AI import workflow
    document.getElementById('aiStep1').style.display = 'block';
    document.getElementById('aiStep2').style.display = 'none';
    document.getElementById('aiStep3').style.display = 'none';
    document.getElementById('aiStep4').style.display = 'none';
    document.getElementById('aiImageInput').value = '';
    document.getElementById('imagePreview').style.display = 'none';
    document.getElementById('processBtn').style.display = 'none';
    document.getElementById('cancelStep1Btn').style.display = 'none';
    aiImportedData = null;
    originalImages = [];
    imageRotations = [];
    compressedFiles = [];
    // Vymazať uložený stav
    localStorage.removeItem('aiImportState');
}

function cancelAIImport() {
    // Potvrdenie pred zrušením
    if (confirm('Naozaj chcete zrušiť import? Všetky rozpoznané otázky sa stratia.')) {
        resetAIImportPage();
    }
}

// Konvertovať obrázok na JPEG bez zmeny veľkosti (len optimalizácia)
async function convertToJPEG(file, quality = 0.92) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = function(e) {
            const img = new Image();
            img.onload = function() {
                // Vytvoriť canvas s pôvodnou veľkosťou
                const canvas = document.createElement('canvas');
                canvas.width = img.width;
                canvas.height = img.height;

                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0);

                // Konvertovať na JPEG s vysokou kvalitou
                canvas.toBlob(
                    (blob) => {
                        if (blob) {
                            const jpegFile = new File([blob], file.name.replace(/\.[^/.]+$/, '.jpg'), {
                                type: 'image/jpeg',
                                lastModified: Date.now()
                            });
                            console.log(`Konvertované: ${file.name} (${img.width}x${img.height}px) - ${(file.size / 1024 / 1024).toFixed(2)}MB → ${(blob.size / 1024 / 1024).toFixed(2)}MB`);
                            resolve(jpegFile);
                        } else {
                            reject(new Error('Konverzia zlyhala'));
                        }
                    },
                    'image/jpeg',
                    quality
                );
            };
            img.onerror = reject;
            img.src = e.target.result;
        };
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

async function previewImages(input) {
    if (input.files && input.files.length > 0) {
        const container = document.getElementById('previewContainer');
        container.innerHTML = '';
        originalImages = [];
        imageRotations = [];
        compressedFiles = []; // Uložiť komprimované súbory

        // Zobraziť loading počas konverzie
        container.innerHTML = '<p>Pripravujem obrázky...</p>';

        for (let i = 0; i < input.files.length; i++) {
            const file = input.files[i];

            // Konvertovať na JPEG
            try {
                const converted = await convertToJPEG(file);
                compressedFiles.push(converted);

                const reader = new FileReader();
                reader.onload = function(e) {
                    if (i === 0) {
                        container.innerHTML = ''; // Vymazať loading pri prvom obrázku
                    }

                    originalImages.push(e.target.result);
                    imageRotations.push(0);

                    const imgDiv = document.createElement('div');
                    imgDiv.style.cssText = 'position: relative; margin: 10px;';

                    const previewImg = document.createElement('img');
                    previewImg.id = `preview-img-${i}`;
                    previewImg.src = e.target.result;
                    previewImg.style.cssText = 'max-width: 200px; max-height: 200px; border-radius: 8px; object-fit: cover; transition: transform 0.3s;';

                    const indexLabel = document.createElement('div');
                    indexLabel.style.cssText = 'position: absolute; top: 5px; right: 5px; background: rgba(0,0,0,0.7); color: white; padding: 3px 8px; border-radius: 4px; font-size: 12px;';
                    indexLabel.textContent = i + 1;

                    const imgContainer = document.createElement('div');
                    imgContainer.style.cssText = 'position: relative; min-height: 200px; display: flex; align-items: center; justify-content: center;';
                    imgContainer.appendChild(previewImg);
                    imgContainer.appendChild(indexLabel);

                    const buttonContainer = document.createElement('div');
                    buttonContainer.style.cssText = 'margin-top: 15px; display: flex; gap: 5px;';

                    const rotateBtn = document.createElement('button');
                    rotateBtn.className = 'btn-small';
                    rotateBtn.style.cssText = 'padding: 5px 10px; font-size: 16px;';
                    rotateBtn.title = 'Otočiť o 90° (stlačte 3x pre 270°)';
                    rotateBtn.textContent = '↷';
                    rotateBtn.onclick = () => rotatePreviewImage(i, 90);

                    buttonContainer.appendChild(rotateBtn);

                    const flexContainer = document.createElement('div');
                    flexContainer.style.cssText = 'display: flex; flex-direction: column; align-items: center;';
                    flexContainer.appendChild(imgContainer);
                    flexContainer.appendChild(buttonContainer);

                    imgDiv.appendChild(flexContainer);
                    container.appendChild(imgDiv);
                };
                reader.readAsDataURL(converted);
            } catch (error) {
                console.error('Chyba pri konverzii:', error);
                compressedFiles.push(file); // Použiť originál ak konverzia zlyhá
            }
        }

        document.getElementById('imagePreview').style.display = 'block';
        document.getElementById('processBtn').style.display = 'inline-block';
        document.getElementById('cancelStep1Btn').style.display = 'inline-block';
    }
}

function rotatePreviewImage(index, degrees) {
    // Aktualizovať rotáciu
    imageRotations[index] = (imageRotations[index] + degrees) % 360;
    if (imageRotations[index] < 0) imageRotations[index] += 360;

    // Aplikovať CSS transform
    const img = document.getElementById(`preview-img-${index}`);
    if (img) {
        img.style.transform = `rotate(${imageRotations[index]}deg)`;
    }
}

// Spojiť všetky obrázky do jedného (vertikálne)
async function mergeImagesToCanvas(files, rotations, progressCallback) {
    return new Promise((resolve, reject) => {
        const images = [];
        let loadedCount = 0;

        // Načítať všetky obrázky
        files.forEach((file, index) => {
            const reader = new FileReader();
            reader.onload = function(e) {
                const img = new Image();
                img.onload = function() {
                    images[index] = { img, rotation: rotations[index] || 0 };
                    loadedCount++;

                    // Volať progress callback ak existuje
                    if (progressCallback) {
                        progressCallback(loadedCount, files.length);
                    }

                    // Keď sú všetky načítané, spojíme ich
                    if (loadedCount === files.length) {
                        // Vypočítať rozmery spojeného canvasu
                        let totalHeight = 0;
                        let maxWidth = 0;
                        const gap = 50; // Medzera medzi fotkami

                        // Pripraviť info o každom obrázku s rotáciou
                        const imageInfos = images.map(({ img, rotation }) => {
                            let width, height;
                            // Pri 90° alebo 270° rotácii sa vymenia rozmery
                            if (rotation === 90 || rotation === 270) {
                                width = img.height;
                                height = img.width;
                            } else {
                                width = img.width;
                                height = img.height;
                            }
                            return { img, rotation, width, height };
                        });

                        // Vypočítať celkovú výšku a max šírku
                        imageInfos.forEach((info) => {
                            totalHeight += info.height + gap;
                            maxWidth = Math.max(maxWidth, info.width);
                        });

                        // Vytvoriť canvas
                        const canvas = document.createElement('canvas');
                        canvas.width = maxWidth;
                        canvas.height = totalHeight;
                        const ctx = canvas.getContext('2d');

                        // Biela pozadie
                        ctx.fillStyle = '#FFFFFF';
                        ctx.fillRect(0, 0, canvas.width, canvas.height);

                        // Nakresliť všetky obrázky pod seba
                        let currentY = 0;
                        imageInfos.forEach((info) => {
                            ctx.save();

                            // Centrovať obrázok horizontálne
                            const xOffset = (maxWidth - info.width) / 2;

                            // Aplikovať rotáciu
                            if (info.rotation !== 0) {
                                // Posunúť na stred oblasti kde bude obrázok
                                const centerX = xOffset + info.width / 2;
                                const centerY = currentY + info.height / 2;

                                ctx.translate(centerX, centerY);
                                ctx.rotate((info.rotation * Math.PI) / 180);

                                // Pri rotácii kreslíme z pôvodných rozmerov obrázka
                                ctx.drawImage(info.img, -info.img.width / 2, -info.img.height / 2);
                            } else {
                                // Bez rotácie jednoducho nakreslíme
                                ctx.drawImage(info.img, xOffset, currentY);
                            }

                            ctx.restore();
                            currentY += info.height + gap;
                        });

                        // OpenAI API má limit na detail:"high" = 2048px na dlhší rozmer
                        // Zmenšíme ak je potrebné, aby sme sa vyhli API errors
                        let finalCanvas = canvas;
                        let finalWidth = maxWidth;
                        let finalHeight = totalHeight;
                        const MAX_DIMENSION = 2048;

                        if (maxWidth > MAX_DIMENSION || totalHeight > MAX_DIMENSION) {
                            // Zmenšiť podľa dlhšej strany
                            let scale;
                            if (maxWidth > totalHeight) {
                                scale = MAX_DIMENSION / maxWidth;
                            } else {
                                scale = MAX_DIMENSION / totalHeight;
                            }

                            finalWidth = Math.round(maxWidth * scale);
                            finalHeight = Math.round(totalHeight * scale);

                            const resizedCanvas = document.createElement('canvas');
                            resizedCanvas.width = finalWidth;
                            resizedCanvas.height = finalHeight;
                            const resizedCtx = resizedCanvas.getContext('2d');
                            resizedCtx.drawImage(canvas, 0, 0, finalWidth, finalHeight);
                            finalCanvas = resizedCanvas;

                            console.log(`Prispôsobené pre OpenAI API: ${maxWidth}x${totalHeight}px → ${finalWidth}x${finalHeight}px`);
                        }

                        // Konvertovať na blob
                        finalCanvas.toBlob(
                            (blob) => {
                                if (blob) {
                                    const mergedFile = new File([blob], 'merged_images.jpg', {
                                        type: 'image/jpeg',
                                        lastModified: Date.now()
                                    });
                                    console.log(`Spojené ${files.length} fotky do jednej (${(blob.size / 1024 / 1024).toFixed(2)}MB, ${finalWidth}x${finalHeight}px)`);
                                    resolve(mergedFile);
                                } else {
                                    reject(new Error('Zlyhalo spojenie fotiek'));
                                }
                            },
                            'image/jpeg',
                            0.95
                        );
                    }
                };
                img.onerror = reject;
                img.src = e.target.result;
            };
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    });
}

async function processImagesWithAI() {
    if (!compressedFiles || compressedFiles.length === 0) {
        alert('Najprv nahrajte obrázok');
        return;
    }

    // Skryť Step 1, zobraziť Step 2 (loading)
    document.getElementById('aiStep1').style.display = 'none';
    document.getElementById('aiStep2').style.display = 'block';

    // Uložiť stav do localStorage - processing
    localStorage.setItem('aiImportState', JSON.stringify({
        step: 'processing',
        timestamp: Date.now()
    }));

    try {
        // Získať nastavenie pokročilého predspracovania
        const advancedPreprocessing = document.getElementById('advancedPreprocessing').checked;

        // Inicializovať aiImportedData
        aiImportedData = {
            suggestedTitle: '',
            suggestedDescription: '',
            questions: [],
            processedImages: [],
            totalPages: compressedFiles.length
        };

        // Spracovať každú fotku samostatne
        for (let i = 0; i < compressedFiles.length; i++) {
            const fileToProcess = compressedFiles[i];
            const pageNumber = i + 1;

            // Update loading message
            document.querySelector('.ai-processing p').textContent = `AI analyzuje stranu ${pageNumber}/${compressedFiles.length}...`;

            const formData = new FormData();
            formData.append('image', fileToProcess);
            formData.append('advancedPreprocessing', advancedPreprocessing);
            formData.append('rotation', imageRotations[i] || 0);

            const response = await fetch('/api/ai-import', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                // Prvá strana nastaví title a description
                if (i === 0) {
                    aiImportedData.suggestedTitle = result.data.suggestedTitle || 'Importovaný test';
                    aiImportedData.suggestedDescription = result.data.suggestedDescription || '';
                }

                // Uložiť spracovaný obrázok
                aiImportedData.processedImages.push({
                    image: result.data.processedImage,
                    pageNumber: pageNumber
                });

                // Pridať otázky s označením strany
                if (result.data.questions && result.data.questions.length > 0) {
                    result.data.questions.forEach(q => {
                        q.pageNumber = pageNumber;
                        aiImportedData.questions.push(q);
                    });
                }
            } else {
                throw new Error(`Chyba pri spracovaní strany ${pageNumber}: ${result.error || 'Neznáma chyba'}`);
            }
        }

        if (aiImportedData.questions.length === 0) {
            throw new Error('Žiadne otázky neboli rozpoznané');
        }

        displayAIQuestions();
        displayProcessedAndOriginalImages(); // Zobraziť predspracované a pôvodné fotky

        // Skryť loading, zobraziť Step 3 a 4
        document.getElementById('aiStep2').style.display = 'none';
        document.getElementById('aiStep3').style.display = 'block';
        document.getElementById('aiStep4').style.display = 'block';

        // Uložiť stav do localStorage - completed (bez obrázkov kvôli kvóte)
        try {
            // Vytvoriť kópiu dát bez base64 obrázkov
            const dataToSave = {
                suggestedTitle: aiImportedData.suggestedTitle,
                suggestedDescription: aiImportedData.suggestedDescription,
                totalPages: aiImportedData.totalPages,
                questions: aiImportedData.questions.map(q => ({
                    question: q.question,
                    answers: q.answers,
                    correct: q.correct,
                    positionPercent: q.positionPercent,
                    pageNumber: q.pageNumber
                    // Vynechať cropImage - príliš veľké
                }))
                // Vynechať processedImages - príliš veľké
            };

            localStorage.setItem('aiImportState', JSON.stringify({
                step: 'completed',
                timestamp: Date.now(),
                data: dataToSave
            }));
        } catch (e) {
            // Ak localStorage presiahne kvótu, len to ignoruj
            console.warn('Nepodarilo sa uložiť stav do localStorage:', e);
        }

    } catch (error) {
        alert('Chyba pri spracovaní obrázkov: ' + error.message);
        // Vrátiť sa na Step 1
        document.getElementById('aiStep2').style.display = 'none';
        document.getElementById('aiStep1').style.display = 'block';
        // Vymazať stav z localStorage
        localStorage.removeItem('aiImportState');
    }
}

let currentPageIndex = 0;

function displayProcessedAndOriginalImages() {
    const container = document.getElementById('originalImagesPreview');
    container.innerHTML = '';

    if (!aiImportedData.processedImages || aiImportedData.processedImages.length === 0) {
        return;
    }

    // Vytvor wrapper pre obrázky a navigáciu
    const wrapper = document.createElement('div');
    wrapper.style.cssText = 'position: relative; width: 100%; height: 100%;';

    // Indikátor stránky
    const pageIndicator = document.createElement('div');
    pageIndicator.id = 'pageIndicator';
    pageIndicator.style.cssText = `
        position: absolute;
        top: 10px;
        right: 10px;
        background: rgba(0, 0, 0, 0.7);
        color: white;
        padding: 8px 12px;
        border-radius: 20px;
        font-weight: bold;
        z-index: 10;
        font-size: 14px;
    `;
    pageIndicator.textContent = `Strana ${currentPageIndex + 1}/${aiImportedData.processedImages.length}`;

    // Kontajner pre obrázky
    const imagesContainer = document.createElement('div');
    imagesContainer.id = 'imagesScrollContainer';
    imagesContainer.style.cssText = 'width: 100%; height: 100%; overflow-y: auto; scroll-behavior: smooth;';

    // Pridať všetky obrázky
    aiImportedData.processedImages.forEach((pageData, index) => {
        const imageDiv = document.createElement('div');
        imageDiv.className = 'page-image';
        imageDiv.dataset.pageIndex = index;
        imageDiv.style.cssText = 'margin-bottom: 0; scroll-snap-align: start;';

        const img = document.createElement('img');
        img.src = pageData.image;
        img.style.cssText = 'width: 100%; border-radius: 8px; border: 2px solid #2196F3; cursor: pointer; display: block;';
        img.title = 'Kliknite pre zväčšenie';
        img.onclick = function() {
            const newWin = window.open('', '_blank');
            if (newWin) {
                newWin.document.body.innerHTML = '<img src="' + pageData.image + '" style="max-width:100%;height:auto">';
            }
        };

        imageDiv.appendChild(img);
        imagesContainer.appendChild(imageDiv);
    });

    // Scroll event - automatické prepínanie strán
    imagesContainer.addEventListener('scroll', function() {
        const scrollTop = this.scrollTop;
        const scrollHeight = this.scrollHeight;
        const clientHeight = this.clientHeight;
        const images = this.querySelectorAll('.page-image');

        // Nájsť aktuálnu viditeľnú stranu
        images.forEach((img, index) => {
            const rect = img.getBoundingClientRect();
            const containerRect = imagesContainer.getBoundingClientRect();

            if (rect.top >= containerRect.top && rect.top < containerRect.top + containerRect.height / 2) {
                if (currentPageIndex !== index) {
                    currentPageIndex = index;
                    pageIndicator.textContent = `Strana ${index + 1}/${aiImportedData.processedImages.length}`;
                }
            }
        });

        // Automatický scroll na ďalšiu stranu keď si blízko konca
        if (scrollTop + clientHeight >= scrollHeight - 50) {
            if (currentPageIndex < aiImportedData.processedImages.length - 1) {
                currentPageIndex++;
                const nextImage = images[currentPageIndex];
                if (nextImage) {
                    nextImage.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    pageIndicator.textContent = `Strana ${currentPageIndex + 1}/${aiImportedData.processedImages.length}`;
                }
            }
        }
    });

    wrapper.appendChild(pageIndicator);
    wrapper.appendChild(imagesContainer);
    container.appendChild(wrapper);

    // Reset scroll na začiatok
    currentPageIndex = 0;
    imagesContainer.scrollTop = 0;
}

function displayAIQuestions() {
    if (!aiImportedData) return;

    // Používateľ sám zadá názov testu a popis v kroku 4 (pri ukladaní)

    // Zobraziť otázky
    const container = document.getElementById('aiQuestionsPreview');
    container.innerHTML = '';

    // Zoskupiť otázky podľa strán
    const questionsByPage = {};
    aiImportedData.questions.forEach((q, qIndex) => {
        // Zabezpečiť že correct je array
        if (!Array.isArray(q.correct)) {
            q.correct = [q.correct];
        }

        const pageNum = q.pageNumber || 1;
        if (!questionsByPage[pageNum]) {
            questionsByPage[pageNum] = [];
        }
        questionsByPage[pageNum].push({ question: q, originalIndex: qIndex });
    });

    // Zobraziť otázky zoskupené podľa strán
    Object.keys(questionsByPage).sort((a, b) => parseInt(a) - parseInt(b)).forEach(pageNum => {
        // Pridať hlavičku strany
        if (aiImportedData.totalPages > 1) {
            const pageHeader = document.createElement('div');
            pageHeader.style.cssText = `
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 12px 20px;
                margin: 20px 0 10px 0;
                border-radius: 8px;
                font-weight: bold;
                font-size: 16px;
                text-align: center;
            `;
            pageHeader.textContent = `📄 Strana ${pageNum}`;
            container.appendChild(pageHeader);
        }

        // Zobraziť otázky z tejto strany
        questionsByPage[pageNum].forEach(({ question: q, originalIndex: qIndex }) => {
            const questionDiv = document.createElement('div');
            questionDiv.className = 'ai-question-item';
            questionDiv.innerHTML = `
                <div class="ai-question-header">
                    <h4>Otázka ${qIndex + 1}</h4>
                    <button onclick="deleteQuestion(${qIndex})" class="btn-delete-small">🗑️</button>
                </div>
                <label>Otázka:</label>
                <input type="text" class="ai-input" data-q="${qIndex}" data-field="question"
                       value="${escapeHtml(q.question)}" onchange="updateAIQuestion(${qIndex}, 'question', this.value)">

                <label>Odpovede (zaškrtnite všetky správne):</label>
                ${q.answers.map((ans, aIndex) => `
                    <div class="ai-answer-row">
                        <input type="checkbox" id="correct_${qIndex}_${aIndex}"
                               ${q.correct.includes(aIndex) ? 'checked' : ''}
                               onchange="toggleAICorrect(${qIndex}, ${aIndex})">
                        <input type="text" class="ai-input ai-answer-input"
                               value="${escapeHtml(ans)}"
                               onchange="updateAIAnswer(${qIndex}, ${aIndex}, this.value)">
                    </div>
                `).join('')}
            `;
            container.appendChild(questionDiv);
        });
    });

    // Načítať existujúce testy pre append mode
    loadExistingTestsForAppend();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function toggleAICorrect(qIndex, aIndex) {
    if (aiImportedData && aiImportedData.questions[qIndex]) {
        if (!Array.isArray(aiImportedData.questions[qIndex].correct)) {
            aiImportedData.questions[qIndex].correct = [aiImportedData.questions[qIndex].correct];
        }

        const correctArray = aiImportedData.questions[qIndex].correct;
        const idx = correctArray.indexOf(aIndex);

        if (idx > -1) {
            correctArray.splice(idx, 1);
        } else {
            correctArray.push(aIndex);
        }
    }
}

function updateAIQuestion(qIndex, field, value) {
    if (aiImportedData && aiImportedData.questions[qIndex]) {
        aiImportedData.questions[qIndex][field] = value;
    }
}

function updateAIAnswer(qIndex, aIndex, value) {
    if (aiImportedData && aiImportedData.questions[qIndex]) {
        aiImportedData.questions[qIndex].answers[aIndex] = value;
    }
}

function deleteQuestion(qIndex) {
    if (confirm('Naozaj chcete vymazať túto otázku?')) {
        aiImportedData.questions.splice(qIndex, 1);
        displayAIQuestions();
    }
}

function addNewQuestion() {
    if (!aiImportedData) return;

    aiImportedData.questions.push({
        question: 'Nová otázka',
        answers: ['Odpoveď 1', 'Odpoveď 2', 'Odpoveď 3', 'Odpoveď 4'],
        correct: [0]  // Array pre podporu viacerých správnych
    });

    displayAIQuestions();
}

function updateSaveMode() {
    const mode = document.querySelector('input[name="saveMode"]:checked').value;

    if (mode === 'new') {
        document.getElementById('newTestOptions').style.display = 'block';
        document.getElementById('appendTestOptions').style.display = 'none';
    } else {
        document.getElementById('newTestOptions').style.display = 'none';
        document.getElementById('appendTestOptions').style.display = 'block';
    }
}

async function loadExistingTestsForAppend() {
    try {
        const response = await fetch('/api/list-files', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder: 'testy' })
        });

        const result = await response.json();

        const select = document.getElementById('existingTestSelect');
        select.innerHTML = '';

        // Pridať default option
        const defaultOption = document.createElement('option');
        defaultOption.value = '';
        defaultOption.textContent = '-- Vyberte existujúci test --';
        defaultOption.selected = true;
        select.appendChild(defaultOption);

        if (result.files && result.files.length > 0) {
            result.files.forEach(file => {
                const option = document.createElement('option');
                option.value = file.replace('.json', '');
                option.textContent = file;
                select.appendChild(option);
            });
        } else {
            const option = document.createElement('option');
            option.value = '';
            option.textContent = 'Žiadne existujúce testy';
            option.disabled = true;
            select.appendChild(option);
        }
    } catch (error) {
        console.error('Chyba pri načítaní existujúcich testov:', error);
        // Pridať error option
        const select = document.getElementById('existingTestSelect');
        select.innerHTML = '';
        const errorOption = document.createElement('option');
        errorOption.value = '';
        errorOption.textContent = 'Chyba pri načítaní testov';
        errorOption.disabled = true;
        select.appendChild(errorOption);
    }
}

async function saveAITest() {
    if (!aiImportedData) {
        alert('Žiadne údaje na uloženie');
        return;
    }

    const mode = document.querySelector('input[name="saveMode"]:checked').value;
    let testName;
    let title;
    let description;

    if (mode === 'new') {
        testName = document.getElementById('newTestFileName').value.trim();
        if (!testName) {
            alert('Zadajte názov súboru');
            return;
        }

        title = document.getElementById('aiTestTitle').value.trim();
        description = document.getElementById('aiTestDesc').value.trim();

        if (!title) {
            alert('Zadajte názov testu');
            return;
        }
    } else {
        // Append mode
        testName = document.getElementById('existingTestSelect').value;
        if (!testName) {
            alert('Vyberte existujúci test');
            return;
        }

        // V append móde načítame existujúci test a použijeme jeho title/description
        try {
            const loadResponse = await fetch(`/api/load-test/${testName}.json`);
            const loadResult = await loadResponse.json();

            if (loadResult.success && loadResult.data) {
                // Získať title a description z existujúceho testu
                const existingTest = Array.isArray(loadResult.data) ? loadResult.data[0] : loadResult.data;
                title = existingTest.title || testName;
                description = existingTest.description || '';
            } else {
                alert('Nepodarilo sa načítať existujúci test');
                return;
            }
        } catch (error) {
            alert('Chyba pri načítaní existujúceho testu: ' + error.message);
            return;
        }
    }

    if (aiImportedData.questions.length === 0) {
        alert('Test musí obsahovať aspoň jednu otázku');
        return;
    }

    const testData = {
        title: title,
        description: description,
        questions: aiImportedData.questions
    };

    try {
        const response = await fetch('/api/save-test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                testName: testName,
                testData: testData,
                mode: mode
            })
        });

        const result = await response.json();

        if (result.success) {
            alert(`Test úspešne uložený do ${result.filename}!`);
            // Vymazať uložený stav AI importu
            localStorage.removeItem('aiImportState');
            backToList();
        } else {
            throw new Error(result.error || 'Neznáma chyba');
        }
    } catch (error) {
        alert('Chyba pri ukladaní testu: ' + error.message);
    }
}

// ============================================
// TEST EDIT FUNKCIE
// ============================================

let editingTestData = null;
let editingFilename = null;

async function editTest(filename, index) {
    try {
        const response = await fetch(`/api/load-test/${encodeURIComponent(filename)}`);
        const result = await response.json();

        if (result.success) {
            editingTestData = result.data;
            editingFilename = filename;
            showEditTestPage();
        } else {
            throw new Error(result.error || 'Chyba pri načítaní testu');
        }
    } catch (error) {
        alert('Chyba pri načítaní testu: ' + error.message);
    }
}

function showEditTestPage() {
    document.querySelector('.section').style.display = 'none';
    document.getElementById('editTestPage').style.display = 'block';

    // Ak je test array, zobrazíme len prvý test (alebo všetky?)
    const testData = Array.isArray(editingTestData) ? editingTestData[0] : editingTestData;

    document.getElementById('editTestTitle').value = testData.title || '';
    document.getElementById('editTestDesc').value = testData.description || '';

    displayEditQuestions();
}

function displayEditQuestions() {
    const testData = Array.isArray(editingTestData) ? editingTestData[0] : editingTestData;
    const container = document.getElementById('editQuestionsContainer');
    container.innerHTML = '';

    testData.questions.forEach((q, qIndex) => {
        // Zabezpečiť že correct je array
        if (!Array.isArray(q.correct)) {
            q.correct = [q.correct];
        }

        const questionDiv = document.createElement('div');
        questionDiv.className = 'ai-question-item';
        questionDiv.innerHTML = `
            <div class="ai-question-header">
                <h4>Otázka ${qIndex + 1}</h4>
                <button onclick="deleteEditQuestion(${qIndex})" class="btn-delete-small">🗑️</button>
            </div>
            <label>Otázka:</label>
            <input type="text" class="ai-input" value="${escapeHtml(q.question)}"
                   onchange="updateEditQuestion(${qIndex}, 'question', this.value)">

            <label>Odpovede (zaškrtnite všetky správne):</label>
            ${q.answers.map((ans, aIndex) => `
                <div class="ai-answer-row">
                    <input type="checkbox" id="edit_correct_${qIndex}_${aIndex}"
                           ${q.correct.includes(aIndex) ? 'checked' : ''}
                           onchange="toggleEditCorrect(${qIndex}, ${aIndex})">
                    <input type="text" class="ai-input ai-answer-input"
                           value="${escapeHtml(ans)}"
                           onchange="updateEditAnswer(${qIndex}, ${aIndex}, this.value)">
                </div>
            `).join('')}
        `;
        container.appendChild(questionDiv);
    });
}

// Debounce timeout pre autosave
let autosaveTimeout = null;

// Automatické uloženie zmien
async function autoSaveEditedTest() {
    if (!editingFilename || !editingTestData) return;

    try {
        const testData = Array.isArray(editingTestData) ? editingTestData[0] : editingTestData;

        // Aktualizovať názov a popis z input polí
        testData.title = document.getElementById('editTestTitle').value.trim();
        testData.description = document.getElementById('editTestDesc').value.trim();

        const response = await fetch(`/api/update-test/${encodeURIComponent(editingFilename)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                data: Array.isArray(editingTestData) ? editingTestData : [editingTestData]
            })
        });

        const result = await response.json();

        if (result.success) {
            // Ak bol súbor premenovaný, aktualizovať názov
            if (result.renamed && result.filename) {
                editingFilename = result.filename;
            }
            console.log('✓ Zmeny automaticky uložené');
        }
    } catch (error) {
        console.error('Chyba pri automatickom ukladaní:', error);
    }
}

// Debounce funkcia pre autosave (čaká 1 sekundu po poslednej zmene)
function triggerAutosave() {
    if (autosaveTimeout) {
        clearTimeout(autosaveTimeout);
    }
    autosaveTimeout = setTimeout(autoSaveEditedTest, 1000);
}

function toggleEditCorrect(qIndex, aIndex) {
    const testData = Array.isArray(editingTestData) ? editingTestData[0] : editingTestData;
    if (testData.questions[qIndex]) {
        if (!Array.isArray(testData.questions[qIndex].correct)) {
            testData.questions[qIndex].correct = [testData.questions[qIndex].correct];
        }

        const correctArray = testData.questions[qIndex].correct;
        const idx = correctArray.indexOf(aIndex);

        if (idx > -1) {
            correctArray.splice(idx, 1);
        } else {
            correctArray.push(aIndex);
        }

        triggerAutosave();
    }
}

function updateEditQuestion(qIndex, field, value) {
    const testData = Array.isArray(editingTestData) ? editingTestData[0] : editingTestData;
    if (testData.questions[qIndex]) {
        testData.questions[qIndex][field] = value;
        triggerAutosave();
    }
}

function updateEditAnswer(qIndex, aIndex, value) {
    const testData = Array.isArray(editingTestData) ? editingTestData[0] : editingTestData;
    if (testData.questions[qIndex]) {
        testData.questions[qIndex].answers[aIndex] = value;
        triggerAutosave();
    }
}

function deleteEditQuestion(qIndex) {
    if (confirm('Naozaj chcete vymazať túto otázku?')) {
        const testData = Array.isArray(editingTestData) ? editingTestData[0] : editingTestData;
        testData.questions.splice(qIndex, 1);
        displayEditQuestions();
    }
}

function addEditQuestion() {
    const testData = Array.isArray(editingTestData) ? editingTestData[0] : editingTestData;
    testData.questions.push({
        question: 'Nová otázka',
        answers: ['Odpoveď 1', 'Odpoveď 2', 'Odpoveď 3', 'Odpoveď 4'],
        correct: [0]  // Array pre podporu viacerých správnych
    });
    displayEditQuestions();
}

async function saveEditedTest() {
    const testData = Array.isArray(editingTestData) ? editingTestData[0] : editingTestData;

    testData.title = document.getElementById('editTestTitle').value.trim();
    testData.description = document.getElementById('editTestDesc').value.trim();

    if (!testData.title) {
        alert('Zadajte názov testu');
        return;
    }

    if (testData.questions.length === 0) {
        alert('Test musí obsahovať aspoň jednu otázku');
        return;
    }

    try {
        const response = await fetch(`/api/update-test/${encodeURIComponent(editingFilename)}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                data: Array.isArray(editingTestData) ? editingTestData : [editingTestData]
            })
        });

        const result = await response.json();

        if (result.success) {
            alert('Test úspešne aktualizovaný!');
            backToList();
            loadTests(); // Reload tests
        } else {
            throw new Error(result.error || 'Neznáma chyba');
        }
    } catch (error) {
        alert('Chyba pri ukladaní testu: ' + error.message);
    }
}

async function deleteTest(filename, index) {
    if (!confirm(`Naozaj chcete zmazať test "${filename}"? Táto akcia je nezvratná.`)) {
        return;
    }

    try {
        const response = await fetch(`/api/delete-test/${encodeURIComponent(filename)}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.success) {
            alert(result.message);
            loadTests(); // Reload tests
        } else {
            throw new Error(result.error || 'Neznáma chyba');
        }
    } catch (error) {
        alert('Chyba pri mazaní testu: ' + error.message);
    }
}
