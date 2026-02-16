const numbersEl = document.getElementById('numbers');
const generateBtn = document.getElementById('generate-btn');
const roundNoteEl = document.getElementById('round-note');

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
  roundNoteEl.textContent = `${drawCount}회차 추첨 결과: ${nums.join(', ')}`;
}

generateBtn.addEventListener('click', runDraw);

runDraw();
