const API_BASE = '';
let authToken = localStorage.getItem('lvv_token');
let currentUser = null;
let currentQuiz = null;
let currentQuestionIndex = 0;
let selectedAnswer = null;
let quizAnswers = [];
let currentStandard = null;
let currentView = 'dashboard';

document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
});

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
    const email = document.getElementById('login-email').value || 'demo@lvvlearn.nz';
    showLoading('Logging in...');
    currentUser = { email: email, id: 1 };
    authToken = 'mock-token';
    localStorage.setItem('lvv_token', authToken);
    localStorage.setItem('lvv_user', JSON.stringify(currentUser));
    document.getElementById('username-display').textContent = email;
    hideLoading();
    showMainContent();
}

async function handleRegister(e) {
    e.preventDefault();
    const email = document.getElementById('register-email').value || 'demo@lvvlearn.nz';
    showLoading('Creating account...');
    currentUser = { email: email, id: 1 };
    authToken = 'mock-token';
    localStorage.setItem('lvv_token', authToken);
    localStorage.setItem('lvv_user', JSON.stringify(currentUser));
    document.getElementById('username-display').textContent = email;
    hideLoading();
    showMainContent();
}

function handleLogout() {
    localStorage.removeItem('lvv_token');
    localStorage.removeItem('lvv_quiz_state');
    localStorage.removeItem('lvv_user');
    authToken = null;
    currentUser = null;
    showAuthSection();
}

async function loadCurrentUser() {
    const savedUser = localStorage.getItem('lvv_user');
    if (savedUser) {
        currentUser = JSON.parse(savedUser);
        document.getElementById('username-display').textContent = currentUser.email;
    } else {
        currentUser = { email: 'demo@lvvlearn.nz', id: 1 };
        document.getElementById('username-display').textContent = currentUser.email;
    }
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
    
    if (view === 'readiness') {
        updateReadinessScores();
    }
}

async function loadProgress() {
    const savedProgress = JSON.parse(localStorage.getItem('lvv_progress') || '{"quizzes":0,"score":0,"mastered":0}');
    document.getElementById('total-quizzes').textContent = savedProgress.quizzes || 0;
    document.getElementById('avg-score').textContent = `${Math.round(savedProgress.score || 0)}%`;
    document.getElementById('sections-mastered').textContent = savedProgress.mastered || 0;
    
    const readiness = calculateReadiness();
    document.getElementById('readiness-score').textContent = `${readiness}%`;
}

function calculateReadiness() {
    const progress = JSON.parse(localStorage.getItem('lvv_progress') || '{}');
    const assessment = JSON.parse(localStorage.getItem('lvv_self_assessment') || '{}');
    
    let score = 0;
    if (progress.quizzes > 0) score += Math.min(20, progress.quizzes * 2);
    if (progress.score > 0) score += (progress.score / 100) * 30;
    if (progress.mastered > 0) score += Math.min(20, progress.mastered * 4);
    if (Object.keys(assessment).length > 0) {
        const avgSelfScore = Object.values(assessment).reduce((a, b) => a + b, 0) / 7;
        score += (avgSelfScore / 5) * 30;
    }
    
    return Math.min(100, Math.round(score));
}

async function loadCategories() {
    const grid = document.getElementById('categories-grid');
    
    try {
        const response = await fetch(`${API_BASE}/api/standards/categories`);
        const categories = await response.json();
        
        if (categories.length === 0) {
            grid.innerHTML = `
                <div class="category-card" onclick="updateStandards()">
                    <h3>Get Started</h3>
                    <p>Click here to fetch LVVTA standards and begin training</p>
                </div>
            `;
            return;
        }
        
        grid.innerHTML = categories.map(cat => `
            <div class="category-card" onclick="selectCategory('${cat}')">
                <h3>${cat}</h3>
                <p>Study ${cat.toLowerCase()} standards</p>
            </div>
        `).join('');
    } catch (e) {
        grid.innerHTML = '<p>Failed to load categories. Please try again.</p>';
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
        const response = await fetch(`${API_BASE}/api/standards/by-category/${encodeURIComponent(category)}`);
        const standards = await response.json();
        
        document.getElementById('selected-category-title').textContent = category;
        
        const list = document.getElementById('standards-list');
        list.innerHTML = standards.map(std => `
            <div class="standard-card">
                <h4>${std.title}</h4>
                <p class="standard-summary">${std.summary || 'LVVTA standard document'}</p>
                <div class="standard-actions">
                    <button class="btn btn-read" onclick="viewDocument('${std.standard_number}', '${std.title.replace(/'/g, "\\'")}')">Read Document</button>
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

async function submitAnswer() {
    const question = currentQuiz.questions[currentQuestionIndex];
    let userAnswer;
    
    if (question.options && question.options.length > 0) {
        if (selectedAnswer === null) {
            alert('Please select an answer');
            return;
        }
        userAnswer = question.options[selectedAnswer];
    } else {
        userAnswer = document.getElementById('text-answer').value.trim();
        if (!userAnswer) {
            alert('Please enter your answer');
            return;
        }
    }
    
    showLoading('AI is evaluating your answer...');
    
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
        
        let feedback;
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
    } catch (e) {
        alert('Failed to evaluate answer: ' + e.message);
    } finally {
        hideLoading();
    }
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
    
    const masteryMsg = document.getElementById('mastery-message');
    if (percentage >= 80) {
        masteryMsg.textContent = 'Excellent! You have demonstrated mastery of this topic.';
        masteryMsg.className = 'mastery-achieved';
    } else {
        masteryMsg.textContent = 'Keep studying! You need 80% or higher to achieve mastery.';
        masteryMsg.className = '';
    }
    
    updateProgress(percentage);
    localStorage.removeItem('lvv_quiz_state');
}

function updateProgress(score) {
    const progress = JSON.parse(localStorage.getItem('lvv_progress') || '{"quizzes":0,"score":0,"mastered":0,"totalScore":0}');
    progress.quizzes = (progress.quizzes || 0) + 1;
    progress.totalScore = (progress.totalScore || 0) + score;
    progress.score = progress.totalScore / progress.quizzes;
    if (score >= 80) {
        progress.mastered = (progress.mastered || 0) + 1;
    }
    localStorage.setItem('lvv_progress', JSON.stringify(progress));
}

function saveQuizState() {
    const state = {
        quiz: currentQuiz,
        questionIndex: currentQuestionIndex,
        answers: quizAnswers,
        timestamp: Date.now()
    };
    localStorage.setItem('lvv_quiz_state', JSON.stringify(state));
}

async function checkSavedQuiz() {
    const saved = localStorage.getItem('lvv_quiz_state');
    if (saved) {
        const state = JSON.parse(saved);
        const hoursSincesSaved = (Date.now() - state.timestamp) / (1000 * 60 * 60);
        
        if (hoursSincesSaved < 24 && state.quiz) {
            document.getElementById('resume-section').classList.remove('hidden');
            document.getElementById('resume-info').textContent = 
                `${state.quiz.title} - Question ${state.questionIndex + 1} of ${state.quiz.totalQuestions}`;
        } else {
            localStorage.removeItem('lvv_quiz_state');
        }
    }
}

function resumeQuiz() {
    const saved = localStorage.getItem('lvv_quiz_state');
    if (saved) {
        const state = JSON.parse(saved);
        currentQuiz = state.quiz;
        currentQuestionIndex = state.questionIndex;
        quizAnswers = state.answers || [];
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

function updateReadinessScores() {
    const progress = JSON.parse(localStorage.getItem('lvv_progress') || '{}');
    const assessment = JSON.parse(localStorage.getItem('lvv_self_assessment') || '{}');
    
    const techScore = Math.min(100, (progress.quizzes || 0) * 10);
    document.getElementById('tech-skills-meter').style.width = `${techScore}%`;
    document.getElementById('tech-skills-meter').parentElement.nextElementSibling.textContent = `${techScore}%`;
    
    const standardsScore = Math.min(100, (progress.mastered || 0) * 20);
    document.getElementById('standards-meter').style.width = `${standardsScore}%`;
    document.getElementById('standards-meter').parentElement.nextElementSibling.textContent = `${standardsScore}%`;
    
    const orsScore = Math.min(100, (progress.score || 0));
    document.getElementById('ors-meter').style.width = `${orsScore}%`;
    document.getElementById('ors-meter').parentElement.nextElementSibling.textContent = `${Math.round(orsScore)}%`;
    
    document.getElementById('threshold-meter').style.width = `${techScore}%`;
    document.getElementById('threshold-meter').parentElement.nextElementSibling.textContent = `${techScore}%`;
    
    document.getElementById('scenario-meter').style.width = `${standardsScore}%`;
    document.getElementById('scenario-meter').parentElement.nextElementSibling.textContent = `${standardsScore}%`;
    
    const overall = calculateReadiness();
    document.getElementById('overall-readiness-score').textContent = `${overall}%`;
    
    let message = 'Complete more training to build your certification readiness';
    if (overall >= 80) message = 'You are well prepared! Consider applying to become an LVV Certifier.';
    else if (overall >= 60) message = 'Good progress! Continue studying to reach certification readiness.';
    else if (overall >= 40) message = 'You are making progress. Focus on areas that need improvement.';
    document.getElementById('readiness-message').textContent = message;
}

function showLoading(message = 'Loading...') {
    document.getElementById('loading-message').textContent = message;
    document.getElementById('loading-overlay').classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loading-overlay').classList.add('hidden');
}
