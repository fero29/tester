let tests = [];
let currentTest = null;
let currentQuestionIndex = 0;
let userAnswers = [];
let selectedTestIndex = null;
let testMode = 'test'; // 'test' alebo 'learn'
let timerInterval = null;
let timeLeft = 0;
let testStartTime = null;
let showAnswersMode = 'none'; // 'none', 'each', 'end'
let questionAnswered = false; // Pre režim 'each' - či už bola ukázaná odpoveď

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

function showHelpPage() {
    document.querySelector('.section').style.display = 'none';
    document.getElementById('helpPage').style.display = 'block';
}

function showImportPage() {
    document.querySelector('.section').style.display = 'none';
    document.getElementById('importPage').style.display = 'block';
    loadFilesList();
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
}

function startTestWithSettings() {
    const timeLimit = parseInt(document.querySelector('input[name="time"]:checked').value);
    const shuffle = document.querySelector('input[name="shuffle"]:checked').value === 'true';
    const questionFrom = parseInt(document.getElementById('questionFrom').value) - 1;
    const questionTo = parseInt(document.getElementById('questionTo').value);
    showAnswersMode = document.querySelector('input[name="showAnswers"]:checked').value;

    testMode = 'test';
    questionAnswered = false;
    currentTest = JSON.parse(JSON.stringify(tests[selectedTestIndex])); // Deep copy

    // Filtrovať rozsah otázok
    currentTest.questions = currentTest.questions.slice(questionFrom, questionTo);

    if (currentTest.questions.length === 0) {
        alert('Neplatný rozsah otázok!');
        return;
    }

    // Mixáž otázok
    if (shuffle) {
        currentTest.questions = shuffleArray(currentTest.questions);
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
        const isMultiple = Array.isArray(question.correct);

        return `
            <div class="learn-question">
                <h3>Otázka ${qIndex + 1}: ${question.question}</h3>
                ${isMultiple ? '<p class="multiple-note">Viacero správnych odpovedí</p>' : ''}
                <div class="learn-answers">
                    ${question.answers.map((answer, aIndex) => {
                        const isCorrect = isMultiple
                            ? question.correct.includes(aIndex)
                            : question.correct === aIndex;

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
    const isMultiple = Array.isArray(question.correct);
    const userAnswer = userAnswers[currentQuestionIndex];

    // Ak je už zodpovedané a režim "each", zobraz feedback
    const showFeedback = questionAnswered && showAnswersMode === 'each';

    let questionHTML = `
        <div class="question">
            <h3>Otázka ${currentQuestionIndex + 1}: ${question.question}</h3>
            ${question.answers.map((answer, index) => {
                const isSelected = userAnswer.includes(index);
                const isCorrect = isMultiple
                    ? question.correct.includes(index)
                    : question.correct === index;

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
                    return `
                        <div class="answer ${isSelected ? 'selected' : ''}" onclick="selectAnswer(${index})">
                            ${answer}
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
    // Vždy používať toggle (pridať/odobrať z poľa)
    const currentAnswers = userAnswers[currentQuestionIndex];
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
    // Ak je režim "each" a ešte nebola ukázaná odpoveď, ukáž feedback
    if (showAnswersMode === 'each' && !questionAnswered) {
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
    // Ak je režim "each" a posledná otázka nebola ešte ukázaná, ukáž ju najprv
    if (showAnswersMode === 'each' && !questionAnswered) {
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
        const isMultiple = Array.isArray(question.correct);
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
            // Jedna správna odpoveď - userAnswer je pole, correct je číslo
            correct = userAnswer.length === 1 && userAnswer[0] === question.correct;

            userAnswerText = userAnswer && userAnswer.length > 0
                ? userAnswer.map(i => question.answers[i]).join(', ')
                : 'Nezodpovedané';
            correctAnswerText = question.answers[question.correct];
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
    saveTestResult({
        testName: currentTest.title,
        date: new Date().toISOString(),
        score: correctCount,
        total: currentTest.questions.length,
        percentage: percentage
    });

    document.getElementById('testInterface').style.display = 'none';
    document.getElementById('results').style.display = 'block';

    // Zobraz výsledky podobne ako learn mode - všetky otázky s odpoveďami
    document.getElementById('resultsContainer').innerHTML = `
        <div class="results-summary">
            <h3>Výsledok: ${correctCount} / ${currentTest.questions.length}</h3>
            <p style="font-size: 1.2em; margin-top: 10px;">${percentage}%</p>
        </div>
        ${currentTest.questions.map((question, qIndex) => {
            const userAnswer = userAnswers[qIndex];
            const isMultiple = Array.isArray(question.correct);

            // Vypočítaj správnosť tejto otázky
            let questionCorrect = false;
            if (isMultiple) {
                const sortedUser = userAnswer ? [...userAnswer].sort() : [];
                const sortedCorrect = [...question.correct].sort();
                questionCorrect = JSON.stringify(sortedUser) === JSON.stringify(sortedCorrect);
            } else {
                questionCorrect = userAnswer.length === 1 && userAnswer[0] === question.correct;
            }

            return `
                <div class="result-question ${questionCorrect ? 'result-correct' : 'result-incorrect'}">
                    <h4>Otázka ${qIndex + 1}: ${question.question}</h4>
                    ${isMultiple ? '<p class="multiple-note">Viacero správnych odpovedí</p>' : ''}
                    <div class="result-answers">
                        ${question.answers.map((answer, aIndex) => {
                            const isCorrect = isMultiple
                                ? question.correct.includes(aIndex)
                                : question.correct === aIndex;
                            const isUserAnswer = userAnswer && userAnswer.includes(aIndex);

                            let cssClass = '';
                            let label = '';

                            if (showAnswersMode === 'end' || showAnswersMode === 'each') {
                                // Zobraz detailný feedback
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
                            } else {
                                // Režim "none" - zobraz len nesprávne
                                if (!questionCorrect && isCorrect) {
                                    cssClass = 'result-answer-correct-missed';
                                    label = ' ✓ SPRÁVNE';
                                } else if (isUserAnswer) {
                                    cssClass = 'result-answer-user-selected';
                                    label = ' - Vaša odpoveď';
                                } else {
                                    cssClass = 'result-answer-neutral';
                                }
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
    document.querySelector('.section').style.display = 'block';
    currentTest = null;
    testMode = 'test';
    showAnswersMode = 'none';
    questionAnswered = false;

    // Odznačiť všetky checkboxy
    document.querySelectorAll('.test-checkbox').forEach(cb => cb.checked = false);
    updateMultiTestButton();

    // Obnoviť zoznam testov (odstrániť zlúčené testy)
    loadTests();
}
