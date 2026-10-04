// Jeden priebeh otázkového testu; predvoľby iba nastavujú tieto voľby.
const PRACTICE_DEFAULTS = {
    selection: 'all', from: 1, to: 1, count: 20, toEnd: true,
    shuffleQuestions: false, shuffleOptions: false, minutes: 0,
    feedback: 'each', explanations: 'click', hints: false,
    repeat: false, statistics: true, learning: true
};
const PRACTICE_PRESETS = {
    learning: {...PRACTICE_DEFAULTS, hints: true, explanations: 'auto', repeat: true, statistics: false},
    training: {...PRACTICE_DEFAULTS},
    exam: {...PRACTICE_DEFAULTS, minutes: 20, feedback: 'end', shuffleQuestions: true, shuffleOptions: true}
};
let practice = null;
const practiceCheckboxes = {
    shuffleQuestions: 'shuffleQuestions', shuffleOptions: 'shuffleOptions', hints: 'allowHints',
    repeat: 'repeatMistakes', statistics: 'countStatistics', learning: 'trackLearning'
};

function readPracticeStorage(key) {
    try {
        const value = JSON.parse(localStorage.getItem(key) || '{}');
        return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
    } catch { return {}; }
}

function writePracticeStorage(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); return true; }
    catch { return false; }
}

function normalizedPracticeOptions(value = {}) {
    const options = {...PRACTICE_DEFAULTS};
    for (const key of [...Object.keys(practiceCheckboxes), 'toEnd']) {
        if (typeof value[key] === 'boolean') options[key] = value[key];
    }
    for (const [key, allowed] of Object.entries({
        selection: ['all', 'range', 'random', 'due'], feedback: ['each', 'end'],
        explanations: ['auto', 'click', 'off'], minutes: [0, 20, 30, 60]
    })) if (allowed.includes(value[key])) options[key] = value[key];
    for (const key of ['from', 'to', 'count']) {
        if (Number.isInteger(value[key]) && value[key] > 0) options[key] = value[key];
    }
    return options;
}

// Kľúč vzniká pred miešaním. Obsahová revízia zabráni prenosu znalosti po oprave otázky.
// Existujúce JSON súbory bez ID sa kvôli sledovaniu pokroku neprepisujú.
function practiceQuestionKey(question) {
    return JSON.stringify([question.id || '', question.question, question.answers, question.correct]);
}

function reviewedLearning(question) {
    return question.learning?.status === 'reviewed' ? question.learning : null;
}

function practiceHints(question) {
    const hints = reviewedLearning(question)?.hints;
    return Array.isArray(hints) ? hints.filter(h => typeof h === 'string' && h.trim()) : [];
}

function practiceExplanation(question) {
    const explanation = reviewedLearning(question)?.explanation;
    if (explanation && typeof explanation === 'object') return explanation;
    if (isTFQuestion(question)) {
        const correct = Array.isArray(question.correct) ? question.correct : [question.correct];
        const summary = tfExplanation(question.answers[correct[0]]);
        if (summary) return {summary};
    }
    return null;
}

function readPracticeSettings() {
    const total = tests[selectedTestIndex]?.questions?.length || 1;
    const options = {
        selection: document.querySelector('input[name="questionMode"]:checked').value,
        from: Number(document.getElementById('questionFrom').value),
        to: Number(document.getElementById('questionTo').value),
        count: Number(document.getElementById('randomCount').value),
        minutes: Number(document.getElementById('practiceTime').value),
        feedback: document.getElementById('practiceFeedback').value,
        explanations: document.getElementById('practiceExplanation').value
    };
    options.toEnd = options.to === total;
    for (const [key, id] of Object.entries(practiceCheckboxes)) options[key] = document.getElementById(id).checked;
    return options;
}

function fillPracticeSettings(options) {
    const total = tests[selectedTestIndex].questions.length;
    document.querySelector(`input[name="questionMode"][value="${options.selection}"]`).checked = true;
    document.getElementById('questionFrom').value = Math.min(options.from, total);
    document.getElementById('questionTo').value = options.toEnd ? total : Math.min(options.to, total);
    document.getElementById('randomCount').value = Math.min(options.count, total);
    document.getElementById('practiceTime').value = options.minutes;
    document.getElementById('practiceFeedback').value = options.feedback;
    document.getElementById('practiceExplanation').value = options.explanations;
    for (const [key, id] of Object.entries(practiceCheckboxes)) document.getElementById(id).checked = options[key];
    practiceSettingsChanged(false);
}

function initializePracticeSettings() {
    fillPracticeSettings(normalizedPracticeOptions(readPracticeStorage('practiceSettings')));
    document.getElementById('practiceSettingsError').textContent = '';
}

function applyPracticePreset(name) {
    if (PRACTICE_PRESETS[name]) {
        fillPracticeSettings(PRACTICE_PRESETS[name]);
        practiceSettingsChanged();
    }
}

function practiceSettingsChanged(save = true) {
    toggleQuestionMode();
    const options = readPracticeSettings();
    const questions = tests[selectedTestIndex].questions;
    const progress = readPracticeStorage('learningProgress');
    const due = questions.filter(q => isPracticeDue(progress[practiceQuestionKey(q)])).length;
    const known = questions.filter(q => progress[practiceQuestionKey(q)]).length;
    document.getElementById('practiceProgressSummary').textContent =
        `Na zopakovanie: ${due}. Zaznamenaný pokus: ${known} z ${questions.length} otázok.`;
    const withHints = questions.filter(q => practiceHints(q).length).length;
    const withExplanation = questions.filter(q => practiceExplanation(q)).length;
    document.getElementById('practiceContentSummary').textContent =
        `Nápovedy: ${withHints}/${questions.length}. Vysvetlenia: ${withExplanation}/${questions.length}. Chýbajúci obsah treba ešte doplniť.`;
    let selected = null;
    for (const [name, preset] of Object.entries(PRACTICE_PRESETS)) {
        const matches = Object.keys(preset).filter(k => !['from', 'to', 'count', 'toEnd'].includes(k))
            .every(key => preset[key] === options[key]);
        document.querySelector(`[data-preset="${name}"]`).setAttribute('aria-pressed', String(matches));
        if (matches) selected = {learning: 'Učenie', training: 'Tréning', exam: 'Skúška'}[name];
    }
    document.getElementById('practicePresetLabel').textContent = selected ? `Predvoľba: ${selected}` : 'Vlastné nastavenia';
    document.getElementById('practiceSettingsError').textContent = '';
    if (save && !writePracticeStorage('practiceSettings', options)) {
        document.getElementById('practiceSettingsError').textContent = 'Prehliadač neumožnil zapamätať nastavenia. Test môžete spustiť.';
    }
}

function isPracticeDue(record, now = Date.now()) {
    return !!record && Number.isFinite(record.nextReviewAt) && record.nextReviewAt <= now;
}

function emptyPracticeState() {
    return {answer: [], none: false, answered: false, closed: false, hints: 0, revealed: false};
}

function startTestWithSettings() {
    const options = readPracticeSettings();
    const source = tests[selectedTestIndex];
    let questions = JSON.parse(JSON.stringify(source.questions));
    const error = document.getElementById('practiceSettingsError');
    questions.forEach(q => { q._practiceKey = practiceQuestionKey(q); });
    if (options.selection === 'range') {
        if (![options.from, options.to].every(Number.isInteger) || options.from < 1 ||
            options.to < options.from || options.to > questions.length) {
            error.textContent = 'Zadajte platný rozsah otázok od 1 po ' + questions.length + '.'; return;
        }
        questions = questions.slice(options.from - 1, options.to);
    } else if (options.selection === 'random') {
        if (!Number.isInteger(options.count) || options.count < 1 || options.count > questions.length) {
            error.textContent = 'Zadajte počet otázok od 1 po ' + questions.length + '.'; return;
        }
        // Náhodný výber a poradie sú nezávislé nastavenia.
        const selected = new Set(shuffleArray(questions.map((_, i) => i)).slice(0, options.count));
        questions = questions.filter((_, i) => selected.has(i));
    } else if (options.selection === 'due') {
        const progress = readPracticeStorage('learningProgress');
        questions = questions.filter(q => isPracticeDue(progress[q._practiceKey]));
    }
    if (!questions.length) {
        error.textContent = 'V tomto výbere teraz nie sú otázky na zopakovanie. Vyberte všetky otázky alebo iný rozsah.'; return;
    }
    if (options.shuffleQuestions) questions = shuffleArray(questions);
    if (options.shuffleOptions) questions = questions.map(shuffleAnswers);
    writePracticeStorage('practiceSettings', options);
    practice = {options, first: null, retry: false, finished: false, statisticsSaved: false, learningSaved: false,
        storageErrors: [], states: questions.map(emptyPracticeState)};
    currentTest = {...source, questions};
    currentQuestionIndex = 0;
    userAnswers = practice.states.map(s => s.answer);
    if (timerInterval) clearInterval(timerInterval);
    timerInterval = null;
    testStartTime = Date.now();
    timeLeft = options.minutes * 60;
    document.getElementById('testSettings').style.display = 'none';
    document.getElementById('testInterface').style.display = 'block';
    document.getElementById('results').style.display = 'none';
    document.getElementById('testTitle').textContent = source.title;
    document.getElementById('timer').style.display = options.minutes ? 'block' : 'none';
    document.getElementById('timer').style.color = '';
    document.getElementById('finishRetryBtn').style.display = 'none';
    track('test_start', {test: source.title, mode: options.selection});
    if (options.minutes) startTimer();
    showQuestion();
}

function practiceCorrect(question, state) {
    return state.answered && !state.revealed && (state.none || state.answer.length > 0) &&
        isQuestionCorrect(question, state.answer);
}

function practiceAssisted(state) { return state.hints > 0 || state.revealed; }

function practiceExplanationHTML(question, mode) {
    if (mode === 'off') return '';
    const explanation = practiceExplanation(question);
    if (!explanation) return '<p class="settings-note">Vysvetlenie k tejto otázke zatiaľ nie je doplnené.</p>';
    const summary = typeof explanation.summary === 'string' ? `<p>${escapeHtml(explanation.summary)}</p>` : '';
    const byAnswer = Array.isArray(explanation.byAnswer) ? explanation.byAnswer.map((text, i) =>
        `<li><strong>${escapeHtml(question.answers[i] || '')}</strong><br>${escapeHtml(text)}</li>`).join('') : '';
    const sources = Array.isArray(explanation.sources) ? explanation.sources.map(source => {
        if (!source || typeof source.url !== 'string' || !/^https?:\/\//i.test(source.url)) return '';
        return `<li><a href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(source.title || source.url)}</a></li>`;
    }).join('') : '';
    const memory = typeof explanation.memoryTip === 'string' && explanation.memoryTip
        ? `<p><strong>Na zapamätanie:</strong> ${escapeHtml(explanation.memoryTip)}</p>` : '';
    return `<details class="practice-explanation" ${mode === 'auto' ? 'open' : ''}>
        <summary>Prečo je to tak?</summary>${summary}
        ${byAnswer ? `<details><summary>Vysvetlenie jednotlivých možností</summary><ul>${byAnswer}</ul></details>` : ''}
        ${memory}${sources ? `<details><summary>Zdroje</summary><ul>${sources}</ul></details>` : ''}</details>`;
}

function practiceAnswersHTML(question, state, feedback, locked = false) {
    const isTF = isTFQuestion(question);
    const options = isTF ? ['pravda', 'nepravda'].map(polarity => ({
        index: question.answers.findIndex((_, i) => tfPolarityAt(question, i) === polarity),
        label: polarity === 'pravda' ? 'Pravda' : 'Nepravda'
    })) : question.answers.map((label, index) => ({index, label}));
    // Rovnaká voľba pri každej MC otázke; prázdny výber nie je správna odpoveď.
    if (!isTF || (Array.isArray(question.correct) && !question.correct.length)) options.push({index: -1, label: 'Žiadna z možností'});
    return options.map(({index, label}) => {
        const selected = index === -1 ? state.none : isTF
            ? state.answer.some(i => tfPolarityAt(question, i) === tfPolarityAt(question, index))
            : state.answer.includes(index);
        const correct = index === -1 ? Array.isArray(question.correct) && question.correct.length === 0
            : isQuestionAnswerCorrect(question, index);
        let css = selected ? 'selected' : '';
        let suffix = '';
        if (feedback) {
            css = correct ? (selected ? 'answer-correct-selected' : 'answer-correct-missed')
                : selected ? 'answer-wrong-selected' : 'answer-neutral';
            suffix = correct ? ' ✓ Správne' : selected ? ' ✗ Vaša odpoveď' : '';
        }
        return `<button type="button" class="answer ${css}" data-answer-index="${index}" aria-pressed="${selected}"
            ${locked ? 'disabled' : `onclick="selectAnswer(${index})"`}>
            <span class="answer-icon" aria-hidden="true">${selected ? '☑' : '☐'}</span>
            <span>${escapeHtml(label)}${suffix}</span></button>`;
    }).join('');
}

function practiceOutcome(question, state) {
    if (state.revealed) return 'Riešenie odkryté – skúste neskôr samostatne.';
    if (!state.answered) return 'Nezodpovedané';
    if (practiceCorrect(question, state)) return practiceAssisted(state) ? 'Správne s pomocou' : 'Správne samostatne';
    return practiceAssisted(state) ? 'Nesprávne s pomocou' : 'Nesprávne';
}

function showQuestion() {
    if (!practice || practice.finished) return;
    const question = currentTest.questions[currentQuestionIndex];
    const state = practice.states[currentQuestionIndex];
    const feedback = state.closed && (practice.options.feedback === 'each' || state.revealed);
    const hints = practiceHints(question);
    const hintContent = hints.slice(0, state.hints).map((hint, i) => `<p><strong>Nápoveda ${i + 1}:</strong> ${escapeHtml(hint)}</p>`).join('');
    const help = !state.closed && practice.options.hints ? `<div class="practice-help">
        ${hintContent}
        <button type="button" class="btn-secondary" onclick="showPracticeHint()" ${state.hints >= hints.length ? 'disabled' : ''}>
            ${state.hints ? 'Ďalšia nápoveda' : 'Potrebujem nápovedu'}</button>
        ${!hints.length ? '<p class="settings-note">Nápoveda k tejto otázke ešte nie je doplnená.</p>' : ''}
        <button type="button" class="btn-secondary" onclick="revealPracticeAnswer()">Neviem – ukáž riešenie</button>
        </div>` : hintContent;
    document.getElementById('questionContainer').innerHTML = `<div class="question">
        <h3 tabindex="-1">Otázka ${currentQuestionIndex + 1}: ${escapeHtml(question.question)}</h3>
        ${!isTFQuestion(question) ? '<p class="settings-note">Vyberte všetky správne možnosti alebo „Žiadna z možností“.</p>' : ''}
        ${practiceAnswersHTML(question, state, feedback, state.closed)}
        ${help}
        ${feedback ? `<p class="practice-outcome" role="status">${practiceOutcome(question, state)}</p>${practiceExplanationHTML(question, practice.options.explanations)}` : ''}
        ${!state.closed ? `<div class="practice-actions">
            ${practice.options.feedback === 'each' ? '<button type="button" id="confirmAnswerBtn" onclick="confirmPracticeAnswer()">Potvrdiť odpoveď</button>' : ''}
            <button type="button" class="btn-secondary" onclick="skipPracticeQuestion()">Neviem / preskočiť</button></div>` : ''}
        <p id="practiceAnswerError" class="practice-error" role="alert"></p></div>`;
    document.getElementById('questionNumber').textContent = `${currentQuestionIndex + 1} / ${currentTest.questions.length}`;
    document.getElementById('prevBtn').disabled = currentQuestionIndex === 0;
    const canContinue = practice.options.feedback === 'end' || state.closed;
    document.getElementById('nextBtn').style.display = canContinue && currentQuestionIndex < currentTest.questions.length - 1 ? 'inline-block' : 'none';
    document.getElementById('nextBtn').textContent = 'Ďalšia';
    document.getElementById('submitBtn').style.display = canContinue && currentQuestionIndex === currentTest.questions.length - 1 ? 'inline-block' : 'none';
    document.getElementById('submitBtn').textContent = 'Odovzdať test';
    document.getElementById('practiceSessionNote').textContent = practice.retry
        ? 'Opakovanie. Pôvodný výsledok zostáva zachovaný; tieto pokusy nezvyšujú štatistiky ani interval učenia.'
        : `Štatistiky: ${practice.options.statistics ? 'zapnuté' : 'vypnuté'}. Plánovanie učenia: ${practice.options.learning ? 'zapnuté' : 'vypnuté'}.`;
}

function selectAnswer(index) {
    if (!practice || practice.finished) return;
    const state = practice.states[currentQuestionIndex];
    if (state.closed) return;
    const question = currentTest.questions[currentQuestionIndex];
    if (index === -1) {
        state.none = !state.none;
        state.answer.splice(0);
    } else if (Number.isInteger(index) && index >= 0 && index < question.answers.length) {
        state.none = false;
        if (isTFQuestion(question)) state.answer.splice(0, state.answer.length, index);
        else {
            const existing = state.answer.indexOf(index);
            if (existing < 0) state.answer.push(index);
            else state.answer.splice(existing, 1);
        }
    }
    showQuestion();
}

function confirmPracticeAnswer() {
    if (!practice || practice.finished) return;
    const state = practice.states[currentQuestionIndex];
    if (state.closed) return;
    if (!state.none && !state.answer.length) {
        document.getElementById('practiceAnswerError').textContent = 'Vyberte odpoveď, „Žiadna z možností“, alebo použite „Neviem / preskočiť“.'; return;
    }
    state.answered = true;
    state.closed = true;
    showQuestion();
}

function showPracticeHint() {
    if (!practice || practice.finished || !practice.options.hints) return;
    const state = practice.states[currentQuestionIndex];
    if (!state.closed && state.hints < practiceHints(currentTest.questions[currentQuestionIndex]).length) state.hints++;
    showQuestion();
}

function revealPracticeAnswer() {
    if (!practice || practice.finished || !practice.options.hints) return;
    const state = practice.states[currentQuestionIndex];
    if (state.closed) return;
    state.closed = true;
    state.revealed = true;
    state.answered = false;
    showQuestion();
}

function skipPracticeQuestion() {
    if (!practice || practice.finished) return;
    const state = practice.states[currentQuestionIndex];
    if (state.closed) return;
    state.answer.splice(0);
    state.none = false;
    state.answered = false;
    if (practice.options.feedback === 'each') { state.closed = true; showQuestion(); }
    else if (currentQuestionIndex < currentTest.questions.length - 1) { currentQuestionIndex++; showQuestion(); }
    else submitTest();
}

function previousQuestion() {
    if (practice && !practice.finished && currentQuestionIndex > 0) { currentQuestionIndex--; showQuestion(); }
}

function nextQuestion() {
    if (!practice || practice.finished) return;
    if (practice.options.feedback === 'each' && !practice.states[currentQuestionIndex].closed) {
        confirmPracticeAnswer(); return;
    }
    if (currentQuestionIndex < currentTest.questions.length - 1) { currentQuestionIndex++; showQuestion(); }
}

function practiceScore(questions, states) {
    let score = 0, independent = 0, assisted = 0;
    questions.forEach((q, i) => {
        const helped = practiceAssisted(states[i]);
        if (helped) assisted++;
        if (practiceCorrect(q, states[i])) { score++; if (!helped) independent++; }
    });
    return {score, independent, assisted, total: questions.length, percentage: Math.round(score / questions.length * 100)};
}

function updatePracticeProgress(questions, states) {
    const progress = readPracticeStorage('learningProgress');
    const now = Date.now();
    const byKey = new Map();
    questions.forEach((q, i) => {
        const independent = practiceCorrect(q, states[i]) && !practiceAssisted(states[i]);
        // Pri duplicitách má neúspešný pokus prednosť pred úspešným v tom istom teste.
        const previous = byKey.get(q._practiceKey);
        if (!previous || !independent) byKey.set(q._practiceKey, {state: states[i], independent});
    });
    for (const [key, {state, independent}] of byKey) {
        const old = progress[key] || {};
        const oldStreak = Number.isInteger(old.streak) ? Math.min(5, Math.max(0, old.streak)) : 0;
        const spaced = !Number.isFinite(old.lastIndependentAt) || now - old.lastIndependentAt >= 20 * 3600000;
        const streak = independent ? Math.min(5, Math.max(1, oldStreak + (spaced ? 1 : 0))) : 0;
        const days = independent ? [1, 3, 7, 14, 30][streak - 1] : 0;
        progress[key] = {
            attempts: (Number.isInteger(old.attempts) ? old.attempts : 0) + 1,
            streak, lastSeenAt: now, lastIndependentAt: independent ? now : (old.lastIndependentAt || null),
            outcome: state.revealed ? 'revealed' : independent ? 'independent' : state.hints ? 'assisted' : 'incorrect',
            highestHint: state.hints, nextReviewAt: now + days * 86400000
        };
    }
    practice.learningSaved = writePracticeStorage('learningProgress', progress);
    if (!practice.learningSaved) practice.storageErrors.push('Pokrok v učení sa nepodarilo uložiť.');
}

function savePracticeFirstAttempt() {
    if (practice.first) return;
    practice.first = JSON.parse(JSON.stringify({test: currentTest, states: practice.states}));
    const result = practiceScore(currentTest.questions, practice.states);
    if (practice.options.statistics) {
        try {
            saveTestResult({testName: currentTest.title, date: new Date().toISOString(), ...result, settings: {...practice.options}});
            practice.statisticsSaved = true;
        } catch { practice.storageErrors.push('Výsledok sa nepodarilo uložiť do štatistík.'); }
    }
    if (practice.options.learning) updatePracticeProgress(currentTest.questions, practice.states);
    track('test_finish', {test: currentTest.title, score: result.score, total: result.total, percent: result.percentage,
        duration_sec: Math.round((Date.now() - testStartTime) / 1000)});
    displayTestList();
}

function submitTest(timedOut = false) {
    if (!practice || practice.finished || !currentTest || document.getElementById('testInterface').style.display === 'none') return;
    if (!timedOut && practice.options.feedback === 'each' && !practice.states[currentQuestionIndex].closed) {
        confirmPracticeAnswer(); return;
    }
    practice.states.forEach(state => {
        if (!state.closed) { state.answered = state.none || state.answer.length > 0; state.closed = true; }
    });
    savePracticeFirstAttempt();
    const remaining = currentTest.questions.filter((q, i) => !practiceCorrect(q, practice.states[i]) || practiceAssisted(practice.states[i]));
    if (!timedOut && practice.options.repeat && remaining.length) {
        practice.retry = true;
        currentTest = {...currentTest, questions: remaining};
        practice.states = remaining.map(emptyPracticeState);
        userAnswers = practice.states.map(s => s.answer);
        currentQuestionIndex = 0;
        document.getElementById('finishRetryBtn').style.display = 'inline-block';
        showQuestion();
        return;
    }
    showResults(timedOut);
}

function finishPracticeRetry() {
    if (practice?.retry && !practice.finished) showResults();
}

function showResults(timedOut = false) {
    if (!practice || practice.finished || !practice.first) return;
    practice.finished = true;
    if (timerInterval) clearInterval(timerInterval);
    timerInterval = null;
    const {test, states} = practice.first;
    const result = practiceScore(test.questions, states);
    document.getElementById('testInterface').style.display = 'none';
    document.getElementById('results').style.display = 'block';
    const settings = practice.options;
    document.getElementById('resultsContainer').innerHTML = `<div class="results-summary">
        <h3>Výsledok: ${result.score} / ${result.total} (${result.percentage} %)</h3>
        <p>Samostatne správne: ${result.independent} / ${result.total}. Pomoc použitá pri ${result.assisted} otázkach.</p>
        ${practice.retry ? '<p>Zobrazený je prvý pokus pred opakovaním.</p>' : ''}
        ${timedOut ? '<p>Časový limit vypršal.</p>' : ''}</div>
        <p class="settings-note">${practice.statisticsSaved ? 'Výsledok započítaný do štatistík.' : 'Výsledok sa nezapočítal do štatistík.'}
        ${practice.learningSaved ? 'Odpovede použité na plánovanie učenia.' : 'Plán učenia zostal bez zmeny.'}</p>
        <p class="settings-note">Vyhodnotenie: ${settings.feedback === 'each' ? 'po každej otázke' : 'na konci'}.
        Čas: ${settings.minutes ? settings.minutes + ' min' : 'bez limitu'}.</p>
        ${practice.storageErrors.map(error => `<p class="practice-error" role="alert">${escapeHtml(error)}</p>`).join('')}
        ${test.questions.map((q, i) => `<div class="result-question ${practiceCorrect(q, states[i]) ? 'result-correct' : 'result-incorrect'}">
            <h4>Otázka ${i + 1}: ${escapeHtml(q.question)}</h4>
            <p class="practice-outcome">${practiceOutcome(q, states[i])}</p>
            ${practiceAnswersHTML(q, states[i], true, true)}
            ${practiceExplanationHTML(q, settings.explanations)}</div>`).join('')}`;
}
