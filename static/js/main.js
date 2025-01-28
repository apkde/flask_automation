function showSplashScreen() {
    const splash = document.getElementById('splash-screen');
    splash.style.display = 'flex';  // Make sure splash is visible
    
    setTimeout(() => {
        splash.classList.add('opacity-0');
        setTimeout(() => {
            splash.style.display = 'none';
            showWelcomeModal();
        }, 500);
    }, 2000);
}

function showWelcomeModal() {
    const modal = document.getElementById('welcome-modal');
    modal.classList.remove('hidden');
    modal.style.display = 'block';  // Make sure modal is visible
    
    const langBtns = document.querySelectorAll('.lang-select-btn');
    let selectedLang = 'il';
    
    // Update button styles when selected
    langBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            langBtns.forEach(b => {
                b.classList.remove('border-blue-500');
                b.classList.add('opacity-50');
            });
            btn.classList.add('border-blue-500');
            btn.classList.remove('opacity-50');
            selectedLang = btn.dataset.lang;
        });
    });
    
    // Select IL by default
    const ilBtn = document.querySelector('[data-lang="il"]');
    if (ilBtn) {
        ilBtn.classList.add('border-blue-500');
        ilBtn.classList.remove('opacity-50');
    }
    
    document.getElementById('start-btn').addEventListener('click', () => {
        modal.style.display = 'none';
        localStorage.setItem('preferredLang', selectedLang);
        initializeApp(selectedLang);
        
        // Update the button text based on selection
        const translateBtn = document.getElementById('translate-btn');
        translateBtn.innerHTML = `<div class="flex items-center justify-center">
            <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>
            </svg>
            Generate ${selectedLang.toUpperCase()} Code
        </div>`;
    });
}

function initializeApp(selectedLang) {
    // Get all required elements
    const inputText = document.getElementById('input-text');
    const translateBtn = document.getElementById('translate-btn');
    const exportBtn = document.getElementById('export-btn');
    const result = document.getElementById('result');
    const formatBtns = document.querySelectorAll('.format-btn');
    
    // Only proceed if required elements exist
    if (!inputText || !translateBtn || !result) {
        console.warn('Required elements not found');
        return;
    }

    // Store the selected language
    let currentFormat = selectedLang;

    if (formatBtns.length) {
        formatBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                formatBtns.forEach(b => b.classList.remove('selected'));
                btn.classList.add('selected');
                currentFormat = btn.dataset.format;
            });
        });
    }

    translateBtn.addEventListener('click', async () => {
        if (!inputText.value.trim()) {
            alert('Please enter some text');
            return;
        }

        translateBtn.classList.add('loading');
        translateBtn.disabled = true;

        try {
            const response = await fetch('/translate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    text: inputText.value,
                    format_type: currentFormat
                })
            });

            const data = await response.json();
            
            if (data.success) {
                result.textContent = data.result;
                updateLineNumbers();
                if (exportBtn) exportBtn.style.display = 'block';
            } else {
                result.textContent = 'Error: ' + data.error;
            }
        } catch (error) {
            result.textContent = 'Error: ' + error.message;
        } finally {
            translateBtn.classList.remove('loading');
            translateBtn.disabled = false;
        }
    });

    if (exportBtn) {
        exportBtn.addEventListener('click', async () => {
            exportBtn.classList.add('loading');
            exportBtn.disabled = true;

            try {
                const response = await fetch('/export', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        code: result.textContent,
                        plc_type: 'somachine'
                    })
                });

                const data = await response.json();
                
                if (data.success) {
                    const downloadUrl = `/download/${encodeURIComponent(data.file_path)}`;
                    const link = document.createElement('a');
                    link.href = downloadUrl;
                    link.download = data.filename;
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                } else {
                    alert('Export failed: ' + data.error);
                }
            } catch (error) {
                alert('Export failed: ' + error.message);
            } finally {
                exportBtn.classList.remove('loading');
                exportBtn.disabled = false;
            }
        });
    }
}

function updateLineNumbers() {
    const result = document.getElementById('result');
    const lineNumbers = document.getElementById('line-numbers');
    const lines = result.textContent.split('\n');
    
    lineNumbers.innerHTML = lines.map((_, i) => 
        `<div>${i + 1}</div>`
    ).join('');
}

// Voice Command Support
function initVoiceCommands() {
    const voiceBtn = document.getElementById('voice-btn');
    const voiceInterface = document.getElementById('voice-interface');
    const voiceClose = document.getElementById('voice-close');
    const voiceStatus = document.getElementById('voice-status');
    const voiceTranscript = document.getElementById('voice-transcript');
    const voiceWave = document.getElementById('voice-wave');
    
    let recognition;
    
    if ('webkitSpeechRecognition' in window) {
        recognition = new webkitSpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = true;
        
        recognition.onstart = () => {
            voiceStatus.textContent = 'Listening...';
            voiceWave.classList.add('animate-pulse');
        };
        
        recognition.onresult = (event) => {
            const transcript = Array.from(event.results)
                .map(result => result[0].transcript)
                .join('');
            
            voiceTranscript.textContent = transcript;
            
            if (event.results[0].isFinal) {
                handleVoiceCommand(transcript.toLowerCase());
            }
        };
        
        recognition.onend = () => {
            voiceStatus.textContent = 'Tap to speak';
            voiceWave.classList.remove('animate-pulse');
        };
        
        recognition.onerror = (event) => {
            voiceStatus.textContent = 'Error: ' + event.error;
            setTimeout(() => {
                voiceInterface.classList.add('hidden');
            }, 2000);
        };
    }
    
    function handleVoiceCommand(command) {
        // Show processing state
        voiceStatus.textContent = 'Processing...';
        
        fetch('/voice_command', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ command: command })
        })
        .then(response => response.json())
        .then(data => {
            // Show AI response
            voiceStatus.textContent = data.response;
            
            // Handle different actions
            switch(data.action) {
                case 'generate':
                    if (data.input_text) {
                        document.getElementById('input-text').value = data.input_text;
                    }
                    document.getElementById('translate-btn').click();
                    break;
                    
                case 'export':
                    document.getElementById('export-btn').click();
                    break;
                    
                case 'clear':
                    document.getElementById('input-text').value = '';
                    document.getElementById('result').textContent = '';
                    break;
                    
                default:
                    // Just show the response for other commands
                    break;
            }
            
            // Close interface after showing response
            setTimeout(() => {
                voiceInterface.classList.add('hidden');
            }, 2000);
        })
        .catch(error => {
            voiceStatus.textContent = 'Sorry, something went wrong';
            setTimeout(() => {
                voiceInterface.classList.add('hidden');
            }, 2000);
        });
    }
    
    voiceBtn.addEventListener('click', () => {
        voiceInterface.classList.remove('hidden');
        if (recognition) {
            recognition.start();
        }
    });
    
    voiceClose.addEventListener('click', () => {
        voiceInterface.classList.add('hidden');
        if (recognition) {
            recognition.stop();
        }
    });
}

document.addEventListener('DOMContentLoaded', function() {
    const splash = document.getElementById('splash-screen');
    const welcomeModal = document.getElementById('welcome-modal');
    const startBtn = document.getElementById('start-btn');
    
    // Initialize voice commands
    initVoiceCommands();
    
    if (splash && welcomeModal) {
        showSplashScreen();
    } else {
        // If no splash/welcome, initialize directly
        initializeApp('il');
    }

    // Add copy button functionality if it exists
    const copyBtn = document.getElementById('copy-btn');
    if (copyBtn) {
        copyBtn.addEventListener('click', () => {
            const result = document.getElementById('result');
            if (result) {
                const text = result.textContent;
                navigator.clipboard.writeText(text).then(() => {
                    copyBtn.classList.add('copy-success');
                    setTimeout(() => copyBtn.classList.remove('copy-success'), 1000);
                });
            }
        });
    }
}); 