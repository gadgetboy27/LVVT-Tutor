const API_BASE = '';
let authToken = localStorage.getItem('lvv_token');
let currentUser = null;
let currentQuiz = null;
let currentQuestionIndex = 0;
let selectedAnswer = null;
let quizAnswers = [];
let currentStandard = null;
let currentView = 'dashboard';
let currentTeachStandard = null;
let currentTeachTree = null;
let userStats = { quizzes: 0, score: 0, mastered: 0, atPass: 0 };
let savedState = null;
let isGuest = false;
let mockExam = null;      // active exam: {id, questions, ...}
let mockAnswers = {};     // question_id -> option letter
let mockIndex = 0;
let mockTimer = null;
let mockEndsAt = 0;

document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

function authHeaders(extra = {}) {
    const h = { ...extra };
    if (authToken) h['Authorization'] = `Bearer ${authToken}`;
    return h;
}

function showError(id, msg) {
    const el = document.getElementById(id);
    if (el) { el.textContent = msg; el.classList.remove('hidden'); }
}

function hideError(id) {
    const el = document.getElementById(id);
    if (el) { el.textContent = ''; el.classList.add('hidden'); }
}

async function initializeApp() {
    setupEventListeners();
    
    if (authToken) {
        try {
            await loadCurrentUser();
            showMainContent();
        } catch (e) {
            localStorage.removeItem('lvv_token');
            authToken = null;
            showAuthSection();
        }
    } else {
        showAuthSection();
    }
}

function setupEventListeners() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => switchAuthTab(btn.dataset.tab));
    });
    
    document.getElementById('login-form').addEventListener('submit', handleLogin);
    document.getElementById('register-form').addEventListener('submit', handleRegister);
    document.getElementById('logout-btn').addEventListener('click', handleLogout);
    document.getElementById('guest-btn').addEventListener('click', continueAsGuest);
    document.getElementById('mock-start-btn').addEventListener('click', startMockExam);
    document.getElementById('mock-prev-btn').addEventListener('click', () => goMockQuestion(mockIndex - 1));
    document.getElementById('mock-next-btn').addEventListener('click', () => goMockQuestion(mockIndex + 1));
    document.getElementById('mock-submit-btn').addEventListener('click', () => submitMockExam(false));
    document.getElementById('guest-signup-btn').addEventListener('click', () => {
        handleLogout();
        switchAuthTab('register');
    });
    document.getElementById('back-to-categories').addEventListener('click', showCategories);
    document.getElementById('submit-answer-btn').addEventListener('click', submitAnswer);
    document.getElementById('next-question-btn').addEventListener('click', nextQuestion);
    document.getElementById('save-exit-btn').addEventListener('click', saveAndExit);
    document.getElementById('retry-quiz-btn').addEventListener('click', retryQuiz);
    document.getElementById('back-to-dashboard-btn').addEventListener('click', backToDashboard);
    document.getElementById('resume-btn').addEventListener('click', resumeQuiz);
    
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', () => switchView(btn.dataset.view));
    });
    
    document.getElementById('back-from-doc').addEventListener('click', closeDocViewer);
    document.getElementById('start-quiz-from-doc').addEventListener('click', startQuizFromDoc);

    document.getElementById('back-from-teach').addEventListener('click', closeTeachInterface);
    document.getElementById('teach-quiz-btn').addEventListener('click', () => {
        if (currentTeachStandard) startQuiz(currentTeachStandard.number, currentTeachStandard.title);
    });
    
    document.querySelectorAll('.path-card').forEach(card => {
        card.addEventListener('click', () => selectLearningPath(card.dataset.path));
    });
    
    document.querySelectorAll('.start-scenario-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            startScenario(e.target.closest('.scenario-card').dataset.scenario);
        });
    });
    
    document.getElementById('self-assess-btn').addEventListener('click', showSelfAssessment);
    document.getElementById('cancel-assessment').addEventListener('click', hideSelfAssessment);
    document.getElementById('save-assessment').addEventListener('click', saveSelfAssessment);
    
    document.querySelectorAll('.assess-slider').forEach(slider => {
        slider.addEventListener('input', (e) => {
            e.target.nextElementSibling.textContent = `${e.target.value}/5`;
        });
    });
}

function switchAuthTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelector(`[data-tab="${tab}"]`).classList.add('active');
    document.getElementById('login-form').classList.toggle('hidden', tab !== 'login');
    document.getElementById('register-form').classList.toggle('hidden', tab !== 'register');
}

async function handleLogin(e) {
    e.preventDefault();
    hideError('login-error');
    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value;
    if (!email || !password) {
        showError('login-error', 'Enter your email and password.');
        return;
    }
    showLoading('Logging in...');
    try {
        // /api/auth/login uses OAuth2PasswordRequestForm -> form-encoded username/password
        const body = new URLSearchParams({ username: email, password });
        const response = await fetch(`${API_BASE}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body
        });
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || 'Incorrect email or password');
        }
        const data = await response.json();
        authToken = data.access_token;
        localStorage.setItem('lvv_token', authToken);
        await loadCurrentUser();
        await showMainContent();
    } catch (err) {
        showError('login-error', err.message);
    } finally {
        hideLoading();
    }
}

async function handleRegister(e) {
    e.preventDefault();
    hideError('register-error');
    const email = document.getElementById('register-email').value.trim();
    const password = document.getElementById('register-password').value;
    const confirm = document.getElementById('register-confirm').value;
    if (!email || !password) {
        showError('register-error', 'Enter an email and password.');
        return;
    }
    if (password.length < 6) {
        showError('register-error', 'Password must be at least 6 characters.');
        return;
    }
    if (password !== confirm) {
        showError('register-error', 'Passwords do not match.');
        return;
    }
    showLoading('Creating account...');
    try {
        const response = await fetch(`${API_BASE}/api/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || 'Registration failed');
        }
        // Registered — log straight in.
        const body = new URLSearchParams({ username: email, password });
        const loginResp = await fetch(`${API_BASE}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body
        });
        const data = await loginResp.json();
        authToken = data.access_token;
        localStorage.setItem('lvv_token', authToken);
        await loadCurrentUser();
        await showMainContent();
    } catch (err) {
        showError('register-error', err.message);
    } finally {
        hideLoading();
    }
}

function continueAsGuest() {
    isGuest = true;
    authToken = null;
    currentUser = null;
    document.getElementById('username-display').textContent = 'Guest';
    document.getElementById('guest-banner').classList.remove('hidden');
    showMainContent();
}

function handleLogout() {
    isGuest = false;
    clearInterval(mockTimer);
    mockExam = null;
    document.getElementById('mock-result').innerHTML = '';
    document.getElementById('guest-banner').classList.add('hidden');
    localStorage.removeItem('lvv_token');
    localStorage.removeItem('lvv_quiz_state');
    localStorage.removeItem('lvv_user');
    authToken = null;
    currentUser = null;
    savedState = null;
    userStats = { quizzes: 0, score: 0, mastered: 0, atPass: 0 };
    showAuthSection();
}

async function loadCurrentUser() {
    const response = await fetch(`${API_BASE}/api/auth/me`, { headers: authHeaders() });
    if (!response.ok) throw new Error('Session expired');
    currentUser = await response.json();
    document.getElementById('username-display').textContent = currentUser.email;
}

function showAuthSection() {
    document.getElementById('auth-section').classList.remove('hidden');
    document.getElementById('main-content').classList.add('hidden');
    document.getElementById('user-info').classList.add('hidden');
}

async function showMainContent() {
    document.getElementById('auth-section').classList.add('hidden');
    document.getElementById('main-content').classList.remove('hidden');
    document.getElementById('user-info').classList.remove('hidden');
    document.getElementById('quiz-container').classList.add('hidden');
    document.getElementById('document-viewer').classList.add('hidden');
    document.getElementById('teach-interface').classList.add('hidden');
    switchView('dashboard');

    await Promise.all([
        loadProgress(),
        loadCategories(),
        checkSavedQuiz(),
        updateReadinessScores()
    ]);
}

function switchView(view) {
    currentView = view;
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === view);
    });
    
    document.querySelectorAll('.view-section').forEach(section => {
        section.classList.add('hidden');
    });
    
    document.getElementById(view).classList.remove('hidden');
    document.getElementById('quiz-container').classList.add('hidden');
    document.getElementById('document-viewer').classList.add('hidden');
    document.getElementById('teach-interface').classList.add('hidden');

    if (view === 'readiness') {
        updateReadinessScores();
    }
    if (view === 'report-card') {
        loadReportCard();
    }
    if (view === 'mock-exam') {
        showMockView();
    }
}

// ---- Mock Formal Assessment: 20 closed-book MCQs, 30 minutes, 15 to pass ----
function showMockPanel(which) {
    ['mock-intro', 'mock-run', 'mock-result'].forEach(id =>
        document.getElementById(id).classList.toggle('hidden', id !== which));
}

function showMockView() {
    // Coming back mid-exam must not reset it; the timer keeps running regardless.
    if (mockExam) {
        showMockPanel('mock-run');
        return;
    }
    document.getElementById('mock-guest-note').classList.toggle('hidden', !isGuest);
    document.getElementById('mock-start-btn').disabled = isGuest;
    hideError('mock-error');
    if (document.getElementById('mock-result').innerHTML.trim()) return;
    showMockPanel('mock-intro');
}

async function startMockExam() {
    hideError('mock-error');
    showLoading('Building your exam from the standards...');
    try {
        const response = await fetch(`${API_BASE}/api/practice-exam/formal/start`, {
            method: 'POST',
            headers: authHeaders({ 'Content-Type': 'application/json' })
        });
        if (response.status === 401) throw new Error('Please log in or create an account to sit the mock exam.');
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || 'Could not start the exam');
        }
        mockExam = await response.json();
        mockAnswers = {};
        mockIndex = 0;
        document.getElementById('mock-result').innerHTML = '';
        mockEndsAt = Date.now() + mockExam.time_remaining_seconds * 1000;
        clearInterval(mockTimer);
        mockTimer = setInterval(tickMockTimer, 1000);
        showMockPanel('mock-run');
        tickMockTimer();
        renderMockQuestion();
    } catch (e) {
        showError('mock-error', e.message);
    } finally {
        hideLoading();
    }
}

function tickMockTimer() {
    if (!mockExam) return;
    const left = Math.max(0, Math.round((mockEndsAt - Date.now()) / 1000));
    const el = document.getElementById('mock-timer');
    el.textContent = `${String(Math.floor(left / 60)).padStart(2, '0')}:${String(left % 60).padStart(2, '0')}`;
    el.classList.toggle('low', left <= 300);
    if (left === 0) submitMockExam(true);
}

function goMockQuestion(i) {
    if (!mockExam) return;
    mockIndex = Math.min(Math.max(0, i), mockExam.questions.length - 1);
    renderMockQuestion();
}

function renderMockQuestion() {
    const qs = mockExam.questions;
    const q = qs[mockIndex];
    document.getElementById('mock-progress').textContent = `Question ${mockIndex + 1} of ${qs.length}`;
    document.getElementById('mock-question').textContent = q.question;
    document.getElementById('mock-options').innerHTML = (q.options || []).map((o, i) => {
        const letter = String.fromCharCode(65 + i);
        return `<div class="answer-option ${mockAnswers[q.question_id] === letter ? 'selected' : ''}" data-letter="${letter}">${escapeHtml(o)}</div>`;
    }).join('');
    document.querySelectorAll('#mock-options .answer-option').forEach(el => {
        el.addEventListener('click', () => {
            mockAnswers[q.question_id] = el.dataset.letter;
            renderMockQuestion();
        });
    });
    document.getElementById('mock-nav').innerHTML = qs.map((x, i) =>
        `<button class="mock-dot ${mockAnswers[x.question_id] ? 'answered' : ''} ${i === mockIndex ? 'current' : ''}" data-i="${i}">${i + 1}</button>`).join('');
    document.querySelectorAll('#mock-nav .mock-dot').forEach(b =>
        b.addEventListener('click', () => goMockQuestion(parseInt(b.dataset.i, 10))));
    document.getElementById('mock-prev-btn').disabled = mockIndex === 0;
    document.getElementById('mock-next-btn').disabled = mockIndex === qs.length - 1;
}

async function submitMockExam(auto) {
    if (!mockExam) return;
    const unanswered = mockExam.questions.filter(q => !mockAnswers[q.question_id]).length;
    if (!auto && unanswered > 0 &&
        !confirm(`${unanswered} question(s) are unanswered and will be marked wrong. Submit anyway?`)) {
        return;
    }
    const exam = mockExam;
    clearInterval(mockTimer);
    showLoading('Marking your exam...');
    try {
        const response = await fetch(`${API_BASE}/api/practice-exam/submit`, {
            method: 'POST',
            headers: authHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ exam_id: exam.id, answers: mockAnswers })
        });
        if (!response.ok) throw new Error('Could not submit the exam');
        renderMockResult(await response.json(), auto);
        mockExam = null;
    } catch (e) {
        // Keep the exam so the user can retry the submit instead of losing their answers.
        mockTimer = setInterval(tickMockTimer, 1000);
        alert(e.message);
    } finally {
        hideLoading();
    }
}

function renderMockResult(r, auto) {
    const pct = Math.round(r.score);
    const review = r.results.map((q, i) => `
        <li class="${q.is_correct ? 'ok' : 'bad'}">
            <strong>${i + 1}. ${escapeHtml(q.question)}</strong>
            <div>Your answer: ${escapeHtml(q.user_answer || '(none)')} · Correct: ${escapeHtml(q.correct_answer)}</div>
            ${q.explanation ? `<div class="rc-hint">${escapeHtml(q.explanation)}</div>` : ''}
        </li>`).join('');
    const el = document.getElementById('mock-result');
    el.innerHTML = `
        <div class="rc-summary ${r.passed ? '' : 'needs-support'}">
            <div class="rc-grade">${r.passed ? 'PASS' : 'FAIL'}</div>
            <div><h3>${r.correct_answers} / ${r.total_questions} correct (${pct}%)</h3>
            <p>You needed ${r.required_correct} to pass.
            ${r.timed_out ? ' Your submission arrived after the time limit, so it counts as a fail.' : ''}
            ${auto && !r.timed_out ? ' Time ran out, so your answers were submitted automatically.' : ''}
            This attempt now counts toward your Report Card.</p></div>
        </div>
        <div class="mock-actions">
            <button class="btn btn-primary" id="mock-again-btn">Sit another exam</button>
            <button class="btn btn-secondary" id="mock-report-btn">View Report Card</button>
        </div>
        <h3>Review</h3><ol class="mock-review">${review}</ol>`;
    showMockPanel('mock-result');
    document.getElementById('mock-again-btn').addEventListener('click', () => {
        el.innerHTML = '';
        showMockPanel('mock-intro');
    });
    document.getElementById('mock-report-btn').addEventListener('click', () => switchView('report-card'));
}

async function loadReportCard() {
    const body = document.getElementById('report-card-body');
    body.innerHTML = '<p>Loading your report card...</p>';
    if (isGuest) {
        body.innerHTML = `<div class="rc-locked"><h3>Report Card needs an account</h3>
            <p>As a guest your quiz results aren't saved, so there's nothing to report on.
            Create a free account to track your scores and get a personalised study plan after 5 quizzes.</p></div>`;
        return;
    }
    try {
        const response = await fetch(`${API_BASE}/api/report/card`, { headers: authHeaders() });
        if (!response.ok) throw new Error('Could not load report card');
        body.innerHTML = renderReportCard(await response.json());
        body.querySelectorAll('.practice-btn').forEach(btn => {
            btn.addEventListener('click', () => startQuiz(btn.dataset.standard, btn.dataset.title));
        });
    } catch (e) {
        body.innerHTML = `<p class="error-message">${escapeHtml(e.message)}</p>`;
    }
}

function renderMockSummary(r) {
    const m = r.mock_exams;
    if (!m || !m.attempts) {
        return `<div class="rc-focus"><h4>Mock Formal Assessment</h4>
            <p class="rc-hint">You haven't sat a mock exam yet. The real written test is ${escapeHtml(m ? m.pass_rule : '15 of 20 correct in 30 minutes')}.</p></div>`;
    }
    const rows = m.recent.map(a => `<li>${a.correct}/${a.total} (${a.score}%) — ${a.passed ? 'pass' : 'not yet'}</li>`).join('');
    return `<div class="rc-focus"><h4>Mock Formal Assessment <span class="rc-score">${m.attempts} attempt${m.attempts === 1 ? '' : 's'} · best ${Math.round(m.best)}%</span></h4>
        <p class="rc-hint">Pass mark: ${escapeHtml(m.pass_rule)}.</p><ul class="rc-missed">${rows}</ul></div>`;
}

function renderReportCard(r) {
    if (!r.eligible) {
        return `<div class="rc-locked"><h3>Report card unlocks after ${r.min_quizzes} quizzes</h3>
            <p>You've completed ${r.quizzes_completed}. Take ${r.quizzes_needed} more to see where to focus.</p></div>`;
    }
    const trend = r.trend
        ? `<span class="rc-trend ${r.trend.direction}">${r.trend.direction === 'up' ? '▲' : r.trend.direction === 'down' ? '▼' : '■'} ${Math.abs(r.trend.change)} pts vs earlier</span>`
        : '';
    const row = s => `<div class="rc-row ${s.is_weak ? 'weak' : ''}">
        <span class="rc-name">${escapeHtml(s.name)}</span>
        <div class="meter"><div class="meter-fill" style="width:${s.average}%"></div></div>
        <span class="rc-score">${s.average}% · ${s.grade}</span></div>`;

    const focus = r.focus_areas.map(f => `
        <div class="rc-focus">
            <h4>${escapeHtml(f.name)} <span class="rc-score">${f.average}% over ${f.attempts} quiz${f.attempts === 1 ? '' : 'zes'}</span></h4>
            <p class="rc-hint">${escapeHtml(f.hint)}</p>
            ${(f.missed_questions || []).length ? `<ul class="rc-missed">${f.missed_questions.map(m => `
                <li><strong>${escapeHtml(m.question)}</strong>
                    <div>Correct answer: ${escapeHtml(m.correct_answer)}</div>
                    ${m.hint ? `<div class="rc-hint">${escapeHtml(m.hint)}</div>` : ''}</li>`).join('')}</ul>` : ''}
            <button class="btn btn-primary practice-btn" data-standard="${escapeHtml(f.standard_number)}" data-title="${escapeHtml(f.name)}">Practice with a new quiz</button>
        </div>`).join('');

    return `
        <div class="rc-summary ${r.needs_support ? 'needs-support' : ''}">
            <div class="rc-grade">${r.grade}</div>
            <div><h3>${r.overall_average}% overall ${trend}</h3><p>${escapeHtml(r.summary)}</p></div>
        </div>
        ${renderMockSummary(r)}
        <h3>By subject area</h3>${r.categories.map(row).join('')}
        <h3>By standard</h3>${r.standards.map(row).join('')}
        ${focus ? `<h3>Where to focus</h3>${focus}` : ''}`;
}

async function loadProgress() {
    // Source of truth is the server: aggregate the user's saved quiz results.
    try {
        if (isGuest) throw new Error('guest');
        const response = await fetch(`${API_BASE}/api/quiz/history`, { headers: authHeaders() });
        if (response.ok) {
            const history = await response.json();
            const quizzes = history.length;
            const avg = quizzes ? history.reduce((s, r) => s + (r.score || 0), 0) / quizzes : 0;
            const mastered = history.filter(r => (r.score || 0) >= 80).length;
            // 75% = the real written test's pass mark (15 of 20)
            const atPass = history.filter(r => (r.score || 0) >= 75).length;
            userStats = { quizzes, score: avg, mastered, atPass };
        }
    } catch (e) {
        if (!isGuest) console.error('loadProgress error:', e);
    }

    document.getElementById('total-quizzes').textContent = userStats.quizzes;
    document.getElementById('avg-score').textContent = `${Math.round(userStats.score)}%`;
    document.getElementById('sections-mastered').textContent = userStats.mastered;

    document.getElementById('readiness-score').textContent = userStats.atPass;
}

async function loadCategories() {
    const grid = document.getElementById('categories-grid');
    
    try {
        const response = await fetch(`${API_BASE}/api/standards/categories`, {
            method: 'GET',
            headers: { 'Accept': 'application/json' },
            cache: 'no-cache'
        });
        
        if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
        }
        
        const categories = await response.json();
        
        if (!categories || categories.length === 0) {
            grid.innerHTML = `
                <div class="category-card" onclick="updateStandards()">
                    <h3>Get Started</h3>
                    <p>Click here to fetch LVVTA standards and begin training</p>
                </div>
            `;
            return;
        }
        
        grid.innerHTML = categories.map(cat => {
            const escapedCat = cat.replace(/&/g, '&amp;').replace(/"/g, '&quot;');
            return `
            <div class="category-card" data-category="${escapedCat}">
                <h3>${cat.replace(/&/g, '&amp;')}</h3>
                <p>Study ${cat.toLowerCase().replace(/&/g, '&amp;')} standards</p>
            </div>
        `;
        }).join('');
        
        grid.querySelectorAll('.category-card').forEach(card => {
            card.addEventListener('click', () => {
                const category = card.dataset.category.replace(/&amp;/g, '&').replace(/&quot;/g, '"');
                selectCategory(category);
            });
        });
    } catch (e) {
        console.error('loadCategories error:', e);
        grid.innerHTML = `<p>Failed to load categories. ${e.message || 'Please check your connection and try again.'}</p>`;
    }
}

async function updateStandards() {
    showLoading('Fetching LVVTA standards... This may take a minute.');
    
    try {
        const response = await fetch(`${API_BASE}/api/standards/update`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        if (response.ok) {
            await loadCategories();
        }
    } catch (e) {
        alert('Failed to update standards: ' + e.message);
    } finally {
        hideLoading();
    }
}

async function selectCategory(category) {
    showLoading('Loading standards...');
    
    try {
        const response = await fetch(`${API_BASE}/api/standards/by-category/${encodeURIComponent(category)}`, {
            method: 'GET',
            headers: { 'Accept': 'application/json' },
            cache: 'no-cache'
        });
        
        if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
        }
        
        const standards = await response.json();
        
        document.getElementById('selected-category-title').textContent = category;
        
        const list = document.getElementById('standards-list');
        list.innerHTML = standards.map(std => `
            <div class="standard-card">
                <h4>${std.title}</h4>
                <p class="standard-summary">${std.summary || 'LVVTA standard document'}</p>
                <div class="standard-actions">
                    <button class="btn btn-read" onclick="viewDocument('${std.standard_number}', '${std.title.replace(/'/g, "\\'")}')">Read Document</button>
                    <button class="btn btn-secondary" onclick="startTeachBack('${std.standard_number}', '${std.title.replace(/'/g, "\\'")}')">Teach It</button>
                    <button class="btn btn-primary" onclick="startQuiz('${std.standard_number}', '${std.title.replace(/'/g, "\\'")}')">Take Quiz</button>
                </div>
            </div>
        `).join('');
        
        document.querySelector('.category-section').classList.add('hidden');
        document.getElementById('standards-section').classList.remove('hidden');
    } catch (e) {
        alert('Failed to load standards');
    } finally {
        hideLoading();
    }
}

function showCategories() {
    document.querySelector('.category-section').classList.remove('hidden');
    document.getElementById('standards-section').classList.add('hidden');
}

async function viewDocument(standardNumber, title) {
    showLoading('Loading document content...');
    currentStandard = { number: standardNumber, title: title };
    
    try {
        const response = await fetch(`${API_BASE}/api/standards/content/${encodeURIComponent(standardNumber)}`);
        
        let content;
        if (response.ok) {
            const data = await response.json();
            content = data.content || data.chunks?.join('\n\n') || 'Content not available';
        } else {
            content = `<p>Document content for <strong>${title}</strong> is being indexed. You can still take the quiz to test your knowledge.</p>
                       <p><em>Standard Number: ${standardNumber}</em></p>`;
        }
        
        document.getElementById('doc-title').textContent = title;
        document.getElementById('doc-content').innerHTML = formatDocContent(content);
        
        document.querySelectorAll('.view-section').forEach(s => s.classList.add('hidden'));
        document.getElementById('document-viewer').classList.remove('hidden');
    } catch (e) {
        document.getElementById('doc-title').textContent = title;
        document.getElementById('doc-content').innerHTML = `
            <div class="doc-section">
                <p>Unable to load document content. The document may still be processing.</p>
                <p>You can take the quiz to test your knowledge of this standard.</p>
            </div>
        `;
        document.querySelectorAll('.view-section').forEach(s => s.classList.add('hidden'));
        document.getElementById('document-viewer').classList.remove('hidden');
    } finally {
        hideLoading();
    }
}

function formatDocContent(content) {
    if (typeof content !== 'string') content = JSON.stringify(content);
    
    const paragraphs = content.split('\n\n').filter(p => p.trim());
    return paragraphs.map(p => `<div class="doc-section"><p>${p.replace(/\n/g, '<br>')}</p></div>`).join('');
}

function closeDocViewer() {
    document.getElementById('document-viewer').classList.add('hidden');
    switchView('dashboard');
    
    if (document.getElementById('standards-section').innerHTML.trim()) {
        document.querySelector('.category-section').classList.add('hidden');
        document.getElementById('standards-section').classList.remove('hidden');
    }
    document.getElementById('dashboard').classList.remove('hidden');
}

function startQuizFromDoc() {
    if (currentStandard) {
        startQuiz(currentStandard.number, currentStandard.title);
    }
}

function escapeHtml(s) {
    if (s === null || s === undefined) return '';
    return String(s)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

async function startTeachBack(standardNumber, title) {
    showLoading('Loading teach-back questions...');
    currentTeachStandard = { number: standardNumber, title: title };

    try {
        const response = await fetch(`${API_BASE}/api/teach/tree/${encodeURIComponent(standardNumber)}`);
        if (!response.ok) throw new Error(`Server error: ${response.status}`);
        currentTeachTree = await response.json();

        renderTeachAspects(currentTeachTree);

        document.querySelectorAll('.view-section').forEach(s => s.classList.add('hidden'));
        document.getElementById('document-viewer').classList.add('hidden');
        document.getElementById('quiz-container').classList.add('hidden');
        document.getElementById('teach-interface').classList.remove('hidden');
    } catch (e) {
        alert('Failed to load teach-back: ' + e.message);
    } finally {
        hideLoading();
    }
}

function renderTeachAspects(data) {
    document.getElementById('teach-title').textContent = `Teach It: ${data.title || ''}`;
    const container = document.getElementById('teach-aspects');
    const aspects = (data && data.aspects) || [];

    if (!aspects.length) {
        container.innerHTML = '<p>No teach-back questions are available for this standard yet. Try "Read Document" first.</p>';
        return;
    }

    container.innerHTML = aspects.map((a, i) => `
        <div class="teach-aspect" data-index="${i}">
            <h4>${escapeHtml(a.aspect || 'Explain this')}</h4>
            <p class="teach-prompt">${escapeHtml(a.prompt || '')}</p>
            <textarea class="teach-input" data-index="${i}" rows="4" placeholder="Explain in your own words..."></textarea>
            <button class="btn btn-primary teach-submit" data-index="${i}">Check My Explanation</button>
            <div class="teach-eval hidden" data-index="${i}"></div>
        </div>
    `).join('');

    container.querySelectorAll('.teach-submit').forEach(btn => {
        btn.addEventListener('click', () => submitTeachback(parseInt(btn.dataset.index, 10)));
    });
}

async function submitTeachback(index) {
    const aspect = currentTeachTree.aspects[index];
    const textarea = document.querySelector(`.teach-input[data-index="${index}"]`);
    const explanation = (textarea.value || '').trim();
    if (!explanation) {
        alert('Please write your explanation first');
        return;
    }

    const evalDiv = document.querySelector(`.teach-eval[data-index="${index}"]`);
    evalDiv.classList.remove('hidden');
    evalDiv.innerHTML = '<p class="loading">Checking your explanation against the standard...</p>';

    try {
        const response = await fetch(`${API_BASE}/api/teach/evaluate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                standard_number: currentTeachStandard.number,
                topic: aspect.aspect || currentTeachStandard.title,
                explanation: explanation,
                key_points: aspect.key_points || []
            })
        });
        if (!response.ok) throw new Error(`Server error: ${response.status}`);
        renderTeachEvaluation(evalDiv, await response.json());
    } catch (e) {
        evalDiv.innerHTML = `<p class="error-message">Failed to check explanation: ${escapeHtml(e.message)}</p>`;
    }
}

function renderTeachEvaluation(el, r) {
    const score = r.accuracy_score || 0;
    const cls = r.is_accurate ? 'correct' : (score >= 40 ? 'partial' : 'incorrect');
    const list = (arr) => (arr && arr.length)
        ? `<ul>${arr.map(x => `<li>${escapeHtml(String(x))}</li>`).join('')}</ul>`
        : '<p class="muted">None</p>';

    const misconceptions = (r.misconceptions && r.misconceptions.length)
        ? `<div><strong>Misconceptions</strong>${list(r.misconceptions)}</div>` : '';
    const insufficient = r.insufficient_context ? ' · limited source coverage' : '';
    const offline = r.method === 'lexical-fallback' ? ' · offline check' : '';
    const citation = (r.citations && r.citations.length) ? `Source: ${escapeHtml(r.citations.join(', '))}` : '';

    el.innerHTML = `
        <div class="teach-score ${cls}">${score}% accurate${insufficient}</div>
        <p class="teach-feedback">${escapeHtml(r.feedback || '')}</p>
        <div class="teach-cols">
            <div><strong>Covered</strong>${list(r.covered_points)}</div>
            <div><strong>Gaps</strong>${list(r.gaps)}</div>
            ${misconceptions}
        </div>
        <p class="citation">${citation}${offline}</p>
    `;
}

function closeTeachInterface() {
    document.getElementById('teach-interface').classList.add('hidden');
    switchView('dashboard');

    if (document.getElementById('standards-section').innerHTML.trim()) {
        document.querySelector('.category-section').classList.add('hidden');
        document.getElementById('standards-section').classList.remove('hidden');
    }
}

async function startQuiz(standardNumber, title) {
    showLoading('Generating AI quiz questions...');
    
    try {
        const response = await fetch(`${API_BASE}/api/quiz/generate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                standard_number: standardNumber,
                num_questions: 5
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to generate quiz');
        }
        
        const quizData = await response.json();
        
        currentQuiz = {
            standardNumber,
            title,
            questions: quizData.questions,
            totalQuestions: quizData.questions.length
        };
        currentQuestionIndex = 0;
        quizAnswers = [];
        selectedAnswer = null;
        
        saveQuizState();
        showQuizInterface();
    } catch (e) {
        alert('Failed to generate quiz: ' + e.message);
    } finally {
        hideLoading();
    }
}

function showQuizInterface() {
    document.querySelectorAll('.view-section').forEach(s => s.classList.add('hidden'));
    document.getElementById('document-viewer').classList.add('hidden');
    document.getElementById('quiz-container').classList.remove('hidden');
    document.getElementById('quiz-complete').classList.add('hidden');
    document.getElementById('question-card').classList.remove('hidden');
    
    document.getElementById('quiz-title').textContent = currentQuiz.title;
    document.getElementById('quiz-standard').textContent = `Standard: ${currentQuiz.standardNumber}`;
    
    displayQuestion();
}

function displayQuestion() {
    const question = currentQuiz.questions[currentQuestionIndex];
    
    document.getElementById('question-counter').textContent = 
        `Question ${currentQuestionIndex + 1} of ${currentQuiz.totalQuestions}`;
    
    const progress = ((currentQuestionIndex + 1) / currentQuiz.totalQuestions) * 100;
    document.getElementById('progress-fill').style.width = `${progress}%`;
    
    document.getElementById('question-text').textContent = question.question;
    
    const diffBadge = document.getElementById('difficulty-badge');
    const difficulty = question.difficulty || 'medium';
    diffBadge.textContent = difficulty.charAt(0).toUpperCase() + difficulty.slice(1);
    diffBadge.className = `difficulty-badge ${difficulty}`;
    
    const optionsContainer = document.getElementById('answer-options');
    const textSection = document.getElementById('text-answer-section');
    
    if (question.options && question.options.length > 0) {
        textSection.classList.add('hidden');
        optionsContainer.classList.remove('hidden');
        
        const letters = ['A', 'B', 'C', 'D'];
        optionsContainer.innerHTML = question.options.map((opt, i) => `
            <div class="answer-option" data-index="${i}" onclick="selectOption(${i})">
                <span class="option-letter">${letters[i]}</span>
                <span>${opt}</span>
            </div>
        `).join('');
    } else {
        optionsContainer.classList.add('hidden');
        textSection.classList.remove('hidden');
        document.getElementById('text-answer').value = '';
    }
    
    document.getElementById('feedback-section').classList.add('hidden');
    document.getElementById('submit-answer-btn').classList.remove('hidden');
    document.getElementById('next-question-btn').classList.add('hidden');
    selectedAnswer = null;
}

function selectOption(index) {
    document.querySelectorAll('.answer-option').forEach((opt, i) => {
        opt.classList.toggle('selected', i === index);
    });
    selectedAnswer = index;
}

function gradeMCQ(question) {
    // We already know the correct option, so grade locally — no AI call needed.
    // correct_answer may be a letter ("B") or the full option text.
    const ca = String(question.correct_answer || '').trim();
    const letters = ['A', 'B', 'C', 'D', 'E', 'F'];
    let correctIndex = question.options.findIndex(o => o === ca);
    if (correctIndex === -1 && ca.length === 1 && letters.includes(ca.toUpperCase())) {
        correctIndex = letters.indexOf(ca.toUpperCase());
    }
    if (correctIndex === -1 && ca) {
        correctIndex = question.options.findIndex(o => o.toLowerCase().includes(ca.toLowerCase()));
    }
    const isCorrect = selectedAnswer === correctIndex;
    const correctText = correctIndex >= 0 ? question.options[correctIndex] : ca;
    return {
        is_correct: isCorrect,
        score: isCorrect ? 100 : 0,
        explanation: question.explanation || (isCorrect ? 'Correct!' : `The correct answer is: ${correctText}`),
        citation: ''
    };
}

async function submitAnswer() {
    const question = currentQuiz.questions[currentQuestionIndex];
    const isMCQ = question.options && question.options.length > 0;
    let feedback;
    let userAnswer;

    if (isMCQ) {
        if (selectedAnswer === null) {
            alert('Please select an answer');
            return;
        }
        userAnswer = question.options[selectedAnswer];
        feedback = gradeMCQ(question);
    } else {
        userAnswer = document.getElementById('text-answer').value.trim();
        if (!userAnswer) {
            alert('Please enter your answer');
            return;
        }
        // Open-ended answers need real grading — this is the only AI call per quiz.
        showLoading('Evaluating your answer...');
        try {
            const response = await fetch(`${API_BASE}/api/quiz/evaluate-answer`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    question: question.question,
                    user_answer: userAnswer,
                    correct_answer: question.correct_answer,
                    difficulty: question.difficulty || 'medium',
                    standard_number: currentQuiz.standardNumber
                })
            });
            if (response.ok) {
                feedback = await response.json();
            } else {
                const isCorrect = userAnswer.toLowerCase().includes(question.correct_answer.toLowerCase()) ||
                                 question.correct_answer.toLowerCase().includes(userAnswer.toLowerCase());
                feedback = {
                    is_correct: isCorrect,
                    score: isCorrect ? 100 : 0,
                    explanation: isCorrect ? 'Correct!' : `The correct answer is: ${question.correct_answer}`,
                    citation: ''
                };
            }
        } catch (e) {
            alert('Failed to evaluate answer: ' + e.message);
            return;
        } finally {
            hideLoading();
        }
    }

    quizAnswers.push({
        question: question.question,
        userAnswer,
        correctAnswer: question.correct_answer,
        isCorrect: feedback.is_correct,
        score: feedback.score,
        explanation: feedback.explanation
    });

    showFeedback(feedback);
    saveQuizState();
}

function showFeedback(feedback) {
    const feedbackSection = document.getElementById('feedback-section');
    const resultDiv = document.getElementById('feedback-result');
    
    resultDiv.className = `feedback-result ${feedback.is_correct ? 'correct' : 'incorrect'}`;
    resultDiv.textContent = feedback.is_correct ? 'Correct!' : 'Incorrect';
    
    document.getElementById('feedback-explanation').textContent = feedback.explanation || '';
    document.getElementById('feedback-citation').textContent = feedback.citation ? `Source: ${feedback.citation}` : '';
    
    feedbackSection.classList.remove('hidden');
    document.getElementById('submit-answer-btn').classList.add('hidden');
    document.getElementById('next-question-btn').classList.remove('hidden');
    
    if (feedback.is_correct && selectedAnswer !== null) {
        document.querySelectorAll('.answer-option')[selectedAnswer].classList.add('correct');
    } else if (selectedAnswer !== null) {
        document.querySelectorAll('.answer-option')[selectedAnswer].classList.add('incorrect');
    }
}

function nextQuestion() {
    currentQuestionIndex++;
    
    if (currentQuestionIndex >= currentQuiz.totalQuestions) {
        showQuizComplete();
    } else {
        displayQuestion();
        saveQuizState();
    }
}

function showQuizComplete() {
    const totalScore = quizAnswers.reduce((sum, a) => sum + (a.isCorrect ? 1 : 0), 0);
    const percentage = Math.round((totalScore / quizAnswers.length) * 100);
    
    document.getElementById('question-card').classList.add('hidden');
    document.getElementById('quiz-complete').classList.remove('hidden');
    
    document.getElementById('final-score').textContent = `${percentage}%`;
    
    const breakdown = document.getElementById('score-breakdown');
    breakdown.innerHTML = `<p>You got ${totalScore} out of ${quizAnswers.length} questions correct</p>`;
    
    if (isGuest) {
        breakdown.innerHTML += '<p class="guest-note">Guest mode: this result was not saved. Create an account to track your progress and unlock your Report Card.</p>';
    }

    const masteryMsg = document.getElementById('mastery-message');
    if (percentage >= 80) {
        masteryMsg.textContent = 'Excellent! You have demonstrated mastery of this topic.';
        masteryMsg.className = 'mastery-achieved';
    } else {
        masteryMsg.textContent = 'Keep studying! You need 80% or higher to achieve mastery.';
        masteryMsg.className = '';
    }
    
    persistQuizResult(percentage, totalScore);
}

async function persistQuizResult(percentage, correct) {
    // Scenario practice isn't a real standard — don't record it as a quiz result.
    if (!isGuest && currentQuiz.standardNumber && currentQuiz.standardNumber !== 'SCENARIO') {
        try {
            await fetch(`${API_BASE}/api/quiz/submit`, {
                method: 'POST',
                headers: authHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify({
                    standard_number: currentQuiz.standardNumber,
                    score: percentage,
                    total_questions: quizAnswers.length,
                    correct_answers: correct,
                    answers: quizAnswers
                })
            });
        } catch (e) {
            console.error('persistQuizResult error:', e);
        }
        await loadProgress();
    }
    clearSavedQuiz();
}

function quizStatePayload() {
    return {
        quiz: currentQuiz,
        questionIndex: currentQuestionIndex,
        answers: quizAnswers,
        timestamp: Date.now()
    };
}

function saveQuizState() {
    // Scenarios are transient — don't persist them as a resumable quiz.
    if (!currentQuiz || currentQuiz.standardNumber === 'SCENARIO') return;
    const state = quizStatePayload();
    localStorage.setItem('lvv_quiz_state', JSON.stringify(state));
    if (authToken) {
        fetch(`${API_BASE}/api/quiz/state`, {
            method: 'PUT',
            headers: authHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ state })
        }).catch(e => console.error('saveQuizState error:', e));
    }
}

function clearSavedQuiz() {
    localStorage.removeItem('lvv_quiz_state');
    savedState = null;
    document.getElementById('resume-section').classList.add('hidden');
    if (authToken) {
        fetch(`${API_BASE}/api/quiz/state`, { method: 'DELETE', headers: authHeaders() })
            .catch(e => console.error('clearSavedQuiz error:', e));
    }
}

async function checkSavedQuiz() {
    // Prefer the server copy (cross-device); fall back to a recent local copy.
    savedState = null;
    if (authToken) {
        try {
            const response = await fetch(`${API_BASE}/api/quiz/state`, { headers: authHeaders() });
            if (response.ok) {
                const data = await response.json();
                if (data.state && data.state.quiz) savedState = data.state;
            }
        } catch (e) {
            console.error('checkSavedQuiz error:', e);
        }
    }
    if (!savedState) {
        const local = localStorage.getItem('lvv_quiz_state');
        if (local) {
            const state = JSON.parse(local);
            const hoursSince = (Date.now() - (state.timestamp || 0)) / (1000 * 60 * 60);
            if (hoursSince < 24 && state.quiz) savedState = state;
            else localStorage.removeItem('lvv_quiz_state');
        }
    }

    const section = document.getElementById('resume-section');
    if (savedState && savedState.quiz) {
        section.classList.remove('hidden');
        document.getElementById('resume-info').textContent =
            `${savedState.quiz.title} - Question ${savedState.questionIndex + 1} of ${savedState.quiz.totalQuestions}`;
    } else {
        section.classList.add('hidden');
    }
}

function resumeQuiz() {
    if (savedState && savedState.quiz) {
        currentQuiz = savedState.quiz;
        currentQuestionIndex = savedState.questionIndex;
        quizAnswers = savedState.answers || [];
        showQuizInterface();
    }
}

function saveAndExit() {
    saveQuizState();
    backToDashboard();
}

function retryQuiz() {
    currentQuestionIndex = 0;
    quizAnswers = [];
    selectedAnswer = null;
    showQuizInterface();
}

function backToDashboard() {
    document.getElementById('quiz-container').classList.add('hidden');
    switchView('dashboard');
    loadProgress();
    checkSavedQuiz();
}

function selectLearningPath(path) {
    const pathMappings = {
        'general': 'Body & Structure',
        'motorcycles': 'Wheels & Tyres',
        'disability': 'General Compliance',
        'ors': 'Certification Process',
        'thresholds': 'Certification Process',
        'rhd': 'General Compliance'
    };
    
    const category = pathMappings[path] || 'General Compliance';
    switchView('dashboard');
    setTimeout(() => selectCategory(category), 100);
}

async function startScenario(scenarioType) {
    showLoading('Loading scenario...');
    
    const scenarios = {
        'threshold': {
            title: 'Certification Threshold Decision',
            description: 'A customer has installed 17" wheels on their vehicle that originally came with 15" wheels. The wheel offset has changed by 15mm.',
            question: 'Does this modification require LVV certification?',
            options: ['Yes - exceeds threshold', 'No - within threshold', 'Need more information'],
            correct: 0,
            explanation: 'Wheel offset changes greater than 25mm require LVV certification. At 15mm, this is within threshold but close - always verify the specific vehicle requirements.'
        },
        'inspection': {
            title: 'Inspection Decision',
            description: 'You are inspecting a roll cage installation. The main hoop is constructed from 38mm x 2mm CDS tube. All welds appear to have good penetration.',
            question: 'Should you pass or fail this installation?',
            options: ['Pass - meets requirements', 'Fail - tube wall too thin', 'Request welding certification'],
            correct: 1,
            explanation: 'LVV Standard 190-00 requires minimum 38mm x 2.5mm CDS tube for main hoops. At 2mm wall thickness, this does not meet the minimum requirement.'
        },
        'integrity': {
            title: 'Integrity Challenge',
            description: 'A well-known customer and friend asks you to certify their modification. Upon inspection, you find the work is marginally below standard but the customer insists it will be "fine for now".',
            question: 'What do you do?',
            options: ['Certify it - they are a good customer', 'Refuse certification until fixed', 'Certify with conditions'],
            correct: 1,
            explanation: 'LVV Certifiers must maintain the highest integrity. Personal relationships cannot influence certification decisions. The modification must meet all applicable standards before certification.'
        }
    };
    
    const scenario = scenarios[scenarioType];
    
    currentQuiz = {
        standardNumber: 'SCENARIO',
        title: scenario.title,
        questions: [{
            question: `${scenario.description}\n\n${scenario.question}`,
            options: scenario.options,
            correct_answer: scenario.options[scenario.correct],
            difficulty: 'hard',
            explanation: scenario.explanation
        }],
        totalQuestions: 1
    };
    
    currentQuestionIndex = 0;
    quizAnswers = [];
    selectedAnswer = null;
    
    hideLoading();
    showQuizInterface();
}

function showSelfAssessment() {
    document.getElementById('self-assessment-modal').classList.remove('hidden');
    
    const saved = JSON.parse(localStorage.getItem('lvv_self_assessment') || '{}');
    document.querySelectorAll('.assess-slider').forEach(slider => {
        const comp = slider.dataset.competency;
        if (saved[comp]) {
            slider.value = saved[comp];
            slider.nextElementSibling.textContent = `${saved[comp]}/5`;
        }
    });
}

function hideSelfAssessment() {
    document.getElementById('self-assessment-modal').classList.add('hidden');
}

function saveSelfAssessment() {
    const assessment = {};
    document.querySelectorAll('.assess-slider').forEach(slider => {
        assessment[slider.dataset.competency] = parseInt(slider.value);
    });
    localStorage.setItem('lvv_self_assessment', JSON.stringify(assessment));
    hideSelfAssessment();
    updateReadinessScores();
}

// Published criteria, each with its source. Ticks are self-reported and kept in this browser only.
const CRITERIA = [
    { id: 'exp-industry', text: 'Recent and continuous motor industry experience of more than ten years', src: 'LVVTA "Become a certifier" page. (ORS Ch.4 1.5 Note 1 adds that you need not be working in the industry when you apply.)' },
    { id: 'exp-mod', text: 'Practical vehicle modification or construction experience at industry-expert level — for categories LV1A–LV1D: two years’ full-time modification work, or a variety of complex and diverse modifications, or equivalent experience', src: 'ORS Ch.4 sections 2.2–2.5' },
    { id: 'exp-built', text: 'You have built or modified vehicles yourself', src: 'LVVTA "Become a certifier" page; ORS Ch.4 1.2' },
    { id: 'safety', text: 'Committed to road safety and safety-focused in every decision', src: 'ORS Ch.5 3.3(1)(a)' },
    { id: 'ethics', text: 'Always honest and ethical', src: 'ORS Ch.5 3.3(1)(b); Ch.7 1.2(1)(a)' },
    { id: 'independence', text: 'Able to stay independent: never certifying a vehicle that you, your staff or your business modified, or that you or your family own', src: 'ORS Ch.7 sections 2.2–2.3' },
    { id: 'service', text: 'Professional, efficient and courteous service to customers', src: 'ORS Ch.5 3.3(1)(c)' },
    { id: 'comms', text: 'Fluent English with good written and spoken communication', src: 'ORS Ch.5 3.3(1)(d)–(e)' },
    { id: 'organised', text: 'Methodical and well organised', src: 'ORS Ch.5 3.3(1)(f)' },
    { id: 'licence', text: 'A current NZ driver licence for the vehicle classes you would drive during inspections', src: 'ORS Ch.5 3.3(1)(g)' },
    { id: 'fitproper', text: 'Able to pass a "fit and proper person" test (criminal record and driving history)', src: 'LVVTA "Become a certifier" page' },
    { id: 'qms', text: 'Willing to establish a quality management system (this may be the NZTA Performance Review System)', src: 'ORS Ch.5 3.4(1)(a)' },
    { id: 'insurance', text: 'Willing to hold public liability and professional indemnity insurance for LVV certification', src: 'ORS Ch.5 3.4(1)(b)' },
    { id: 'geography', text: 'Aware that geographical coverage is considered — areas already well served may not take new certifiers', src: 'LVVTA "Become a certifier" page' },
];

function loadCriteriaTicks() {
    try { return JSON.parse(localStorage.getItem('lvv_criteria') || '{}'); } catch (e) { return {}; }
}

function renderCriteria() {
    const ticks = loadCriteriaTicks();
    const list = document.getElementById('criteria-list');
    list.innerHTML = CRITERIA.map(c => `
        <li><label><input type="checkbox" data-id="${c.id}" ${ticks[c.id] ? 'checked' : ''}> ${escapeHtml(c.text)}</label>
        <div class="rc-hint">${escapeHtml(c.src)}</div></li>`).join('');
    list.querySelectorAll('input[type=checkbox]').forEach(box => box.addEventListener('change', () => {
        const t = loadCriteriaTicks();
        t[box.dataset.id] = box.checked;
        try { localStorage.setItem('lvv_criteria', JSON.stringify(t)); } catch (e) { /* storage unavailable */ }
        document.getElementById('criteria-count').textContent = criteriaCountText();
    }));
    document.getElementById('criteria-count').textContent = criteriaCountText();
}

function criteriaCountText() {
    const t = loadCriteriaTicks();
    return `${CRITERIA.filter(c => t[c.id]).length} of ${CRITERIA.length} ticked`;
}

async function updateReadinessScores() {
    renderCriteria();
    const el = document.getElementById('readiness-practice');
    const assessment = JSON.parse(localStorage.getItem('lvv_self_assessment') || '{}');
    const names = { integrity: 'Integrity', technical: 'Technically skilled', experience: 'Vastly experienced',
                    conscientious: 'Conscientious', independent: 'Independent', reliable: 'Reliable', people: 'People skills' };
    document.getElementById('self-ratings').textContent = Object.keys(assessment).length
        ? 'Your ratings: ' + Object.entries(assessment).map(([k, v]) => `${names[k] || k} ${v}/5`).join(' · ')
        : '';

    if (isGuest || !authToken) {
        el.innerHTML = '<h4>Your practice so far</h4><p class="rc-hint">Create an account to see your quiz and mock exam results here.</p>';
        return;
    }
    let mockLine = 'No mock exams sat yet.';
    try {
        const r = await fetch(`${API_BASE}/api/practice-exam/history/all`, { headers: authHeaders() });
        if (r.ok) {
            const done = (await r.json()).filter(e => e.status === 'completed' && e.score !== null);
            if (done.length) {
                const best = Math.max(...done.map(e => e.score));
                mockLine = `${done.length} mock exam${done.length === 1 ? '' : 's'} sat · best ${Math.round(best)}% (pass mark 75%).`;
            }
        }
    } catch (e) { /* leave default */ }
    const q = userStats;
    el.innerHTML = `<h4>Your practice so far</h4>
        <p>${q.quizzes} quiz${q.quizzes === 1 ? '' : 'zes'} taken · average ${Math.round(q.score)}% · ${q.atPass} at or above the 75% written-test pass mark.</p>
        <p>${escapeHtml(mockLine)}</p>
        <p class="rc-hint">These are practice results on generated questions. They show where you stand against the published syllabus — they don't predict the outcome of a real assessment.</p>`;
}

function showLoading(message = 'Loading...') {
    document.getElementById('loading-message').textContent = message;
    document.getElementById('loading-overlay').classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loading-overlay').classList.add('hidden');
}
