/**
 * PRIVACY68 // Autonomous Voice Intelligence - Interactive Controller
 * Web Audio API retro sound synthesis, simulated audio HUD, terminal router demo, and telemetry.
 */

// Global State
const state = {
    sfxEnabled: true,
    crtEnabled: true
};

// Web Audio API Sound Synthesizer
let audioCtx = null;

function initAudio() {
    if (!audioCtx) {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (AudioContext) {
            audioCtx = new AudioContext();
        }
    }
    if (audioCtx && audioCtx.state === 'suspended') {
        audioCtx.resume();
    }
}

function playRetroSFX(type = 'click') {
    if (!state.sfxEnabled) return;
    try {
        initAudio();
        if (!audioCtx) return;

        const now = audioCtx.currentTime;
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();

        osc.connect(gain);
        gain.connect(audioCtx.destination);

        if (type === 'click') {
            osc.type = 'square';
            osc.frequency.setValueAtTime(800, now);
            osc.frequency.exponentialRampToValueAtTime(180, now + 0.04);
            gain.gain.setValueAtTime(0.06, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.04);
            osc.start(now);
            osc.stop(now + 0.04);
        } else if (type === 'beep') {
            osc.type = 'triangle';
            osc.frequency.setValueAtTime(540, now);
            osc.frequency.exponentialRampToValueAtTime(880, now + 0.08);
            gain.gain.setValueAtTime(0.08, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.08);
            osc.start(now);
            osc.stop(now + 0.08);
        } else if (type === 'success') {
            osc.type = 'sine';
            osc.frequency.setValueAtTime(440, now);
            osc.frequency.setValueAtTime(880, now + 0.06);
            gain.gain.setValueAtTime(0.1, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.16);
            osc.start(now);
            osc.stop(now + 0.16);
        }
    } catch (e) {
        // Ignore audio errors if blocked
    }
}

// Background Dot Matrix Canvas
function initMatrixCanvas() {
    const canvas = document.getElementById('matrix-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    let width = canvas.width = window.innerWidth;
    let height = canvas.height = window.innerHeight;

    window.addEventListener('resize', () => {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
    });

    const dots = [];
    const spacing = 36;

    for (let x = 0; x < width; x += spacing) {
        for (let y = 0; y < height; y += spacing) {
            dots.push({
                x,
                y,
                baseAlpha: Math.random() * 0.18 + 0.03,
                phase: Math.random() * Math.PI * 2
            });
        }
    }

    let time = 0;
    function render() {
        ctx.clearRect(0, 0, width, height);
        time += 0.02;

        ctx.fillStyle = '#ef4444';
        for (let i = 0; i < dots.length; i++) {
            const dot = dots[i];
            const pulse = Math.sin(time + dot.phase);
            const alpha = dot.baseAlpha + (pulse > 0.8 ? 0.25 : 0);
            ctx.globalAlpha = Math.max(0.02, Math.min(0.4, alpha));
            ctx.fillRect(dot.x, dot.y, 1.5, 1.5);
        }

        requestAnimationFrame(render);
    }
    render();
}

// Interactive Terminal Simulator
function initTerminalSimulator() {
    const chips = document.querySelectorAll('.cmd-chip');
    const termInput = document.getElementById('term-input');
    const termLane = document.getElementById('term-lane');
    const termAction = document.getElementById('term-action');

    chips.forEach(chip => {
        chip.addEventListener('click', () => {
            chips.forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            playRetroSFX('beep');

            const cmd = chip.getAttribute('data-cmd');
            if (termInput) termInput.textContent = `> [DEMO INPUT] "${cmd}"`;
            if (termLane) termLane.textContent = '> [CURRENT FLOW] Request forwarded to Agent Brain (website simulation only)';
            if (termAction) termAction.textContent = '> [DEMO ONLY] No model request was sent and no command was executed';

        });
    });
}

// Copy Code Helper
window.copyCode = function (button, text) {
    playRetroSFX('click');
    navigator.clipboard.writeText(text).then(() => {
        const orig = button.innerText;
        button.innerText = 'COPIED!';
        button.style.backgroundColor = '#10b981';
        button.style.borderColor = '#10b981';
        setTimeout(() => {
            button.innerText = orig;
            button.style.backgroundColor = '';
            button.style.borderColor = '';
        }, 1800);
    });
};

// UI Toggles & Telemetry Setup
function initControls() {
    // SFX Toggle
    const sfxBtn = document.getElementById('sfx-toggle');
    const sfxStatus = document.getElementById('sfx-status');
    if (sfxBtn && sfxStatus) {
        sfxBtn.addEventListener('click', () => {
            state.sfxEnabled = !state.sfxEnabled;
            sfxStatus.innerText = state.sfxEnabled ? 'ON' : 'OFF';
            sfxStatus.style.color = state.sfxEnabled ? 'var(--color-ruby)' : 'var(--text-muted)';
            if (state.sfxEnabled) playRetroSFX('beep');
        });
    }

    // CRT Toggle
    const crtBtn = document.getElementById('crt-toggle');
    const crtStatus = document.getElementById('crt-status');
    if (crtBtn && crtStatus) {
        crtBtn.addEventListener('click', () => {
            state.crtEnabled = !state.crtEnabled;
            document.body.classList.toggle('crt-enabled', state.crtEnabled);
            crtStatus.innerText = state.crtEnabled ? 'ON' : 'OFF';
            crtStatus.style.color = state.crtEnabled ? 'var(--color-ruby)' : 'var(--text-muted)';
            playRetroSFX('click');
        });
    }

    // Mobile Navigation Menu Toggle
    const navToggle = document.getElementById('nav-toggle');
    const mainNav = document.getElementById('main-nav');
    const navToggleText = document.getElementById('nav-toggle-text');

    if (navToggle && mainNav) {
        navToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = mainNav.classList.toggle('open');
            if (navToggleText) {
                navToggleText.innerText = isOpen ? 'CLOSE' : 'MENU';
            }
            playRetroSFX('beep');
        });

        // Close menu when clicking anywhere outside
        document.addEventListener('click', (e) => {
            if (mainNav.classList.contains('open') && !mainNav.contains(e.target) && !navToggle.contains(e.target)) {
                mainNav.classList.remove('open');
                if (navToggleText) navToggleText.innerText = 'MENU';
            }
        });

        // Close menu when clicking any nav link
        mainNav.querySelectorAll('.nav-item').forEach(link => {
            link.addEventListener('click', () => {
                if (mainNav.classList.contains('open')) {
                    mainNav.classList.remove('open');
                    if (navToggleText) navToggleText.innerText = 'MENU';
                }
            });
        });

        // Close menu on resize to desktop
        window.addEventListener('resize', () => {
            if (window.innerWidth > 820 && mainNav.classList.contains('open')) {
                mainNav.classList.remove('open');
                if (navToggleText) navToggleText.innerText = 'MENU';
            }
        });
    }

    // Global interactive clicks for sound
    document.querySelectorAll('.pixel-btn, .nav-item, .social-icon').forEach(el => {
        el.addEventListener('click', () => playRetroSFX('click'));
    });
}

// On Document Loaded
document.addEventListener('DOMContentLoaded', () => {
    // Initialize Lucide Icons
    if (window.lucide) {
        window.lucide.createIcons();
    }

    initMatrixCanvas();
    initTerminalSimulator();
    initControls();
});
