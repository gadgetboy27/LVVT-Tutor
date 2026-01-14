const API_BASE = '';
let authToken = localStorage.getItem('lvv_token');
let currentUser = null;
let currentQuiz = null;
let currentQuestionIndex = 0;
let selectedAnswer = null;
let quizAnswers = [];
let savedQuizState = null;

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
    document.getElementById('dashboard').classList.remove('hidden');
    
    await Promise.all([
        loadProgress(),
        loadCategories(),
        checkSavedQuiz()
    ]);
}

async function loadProgress() {
    const savedProgress = JSON.parse(localStorage.getItem('lvv_progress') || '{"quizzes":0,"score":0,"mastered":0}');
    document.getElementById('total-quizzes').textContent = savedProgress.quizzes || 0;
    document.getElementById('avg-score').textContent = `${Math.round(savedProgress.score || 0)}%`;
    document.getElementById('sections-mastered').textContent = savedProgress.mastered || 0;
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
            <div class="standard-item">
                <div class="standard-info">
                    <h4>${std.standard_number}</h4>
                    <p>${std.title}</p>
                </div>
                <div class="mastery-indicator">
                    <span class="mastery-badge not-started">Start</span>
                    <button class="btn btn-primary" onclick="startQuiz('${std.standard_number}', '${std.title.replace(/'/g, "\\'")}')">Quiz</button>
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

async function startQuiz(standardNumber, title) {
    showLoading('Generating AI quiz questions...');
    
    try {
        const response = await fetch(`${API_BASE}/api/quiz/generate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
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
    document.getElementById('dashboard').classList.add('hidden');
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
            headers: {
                'Content-Type': 'application/json'
            },
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
            difficulty: question.difficulty
        });
        
        showFeedback(feedback, question);
        saveQuizState();
    } catch (e) {
        console.error('Error evaluating answer:', e);
        const isCorrect = selectedAnswer !== null && 
            question.options[selectedAnswer] === question.correct_answer;
        
        quizAnswers.push({
            question: question.question,
            userAnswer,
            correctAnswer: question.correct_answer,
            isCorrect,
            score: isCorrect ? 100 : 0,
            difficulty: question.difficulty
        });
        
        showFeedback({
            is_correct: isCorrect,
            score: isCorrect ? 100 : 0,
            explanation: isCorrect ? 'Correct!' : `The correct answer is: ${question.correct_answer}`
        }, question);
    } finally {
        hideLoading();
    }
}

function showFeedback(feedback, question) {
    const feedbackSection = document.getElementById('feedback-section');
    const feedbackResult = document.getElementById('feedback-result');
    const feedbackExplanation = document.getElementById('feedback-explanation');
    const feedbackCitation = document.getElementById('feedback-citation');
    
    if (feedback.is_correct) {
        feedbackResult.textContent = `Correct! Score: ${feedback.score}/100`;
        feedbackResult.className = 'feedback-result correct';
    } else if (feedback.score > 0) {
        feedbackResult.textContent = `Partially Correct! Score: ${feedback.score}/100`;
        feedbackResult.className = 'feedback-result partial';
    } else {
        feedbackResult.textContent = `Incorrect. Score: ${feedback.score}/100`;
        feedbackResult.className = 'feedback-result incorrect';
    }
    
    feedbackExplanation.textContent = feedback.explanation || '';
    feedbackCitation.textContent = feedback.citation || '';
    
    if (question.options && question.options.length > 0) {
        document.querySelectorAll('.answer-option').forEach((opt, i) => {
            if (question.options[i] === question.correct_answer) {
                opt.classList.add('correct');
            } else if (i === selectedAnswer && !feedback.is_correct) {
                opt.classList.add('incorrect');
            }
        });
    }
    
    feedbackSection.classList.remove('hidden');
    document.getElementById('submit-answer-btn').classList.add('hidden');
    document.getElementById('next-question-btn').classList.remove('hidden');
    
    if (currentQuestionIndex >= currentQuiz.totalQuestions - 1) {
        document.getElementById('next-question-btn').textContent = 'See Results';
    } else {
        document.getElementById('next-question-btn').textContent = 'Next Question';
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

async function showQuizComplete() {
    const totalScore = quizAnswers.reduce((sum, a) => sum + a.score, 0);
    const avgScore = Math.round(totalScore / quizAnswers.length);
    const correctCount = quizAnswers.filter(a => a.is_correct || a.score >= 80).length;
    
    document.getElementById('question-card').classList.add('hidden');
    document.getElementById('quiz-complete').classList.remove('hidden');
    
    document.getElementById('final-score').textContent = `${avgScore}%`;
    
    const breakdown = document.getElementById('score-breakdown');
    breakdown.innerHTML = `
        <p><span>Questions Answered:</span><span>${quizAnswers.length}</span></p>
        <p><span>Correct/Mostly Correct:</span><span>${correctCount}</span></p>
        <p><span>Average Score:</span><span>${avgScore}%</span></p>
    `;
    
    const masteryMsg = document.getElementById('mastery-message');
    if (avgScore >= 80) {
        masteryMsg.textContent = 'Excellent! You have mastered this section!';
        masteryMsg.className = 'success';
    } else {
        masteryMsg.textContent = 'Keep practicing! You need 80% or higher to master this section.';
        masteryMsg.className = 'encourage';
    }
    
    localStorage.removeItem('lvv_quiz_state');
    
    const progress = JSON.parse(localStorage.getItem('lvv_progress') || '{"quizzes":0,"score":0,"mastered":0,"scores":[]}');
    progress.quizzes = (progress.quizzes || 0) + 1;
    progress.scores = progress.scores || [];
    progress.scores.push(avgScore);
    progress.score = Math.round(progress.scores.reduce((a,b) => a+b, 0) / progress.scores.length);
    if (avgScore >= 80) progress.mastered = (progress.mastered || 0) + 1;
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

function checkSavedQuiz() {
    const saved = localStorage.getItem('lvv_quiz_state');
    if (saved) {
        try {
            savedQuizState = JSON.parse(saved);
            const hoursSince = (Date.now() - savedQuizState.timestamp) / (1000 * 60 * 60);
            
            if (hoursSince < 24 && savedQuizState.quiz) {
                document.getElementById('resume-section').classList.remove('hidden');
                document.getElementById('resume-info').textContent = 
                    `${savedQuizState.quiz.title} - Question ${savedQuizState.questionIndex + 1} of ${savedQuizState.quiz.totalQuestions}`;
            } else {
                localStorage.removeItem('lvv_quiz_state');
            }
        } catch (e) {
            localStorage.removeItem('lvv_quiz_state');
        }
    }
}

function resumeQuiz() {
    if (savedQuizState) {
        currentQuiz = savedQuizState.quiz;
        currentQuestionIndex = savedQuizState.questionIndex;
        quizAnswers = savedQuizState.answers || [];
        showQuizInterface();
    }
}

function saveAndExit() {
    saveQuizState();
    alert('Your progress has been saved. You can resume this quiz when you return.');
    backToDashboard();
}

function retryQuiz() {
    startQuiz(currentQuiz.standardNumber, currentQuiz.title);
}

function backToDashboard() {
    currentQuiz = null;
    currentQuestionIndex = 0;
    quizAnswers = [];
    showMainContent();
}

function showLoading(message) {
    document.getElementById('loading-message').textContent = message || 'Loading...';
    document.getElementById('loading-overlay').classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loading-overlay').classList.add('hidden');
}
