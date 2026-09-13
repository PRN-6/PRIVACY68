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

// Simulated Waveform HUD Visualizer
function initWaveformVisualizer() {
    const canvas = document.getElementById('waveform-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    const bars = 48;
    const barWidth = 8;
    const gap = 5;

    let time = 0;
    function drawWave() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        time += 0.04;

        const totalWidth = bars * (barWidth + gap);
        const startX = (canvas.width - totalWidth) / 2;

        for (let i = 0; i < bars; i++) {
            const x = startX + i * (barWidth + gap);
            const distFromCenter = Math.abs(i - bars / 2) / (bars / 2);
            
            // Generate pseudo-audio frequency bars
            const wave1 = Math.sin(time * 2 + i * 0.3);
            const wave2 = Math.cos(time * 1.5 + i * 0.5);
            const rawH = (Math.abs(wave1 * wave2) * 36 + 6) * (1 - distFromCenter * 0.5);
            const h = Math.max(4, Math.min(46, rawH));

            const y = (canvas.height - h) / 2;

            // Gradient fill: Crimson to Pure White
            if (h > 30) {
                ctx.fillStyle = '#ffffff';
            } else if (h > 18) {
                ctx.fillStyle = '#ef4444';
            } else {
                ctx.fillStyle = '#55111b';
            }

            ctx.fillRect(x, y, barWidth, h);
        }

        requestAnimationFrame(drawWave);
    }
    drawWave();
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
            const lane = chip.getAttribute('data-lane');
            const action = chip.getAttribute('data-action');
            const conf = chip.getAttribute('data-conf');

            // Simulate typing into terminal
            if (termInput) termInput.innerHTML = `&gt; [USER SPOKE] "${cmd}"`;
            
            if (lane === 'FAST_LANE') {
                if (termLane) termLane.innerHTML = `&gt; [DUAL-LANE ROUTER] <span style="color:#10b981;">⚡ FAST LANE ROUTED</span> (Cosine Conf: ${conf} &gt;= 0.78)`;
                if (termAction) termAction.innerHTML = `&gt; [ACTION SUCCESS] ⚡ ${action} in 1.2ms`;
            } else {
                if (termLane) termLane.innerHTML = `&gt; [DUAL-LANE ROUTER] <span style="color:#f59e0b;">🧠 OLLAMA FALLTHROUGH</span> (Complex Request Routed to Local LLM)`;
                if (termAction) termAction.innerHTML = `&gt; [ACTION SUCCESS] 🧠 ${action} in 42ms`;
            }

            setTimeout(() => {
                playRetroSFX('success');
            }, 120);
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
    initWaveformVisualizer();
    initTerminalSimulator();
    initControls();
});
