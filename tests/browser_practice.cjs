// Voliteľná kontrola lokálneho Docker prostredia: node tests/browser_practice.cjs
// Potrebuje Google Chrome, Node >=18 a modul ws. Žiadne zápisy do katalógu/API.
// Fiktívne otázky existujú iba v pamäti izolovaného prehliadača.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const WebSocket = require('ws');
const output = fs.mkdtempSync(path.join(os.tmpdir(), 'tester-practice-'));
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const fixture = {
    title: 'Kontrola nastavení', filename: 'browser-only.json', year: 2, category: 'Kontrola',
    questions: [
        {id: 'check-single', question: 'Jedna správna možnosť', answers: ['A', 'B', 'C'], correct: 0,
            learning: {status: 'reviewed', hints: ['Prvé nasmerovanie', 'Druhý krok'], explanation: {
                summary: 'Dôvod dostupný až po odpovedi', byAnswer: ['Dôvod A', 'Dôvod B', 'Dôvod C'],
                memoryTip: 'Zapamätajte si princíp', sources: [{title: 'Testovací odkaz', url: 'https://example.org'}]}}},
        {id: 'check-multi', question: 'Viac možností', answers: ['A', 'B', 'C'], correct: [0, 2]},
        {id: 'check-none', question: 'Žiadna správna možnosť', answers: ['A', 'B', 'C'], correct: []},
        {id: 'check-tf', question: 'Výrok pravda/nepravda', answers: ['pravda', 'nepravda (Dôvod výroku)'], correct: [1]}
    ]
};

(async () => {
    const chrome = spawn(process.env.CHROME_BIN || 'google-chrome', [
        '--headless=new', '--disable-gpu', '--disable-dev-shm-usage', '--disable-background-networking',
        '--no-first-run', '--no-default-browser-check', '--remote-debugging-port=0',
        '--user-data-dir=' + path.join(output, 'profile'), 'about:blank'
    ], {stdio: ['ignore', 'ignore', 'pipe']});
    let ws;
    const errors = [], checks = [];
    try {
        const endpoint = await new Promise((resolve, reject) => {
            let log = '';
            const timer = setTimeout(() => reject(Error('Chrome startup timeout')), 15000);
            chrome.stderr.on('data', data => {
                log += data;
                const match = log.match(/DevTools listening on (ws:\/\/\S+)/);
                if (match) { clearTimeout(timer); resolve(match[1]); }
            });
            chrome.once('error', error => { clearTimeout(timer); reject(error); });
            chrome.once('exit', code => { clearTimeout(timer); reject(Error('Chrome exit ' + code + ': ' + log.slice(-1200))); });
        });
        const tabs = await (await fetch('http://127.0.0.1:' + new URL(endpoint).port + '/json/list')).json();
        ws = new WebSocket(tabs.find(t => t.type === 'page').webSocketDebuggerUrl);
        await new Promise((resolve, reject) => { ws.once('open', resolve); ws.once('error', reject); });
        let sequence = 0, pageLoads = 0;
        const pending = new Map();
        const send = (method, params = {}) => new Promise((resolve, reject) => {
            const id = ++sequence;
            const timeout = setTimeout(() => { pending.delete(id); reject(Error('Timeout ' + method)); }, 15000);
            pending.set(id, {resolve, reject, timeout});
            ws.send(JSON.stringify({id, method, params}));
        });
        ws.on('message', data => {
            const message = JSON.parse(data);
            const request = pending.get(message.id);
            if (request) {
                pending.delete(message.id); clearTimeout(request.timeout);
                message.error ? request.reject(Error(JSON.stringify(message.error))) : request.resolve(message.result);
            }
            if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails);
            if (message.method === 'Page.loadEventFired') pageLoads++;
            if (message.method === 'Page.javascriptDialogOpening') send('Page.handleJavaScriptDialog', {accept: true}).catch(() => {});
        });
        const evaluate = async expression => {
            const result = await send('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true});
            if (result.exceptionDetails) throw Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
            return result.result.value;
        };
        const check = async (name, expression) => {
            assert.ok(await evaluate(expression), name); checks.push(name); console.log('PASS:', name);
        };
        const waitFor = async expression => {
            for (let n = 0; n < 100; n++) {
                try { if (await evaluate(expression)) return; } catch (error) {
                    if (!/context|not defined|navigated/.test(error.message)) throw error;
                }
                await sleep(100);
            }
            throw Error('Condition timed out: ' + expression);
        };
        const click = selector => evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
        const mount = async (options = {}, questions = fixture.questions) => {
            await evaluate(`
                if (timerInterval) clearInterval(timerInterval);
                document.getElementById('testInterface').style.display = 'none';
                document.getElementById('results').style.display = 'none';
                tests = [${JSON.stringify({...fixture, questions})}];
                showTestSettings(0);
                fillPracticeSettings({...PRACTICE_DEFAULTS, ...${JSON.stringify(options)}});
            `);
        };
        const start = async (options = {}, questions = fixture.questions) => {
            await mount(options, questions);
            await click('#practiceSettingsForm button[type="submit"]');
        };
        const finishCorrect = async () => {
            await evaluate(`for (let i = 0; i < currentTest.questions.length; i++) {
                currentQuestionIndex = i;
                const q = currentTest.questions[i];
                const correct = Array.isArray(q.correct) ? q.correct : [q.correct];
                if (!correct.length) selectAnswer(-1);
                else for (const index of correct) selectAnswer(index);
                if (practice.options.feedback === 'each') confirmPracticeAnswer();
            } submitTest();`);
        };
        const snap = async name => fs.writeFileSync(path.join(output, name + '.png'),
            Buffer.from((await send('Page.captureScreenshot', {captureBeyondViewport: true})).data, 'base64'));
        await send('Page.enable'); await send('Runtime.enable');
        await send('Page.navigate', {url: 'http://test.localhost'});
        await waitFor("typeof tests !== 'undefined' && tests.length > 0 && typeof PRACTICE_DEFAULTS !== 'undefined'");
        const expectedVersion = fs.readFileSync(path.join(__dirname, '..', 'VERSION'), 'utf8').trim();
        await check('Local app serves version ' + expectedVersion, `document.body.dataset.version === ${JSON.stringify(expectedVersion)}`);
        const catalogSize = await evaluate('tests.length');

        await mount();
        await click('[data-preset="learning"]');
        await check('Learning preset and independent saving switches', "readPracticeSettings().hints && !readPracticeSettings().statistics && readPracticeSettings().learning && readPracticeSettings().repeat");
        await click('#countStatistics');
        await check('Preset can be customized', "document.getElementById('practicePresetLabel').textContent === 'Vlastné nastavenia' && readPracticeSettings().statistics");
        const loadsBeforeReload = pageLoads;
        await send('Page.reload');
        for (let n = 0; n < 100 && pageLoads === loadsBeforeReload; n++) await sleep(100);
        assert.ok(pageLoads > loadsBeforeReload, 'Reload completed');
        await waitFor("typeof PRACTICE_DEFAULTS !== 'undefined' && tests.length > 0");
        await evaluate('showTestSettings(tests.findIndex(t => t.questions))');
        await check('Custom settings survive reload', 'readPracticeSettings().hints && readPracticeSettings().statistics && readPracticeSettings().repeat');

        await start({feedback: 'end', statistics: false, learning: false});
        await check('No early answer-count or feedback disclosure', "!document.querySelector('#questionContainer .multiple-note') && !document.querySelector('#questionContainer .answer-correct-missed') && !document.querySelector('#questionContainer .practice-explanation')");
        await check('No reveal or hint button when assistance disabled', "!document.querySelector('[onclick=\"showPracticeHint()\"]') && !document.querySelector('[onclick=\"revealPracticeAnswer()\"]')");
        await evaluate('currentQuestionIndex = 2; showQuestion(); submitTest()');
        await check('Unanswered zero-correct question earns no points', "practice.finished && practiceScore(practice.first.test.questions, practice.first.states).score === 0");

        for (const statistics of [false, true]) for (const learning of [false, true]) {
            await evaluate("localStorage.removeItem('testResults'); localStorage.removeItem('learningProgress')");
            await start({statistics, learning}, [fixture.questions[0]]);
            await click('[data-answer-index="0"]');
            await click('#confirmAnswerBtn');
            await click('#submitBtn');
            await check(`Saving is independent: statistics=${statistics}, learning=${learning}`,
                `savedResults().length === ${statistics ? 1 : 0} && Object.keys(readPracticeStorage('learningProgress')).length === ${learning ? 1 : 0}`);
            await evaluate('submitTest(); showResults();');
            await check('Repeated submit does not add a result', `savedResults().length === ${statistics ? 1 : 0}`);
        }

        await start({statistics: false, learning: false});
        await click('[data-answer-index="1"]'); await click('#confirmAnswerBtn');
        await click('#nextBtn'); await click('#prevBtn');
        await evaluate('selectAnswer(0)');
        await check('Answer stays locked when navigating back', 'practice.states[0].answer.length === 1 && practice.states[0].answer[0] === 1 && document.querySelectorAll("#questionContainer button.answer:disabled").length === 4');
        await click('#nextBtn'); await click('[data-answer-index="0"]'); await click('#confirmAnswerBtn');
        await check('Partial multiple answer remains incorrect', '!practiceCorrect(currentTest.questions[1], practice.states[1])');
        await click('#nextBtn'); await click('[data-answer-index="-1"]'); await click('#confirmAnswerBtn');
        await check('Explicit none is correct', 'practiceCorrect(currentTest.questions[2], practice.states[2])');
        await click('#nextBtn');
        await check('TF still has only two answer buttons', 'document.querySelectorAll("#questionContainer button.answer").length === 2');
        await click('[data-answer-index="1"]'); await click('#confirmAnswerBtn');
        await check('Legacy TF explanation is available after answer', 'document.querySelector("#questionContainer .practice-explanation").textContent.includes("Dôvod výroku")');
        await click('#submitBtn');

        await evaluate("localStorage.removeItem('testResults'); localStorage.removeItem('learningProgress')");
        await start({hints: true, statistics: true, learning: true}, [fixture.questions[0]]);
        await click('[onclick="showPracticeHint()"]');
        await check('First hint only; no solution before confirmation', "document.getElementById('questionContainer').textContent.includes('Prvé nasmerovanie') && !document.getElementById('questionContainer').textContent.includes('Druhý krok') && !document.getElementById('questionContainer').textContent.includes('Dôvod dostupný')");
        await click('[onclick="showPracticeHint()"]');
        await click('[data-answer-index="0"]'); await click('#confirmAnswerBtn');
        await check('Click explanation starts collapsed', "!document.querySelector('.practice-explanation').open");
        await click('.practice-explanation > summary');
        await check('Explanation expands on request', "document.querySelector('.practice-explanation').open");
        await click('#submitBtn');
        await check('Assisted score and highest hint stored; question remains due', `savedResults()[0].score === 1 && savedResults()[0].independent === 0 && savedResults()[0].assisted === 1 && Object.values(readPracticeStorage('learningProgress'))[0].highestHint === 2 && isPracticeDue(Object.values(readPracticeStorage('learningProgress'))[0])`);
        await mount({selection: 'due'});
        await click('#practiceSettingsForm button[type="submit"]');
        await check('Due selection uses question progress', 'currentTest.questions.length === 1 && currentTest.questions[0].id === "check-single"');

        await start({hints: true, statistics: false, learning: false}, [fixture.questions[0]]);
        await click('[onclick="revealPracticeAnswer()"]');
        await evaluate('selectAnswer(0)'); await click('#submitBtn');
        await check('Reveal cannot become a correct answer', 'practice.first.states[0].revealed && practiceScore(practice.first.test.questions, practice.first.states).score === 0');

        await evaluate("localStorage.removeItem('testResults'); localStorage.removeItem('learningProgress')");
        await start({repeat: true}, [fixture.questions[0]]);
        await click('[data-answer-index="1"]'); await click('#confirmAnswerBtn'); await click('#submitBtn');
        await check('Retry saves first attempt once', 'practice.retry && savedResults().length === 1 && savedResults()[0].score === 0');
        await click('[data-answer-index="0"]'); await click('#confirmAnswerBtn'); await click('#submitBtn');
        await check('Retry does not overwrite score or learning interval', 'practice.finished && savedResults().length === 1 && savedResults()[0].score === 0 && Object.values(readPracticeStorage("learningProgress"))[0].attempts === 1 && Object.values(readPracticeStorage("learningProgress"))[0].streak === 0');

        await start({minutes: 20, feedback: 'end'}, [fixture.questions[2]]);
        await evaluate('timeLeft = 1');
        await waitFor('practice.finished');
        await check('Timeout ends test and unselected none is wrong', 'practiceScore(practice.first.test.questions, practice.first.states).score === 0 && timerInterval === null');

        await start({explanations: 'off', hints: true, statistics: false, learning: false}, [fixture.questions[0]]);
        await finishCorrect();
        await check('Explanations off is honored in results', '!document.querySelector("#results .practice-explanation")');

        const draft = structuredClone(fixture.questions[0]); draft.learning.status = 'draft';
        await start({hints: true, explanations: 'auto', statistics: false, learning: false}, [draft]);
        await check('Draft hints are unavailable', 'document.querySelector("[onclick*=showPracticeHint]").disabled');
        await finishCorrect();
        await check('Draft explanation is not shown', '!document.querySelector("#results .practice-explanation")');

        await mount({selection: 'range', from: 3, to: 1, toEnd: false});
        await evaluate('startTestWithSettings()');
        await check('Invalid range is rejected', "document.getElementById('practiceSettingsError').textContent.includes('platný rozsah')");
        await start({selection: 'random', count: 2, shuffleQuestions: false, shuffleOptions: false});
        await check('Random subset preserves order when shuffling off', 'currentTest.questions.length === 2 && tests[0].questions.indexOf(tests[0].questions.find(q => q.id === currentTest.questions[0].id)) < tests[0].questions.indexOf(tests[0].questions.find(q => q.id === currentTest.questions[1].id))');
        await check('Shuffling keeps answer explanations and key aligned', `(function () {
            const original = tests[0].questions[0];
            for (let i=0;i<30;i++) { const q = shuffleAnswers(original);
                if (q.answers[q.correct] !== 'A' || !q.answers.every((a,j) => q.learning.explanation.byAnswer[j] === 'Dôvod ' + a)) return false;
            } return original.answers[0] === 'A'; })()`);
        await check('Progress identity survives shuffling and content edit invalidates it', `(function () {
            const original = {...tests[0].questions[0]}; original._practiceKey = practiceQuestionKey(original);
            return shuffleAnswers(original)._practiceKey === original._practiceKey && practiceQuestionKey({...original, question:'Zmenené'}) !== original._practiceKey;
        })()`);

        await start({feedback: 'end', repeat: true, statistics: false, learning: false}, [fixture.questions[0]]);
        await click('[data-answer-index="1"]');
        await check('Retry setting does not enable early feedback', '!document.querySelector("#questionContainer .answer-correct-missed") && !document.querySelector("#confirmAnswerBtn")');
        await click('#submitBtn'); await click('#finishRetryBtn');
        await check('Retry can be stopped while preserving original result', 'practice.finished && practiceScore(practice.first.test.questions, practice.first.states).score === 0');

        await start({statistics: false, learning: true}, [fixture.questions[0]]);
        await evaluate("localStorage.removeItem('learningProgress')");
        await finishCorrect();
        await check('Independent success schedules later review', 'Object.values(readPracticeStorage("learningProgress"))[0].streak === 1 && !isPracticeDue(Object.values(readPracticeStorage("learningProgress"))[0])');
        await evaluate('updatePracticeProgress(practice.first.test.questions, practice.first.states)');
        await check('Same-day repetitions do not extend interval', 'Object.values(readPracticeStorage("learningProgress"))[0].streak === 1');
        await evaluate(`{
            const progress = readPracticeStorage('learningProgress');
            const key = practice.first.test.questions[0]._practiceKey;
            progress[key].lastIndependentAt -= 86400000;
            writePracticeStorage('learningProgress', progress);
            updatePracticeProgress(practice.first.test.questions, practice.first.states);
        }`);
        await check('Spaced success extends the next review', 'Object.values(readPracticeStorage("learningProgress"))[0].streak === 2 && Object.values(readPracticeStorage("learningProgress"))[0].nextReviewAt > Date.now() + 2 * 86400000');

        const htmlFixture = structuredClone(fixture.questions[0]);
        htmlFixture.question = '<img src=x onerror="window.practiceInjected=1">';
        htmlFixture.learning.hints = ['<img src=x onerror="window.practiceInjected=1">'];
        htmlFixture.learning.explanation.summary = '<img src=x onerror="window.practiceInjected=1">';
        htmlFixture.learning.explanation.sources = [{title: 'Blocked link', url: 'javascript:alert(1)'}];
        await start({hints: true, explanations: 'auto', statistics: false, learning: false}, [htmlFixture]);
        await click('[onclick="showPracticeHint()"]');
        await click('[data-answer-index="0"]'); await click('#confirmAnswerBtn');
        await check('Question, hint and explanation HTML are escaped; unsafe source omitted', '!window.practiceInjected && !document.querySelector("#questionContainer img") && !document.querySelector("#questionContainer a[href^=javascript]")');

        // Mobil aj desktop, svetlá aj tmavá téma. Obrázky zostanú v dočasnom adresári.
        for (const width of [390, 1440]) for (const theme of ['light', 'dark']) {
            await send('Emulation.setDeviceMetricsOverride', {width, height: 1000, deviceScaleFactor: 1, mobile: width < 600});
            await evaluate(`document.documentElement.setAttribute('data-theme', '${theme}')`);
            await mount();
            await sleep(350); // Dokončenie CSS prechodu témy pred snímkou.
            await check(`Settings fit viewport ${width}/${theme}`, 'document.documentElement.scrollWidth <= document.documentElement.clientWidth');
            await snap(`settings-${width}-${theme}`);
            await start({hints: true, explanations: 'auto', statistics: false, learning: false}, [fixture.questions[0]]);
            await click('[data-answer-index="0"]'); await click('#confirmAnswerBtn');
            await check(`Question fits viewport ${width}/${theme}`, 'document.documentElement.scrollWidth <= document.documentElement.clientWidth');
            await snap(`question-${width}-${theme}`);
        }

        await start({statistics: true, learning: true}, [fixture.questions[0]]);
        await evaluate('window.originalStorageSet = Storage.prototype.setItem; Storage.prototype.setItem = function () { throw new Error("Simulated quota"); }');
        await finishCorrect();
        await check('Storage failure does not prevent results or claim success', 'practice.finished && practice.storageErrors.length === 2 && !document.getElementById("resultsContainer").textContent.includes("Výsledok započítaný")');
        await evaluate('Storage.prototype.setItem = window.originalStorageSet');
        await check('Server catalog unchanged', `(async () => (await (await fetch('/api/tests')).json()).length === ${catalogSize})()`);
        assert.equal(errors.length, 0, JSON.stringify(errors));
        fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify({checks, errors}, null, 2));
        console.log(`${checks.length} browser checks passed. Artifacts: ${output}`);
    } finally {
        if (ws) ws.close();
        chrome.kill('SIGTERM');
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
