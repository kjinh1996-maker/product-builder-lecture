const numbersEl = document.getElementById('numbers');
const generateBtn = document.getElementById('generate-btn');
const roundNoteEl = document.getElementById('round-note');
const partnerForm = document.getElementById('partner-form');
const partnerStatusEl = document.getElementById('partner-status');
const partnerSubmitBtn = document.getElementById('partner-submit-btn');
const updatedAtEl = document.getElementById('updated-at');

let drawCount = 0;

function pickLottoNumbers() {
  const picked = new Set();

  while (picked.size < 6) {
    const n = Math.floor(Math.random() * 45) + 1;
    picked.add(n);
  }

  return [...picked].sort((a, b) => a - b);
}

function numberColorClass(n) {
  if (n <= 10) return 'ball-yellow';
  if (n <= 20) return 'ball-blue';
  if (n <= 30) return 'ball-red';
  if (n <= 40) return 'ball-gray';
  return 'ball-green';
}

function renderNumbers(nums) {
  if (!numbersEl) return;
  numbersEl.innerHTML = '';

  nums.forEach((num, index) => {
    const ball = document.createElement('div');
    ball.className = `ball ${numberColorClass(num)}`;
    ball.textContent = String(num);
    ball.style.animationDelay = `${index * 80}ms`;
    numbersEl.appendChild(ball);
  });
}

function runDraw() {
  const nums = pickLottoNumbers();
  drawCount += 1;

  renderNumbers(nums);
  if (roundNoteEl) {
    roundNoteEl.textContent = `${drawCount}회차 추첨 결과: ${nums.join(', ')}`;
  }
}

if (generateBtn) {
  generateBtn.addEventListener('click', runDraw);
}
runDraw();

if (partnerForm && partnerStatusEl && partnerSubmitBtn) {
  partnerForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    const endpoint = partnerForm.action;
    if (!endpoint || endpoint.includes('YOUR_FORMSPREE_ID')) {
      partnerStatusEl.textContent = 'Formspree 폼 ID를 먼저 입력해 주세요.';
      partnerStatusEl.style.color = '#b91c1c';
      return;
    }

    partnerSubmitBtn.disabled = true;
    partnerStatusEl.textContent = '전송 중입니다...';
    partnerStatusEl.style.color = '#374151';

    try {
      const formData = new FormData(partnerForm);
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { Accept: 'application/json' },
        body: formData,
      });

      if (!response.ok) {
        throw new Error('submit_failed');
      }

      partnerForm.reset();
      partnerStatusEl.textContent = '문의가 접수되었습니다. 빠르게 확인 후 연락드리겠습니다.';
      partnerStatusEl.style.color = '#065f46';
    } catch (error) {
      partnerStatusEl.textContent = '전송에 실패했습니다. 잠시 후 다시 시도해 주세요.';
      partnerStatusEl.style.color = '#b91c1c';
    } finally {
      partnerSubmitBtn.disabled = false;
    }
  });
}

if (updatedAtEl) {
  const now = new Date();
  const yyyy = now.getFullYear();
  const mm = String(now.getMonth() + 1).padStart(2, '0');
  const dd = String(now.getDate()).padStart(2, '0');
  updatedAtEl.textContent = `최종 업데이트: ${yyyy}-${mm}-${dd}`;
}
